"""Impacto de las inundaciones en Tumbes y Piura: personas, viviendas, colegios y salud.

Dos tipos de capa:
    radar    lo que el satélite Sentinel-1 vio inundado en 2017, 2023 y los últimos 24 días (data/huellas/).
             Es un MÍNIMO: el radar no ve el agua entre edificios ni bajo árboles.
    peligro  zona que se inunda con una crecida de 1 en 10 y de 1 en 100 años, con su profundidad
             (JRC CEMS-GloFAS v2, 90 m; data/exposicion/peligro_rp*.tif).
Para cada capa:
    personas   WorldPop 2026 (100 m) × fracción inundada de cada celda; también a ≤ 500 m
    viviendas  edificaciones de Google Open Buildings dentro, a ≤ 100 m y a ≤ 500 m (y por profundidad)
    colegios y salud: dentro, a ≤ 500 m y a ≤ 1 km
    por distrito: km², personas y viviendas
Se cruzan la población y las edificaciones de HOY: "¿a cuántos afectaría hoy algo así?".

Salidas: dashboard/data/inundacion.json y dashboard/data/capa_{clave}.geojson

Uso: python src/impacto.py
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd

from config import DASH_DATA
from exposicion import CAJA, CARPETA as EXPO
from huellas import CARPETA as HUELLAS, eventos

LAT0 = (CAJA[1] + CAJA[3]) / 2
VALIDACION = {"2017": {"Piura": 74348, "Tumbes": 11395,
                       "fuente": "INDECI, citado en OCHA, Perú: Temporada de lluvias, informe n.º 10 (10 may 2017)",
                       "url": "https://reliefweb.int/report/peru/peru-rainy-season-situation-report-no-10-10-may-2017",
                       "nota": "INDECI cuenta viviendas afectadas por lluvias, inundaciones y huaicos, no solo por inundación."}}
PELIGROS = {"rp10": ("Zona inundable: crecida de 1 en 10 años", 10), "rp100": ("Zona inundable: crecida de 1 en 100 años", 100)}


def metros(t) -> tuple[float, float]:
    return abs(t.a) * 111_320 * np.cos(np.radians(LAT0)), abs(t.e) * 110_600


def indices(lon, lat, t, forma):
    col = np.floor((np.asarray(lon) - t.c) / t.a).astype(int)
    fil = np.floor((np.asarray(lat) - t.f) / t.e).astype(int)
    ok = (fil >= 0) & (fil < forma[0]) & (col >= 0) & (col < forma[1])
    return fil, col, ok


def rasterizar_distritos(t, forma):
    from rasterio import features
    from shapely.geometry import shape
    g = json.load(open(EXPO / "distritos.geojson", encoding="utf-8"))
    nombres = [(f["properties"]["departamento"], f["properties"]["provincia"], f["properties"]["distrito"]) for f in g["features"]]
    r = features.rasterize(((shape(f["geometry"]), k + 1) for k, f in enumerate(g["features"])),
                           out_shape=forma, transform=t, fill=0, dtype="int32")
    return r, nombres


def cargar_capas():
    """Devuelve {clave: (nombre, tipo, profundidad_o_mascara, transform, meta)}."""
    import rasterio
    from scipy import ndimage as ndi
    capas = {}
    for clave, ev in eventos().items():
        ruta = HUELLAS / f"{clave}.tif"
        if not ruta.exists():
            continue
        with rasterio.open(ruta) as src:
            m, t = src.read(1), src.transform
        meta = json.load(open(HUELLAS / f"{clave}.json", encoding="utf-8"))
        dr, _ = rasterizar_distritos(t, m.shape)
        tierra = ndi.binary_erosion(dr > 0, iterations=4)       # solo tierra de Tumbes y Piura, sin la orilla del mar
        inund = (m == 1) & tierra
        lab, n = ndi.label(inund)                                # quita manchas sueltas (< 0,03 km²)
        if n:
            tam = np.bincount(lab.ravel()); ok = tam >= 10; ok[0] = False; inund = ok[lab]
        capas[clave] = (ev["nombre"], "radar", inund.astype("float32"), t,
                        {"periodo": meta["periodo"], "imagenes": meta["imagenes_evento"]})
    for clave, (nombre, rp) in PELIGROS.items():
        ruta = EXPO / f"peligro_rp{rp}.tif"
        if ruta.exists():
            with rasterio.open(ruta) as src:
                capas[clave] = (nombre, "peligro", src.read(1).astype("float32"), src.transform,
                                {"periodo": None, "imagenes": [], "periodo_retorno": rp})
    return capas


def personas(mascara, t, distritos, extra=None):
    import rasterio
    from rasterio.warp import Resampling, reproject
    with rasterio.open(EXPO / "poblacion_100m.tif") as src:
        pob, tp = src.read(1).astype("float64"), src.transform
    def frac(m):
        dst = np.zeros(pob.shape, dtype="float32")
        reproject(m.astype("float32"), dst, src_transform=t, src_crs="EPSG:4326", dst_transform=tp, dst_crs="EPSG:4326",
                  resampling=Resampling.average)
        return dst
    f = frac(mascara)
    dr = np.zeros(pob.shape, dtype="float32")
    reproject(distritos.astype("float32"), dr, src_transform=t, src_crs="EPSG:4326", dst_transform=tp, dst_crs="EPSG:4326",
              resampling=Resampling.nearest)
    por_d = pd.Series((pob * f).ravel()).groupby(dr.astype(int).ravel()).sum()
    return float((pob * f).sum()), (float((pob * frac(extra)).sum()) if extra is not None else None), por_d


def poligonos(clave: str, tipo: str, valor: np.ndarray, t) -> dict:
    """Capa del mapa en polígonos (se ven nítidos sobre el relieve 3D). Peligro: 4 clases de profundidad."""
    from affine import Affine
    from rasterio import features
    from shapely.geometry import mapping, shape
    k = 2
    h, w = (valor.shape[0] // k) * k, (valor.shape[1] // k) * k
    v = valor[:h, :w].reshape(h // k, k, w // k, k).max(axis=(1, 3))
    tk = t * Affine.scale(k)
    if tipo == "radar":
        clase = (v > 0).astype("uint8")
    else:
        clase = np.digitize(v, [0.0001, 0.5, 1.5, 3.0]).astype("uint8")       # 1: < 0,5 m … 4: > 3 m
    feats = []
    for geom, c in features.shapes(clase, mask=clase > 0, transform=tk):
        g = shape(geom).simplify(abs(tk.a) * 0.6, preserve_topology=True)
        if g.is_empty or g.area < (abs(tk.a) ** 2) * 1.5:
            continue
        m = json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 5))
        feats.append({"type": "Feature", "properties": {"c": int(c)}, "geometry": m})
    ruta = DASH_DATA / f"capa_{clave}.geojson"
    json.dump({"type": "FeatureCollection", "features": feats}, open(ruta, "w"), separators=(",", ":"))
    print(f"  capa_{clave}.geojson: {len(feats)} polígonos, {ruta.stat().st_size // 1024} KB")
    return {"capa": f"capa_{clave}.geojson"}


def main() -> None:
    from scipy import ndimage as ndi
    DASH_DATA.mkdir(parents=True, exist_ok=True)
    viv = pd.read_parquet(EXPO / "viviendas.parquet")
    tablas = {n: pd.read_csv(EXPO / f"{n}.csv") for n in ("salud", "colegios") if (EXPO / f"{n}.csv").exists()}
    salida = {"caja": CAJA, "eventos": {}, "validacion": VALIDACION,
              "fuentes_exposicion": {"poblacion": "WorldPop 2026, 100 m", "viviendas": "Google Open Buildings v3 (confianza ≥ 0,75)",
                                     "salud": "RENIPRESS (SUSALUD)",
                                     "colegios": tablas["colegios"]["fuente"].iloc[0] if "colegios" in tablas else None,
                                     "peligro": "JRC CEMS-GloFAS flood hazard v2 (90 m)"}}
    for clave, (nombre, tipo, valor, t, meta) in cargar_capas().items():
        inund = valor > 0
        mx, my = metros(t)
        dist = ndi.distance_transform_edt(~inund, sampling=(my, mx)).astype("float32")
        dr, nombres = rasterizar_distritos(t, inund.shape)
        p, p500, por_d = personas(inund, t, dr, dist <= 500)
        fil, col, ok = indices(viv["lon"], viv["lat"], t, inund.shape)
        dv = np.full(len(viv), np.inf, dtype="float32"); dv[ok] = dist[fil[ok], col[ok]]
        prof = np.zeros(len(viv), dtype="float32"); prof[ok] = valor[fil[ok], col[ok]]
        dist_d = np.zeros(len(viv), dtype=int); dist_d[ok] = dr[fil[ok], col[ok]]
        dentro = dv <= 0
        r = {"nombre": nombre, "tipo": tipo, "periodo": meta["periodo"], "imagenes": meta["imagenes"],
             "periodo_retorno": meta.get("periodo_retorno"),
             "km2": round(float(inund.sum() * mx * my / 1e6), 1), **poligonos(clave, tipo, valor, t),
             "personas": round(p), "personas_500m": round(p500),
             "viviendas": int(dentro.sum()), "viviendas_100m": int((dv <= 100).sum()), "viviendas_500m": int((dv <= 500).sum())}
        if tipo == "peligro":
            r["viviendas_profundidad"] = {"hasta 0,5 m": int((dentro & (prof <= 0.5)).sum()),
                                          "0,5 a 1,5 m": int((dentro & (prof > 0.5) & (prof <= 1.5)).sum()),
                                          "más de 1,5 m": int((dentro & (prof > 1.5)).sum())}
        muestra = viv[dentro] if dentro.sum() else viv[dv <= 100]
        if len(muestra) > 25000:
            muestra = muestra.sample(25000, random_state=1)
        r["viviendas_puntos"] = np.round(muestra[["lon", "lat"]].to_numpy(), 4).tolist()
        r["viviendas_puntos_cerca"] = bool(not dentro.sum())
        for n, tabla in tablas.items():
            f2, c2, ok2 = indices(tabla["lon"], tabla["lat"], t, inund.shape)
            d = np.full(len(tabla), np.nan); d[ok2] = dist[f2[ok2], c2[ok2]]
            x = tabla.assign(dist_m=np.round(d))
            x["estado"] = np.select([x["dist_m"] <= 0, x["dist_m"] <= 500, x["dist_m"] <= 1000],
                                    ["Dentro de la zona inundada", "A ≤ 500 m", "A ≤ 1 km"], "Fuera")
            r[n] = {e: int((x["estado"] == e).sum()) for e in ["Dentro de la zona inundada", "A ≤ 500 m", "A ≤ 1 km"]}
            cols = [c for c in ["nombre", "tipo", "categoria", "nivel", "alumnos", "distrito", "lat", "lon", "dist_m", "estado"] if c in x]
            r[n + "_lista"] = json.loads(x[x["estado"] != "Fuera"].sort_values("dist_m")[cols].to_json(orient="records", force_ascii=False))
        area = pd.Series(inund.ravel()).groupby(dr.ravel()).sum() * mx * my / 1e6
        cuenta = pd.Series(dist_d[dentro]).value_counts()
        cuenta500 = pd.Series(dist_d[dv <= 500]).value_counts()
        filas = [{"departamento": dep, "provincia": prov, "distrito": dis, "km2": round(float(area.get(k, 0)), 2),
                  "personas": round(float(por_d.get(k, 0))), "viviendas": int(cuenta.get(k, 0)),
                  "viviendas_500m": int(cuenta500.get(k, 0))}
                 for k, (dep, prov, dis) in enumerate(nombres, start=1)]
        r["distritos"] = sorted([f for f in filas if f["km2"] > 0 or f["viviendas_500m"] > 0],
                                key=lambda f: (-f["viviendas"], -f["viviendas_500m"]))
        por_dep = {}
        for f in filas:
            d0 = por_dep.setdefault(f["departamento"], {"viviendas": 0, "viviendas_500m": 0, "personas": 0})
            d0["viviendas"] += f["viviendas"]; d0["viviendas_500m"] += f["viviendas_500m"]; d0["personas"] += f["personas"]
        r["por_departamento"] = por_dep
        salida["eventos"][clave] = r
        print(f"{clave}: {r['km2']} km², {r['personas']:,} personas, {r['viviendas']:,} viviendas "
              f"({r['viviendas_500m']:,} a ≤ 500 m), salud {r.get('salud')}, colegios {r.get('colegios')}")
    shutil.copy(EXPO / "distritos.geojson", DASH_DATA / "distritos_tumbes_piura.geojson")
    for n, tabla in tablas.items():
        cols = [c for c in ["nombre", "tipo", "nivel", "alumnos", "distrito", "lat", "lon"] if c in tabla]
        tabla[cols].to_json(DASH_DATA / f"{n}_tumbes_piura.json", orient="records", force_ascii=False)
    for viejo in list(DASH_DATA.glob("huella_*.png")) + list(DASH_DATA.glob("capa_*.png")) + list(DASH_DATA.glob("_test*.png")):
        viejo.unlink()
    json.dump(salida, open(DASH_DATA / "inundacion.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"inundacion.json: {(DASH_DATA / 'inundacion.json').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
