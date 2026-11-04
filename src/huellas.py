"""Huella de inundación con radar Sentinel-1 (RTC, Microsoft Planetary Computer) en Tumbes y Piura.

Método de detección de cambios (estándar para inundaciones con radar):
    1. Referencia seca: mediana de las imágenes VV de la temporada seca anterior (agosto-noviembre).
    2. Evento: para cada píxel, el valor VV más bajo de las imágenes del periodo del evento.
    3. Inundado si: VV del evento < -17 dB (el agua calma refleja poco) y bajó más de 3 dB frente a la
       referencia; se descarta el agua permanente (ya < -17 dB en la referencia), lo que está a más de
       250 m de altura y las pendientes > 5° (Copernicus DEM 30 m), y las manchas de menos de 5 píxeles.

Eventos: 2017 (El Niño costero, feb-abr), 2023 (ciclón Yaku, mar-abr) y "vivo" (últimos 24 días).
Salidas en data/huellas/: {evento}.tif (1 = inundado) y {evento}.json (imágenes usadas).
El radar ve a través de las nubes, pero no detecta bien el agua bajo árboles o entre edificios densos:
la huella es un mínimo.

Uso: python src/huellas.py [2017 2023 vivo]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from config import DATA
from exposicion import CAJA

CARPETA = DATA / "huellas"
RES = 0.0005                     # grados (~55 m)
UMBRAL_AGUA, CAIDA_DB, ALTURA_MAX, PENDIENTE_MAX, MIN_PIX = -17.0, 3.0, 250.0, 5.0, 5
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def eventos() -> dict:
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    ref_anio = hoy.year if hoy.month >= 11 else hoy.year - 1
    return {
        "2017": {"nombre": "El Niño costero 2017", "evento": ("2017-02-01", "2017-04-30"), "ref": ("2016-08-01", "2016-11-30")},
        "2023": {"nombre": "Ciclón Yaku 2023", "evento": ("2023-03-01", "2023-04-15"), "ref": ("2022-08-01", "2022-11-30")},
        "vivo": {"nombre": "Últimos 24 días", "evento": ((hoy - timedelta(days=24)).isoformat(), hoy.isoformat()),
                 "ref": (f"{ref_anio}-08-01", f"{ref_anio}-10-31")},
    }


def catalogo():
    import planetary_computer as pc
    import pystac_client
    return pystac_client.Client.open(STAC, modifier=pc.sign_inplace)


def cargar_vv(cat, t0: str, t1: str, geobox=None):
    import odc.stac
    items = cat.search(collections=["sentinel-1-rtc"], bbox=CAJA, datetime=f"{t0}/{t1}").item_collection()
    if not len(items):
        return None, []
    kw = {"geobox": geobox} if geobox is not None else {"crs": "EPSG:4326", "resolution": RES, "bbox": CAJA}
    ds = odc.stac.load(items, bands=["vv"], chunks={"latitude": 2048, "longitude": 2048}, groupby="solar_day",
                       resampling="average", **kw)
    vv = ds["vv"].where(ds["vv"] > 0)
    yx = {d: 3 for d in vv.dims if d != "time"}
    vv = vv.rolling(yx, center=True, min_periods=4).mean()          # reduce el moteado (speckle)
    db = 10 * np.log10(vv)
    fechas = sorted({str(i.datetime.date()) for i in items})
    return db, fechas


def dem(cat, geobox):
    import odc.stac
    items = cat.search(collections=["cop-dem-glo-30"], bbox=CAJA).item_collection()
    d = odc.stac.load(items, bands=["data"], geobox=geobox, chunks={"latitude": 2048, "longitude": 2048}, resampling="bilinear")
    return d["data"].max("time").compute().values.astype("float32")


def pendiente(z: np.ndarray, lat0: float) -> np.ndarray:
    dy = RES * 110_600
    dx = RES * 111_320 * np.cos(np.radians(lat0))
    gy, gx = np.gradient(np.nan_to_num(z), dy, dx)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def limpiar(m: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi
    m = ndi.binary_opening(m, structure=np.ones((2, 2)))
    lab, n = ndi.label(m)
    if n == 0:
        return m
    tam = np.bincount(lab.ravel())
    ok = tam >= MIN_PIX
    ok[0] = False
    return ok[lab]


def guardar(nombre: str, m: np.ndarray, geobox, meta: dict) -> None:
    import rasterio
    t = geobox.affine
    perfil = {"driver": "GTiff", "height": m.shape[0], "width": m.shape[1], "count": 1, "dtype": "uint8",
              "crs": "EPSG:4326", "transform": t, "compress": "deflate", "nodata": 255}
    with rasterio.open(CARPETA / f"{nombre}.tif", "w", **perfil) as dst:
        dst.write(m.astype("uint8"), 1)
    json.dump(meta, open(CARPETA / f"{nombre}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def procesar(cat, clave: str, ev: dict, z=None, geobox=None):
    print(f"Evento {clave}: {ev['evento']} frente a referencia {ev['ref']}")
    ref, f_ref = cargar_vv(cat, *ev["ref"], geobox=geobox)
    if ref is None:
        print("  sin imágenes de referencia"); return z, geobox
    geobox = geobox or ref.odc.geobox
    evento, f_ev = cargar_vv(cat, *ev["evento"], geobox=geobox)
    if evento is None:
        print("  sin imágenes del evento"); return z, geobox
    r = ref.median("time").compute().values
    e = evento.min("time").compute().values
    if z is None:
        z = dem(cat, geobox)
    lat0 = (CAJA[1] + CAJA[3]) / 2
    apto = (z < ALTURA_MAX) & (pendiente(z, lat0) < PENDIENTE_MAX)
    permanente = r < UMBRAL_AGUA
    inund = (e < UMBRAL_AGUA) & ((r - e) > CAIDA_DB) & apto & ~permanente & np.isfinite(e) & np.isfinite(r)
    inund = limpiar(inund)
    m = np.where(inund, 1, 0).astype("uint8")
    m[permanente & apto] = 2                                                   # agua permanente (referencia)
    km2 = float(inund.sum() * (RES * 110_600) * (RES * 111_320 * np.cos(np.radians(lat0))) / 1e6)
    print(f"  {len(f_ref)} imágenes de referencia, {len(f_ev)} del evento: {km2:,.1f} km² inundados")
    guardar(clave, m, geobox, {"evento": clave, "nombre": ev["nombre"], "periodo": ev["evento"], "referencia": ev["ref"],
                               "imagenes_evento": f_ev, "imagenes_referencia": f_ref, "km2": round(km2, 1),
                               "resolucion_grados": RES, "metodo": "Sentinel-1 RTC VV, detección de cambios",
                               "calculado": datetime.now(ZoneInfo("America/Lima")).isoformat(timespec="minutes")})
    return z, geobox


def main() -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    pedidos = sys.argv[1:] or ["2017", "2023", "vivo"]
    cat = catalogo()
    z = geobox = None
    for clave, ev in eventos().items():
        if clave not in pedidos:
            continue
        if clave != "vivo" and (CARPETA / f"{clave}.tif").exists() and "--forzar" not in sys.argv:
            print(f"Evento {clave}: ya calculado"); continue
        try:
            z, geobox = procesar(cat, clave, ev, z, geobox)
        except Exception as error:
            print(f"  {clave}: ERROR {error}")


if __name__ == "__main__":
    main()
