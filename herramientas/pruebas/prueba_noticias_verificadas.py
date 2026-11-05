"""Prueba del detector de inundaciones con noticias verificadas (data/eventos/catalogo_verificado.csv).

Pedido del profesor (reunión del 4/11/2026): si una noticia dice que hubo inundación y el tablero no muestra nada,
hay que saber por qué. Para cada evento del catálogo se toma un cuadrado de ~6 km alrededor del lugar y se repite el
cálculo de src/huellas.py en una ventana propia del evento (2 días antes a 12 días después: al menos 2 pasadas de
Sentinel-1) frente a la temporada seca anterior. Se mide cuánto agua nueva queda con cada variante de reglas:

    V0  reglas actuales del tablero: VV < -17 dB, caída > 3 dB, sin agua permanente, altura < 250 m, pendiente < 5°
    V1  sin el límite de altura (solo pendiente < 5°): ¿se ve algo en la sierra?
    V2  sin altura ni pendiente: todo lo que el radar marca como agua nueva

y también la capa publicada del evento (data/huellas/2017.tif, 2023.tif o vivo.tif) en el mismo cuadrado.
Las coordenadas vienen de data/eventos/lugares.csv (centro del centro poblado), no del punto exacto de la noticia.

Salida: docs/evidencia/prueba_noticias_verificadas.json  (la usa src/noticias.py para el tablero)
Uso: python herramientas/pruebas/prueba_noticias_verificadas.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))
SALIDA = R / "docs" / "evidencia" / "prueba_noticias_verificadas.json"
MEDIO = 0.027                     # medio lado del cuadrado en grados (~3 km)
RES = 0.0005
DETECTADO_KM2 = 0.05              # ~17 píxeles de 55 m
CAPA = {"2017": "2017.tif", "2023": "2023.tif"}


def km2_px(lat):
    return (RES * 111_320 * np.cos(np.radians(lat))) * (RES * 110_600) / 1e6


def recortar(ruta, t, forma):
    import rasterio
    from rasterio.warp import Resampling, reproject
    dst = np.zeros(forma, dtype="float32")
    with rasterio.open(ruta) as src:
        reproject(rasterio.band(src, 1), dst, dst_transform=t, dst_crs="EPSG:4326", resampling=Resampling.nearest)
    return dst


def limpiar(m):
    from huellas import limpiar as limpiar_huellas
    return limpiar_huellas(m)


def probar(cat, ev: dict) -> dict:
    import odc.stac
    from huellas import pendiente, referencia_seca
    f = date.fromisoformat(ev["fecha"])
    t0, t1 = (f - timedelta(days=2)).isoformat(), (f + timedelta(days=12)).isoformat()
    r0, r1 = referencia_seca(f - timedelta(days=2))
    lat, lon = ev["lat"], ev["lon"]
    bbox = (lon - MEDIO, lat - MEDIO, lon + MEDIO, lat + MEDIO)

    def vv(a, b):
        items = cat.search(collections=["sentinel-1-rtc"], bbox=bbox, datetime=f"{a}/{b}").item_collection()
        if not len(items):
            return None, None, []
        ds = odc.stac.load(items, bands=["vv"], crs="EPSG:4326", resolution=RES, bbox=bbox, groupby="solar_day",
                           resampling="average")
        v = ds["vv"].where(ds["vv"] > 0)
        v = v.rolling({d: 3 for d in v.dims if d != "time"}, center=True, min_periods=4).mean()
        return 10 * np.log10(v), ds.odc.geobox, sorted({str(i.datetime.date()) for i in items})

    out = {"ventana_evento": [t0, t1], "referencia_seca": [r0, r1]}
    ref, gb, f_ref = vv(r0, r1)
    eve, _, f_ev = vv(t0, t1)
    out["pasadas_evento"] = f_ev
    out["pasadas_desde_la_noticia"] = [x for x in f_ev if x >= ev["fecha"]]
    out["imagenes_referencia"] = len(f_ref)
    if ref is None or eve is None:
        out["resultado"] = "sin imágenes de Sentinel-1"
        return out
    r = ref.median("time").values
    e = eve.min("time").values
    z = odc.stac.load(cat.search(collections=["cop-dem-glo-30"], bbox=bbox).item_collection(), bands=["data"],
                      geobox=gb, resampling="bilinear")["data"].max("time").values.astype("float32")
    occ = odc.stac.load(cat.search(collections=["jrc-gsw"], bbox=bbox).item_collection(), bands=["occurrence"],
                        geobox=gb, resampling="nearest")["occurrence"].max("time").values.astype("float32")
    occ[occ > 100] = 0
    t, forma, px = gb.affine, r.shape, km2_px(lat)
    base = (e < -17) & ((r - e) > 3) & ~(occ >= 75) & np.isfinite(e) & np.isfinite(r)
    alto, lad = z >= 250, pendiente(z, lat) >= 5
    v = {"V0_reglas_actuales": limpiar(base & ~alto & ~lad), "V1_sin_limite_altura": limpiar(base & ~lad),
         "V2_sin_altura_ni_pendiente": limpiar(base)}
    out.update({k: round(float(m.sum() * px), 3) for k, m in v.items()})
    capa = CAPA.get(ev["fecha"][:4])
    if capa is None and ev["fecha"] >= "2026-10-11":
        capa = "vivo.tif"
    if capa:
        pub = recortar(R / "data" / "huellas" / capa, t, forma)
        out["capa_publicada"] = capa
        out["km2_capa_publicada"] = round(float((pub == 1).sum() * px), 3)
    jrc = recortar(R / "data" / "exposicion" / "peligro_rp100.tif", t, forma)
    out["km2_zona_inundable_jrc_rp100"] = round(float((jrc > 0).sum() * px), 2)
    out["altura_mediana_m"] = round(float(np.nanmedian(z)))
    out["pct_area_sobre_250m"] = round(float(alto.mean() * 100), 1)
    out["caida_mediana_db_en_jrc"] = round(float(np.nanmedian((r - e)[jrc > 0])), 1) if (jrc > 0).any() else None
    out["detectado_V0"] = out["V0_reglas_actuales"] >= DETECTADO_KM2
    out["detectado_V1"] = out["V1_sin_limite_altura"] >= DETECTADO_KM2
    return out


def main() -> None:
    from huellas import catalogo
    cat_ev = pd.read_csv(R / "data" / "eventos" / "catalogo_verificado.csv", dtype=str)
    lug = pd.read_csv(R / "data" / "eventos" / "lugares.csv", dtype={"ubigeo": str})
    cat = catalogo()
    res = {"lado_cuadrado_km": round(2 * MEDIO * 111, 1), "umbral_detectado_km2": DETECTADO_KM2, "eventos": []}
    for _, fila in cat_ev.iterrows():
        l = lug[(lug["nombre"] == fila["lugar"]) & (lug["ubigeo"] == fila["ubigeo"])].iloc[0]
        ev = {**fila.to_dict(), "lat": float(l["lat"]), "lon": float(l["lon"]), "altura_lugar_m": int(l["altura_m"])}
        print(f"{ev['id']} ...", flush=True)
        try:
            ev.update(probar(cat, ev))
        except Exception as error:  # noqa: BLE001
            ev["error"] = f"{type(error).__name__}: {error}"
        res["eventos"].append({k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in ev.items()})
        print(json.dumps({k: ev.get(k) for k in ("id", "pasadas_desde_la_noticia", "V0_reglas_actuales",
                                                  "V1_sin_limite_altura", "V2_sin_altura_ni_pendiente",
                                                  "km2_capa_publicada", "error")}, ensure_ascii=False), flush=True)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
