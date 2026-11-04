"""Huella de inundación con radar Sentinel-1 (RTC, Microsoft Planetary Computer) en Tumbes y Piura.

Método de detección de cambios (estándar para inundaciones con radar):
    1. Referencia seca: mediana de las imágenes VV de la temporada seca anterior (agosto-noviembre).
    2. Evento: para cada píxel, el valor VV más bajo de las imágenes del periodo del evento.
    3. Inundado si: VV del evento < -17 dB (el agua calma refleja poco) y bajó más de 3 dB frente a la
       referencia; se descarta el agua permanente, lo que está a más de 250 m de altura y las pendientes > 5° (Copernicus DEM 30 m), y las manchas de menos de 5 píxeles.

Agua permanente: por defecto se toma del mapa mundial JRC Global Surface Water (agua presente al menos el 75 %
del tiempo entre 1984 y 2021). Antes se tomaba de la propia referencia seca (VV < -17 dB), pero la validación con el
mapa oficial de Copernicus EMS de 2017 mostró que en Piura mucha arena y suelo seco ya se ven oscuros en la temporada
seca y quedaban descartados como "agua". Con IAPN_S1_PERMANENTE=referencia se vuelve al criterio anterior.

Eventos: 2017 (El Niño costero, feb-abr), 2023 (ciclón Yaku, mar-abr) y "vivo" (últimos 24 días).
Salidas en data/huellas/: {evento}.tif (1 = inundado) y {evento}.json (imágenes usadas).
El radar ve a través de las nubes, pero no detecta bien el agua bajo árboles o entre edificios densos:
la huella es un mínimo.

Uso: python src/huellas.py [2017 2023 vivo]
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from config import DATA
from exposicion import CAJA

CARPETA = DATA / "huellas"
RES = 0.0005                     # grados (~55 m)
# Parámetros configurables por variables de entorno (los valores por defecto reproducen las capas publicadas).
UMBRAL_AGUA = float(os.getenv("IAPN_S1_UMBRAL_DB", "-17.0"))      # dB, VV
CAIDA_DB = float(os.getenv("IAPN_S1_CAIDA_DB", "3.0"))            # caída mínima frente a la referencia seca
ALTURA_MAX, PENDIENTE_MAX, MIN_PIX = 250.0, 5.0, 5
UMBRAL_MODO = os.getenv("IAPN_S1_UMBRAL_MODO", "fijo")            # "fijo" u "otsu" (adaptativo, acotado)
COMPUESTO = os.getenv("IAPN_S1_COMPUESTO", "minimo")              # "minimo" o "p10" (percentil 10, menos ruido)
OTSU_LIMITES = (-24.0, -14.0)
PERMANENTE = os.getenv("IAPN_S1_PERMANENTE", "gsw")              # "gsw" (JRC Global Surface Water) o "referencia"
GSW_MIN = 75                                                      # % del tiempo con agua para considerarla permanente
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def referencia_seca(evento_ini: date) -> tuple[str, str]:
    """Temporada seca (1 ago - 30 nov) que termina ANTES del inicio del evento: nunca se solapan.

    Si la temporada seca del año en curso aún no tiene al menos 45 días antes del evento, se usa la del año anterior.
    """
    y = evento_ini.year if evento_ini.month >= 8 else evento_ini.year - 1
    ini, fin = date(y, 8, 1), min(date(y, 11, 30), evento_ini - timedelta(days=1))
    if (fin - ini).days < 45:
        ini, fin = date(y - 1, 8, 1), date(y - 1, 11, 30)
    return ini.isoformat(), fin.isoformat()


def eventos(hoy: date | None = None) -> dict:
    hoy = hoy or datetime.now(ZoneInfo("America/Lima")).date()
    vivo_ini = hoy - timedelta(days=24)
    return {
        "2017": {"nombre": "El Niño costero 2017", "evento": ("2017-02-01", "2017-04-30"), "ref": ("2016-08-01", "2016-11-30")},
        "2023": {"nombre": "Ciclón Yaku 2023", "evento": ("2023-03-01", "2023-04-15"), "ref": ("2022-08-01", "2022-11-30")},
        "vivo": {"nombre": "Últimos 24 días", "evento": (vivo_ini.isoformat(), hoy.isoformat()), "ref": referencia_seca(vivo_ini)},
    }


def otsu(valores: np.ndarray, bins: int = 256, limites=OTSU_LIMITES) -> float | None:
    """Umbral de Otsu sobre valores en dB (ignora NaN), acotado a `limites` para evitar umbrales absurdos.

    Devuelve None si no hay suficientes datos o si el histograma no es bimodal (umbral fuera de límites).
    """
    v = np.asarray(valores, dtype="float64")
    v = v[np.isfinite(v)]
    if v.size < 1000:
        return None
    hist, bordes = np.histogram(v, bins=bins, range=(-35, 5))
    centros = (bordes[:-1] + bordes[1:]) / 2
    p = hist / hist.sum()
    w0 = np.cumsum(p); w1 = 1 - w0
    m0 = np.cumsum(p * centros) / np.where(w0 > 0, w0, np.nan)
    mt = (p * centros).sum()
    m1 = (mt - np.cumsum(p * centros)) / np.where(w1 > 0, w1, np.nan)
    var = w0 * w1 * (m0 - m1) ** 2
    if not np.isfinite(var).any():
        return None
    u = float(centros[np.nanargmax(var)])
    return u if limites[0] <= u <= limites[1] else None


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


def agua_permanente_gsw(cat, geobox):
    """Ocurrencia de agua (0-100 %) de JRC Global Surface Water en la misma grilla; None si no se puede cargar."""
    import odc.stac
    items = cat.search(collections=["jrc-gsw"], bbox=CAJA).item_collection()
    if not len(items):
        return None
    d = odc.stac.load(items, bands=["occurrence"], geobox=geobox, chunks={"latitude": 2048, "longitude": 2048},
                      resampling="nearest")
    occ = d["occurrence"].max("time").compute().values.astype("float32")
    occ[occ > 100] = 0                                                         # 255 = sin dato
    return occ


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
    assert ev["ref"][1] < ev["evento"][0], "la referencia seca no puede solaparse con el evento"
    r = ref.median("time").compute().values
    e = (evento.quantile(0.10, "time") if COMPUESTO == "p10" else evento.min("time")).compute().values
    if z is None:
        z = dem(cat, geobox)
    lat0 = (CAJA[1] + CAJA[3]) / 2
    apto = (z < ALTURA_MAX) & (pendiente(z, lat0) < PENDIENTE_MAX)
    u_otsu = otsu(np.where(apto, e, np.nan)[::4, ::4])
    umbral = u_otsu if (UMBRAL_MODO == "otsu" and u_otsu is not None) else UMBRAL_AGUA
    criterio = "referencia seca (VV < umbral)"
    permanente = r < umbral
    if PERMANENTE == "gsw":
        try:
            occ = agua_permanente_gsw(cat, geobox)
            if occ is not None:
                permanente = occ >= GSW_MIN
                criterio = f"JRC Global Surface Water, ocurrencia >= {GSW_MIN} %"
        except Exception as error:  # noqa: BLE001
            print(f"  JRC GSW no disponible ({error}); se usa la referencia seca")
    inund = (e < umbral) & ((r - e) > CAIDA_DB) & apto & ~permanente & np.isfinite(e) & np.isfinite(r)
    inund = limpiar(inund)
    m = np.where(inund, 1, 0).astype("uint8")
    m[permanente & apto] = 2                                                   # agua permanente (referencia)
    km2 = float(inund.sum() * (RES * 110_600) * (RES * 111_320 * np.cos(np.radians(lat0))) / 1e6)
    print(f"  {len(f_ref)} imágenes de referencia, {len(f_ev)} del evento: {km2:,.1f} km² inundados")
    guardar(clave, m, geobox, {"evento": clave, "nombre": ev["nombre"], "periodo": ev["evento"], "referencia": ev["ref"],
                               "imagenes_evento": f_ev, "imagenes_referencia": f_ref, "km2": round(km2, 1),
                               "resolucion_grados": RES, "metodo": "Sentinel-1 RTC VV, detección de cambios",
                               "umbral_db": umbral, "umbral_modo": UMBRAL_MODO, "umbral_otsu_diagnostico": u_otsu,
                               "caida_db": CAIDA_DB, "compuesto_evento": COMPUESTO, "polarizacion": "VV",
                               "agua_permanente": criterio,
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
        previo = CARPETA / f"{clave}.json"
        mismo_criterio = previo.exists() and (PERMANENTE != "gsw" or "Global Surface Water" in
                                              json.load(open(previo, encoding="utf-8")).get("agua_permanente", ""))
        if clave != "vivo" and (CARPETA / f"{clave}.tif").exists() and mismo_criterio and "--forzar" not in sys.argv:
            print(f"Evento {clave}: ya calculado"); continue
        try:
            z, geobox = procesar(cat, clave, ev, z, geobox)
        except Exception as error:
            print(f"  {clave}: ERROR {error}")


if __name__ == "__main__":
    main()
