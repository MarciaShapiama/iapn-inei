"""Diccionario de lugares de Tumbes y Piura para ubicar noticias de inundación (se corre una vez).

Toma los centros poblados urbanos del INEI (polígonos de manzanas en docs_recibidos/, que no se suben) y guarda solo
el NOMBRE, el distrito y el punto central de cada centro poblado: no hay ninguna cifra por manzana. Agrega lugares
que suelen salir en las noticias y no son centros poblados del INEI (asentamientos, sectores, ríos), y la altura de
cada punto (AWS Terrain Tiles, sin clave) para saber si está fuera del alcance del radar (> 250 m).

Salida: data/eventos/lugares.csv
Uso: python herramientas/datos/crear_lugares.py
"""
from __future__ import annotations

import io
import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from PIL import Image

R = Path(__file__).resolve().parents[2]
SHP = R / "docs_recibidos" / "manzanas" / "manzana" / "shp_piura_tumbes" / "manz_piura_tumbes.shp"
SALIDA = R / "data" / "eventos" / "lugares.csv"
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
Z = 11
MIN_MANZANAS = 15          # centros poblados más pequeños no se incluyen (ruido en la búsqueda de nombres)

# Lugares que aparecen en noticias y no son centros poblados del INEI (coordenadas aproximadas, verificadas en mapa)
EXTRA = [
    ("PUERTO PERU", "240302", -3.4745, -80.2470, "asentamiento humano de Aguas Verdes"),
    ("TOMAS ARIZOLA", "240302", -3.4690, -80.2560, "sector de Aguas Verdes"),
    ("VAQUERIA", "240105", -3.6650, -80.4560, "sector de San Jacinto, río Tumbes"),
    ("PLATEROS", "240105", -3.6950, -80.4300, "sector de San Jacinto, río Tumbes"),
    ("BAJO PIURA", "200105", -5.3300, -80.6800, "zona baja del río Piura (Catacaos, Cura Mori, El Tallán, La Arena, La Unión)"),
    ("RIO SERRAN", "200302", -5.3600, -79.6300, "río en Canchaque y San Miguel de El Faique (Huancabamba)"),
    ("QUEBRADA FERNANDEZ", "200706", -4.0900, -81.0300, "quebrada en Máncora"),
    ("QUEBRADA CABO BLANCO", "200704", -4.2500, -81.2200, "quebrada en El Alto"),
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().replace("-", " ").split())


def altura(lons, lats) -> np.ndarray:
    cache, out = {}, []
    for lon, lat in zip(lons, lats):
        n = 2 ** Z
        x = (lon + 180) / 360 * n
        y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(x), int(y)
        if (tx, ty) not in cache:
            r = requests.get(TERRARIUM.format(z=Z, x=tx, y=ty), timeout=60)
            r.raise_for_status()
            a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=float)
            cache[(tx, ty)] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
        out.append(float(cache[(tx, ty)][int((y - ty) * 256), int((x - tx) * 256)]))
    return np.maximum(np.round(out), 0)


def main() -> None:
    import geopandas as gpd
    if not SHP.exists():
        sys.exit(f"No está {SHP}: este paso necesita los polígonos del INEI (solo se usan nombres y centros).")
    g = gpd.read_file(SHP, columns=["ubigeo", "nombdep", "nombprov", "nombdist", "nomccpp", "idccpp"])
    g = g.to_crs(32717)
    cc = g.dissolve(by=["idccpp", "nomccpp", "ubigeo", "nombdep", "nombprov", "nombdist"]).reset_index()
    cc["manzanas"] = g.groupby("idccpp").size().reindex(cc["idccpp"]).values
    pt = cc.geometry.centroid.to_crs(4326)
    cc["lon"], cc["lat"] = pt.x.round(4), pt.y.round(4)
    dist = cc.groupby("ubigeo").agg(departamento=("nombdep", "first"), provincia=("nombprov", "first"),
                                    distrito=("nombdist", "first"))
    # capital del distrito: el centro poblado con el mismo nombre del distrito, o el más grande
    cc["es_capital"] = False
    for u, grupo in cc.groupby("ubigeo"):
        mismo = grupo[grupo["nomccpp"].map(norm) == norm(grupo["nombdist"].iloc[0])]
        idx = (mismo if len(mismo) else grupo).sort_values("manzanas", ascending=False).index[0]
        cc.loc[idx, "es_capital"] = True
    L = cc[(cc["manzanas"] >= MIN_MANZANAS) | cc["es_capital"]].copy()
    L = pd.DataFrame({"nombre": L["nomccpp"].map(norm), "ubigeo": L["ubigeo"], "tipo": np.where(L["es_capital"], "capital de distrito", "centro poblado"),
                      "manzanas": L["manzanas"], "lat": L["lat"], "lon": L["lon"], "nota": ""})
    ex = pd.DataFrame(EXTRA, columns=["nombre", "ubigeo", "lat", "lon", "nota"])
    ex["tipo"], ex["manzanas"] = "lugar citado en noticias", 0
    L = pd.concat([L, ex], ignore_index=True)
    L = L.join(dist, on="ubigeo")
    for c in ("departamento", "provincia", "distrito"):
        L[c] = L[c].map(norm)
    L["altura_m"] = altura(L["lon"], L["lat"]).astype(int)
    L = L.sort_values(["departamento", "provincia", "distrito", "tipo", "nombre"]).drop_duplicates(["nombre", "ubigeo"])
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    L[["nombre", "tipo", "ubigeo", "departamento", "provincia", "distrito", "lat", "lon", "altura_m", "manzanas", "nota"]] \
        .drop(columns="manzanas").to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"{len(L)} lugares, {L['ubigeo'].nunique()} distritos; sobre 250 m: {(L['altura_m'] > 250).sum()}")


if __name__ == "__main__":
    main()
