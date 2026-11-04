"""Impacto adicional de cada zona inundable o mancha de radar (complementa src/impacto.py).

Para cada capa (1 en 10 y 1 en 100 años; radar 2017, 2023 y últimos días):
    niños de 0 a 4 años y personas de 65 años o más (WorldPop 2026 por edad)
    hectáreas de cultivo (ESA WorldCover 2021, clase 40)
    km de carreteras principales dentro de la zona, por tipo, y puentes dentro o a ≤ 100 m (OpenStreetMap)
También por departamento (Tumbes y Piura).

Salida: dashboard/data/inundacion_extra.json
Uso: python src/impacto_extra.py
"""
from __future__ import annotations

import json

import numpy as np

from config import DASH_DATA
from exposicion import CARPETA as EXPO
from impacto import cargar_capas, metros, rasterizar_distritos

TIPOS = {"motorway": "Autopista", "trunk": "Troncal (red nacional)", "primary": "Primaria",
         "secondary": "Secundaria", "tertiary": "Terciaria"}


def fraccion_en(mascara, t, destino_t, destino_forma):
    from rasterio.warp import Resampling, reproject
    f = np.zeros(destino_forma, dtype="float32")
    reproject(mascara.astype("float32"), f, src_transform=t, src_crs="EPSG:4326", dst_transform=destino_t,
              dst_crs="EPSG:4326", resampling=Resampling.average)
    return f


def leer(nombre):
    import rasterio
    ruta = EXPO / nombre
    if not ruta.exists():
        return None
    with rasterio.open(ruta) as s:
        return s.read(1).astype("float64"), s.transform


def km_tramo(coords) -> float:
    c = np.asarray(coords, dtype="float64")
    if len(c) < 2:
        return 0.0
    lat = np.radians(c[:, 1])
    dx = np.radians(np.diff(c[:, 0])) * np.cos((lat[:-1] + lat[1:]) / 2)
    dy = np.diff(lat)
    return float(6371.0 * np.sqrt(dx ** 2 + dy ** 2).sum())


def vias_en(mascara, t, vias, distancia_m):
    """km de vía cuyos vértices (densificados cada ~50 m) caen en la zona; puentes dentro o a ≤ 100 m."""
    H, W = mascara.shape
    por_tipo, puentes, nombres_puente = {}, 0, []
    for f in vias["features"]:
        c = np.asarray(f["geometry"]["coordinates"], dtype="float64")
        if len(c) < 2:
            continue
        # densificar para no saltarse tramos cortos inundados
        seg = np.linalg.norm(np.diff(c, axis=0), axis=1)
        pasos = np.maximum(1, np.ceil(seg / 0.0005)).astype(int)
        pts = np.vstack([np.linspace(c[i], c[i + 1], pasos[i], endpoint=False) for i in range(len(c) - 1)] + [c[-1:]])
        col = np.floor((pts[:, 0] - t.c) / t.a).astype(int)
        fil = np.floor((pts[:, 1] - t.f) / t.e).astype(int)
        ok = (fil >= 0) & (fil < H) & (col >= 0) & (col < W)
        dentro = np.zeros(len(pts), bool)
        dentro[ok] = mascara[fil[ok], col[ok]]
        if dentro.any():
            km = km_tramo(pts) * dentro.mean()
            tipo = f["properties"]["tipo"]
            por_tipo[tipo] = por_tipo.get(tipo, 0.0) + km
        if f["properties"]["puente"]:
            d = np.full(len(pts), np.inf)
            d[ok] = distancia_m[fil[ok], col[ok]]
            if (d <= 100).any():
                puentes += 1
                if f["properties"]["nombre"]:
                    nombres_puente.append(f["properties"]["nombre"])
    return ({TIPOS.get(k, k): round(v, 1) for k, v in sorted(por_tipo.items(), key=lambda x: -x[1])},
            puentes, sorted(set(nombres_puente))[:15])


def main() -> None:
    from scipy import ndimage as ndi
    ninos, adultos, cultivo = leer("poblacion_0a4.tif"), leer("poblacion_65mas.tif"), leer("cultivos_30m.tif")
    vias = json.load(open(EXPO / "vias.geojson", encoding="utf-8")) if (EXPO / "vias.geojson").exists() else None
    salida = {"fuentes": {"edades": "WorldPop 2026, población por edad y sexo, 100 m",
                          "cultivos": "ESA WorldCover 2021 v200, clase 40 (tierras de cultivo), 10 m",
                          "vias": "OpenStreetMap: vías troncales, primarias, secundarias y terciarias"},
              "capas": {}}
    for clave, (nombre, tipo, valor, t, meta) in cargar_capas().items():
        m = valor > 0
        dr, nombres = rasterizar_distritos(t, m.shape)
        depto = np.array(["" if k == 0 else nombres[k - 1][0] for k in range(len(nombres) + 1)])[dr]
        r = {"nombre": nombre}
        for etiqueta, dato in (("ninos_0a4", ninos), ("mayores_65", adultos)):
            if dato is None:
                continue
            pob, tp = dato
            r[etiqueta] = round(float((pob * fraccion_en(m, t, tp, pob.shape)).sum()))
            r[etiqueta + "_por_departamento"] = {
                d: round(float((pob * fraccion_en(m & (depto == d), t, tp, pob.shape)).sum())) for d in ("Piura", "Tumbes")}
        if cultivo is not None:
            cu, tc = cultivo
            f = fraccion_en(m, t, tc, cu.shape)
            mx, my = metros(tc)
            r["cultivo_ha"] = round(float((f * (cu == 1)).sum() * mx * my / 1e4))
        if vias is not None:
            mx, my = metros(t)
            dist = ndi.distance_transform_edt(~m, sampling=(my, mx))
            km, puentes, nombres_p = vias_en(m, t, vias, dist)
            r["vias_km"], r["vias_km_total"] = km, round(sum(km.values()), 1)
            r["puentes"], r["puentes_nombres"] = puentes, nombres_p
        salida["capas"][clave] = r
        print(clave, {k: v for k, v in r.items() if not k.endswith(("nombres", "_por_departamento"))})
    json.dump(salida, open(DASH_DATA / "inundacion_extra.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
