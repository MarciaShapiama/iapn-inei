"""Prueba con el Global Flood Monitoring (GFM) de Copernicus: mapas automáticos de inundación de cada imagen
Sentinel-1, publicados en el STAC abierto de EODC (https://stac.eodc.eu/api/v1, colección GFM).

Se cuentan los píxeles inundados (ensemble_flood_extent = 1) dentro de dos cuadros:
    - valle bajo del río Tumbes (desbordes del 29/4/2023 y 12/2/2025)
    - Tumbes y Piura completos (últimos 25 días)
y se compara con lo que detectó el radar del proyecto. Salida: docs/evidencia/prueba_gfm.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
SALIDA = R / "docs" / "evidencia" / "prueba_gfm.json"
VALLE = (-80.51, -3.70, -80.39, -3.58)
TP = (-81.4, -6.4, -79.15, -3.35)
CASOS = [
    {"caso": "Desborde del río Tumbes, 12/2/2025", "bbox": VALLE, "fechas": "2025-02-10/2025-02-19"},
    {"caso": "Desborde del río Tumbes, 29/4/2023", "bbox": VALLE, "fechas": "2023-04-27/2023-05-08"},
    {"caso": "Inundación del Bajo Piura, marzo de 2017 (control)", "bbox": (-80.85, -5.65, -80.45, -5.15), "fechas": "2017-03-20/2017-04-05"},
    {"caso": "Tumbes y Piura, últimos 25 días", "bbox": TP, "fechas": "2026-10-11/2026-11-05"},
]


def contar(href, bbox):
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    with rasterio.open(href) as s:
        b = transform_bounds("EPSG:4326", s.crs, *bbox)
        w = from_bounds(*b, transform=s.transform).intersection(rasterio.windows.Window(0, 0, s.width, s.height))
        a = s.read(1, window=w)
        px = abs(s.transform.a * s.transform.e)
    return int((a == 1).sum()), float((a == 1).sum() * px / 1e6), int(a.size)


def main() -> None:
    from pystac_client import Client
    cat = Client.open("https://stac.eodc.eu/api/v1")
    out = []
    for c in CASOS:
        o = {**c, "imagenes": []}
        try:
            items = list(cat.search(collections=["GFM"], bbox=c["bbox"], datetime=c["fechas"], max_items=200).items())
            o["n_items"] = len(items)
            for it in items:
                a = it.assets.get("ensemble_flood_extent")
                if a is None:
                    continue
                try:
                    n, km2, tam = contar(a.href, c["bbox"])
                except Exception as e:  # noqa: BLE001
                    o["imagenes"].append({"id": it.id, "error": str(e)[:200]}); continue
                o["imagenes"].append({"id": it.id, "fecha": str(it.datetime)[:16], "km2_inundado": round(km2, 2), "pixeles": tam})
        except Exception as e:  # noqa: BLE001
            o["error"] = str(e)[:300]
        print(json.dumps(o, ensure_ascii=False)[:2000], flush=True)
        out.append(o)
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
