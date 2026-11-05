"""Reemplazo de poligonos() en src/impacto.py: capas de agua sin escalones.

Qué cambia frente a la versión actual:
  1. No agrupa 2×2 celdas (hoy la zona de JRC sale en bloques de 180 m; la celda real es de 90 m).
  2. Antes de convertir a polígonos, remuestrea cada celda en 4×4 y suaviza un poco (≈ 30 m). El borde exterior sale
     de la máscara suavizada cortada en 0,5, así el área se conserva (diferencia < 0,5 % en las pruebas).
  3. Procesa por ventanas con margen, para no pasar de unos pocos MB de memoria.
SOLO es para dibujar. Las cifras de personas, edificaciones y colegios se siguen contando con el ráster original.
"""
from __future__ import annotations

import json

import numpy as np
from scipy import ndimage as ndi

F = 4            # cada celda se divide en F × F
SIGMA = 1.5      # suavizado, en celdas finas (1,5 × 90 m / 4 ≈ 34 m)
VENTANA = 512    # celdas originales por ventana
MARGEN = 8       # celdas de margen para que no se noten las uniones
CORTES = [0.5, 1.5, 3.0]   # mismas clases de profundidad que hoy: < 0,5 / 0,5-1,5 / 1,5-3 / > 3 m


def clases_suaves(valor: np.ndarray, tipo: str) -> np.ndarray:
    """Devuelve la grilla fina (F veces más celdas por lado) con la clase de cada celda: 0 = sin agua."""
    v = np.nan_to_num(valor.astype("float32"), nan=0.0)
    v[v < 0] = 0
    mascara = (v > 0).astype("float32")
    dentro = ndi.gaussian_filter(ndi.zoom(mascara, F, order=1, grid_mode=True, mode="nearest"), SIGMA) >= 0.5
    if tipo == "radar":
        return dentro.astype("uint8")
    prof = ndi.gaussian_filter(ndi.zoom(v, F, order=1, grid_mode=True, mode="nearest"), SIGMA)
    return np.where(dentro, np.digitize(prof, CORTES) + 1, 0).astype("uint8")


def por_ventanas(valor: np.ndarray, tipo: str):
    """Recorre el ráster por ventanas y entrega (fila0, col0, clases_finas) sin el margen."""
    h, w = valor.shape
    for r0 in range(0, h, VENTANA):
        for c0 in range(0, w, VENTANA):
            r1, c1 = min(r0 + VENTANA, h), min(c0 + VENTANA, w)
            if not (valor[r0:r1, c0:c1] > 0).any():
                continue
            a0, b0 = max(r0 - MARGEN, 0), max(c0 - MARGEN, 0)
            a1, b1 = min(r1 + MARGEN, h), min(c1 + MARGEN, w)
            cl = clases_suaves(valor[a0:a1, b0:b1], tipo)
            cl = cl[(r0 - a0) * F:(r0 - a0 + r1 - r0) * F, (c0 - b0) * F:(c0 - b0 + c1 - c0) * F]
            yield r0, c0, cl


def poligonos(clave: str, tipo: str, valor: np.ndarray, t) -> dict:
    """Capa del mapa en polígonos suaves. Peligro: 4 clases de profundidad; radar: 1 clase."""
    from affine import Affine
    from rasterio import features
    from shapely.geometry import mapping, shape
    from config import DASH_DATA          # mismo módulo que usa impacto.py
    fino = abs(t.a) / F
    feats = []
    for r0, c0, cl in por_ventanas(valor, tipo):
        tv = t * Affine.translation(c0, r0) * Affine.scale(1 / F)
        for geom, c in features.shapes(cl, mask=cl > 0, transform=tv):
            g = shape(geom).simplify(fino * 0.75, preserve_topology=True)   # quita la escalera fina
            if g.is_empty or g.area < (abs(t.a) ** 2) * 0.5:                   # descarta manchas menores a media celda
                continue
            m = json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 5))
            feats.append({"type": "Feature", "properties": {"c": int(c)}, "geometry": m})
    ruta = DASH_DATA / f"capa_{clave}.geojson"
    json.dump({"type": "FeatureCollection", "features": feats}, open(ruta, "w"), separators=(",", ":"))
    print(f"  capa_{clave}.geojson: {len(feats)} polígonos, {ruta.stat().st_size // 1024} KB")
    return {"capa": f"capa_{clave}.geojson"}
