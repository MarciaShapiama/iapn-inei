"""Repara el origen del ráster WorldPop recortado (data/exposicion/poblacion_100m.tif) sin volver a descargarlo.

El recorte original quedó desplazado 86 columnas (0,0717°, ~7,9 km) al oeste: la caja pedía -81,40° pero el archivo
de Perú empieza en ~-81,33°. El desplazamiento se estimó maximizando la correlación entre la población y la densidad
de edificaciones de Google Open Buildings (fuente independiente): r = 0,80 con 86 columnas frente a ~0 sin corregir.
Es idempotente: si el ráster ya está alineado (desplazamiento óptimo 0), no cambia nada.
Uso: python src/reparar_poblacion.py
"""
import numpy as np
import pandas as pd
import rasterio
from affine import Affine

from exposicion import CARPETA


def desplazamiento_optimo(pob, t, edif, rango=range(-120, 121, 2)) -> tuple[int, float]:
    col = np.floor((edif.lon - t.c) / t.a).astype(int)
    fil = np.floor((edif.lat - t.f) / t.e).astype(int)
    H, W = pob.shape
    P = max(abs(r) for r in rango) + 2
    ok = (fil >= 0) & (fil < H) & (col >= -P) & (col < W + P)
    B = np.zeros((H, W + 2 * P))
    np.add.at(B, (fil[ok], col[ok] + P), 1)
    mejor = (-1.0, 0)
    for dx in rango:
        sub = B[:, P + dx:P + dx + W]
        m = (pob > 0) | (sub > 0)
        r = float(np.corrcoef(pob[m], sub[m])[0, 1])
        mejor = max(mejor, (r, dx))
    return mejor[1], mejor[0]


def main():
    ruta = CARPETA / "poblacion_100m.tif"
    edif = pd.read_parquet(CARPETA / "viviendas.parquet")
    with rasterio.open(ruta) as s:
        pob, t = s.read(1).astype("float64"), s.transform
    dx, r = desplazamiento_optimo(pob, t, edif)
    # afinar de 1 en 1 alrededor del óptimo
    dx, r = desplazamiento_optimo(pob, t, edif, range(dx - 2, dx + 3))
    print(f"desplazamiento óptimo: {dx} columnas (r = {r:.3f})")
    if dx == 0:
        print("ya alineado: sin cambios"); return
    with rasterio.open(ruta, "r+") as s:
        s.transform = Affine(t.a, t.b, t.c + dx * t.a, t.d, t.e, t.f)
    print(f"origen corregido: {t.c:.5f} -> {t.c + dx * t.a:.5f}")


if __name__ == "__main__":
    main()
