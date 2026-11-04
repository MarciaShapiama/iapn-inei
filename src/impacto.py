"""Impacto de cada huella de inundación en Tumbes y Piura: personas, viviendas, colegios y salud.

Para cada evento (2017, 2023, vivo):
    personas   WorldPop 2026 (100 m) × fracción inundada de cada celda; también a ≤ 500 m de la mancha
    viviendas  edificaciones de Google Open Buildings cuyo centro cae en un píxel inundado; y a ≤ 100 m
    colegios / establecimientos de salud: dentro de la mancha, a ≤ 500 m y a ≤ 1 km
    por distrito: km² inundados, personas y viviendas
Nota: se usa la población y las edificaciones de HOY sobre la huella de 2017 o 2023, es decir, la
pregunta es "¿a cuántos afectaría hoy una inundación como la de 2017?".

Salidas: dashboard/data/inundacion.json y dashboard/data/huella_{evento}.png (capa para el mapa).

Uso: python src/impacto.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from config import DASH_DATA, DATA
from exposicion import CAJA, CARPETA as EXPO
from huellas import CARPETA as HUELLAS, RES, eventos

LAT0 = (CAJA[1] + CAJA[3]) / 2
M_X, M_Y = RES * 111_320 * np.cos(np.radians(LAT0)), RES * 110_600       # metros por píxel
VALIDACION = {"2017": {"Piura": 74348, "Tumbes": 11395,
                       "fuente": "INDECI, citado en OCHA, Perú: Temporada de lluvias, informe n.º 10 (10 may 2017)",
                       "url": "https://reliefweb.int/report/peru/peru-rainy-season-situation-report-no-10-10-may-2017",
                       "nota": "Viviendas afectadas por lluvias, inundaciones y huaicos (no solo inundación)."}}


def leer_huella(clave: str):
    import rasterio
    with rasterio.open(HUELLAS / f"{clave}.tif") as src:
        return src.read(1), src.transform


def indices(lon, lat, t, forma):
    col = np.floor((np.asarray(lon) - t.c) / t.a).astype(int)
    fil = np.floor((np.asarray(lat) - t.f) / t.e).astype(int)
    ok = (fil >= 0) & (fil < forma[0]) & (col >= 0) & (col < forma[1])
    return fil, col, ok


def distancia_m(inund: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi
    return ndi.distance_transform_edt(~inund, sampling=(M_Y, M_X)).astype("float32")


def raster_distritos(t, forma):
    from rasterio import features
    from shapely.geometry import shape
    g = json.load(open(EXPO / "distritos.geojson", encoding="utf-8"))
    nombres = [(f["properties"]["departamento"], f["properties"]["provincia"], f["properties"]["distrito"]) for f in g["features"]]
    r = features.rasterize(((shape(f["geometry"]), k + 1) for k, f in enumerate(g["features"])),
                           out_shape=forma, transform=t, fill=0, dtype="int32")
    return r, nombres


def personas(inund: np.ndarray, t, mascara_extra: np.ndarray | None = None, distritos=None):
    """Población dentro de la máscara: se lleva la máscara a la grilla de WorldPop (fracción por celda)."""
    import rasterio
    from rasterio.warp import Resampling, reproject
    with rasterio.open(EXPO / "poblacion_100m.tif") as src:
        pob = src.read(1).astype("float64")
        tp, crs = src.transform, src.crs
    def frac(m):
        dst = np.zeros(pob.shape, dtype="float32")
        reproject(m.astype("float32"), dst, src_transform=t, src_crs="EPSG:4326", dst_transform=tp, dst_crs=crs,
                  resampling=Resampling.average)
        return dst
    f = frac(inund)
    total = float((pob * f).sum())
    cerca = float((pob * frac(mascara_extra)).sum()) if mascara_extra is not None else None
    por_d = None
    if distritos is not None:
        dr = np.zeros(pob.shape, dtype="float32")
        reproject(distritos[0].astype("float32"), dr, src_transform=t, src_crs="EPSG:4326", dst_transform=tp,
                  dst_crs=crs, resampling=Resampling.nearest)
        por_d = pd.Series((pob * f).ravel()).groupby(dr.astype(int).ravel()).sum()
    return total, cerca, por_d


def puntos_cercanos(tabla: pd.DataFrame, dist: np.ndarray, t) -> pd.DataFrame:
    fil, col, ok = indices(tabla["lon"], tabla["lat"], t, dist.shape)
    d = np.full(len(tabla), np.nan)
    d[ok] = dist[fil[ok], col[ok]]
    x = tabla.copy()
    x["dist_m"] = np.round(d)
    x["estado"] = np.select([x["dist_m"] <= 0, x["dist_m"] <= 500, x["dist_m"] <= 1000],
                            ["Dentro de la zona inundada", "A ≤ 500 m", "A ≤ 1 km"], "Fuera")
    return x


def png(clave: str, m: np.ndarray, t) -> dict:
    """Capa del mapa: agua inundada en azul intenso, agua permanente en azul tenue (reducida a ~110 m)."""
    from PIL import Image
    k = 2
    h, w = (m.shape[0] // k) * k, (m.shape[1] // k) * k
    b = m[:h, :w].reshape(h // k, k, w // k, k)
    inund = (b == 1).any(axis=(1, 3))
    perm = (b == 2).any(axis=(1, 3)) & ~inund
    rgba = np.zeros(inund.shape + (4,), dtype="uint8")
    rgba[inund] = (30, 144, 255, 235)
    rgba[perm] = (120, 170, 210, 120)
    Image.fromarray(rgba, "RGBA").save(DASH_DATA / f"huella_{clave}.png", optimize=True)
    oeste, norte = t.c, t.f
    este, sur = oeste + t.a * w, norte + t.e * h
    return {"imagen": f"huella_{clave}.png", "limites": [oeste, sur, este, norte]}


def main() -> None:
    DASH_DATA.mkdir(parents=True, exist_ok=True)
    viv = pd.read_parquet(EXPO / "viviendas.parquet") if (EXPO / "viviendas.parquet").exists() else None
    salud = pd.read_csv(EXPO / "salud.csv") if (EXPO / "salud.csv").exists() else None
    cole = pd.read_csv(EXPO / "colegios.csv") if (EXPO / "colegios.csv").exists() else None
    salida = {"caja": CAJA, "eventos": {}, "validacion": VALIDACION,
              "fuentes_exposicion": {"poblacion": "WorldPop 2026, 100 m", "viviendas": "Google Open Buildings v3 (confianza ≥ 0,75)",
                                     "salud": "RENIPRESS (SUSALUD)",
                                     "colegios": None if cole is None else cole["fuente"].iloc[0]}}
    distritos = None
    for clave, ev in eventos().items():
        if not (HUELLAS / f"{clave}.tif").exists():
            continue
        m, t = leer_huella(clave)
        meta = json.load(open(HUELLAS / f"{clave}.json", encoding="utf-8"))
        inund = m == 1
        if distritos is None and (EXPO / "distritos.geojson").exists():
            distritos = raster_distritos(t, m.shape)
        dist = distancia_m(inund)
        r = {"nombre": ev["nombre"], "periodo": meta["periodo"], "imagenes": meta["imagenes_evento"],
             "km2": meta["km2"], **png(clave, m, t)}
        if (EXPO / "poblacion_100m.tif").exists():
            p, p500, por_d = personas(inund, t, dist <= 500, distritos)
            r["personas"], r["personas_500m"] = round(p), round(p500)
        else:
            por_d = None
        dist_viv = None
        if viv is not None:
            fil, col, ok = indices(viv["lon"], viv["lat"], t, m.shape)
            dist_viv = np.full(len(viv), np.inf)
            dist_viv[ok] = dist[fil[ok], col[ok]]
            dentro = dist_viv <= 0
            r["viviendas"], r["viviendas_100m"] = int(dentro.sum()), int((dist_viv <= 100).sum())
            muestra = viv[dentro]
            if len(muestra) > 40000:
                muestra = muestra.sample(40000, random_state=1)
            r["viviendas_puntos"] = np.round(muestra[["lon", "lat"]].to_numpy(), 5).tolist()
        for nombre, tabla in (("salud", salud), ("colegios", cole)):
            if tabla is None:
                continue
            x = puntos_cercanos(tabla, dist, t)
            r[nombre] = {e: int((x["estado"] == e).sum()) for e in ["Dentro de la zona inundada", "A ≤ 500 m", "A ≤ 1 km"]}
            cols = [c for c in ["nombre", "tipo", "categoria", "nivel", "alumnos", "distrito", "lat", "lon", "dist_m", "estado"] if c in x]
            cerca = x[x["estado"] != "Fuera"].sort_values("dist_m")[cols]
            r[nombre + "_lista"] = json.loads(cerca.to_json(orient="records", force_ascii=False))
        if distritos is not None:
            dr, nombres = distritos
            area = pd.Series(inund.ravel()).groupby(dr.ravel()).sum() * M_X * M_Y / 1e6
            filas = []
            for k, (dep, prov, dis) in enumerate(nombres, start=1):
                a = float(area.get(k, 0))
                fila = {"departamento": dep, "provincia": prov, "distrito": dis, "km2": round(a, 2)}
                if por_d is not None:
                    fila["personas"] = round(float(por_d.get(k, 0)))
                filas.append(fila)
            if viv is not None and dist_viv is not None:
                fil, col, ok = indices(viv["lon"], viv["lat"], t, m.shape)
                dvi = np.zeros(len(viv), dtype=int)
                dvi[ok] = dr[fil[ok], col[ok]]
                cuenta = pd.Series(dvi[dist_viv <= 0]).value_counts()
                for k, fila in enumerate(filas, start=1):
                    fila["viviendas"] = int(cuenta.get(k, 0))
            r["distritos"] = sorted([f for f in filas if f["km2"] > 0 or f.get("viviendas", 0) > 0],
                                    key=lambda f: -f.get("viviendas", f["km2"]))
            por_dep = {}
            for f in filas:
                por_dep.setdefault(f["departamento"], 0)
                por_dep[f["departamento"]] += f.get("viviendas", 0)
            r["viviendas_por_departamento"] = por_dep
        salida["eventos"][clave] = r
        print(f"{clave}: {r['km2']} km², {r.get('personas')} personas, {r.get('viviendas')} viviendas, "
              f"salud {r.get('salud')}, colegios {r.get('colegios')}")
    if (EXPO / "distritos.geojson").exists():
        import shutil
        shutil.copy(EXPO / "distritos.geojson", DASH_DATA / "distritos_tumbes_piura.geojson")
    for nombre, tabla in (("salud", salud), ("colegios", cole)):
        if tabla is not None:
            cols = [c for c in ["nombre", "tipo", "nivel", "alumnos", "distrito", "lat", "lon"] if c in tabla]
            tabla[cols].to_json(DASH_DATA / f"{nombre}_tumbes_piura.json", orient="records", force_ascii=False)
    json.dump(salida, open(DASH_DATA / "inundacion.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"inundacion.json: {(DASH_DATA / 'inundacion.json').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
