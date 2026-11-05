"""Capas para la vista «río normal frente al río con El Niño» (Tumbes y Piura).

Dónde va: src/rio_normal_vs_nino.py. Uso, desde la raíz del repositorio:  python src/rio_normal_vs_nino.py

Produce en dashboard/data/rio/:
    rio_normal.geojson        agua permanente (JRC Global Surface Water, ocurrencia >= 75 %, 1984-2021)
    ems2017_rio.geojson       ríos y lagunas de referencia del mapa oficial de Copernicus EMS (Bajo Piura)
    ems2017_inundado.geojson  área inundada del 26 y 30 de marzo de 2017, mapa oficial Copernicus EMS (EMSR199)
    rio_pasos.json            para cada tramo y paso (normal, 2017, 2023, hoy): km² de agua, veces el cauce normal,
                              foto Sentinel-2 del paso y fuentes

Reutiliza lo que ya está en el repositorio: data/huellas/{2017,2023,vivo}.tif (radar), dashboard/data/sat/ (fotos)
y data/validacion/ems2017/ (Copernicus). Solo descarga JRC GSW, igual que src/huellas.py.
NOTA: escrito para las librerías de requirements-inundaciones.txt; no se pudo correr en el entorno donde se
preparó (no tenía geopandas ni rasterio). Probarlo primero en la laptop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import DASH_DATA, DATA  # noqa: E402

SALIDA = DASH_DATA / "rio"
GSW_MIN = 75
# Tramos: las mismas cajas del comparador Sentinel-2 (src/satelite.py), para que fotos y capas coincidan.
TRAMOS = {"bajo_piura": {"nombre": "Río Piura: ciudad de Piura y Bajo Piura", "caja": (-80.76, -5.40, -80.52, -5.14)},
          "tumbes": {"nombre": "Río Tumbes: ciudad y valle bajo", "caja": (-80.58, -3.76, -80.36, -3.52)}}
PASOS = [("normal", "Río normal", None), ("2017", "El Niño costero 2017", "2017"),
         ("2023", "Ciclón Yaku 2023", "2023"), ("hoy", "Estos días", "vivo")]
FOTO = {"normal": "antes_2017", "2017": "despues_2017", "2023": "despues_2023", "hoy": "hoy"}


def gsw_permanente():
    """Máscara de agua permanente y su geobox, con el mismo catálogo que huellas.py."""
    import odc.stac
    import planetary_computer as pc
    import pystac_client
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    oeste = min(t["caja"][0] for t in TRAMOS.values()); sur = min(t["caja"][1] for t in TRAMOS.values())
    este = max(t["caja"][2] for t in TRAMOS.values()); norte = max(t["caja"][3] for t in TRAMOS.values())
    items = cat.search(collections=["jrc-gsw"], bbox=(oeste, sur, este, norte)).item_collection()
    d = odc.stac.load(items, bands=["occurrence"], crs="EPSG:4326", resolution=0.00025, bbox=(oeste, sur, este, norte))
    occ = d["occurrence"].max("time").values.astype("float32")
    return occ >= GSW_MIN, d.odc.geobox.affine


def a_poligonos(mascara: np.ndarray, transform, tolerancia: float = 0.00012) -> list:
    from rasterio import features
    from shapely.geometry import mapping, shape
    feats = []
    for geom, v in features.shapes(mascara.astype("uint8"), mask=mascara, transform=transform):
        g = shape(geom).simplify(tolerancia, preserve_topology=True)
        if not g.is_empty:
            feats.append({"type": "Feature", "properties": {}, "geometry": mapping(g)})
    return feats


def km2(mascara: np.ndarray, transform, caja) -> float:
    """Área de agua dentro de la caja, en km² (celdas en grados convertidas a la latitud de la caja)."""
    filas, cols = np.indices(mascara.shape)
    lon = transform.c + (cols + 0.5) * transform.a
    lat = transform.f + (filas + 0.5) * transform.e
    dentro = (lon >= caja[0]) & (lon <= caja[2]) & (lat >= caja[1]) & (lat <= caja[3])
    lat0 = (caja[1] + caja[3]) / 2
    celda = abs(transform.a) * 111.32 * np.cos(np.radians(lat0)) * abs(transform.e) * 110.6
    return float((mascara & dentro).sum() * celda)


def radar(evento: str):
    import rasterio
    with rasterio.open(DATA / "huellas" / f"{evento}.tif") as r:
        m = r.read(1)
        return (m > 0) & (m != (r.nodata if r.nodata is not None else 255)), r.transform   # 255 = sin dato


def ems_2017() -> dict:
    """Ríos de referencia y área inundada del mapa oficial (Bajo Piura), en EPSG:4326."""
    import geopandas as gpd
    import pandas as pd
    zips = sorted((DATA / "validacion" / "ems2017").glob("EMSR199_10PIURA_DELINEATION_OVERVIEW*_vector.zip"))
    capas = {}
    for capa in ("hydrography_poly", "crisis_information_poly"):
        partes = []
        for z in zips:
            import zipfile
            nombre = next(n for n in zipfile.ZipFile(z).namelist() if n.endswith(capa + ".shp"))
            partes.append(gpd.read_file(f"zip://{z}!{nombre}"))
        g = pd.concat(partes, ignore_index=True)
        if capa == "crisis_information_poly":
            g = g[g["subtype"].str.contains("Flood", na=False)]
        g = gpd.GeoDataFrame(g, geometry="geometry", crs=partes[0].crs)
        area = g.to_crs(32717).dissolve().area.iloc[0] / 1e6            # unión: no cuenta dos veces lo que se repite
        capas[capa] = (g.to_crs(4326).dissolve().simplify(0.0001), round(float(area), 1))
    return capas


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    perm, tp = gsw_permanente()
    json.dump({"type": "FeatureCollection", "features": a_poligonos(perm, tp)}, open(SALIDA / "rio_normal.geojson", "w"))

    ems = ems_2017()
    for capa, archivo in (("hydrography_poly", "ems2017_rio"), ("crisis_information_poly", "ems2017_inundado")):
        ems[capa][0].to_file(SALIDA / f"{archivo}.geojson", driver="GeoJSON")

    sat = json.load(open(DASH_DATA / "sat" / "satelite.json", encoding="utf-8"))
    fotos = {z["id"]: {e["periodo"]: e for e in z["escenas"]} for z in sat["zonas"]}
    salida = {"fuentes": {"normal": f"JRC Global Surface Water, ocurrencia >= {GSW_MIN} % (1984-2021)",
                          "eventos": "Radar Sentinel-1, detección de cambios (src/huellas.py); es un mínimo",
                          "oficial_2017": "Copernicus EMS, EMSR199, 26 y 30 de marzo de 2017 (solo Bajo Piura)"},
              "tramos": {}}
    for tid, t in TRAMOS.items():
        base = km2(perm, tp, t["caja"])
        pasos = []
        for pid, etiqueta, evento in PASOS:
            if evento is None:
                agua = base
            else:
                m, tr = radar(evento)
                agua = base + km2(m, tr, t["caja"])        # el radar marca solo agua NUEVA; se suma el cauce
            f = fotos.get(tid, {}).get(FOTO[pid], {})
            pasos.append({"paso": pid, "etiqueta": etiqueta, "km2_agua": round(agua, 1),
                          "veces_normal": round(agua / base, 1) if base else None,
                          "foto_fecha": f.get("fecha"), "foto_nubes_pct": f.get("nubes_en_zona_pct"),
                          "foto": f"sat/{tid}_{FOTO[pid]}_rgb.jpg"})
        salida["tramos"][tid] = {"nombre": t["nombre"], "caja": t["caja"], "pasos": pasos}
    salida["oficial_2017_bajo_piura"] = {"km2_rios_y_lagunas": ems["hydrography_poly"][1],
                                         "km2_inundado": ems["crisis_information_poly"][1]}
    json.dump(salida, open(SALIDA / "rio_pasos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for tid, t in salida["tramos"].items():
        print(tid, [(p["paso"], p["km2_agua"], p["veces_normal"]) for p in t["pasos"]])
    print("Copernicus 2017, Bajo Piura:", salida["oficial_2017_bajo_piura"])


if __name__ == "__main__":
    main()
