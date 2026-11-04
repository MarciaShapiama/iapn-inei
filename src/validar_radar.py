"""Validación con un mapa oficial: inundación de 2017 de Copernicus EMS (activación EMSR199) frente a
(a) lo que el radar Sentinel-1 del proyecto detectó en 2017 y (b) la zona inundable de JRC (1 en 100 años).

El mapa de Copernicus EMS lo hicieron analistas con imágenes de alta resolución (Cosmo-SkyMed, etc.) en
áreas de interés concretas de Piura; fuera de esas áreas no hay referencia, así que todo se mide dentro
de ellas. Se unen todas las fechas (mapa inicial y monitoreo) porque el radar del proyecto resume febrero
a abril de 2017.

Medidas, dentro de cada área de interés:
    acierto (recall)   = área detectada que también marcó Copernicus / área que marcó Copernicus
    precisión          = área detectada que también marcó Copernicus / área detectada
Salida: dashboard/data/validacion_2017.json
"""
from __future__ import annotations

import glob
import json
import re
import tempfile
import zipfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
EMS = RAIZ / "data" / "validacion" / "ems2017"
SALIDA = RAIZ / "dashboard" / "data" / "validacion_2017.json"
NOMBRE = {"08SULLANA": "Sullana", "10PIURA": "Bajo Piura", "11PARACHIQUE": "Sechura (Parachique)", "12PIURANORTH": "Piura norte"}


def leer_ems():
    import geopandas as gpd
    import pandas as pd
    capas = {}
    for z in sorted(EMS.glob("EMSR199_*_DELINEATION_*_vector.zip")):
        aoi = re.match(r"EMSR199_(\d+[A-Z]+)_", z.name).group(1)
        d = tempfile.mkdtemp()
        zipfile.ZipFile(z).extractall(d)
        crisis = glob.glob(d + "/**/*crisis_information_poly.shp", recursive=True)
        zona = glob.glob(d + "/**/*area_of_interest.shp", recursive=True)
        if not crisis or not zona:
            continue
        g = gpd.read_file(crisis[0]).to_crs(4326)
        g = g[g["interpret"].astype(str).str.contains("Flood", case=False)] if "interpret" in g else g
        a = gpd.read_file(zona[0]).to_crs(4326)
        fechas = [str(x)[:10] for x in g["src_date"].tolist() if str(x)[:4] == "2017"] if "src_date" in g else []
        c = capas.setdefault(aoi, {"agua": [], "zona": [], "fechas": set(), "fuentes": set()})
        c["agua"].append(g[["geometry"]]); c["zona"].append(a[["geometry"]]); c["fechas"].update(fechas)
        if "source_nam" in g:
            c["fuentes"].update(g["source_nam"].astype(str).unique())
    return {k: {"agua": pd.concat(v["agua"]), "zona": pd.concat(v["zona"]), "fechas": sorted(map(str, v["fechas"])),
                "fuentes": sorted(v["fuentes"])} for k, v in capas.items()}


def rasterizar(geoms, t, forma):
    from rasterio import features
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(forma, bool)
    return features.rasterize(((g, 1) for g in geoms), out_shape=forma, transform=t, fill=0, dtype="uint8").astype(bool)


def medir(det, ref, zona, px_km2):
    det, ref = det & zona, ref & zona
    ambos = (det & ref).sum()
    return {"km2_copernicus": round(float(ref.sum() * px_km2), 1), "km2_detectado": round(float(det.sum() * px_km2), 1),
            "km2_coinciden": round(float(ambos * px_km2), 1),
            "acierto": round(float(ambos / ref.sum()), 3) if ref.sum() else None,
            "precision": round(float(ambos / det.sum()), 3) if det.sum() else None}


def main() -> None:
    import sys
    sys.path.insert(0, str(RAIZ / "src"))
    import rasterio
    from impacto import cargar_capas, metros
    ems = leer_ems()
    capas = cargar_capas()
    out = {"fuente": "Copernicus Emergency Management Service, activación EMSR199 (Perú, inundaciones 2017), "
                     "productos de delimitación de Piura: https://mapping.emergency.copernicus.eu/activations/EMSR199",
           "nota": "Copernicus EMS solo cartografió algunas áreas de Piura; Tumbes no tiene referencia. Se unen las fechas del mapa inicial y del monitoreo.",
           "areas": {}, "total": {}}
    for clave, etiqueta in (("2017", "radar"), ("rp100", "jrc_rp100")):
        if clave not in capas:
            continue
        _, _, valor, t, _ = capas[clave]
        mx, my = metros(t)
        px = mx * my / 1e6
        det = valor > 0
        tot_ref = tot_det = tot_amb = 0.0
        for aoi, e in ems.items():
            zona = rasterizar(e["zona"].geometry, t, det.shape)
            ref = rasterizar(e["agua"].geometry, t, det.shape)
            m = medir(det, ref, zona, px)
            a = out["areas"].setdefault(aoi, {"nombre": NOMBRE.get(aoi, aoi), "fechas_copernicus": e["fechas"],
                                              "imagenes_copernicus": e["fuentes"]})
            a[etiqueta] = m
            tot_ref += m["km2_copernicus"]; tot_det += m["km2_detectado"]; tot_amb += m["km2_coinciden"]
        out["total"][etiqueta] = {"km2_copernicus": round(tot_ref, 1), "km2_detectado": round(tot_det, 1),
                                  "km2_coinciden": round(tot_amb, 1),
                                  "acierto": round(tot_amb / tot_ref, 3) if tot_ref else None,
                                  "precision": round(tot_amb / tot_det, 3) if tot_det else None}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["total"], ensure_ascii=False))
    for k, a in out["areas"].items():
        print(k, a["nombre"], a["fechas_copernicus"], {x: a[x] for x in ("radar", "jrc_rp100") if x in a})


if __name__ == "__main__":
    main()
