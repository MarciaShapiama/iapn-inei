"""Lo expuesto en Tumbes y Piura (se descarga una vez y se guarda en data/exposicion/).

    poblacion_100m.tif   WorldPop 2026, 100 m, restringida a zonas con edificaciones (recorte Tumbes-Piura)
    viviendas.parquet    centro de cada edificación de Google Open Buildings v3 (confianza ≥ 0,75)
    salud.csv            establecimientos de salud activos (RENIPRESS, SUSALUD): hospitales, centros, postas
    colegios.csv         locales educativos: padrón ESCALE (MINEDU) si se puede descargar; si no, OpenStreetMap
    distritos.geojson    distritos de Tumbes y Piura (GADM 4.1)

Método de viviendas y población tomado del repositorio del curso (alexanderquispe/incendios-peru).

Uso: python src/exposicion.py   (agregar --forzar para volver a descargar)
"""
from __future__ import annotations

import io
import json
import sys
import zipfile

import numpy as np
import pandas as pd
import requests

from config import DATA

CARPETA = DATA / "exposicion"
CAJA = (-81.40, -6.40, -79.15, -3.35)            # oeste, sur, este, norte: Tumbes + Piura
DEPARTAMENTOS = ["TUMBES", "PIURA"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}

WORLDPOP = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2026/PER/v1/100m/constrained/"
            "per_pop_2026_CN_100m_R2025A_v1.tif")
VIDA = "https://data.source.coop/vida/google-microsoft-open-buildings/geoparquet/by_country_s2/country_iso=PER/{}.parquet"
VIDA_CELDAS = ["10394307939971104768", "10466365534009032704", "10502394331027996672"]
RENIPRESS = "https://www.datosabiertos.gob.pe/sites/default/files/RENIPRESS_30-09-2026.csv"
GADM3 = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PER_3.json.zip"
OVERPASS = "https://overpass-api.de/api/interpreter"


def bajar(url: str, timeout: int = 600) -> bytes:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.content


def poblacion(forzar: bool) -> None:
    import rasterio
    from rasterio.windows import from_bounds
    destino = CARPETA / "poblacion_100m.tif"
    if destino.exists() and not forzar:
        return
    tmp = CARPETA / "_worldpop.tif"
    tmp.write_bytes(bajar(WORLDPOP, 1200))
    with rasterio.open(tmp) as src:
        ventana = from_bounds(*CAJA, transform=src.transform)
        datos = src.read(1, window=ventana)
        datos = np.where(datos < 0, 0, datos).astype("float32")
        perfil = src.profile | {"height": datos.shape[0], "width": datos.shape[1], "nodata": 0,
                                "transform": src.window_transform(ventana), "compress": "deflate", "predictor": 3}
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(datos, 1)
    tmp.unlink()
    print(f"  población: {datos.sum():,.0f} personas en la caja Tumbes-Piura")


def viviendas(forzar: bool) -> None:
    import duckdb
    destino = CARPETA / "viviendas.parquet"
    if destino.exists() and not forzar:
        return
    o, s, e, n = CAJA
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar=false;")
    archivos = [VIDA.format(c) for c in VIDA_CELDAS]
    df = con.execute(f"""
        SELECT (bbox.xmin + bbox.xmax) / 2 AS lon, (bbox.ymin + bbox.ymax) / 2 AS lat, area_in_meters AS area_m2
        FROM read_parquet({archivos})
        WHERE bbox.xmax >= {o} AND bbox.xmin <= {e} AND bbox.ymax >= {s} AND bbox.ymin <= {n}
          AND bf_source = 'google' AND confidence >= 0.75""").df()
    df.astype("float32").to_parquet(destino, index=False)
    print(f"  edificaciones: {len(df):,}")


def salud(forzar: bool) -> None:
    destino = CARPETA / "salud.csv"
    if destino.exists() and not forzar:
        return
    r = pd.read_csv(io.BytesIO(bajar(RENIPRESS)), sep=";", encoding="utf-8-sig", dtype=str)
    r = r[r["DEPARTAMENTO"].str.upper().isin(DEPARTAMENTOS) & (r["ESTADO"] == "ACTIVO")].copy()
    r["lat"] = pd.to_numeric(r["NORTE"], errors="coerce")
    r["lon"] = pd.to_numeric(r["ESTE"], errors="coerce")
    r = r[r["lat"].between(CAJA[1], CAJA[3]) & r["lon"].between(CAJA[0], CAJA[2])]
    cat = r["CATEGORIA"].fillna("")
    r["tipo"] = np.select([cat.str.match(r"^(II|III)-"), cat.str.match(r"^I-[34]"), cat.str.match(r"^I-[12]")],
                          ["Hospital / clínica", "Centro de salud", "Posta de salud"], "Otro")
    r = r[r["tipo"] != "Otro"]
    r = r.rename(columns={"NOMBRE": "nombre", "CATEGORIA": "categoria", "INSTITUCION": "institucion",
                          "PROVINCIA": "provincia", "DISTRITO": "distrito", "DEPARTAMENTO": "departamento"})
    r[["nombre", "tipo", "categoria", "institucion", "departamento", "provincia", "distrito", "lat", "lon"]].to_csv(
        destino, index=False)
    print(f"  salud: {len(r)} establecimientos ({r['tipo'].value_counts().to_dict()})")


def colegios(forzar: bool) -> None:
    destino = CARPETA / "colegios.csv"
    if destino.exists() and not forzar:
        return
    # ESCALE suele bloquear descargas automáticas; si el equipo sube el padrón a data/exposicion/padron_escale.csv
    # (columnas CODLOCAL, CEN_EDU, NLAT_IE, NLONG_IE, D_NIV_MOD, TALUMNO, D_DPTO), se usa ese.
    padron = CARPETA / "padron_escale.csv"
    if padron.exists():
        p = pd.read_csv(padron, dtype=str, encoding="latin1")
        p = p[p["D_DPTO"].str.upper().isin(DEPARTAMENTOS)]
        out = pd.DataFrame({"nombre": p["CEN_EDU"], "nivel": p.get("D_NIV_MOD"),
                            "alumnos": pd.to_numeric(p.get("TALUMNO"), errors="coerce"),
                            "lat": pd.to_numeric(p["NLAT_IE"], errors="coerce"),
                            "lon": pd.to_numeric(p["NLONG_IE"], errors="coerce"), "fuente": "ESCALE"})
    else:
        o, s, e, n = CAJA
        q = (f'[out:json][timeout:300];(nwr["amenity"~"^(school|kindergarten|college)$"]({s},{o},{n},{e}););out center tags;')
        j = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=400).json()
        filas = []
        for el in j["elements"]:
            c = el.get("center", el)
            t = el.get("tags", {})
            filas.append({"nombre": t.get("name", "Local educativo sin nombre"), "nivel": t.get("isced:level") or t.get("amenity"),
                          "alumnos": None, "lat": c.get("lat"), "lon": c.get("lon"), "fuente": "OpenStreetMap"})
        out = pd.DataFrame(filas)
    out = out.dropna(subset=["lat", "lon"])
    out.to_csv(destino, index=False)
    print(f"  colegios: {len(out)} ({out['fuente'].iloc[0] if len(out) else '-'})")


def distritos(forzar: bool) -> None:
    destino = CARPETA / "distritos.geojson"
    if destino.exists() and not forzar:
        return
    z = zipfile.ZipFile(io.BytesIO(bajar(GADM3)))
    g = json.loads(z.read(z.namelist()[0]))
    feats = []
    for f in g["features"]:
        p = f["properties"]
        dep = p["NAME_1"].upper()
        if dep in DEPARTAMENTOS:
            feats.append({"type": "Feature", "geometry": f["geometry"],
                          "properties": {"departamento": p["NAME_1"], "provincia": p["NAME_2"], "distrito": p["NAME_3"]}})
    from shapely.geometry import mapping, shape
    for f in feats:
        f["geometry"] = mapping(shape(f["geometry"]).simplify(0.0015))
    json.dump({"type": "FeatureCollection", "features": feats}, open(destino, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  distritos: {len(feats)}")


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    forzar = "--forzar" in sys.argv
    for paso in (distritos, salud, colegios, poblacion, viviendas):
        try:
            paso(forzar)
        except Exception as error:  # una fuente caída no detiene las demás
            print(f"  {paso.__name__}: ERROR {error}")
