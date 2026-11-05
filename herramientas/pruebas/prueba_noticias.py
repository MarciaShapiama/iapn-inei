"""Prueba del detector con noticias reales (reunión del 4/11/2026, punto 4).

Para cada lugar con una noticia de inundación se toma un cuadrado de unos 6 km alrededor del lugar y se repite el
cálculo de src/huellas.py para la ventana "últimos 24 días", guardando lo que quita cada regla:
    a) VV del evento < -17 dB          b) + caída > 3 dB frente a la temporada seca
    c) sin agua permanente (JRC GSW)   d) sin altura > 250 m ni pendiente > 5°
Además se cuenta: pasadas de Sentinel-1 que cubren el lugar (y la fecha de la última), zona inundable de JRC 1 en 100
años en el cuadrado y lo que quedó en la capa publicada (data/huellas/vivo.tif).

Las coordenadas son el centro aproximado de cada localidad (no el punto exacto de la noticia).
Salida: docs/evidencia/prueba_noticias.json

Uso: python herramientas/pruebas/prueba_noticias.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))
SALIDA = R / "docs" / "evidencia" / "prueba_noticias.json"
MEDIO = 0.027                     # medio lado del cuadrado en grados (~3 km)
RES = 0.0005

LUGARES = [
    {"lugar": "Aguas Verdes (Puerto Perú), Zarumilla", "lat": -3.480, "lon": -80.246, "fecha": "2026-11-02",
     "noticia": "Desborde del río Zarumilla en Puerto Perú y Tomás Arizola",
     "fuente": "https://elcomercio.pe/peru/tumbes/tumbes-desborde-del-rio-zarumilla-afecta-a-puerto-peru-y-tomas-arizola-fenomeno-el-nino-fen-apuesplan-ultimas-noticia/"},
    {"lugar": "San Jacinto (río Tumbes)", "lat": -3.643, "lon": -80.448, "fecha": "2026-11-02",
     "noticia": "Desborde del río Tumbes en Vaquería; caudal sobre el umbral rojo",
     "fuente": "https://www.infobae.com/peru/2026/11/03/lluvias-en-tumbes-activan-quebradas-elevan-el-caudal-de-los-rios-y-dejan-aislados-a-agricultores-en-zonas-rurales-y-fronterizas/"},
    {"lugar": "Tumbes (ciudad)", "lat": -3.567, "lon": -80.452, "fecha": "2026-11-02",
     "noticia": "Alerta roja por el caudal del río Tumbes",
     "fuente": "https://elbuho.pe/2026/11/fenomeno-el-nino-alerta-roja-por-incremento-del-caudal-del-rio-tumbes-tras-intensas-precipitaciones/"},
    {"lugar": "Máncora", "lat": -4.106, "lon": -81.047, "fecha": "2026-11-02",
     "noticia": "Lluvia de hora y media inunda calles; se activan las quebradas Fernández y Cabo Blanco",
     "fuente": "https://andina.pe/agencia/noticia-fenomeno-nino-piura-lluvia-hora-y-media-inunda-calles-distrito-mancora-1098350.aspx"},
    {"lugar": "Chulucanas", "lat": -5.093, "lon": -80.163, "fecha": "2026-10-20",
     "noticia": "Aguacero deja calles inundadas y el mercado con unos 30 cm de agua (también 27/10 y 2/11)",
     "fuente": "https://rpp.pe/peru/piura/piura-lluvias-torrenciales-inundan-calles-y-obligan-a-cerrar-el-mercado-modelo-en-chulucanas-noticia-1713517"},
    {"lugar": "Huancabamba (río Serrán)", "lat": -5.239, "lon": -79.451, "fecha": "2026-10-30",
     "noticia": "Crecida del río Serrán (prueba anterior del equipo)", "fuente": None},
]


def km2_px(lat):
    return (RES * 111_320 * np.cos(np.radians(lat))) * (RES * 110_600) / 1e6


def recortar(ruta, t, forma):
    import rasterio
    from rasterio.warp import Resampling, reproject
    dst = np.zeros(forma, dtype="float32")
    with rasterio.open(ruta) as src:
        reproject(rasterio.band(src, 1), dst, dst_transform=t, dst_crs="EPSG:4326", resampling=Resampling.nearest)
    return dst


def probar(cat, l, ev):
    import odc.stac
    from huellas import pendiente
    bbox = (l["lon"] - MEDIO, l["lat"] - MEDIO, l["lon"] + MEDIO, l["lat"] + MEDIO)

    def vv(t0, t1):
        items = cat.search(collections=["sentinel-1-rtc"], bbox=bbox, datetime=f"{t0}/{t1}").item_collection()
        if not len(items):
            return None, None, []
        ds = odc.stac.load(items, bands=["vv"], crs="EPSG:4326", resolution=RES, bbox=bbox, groupby="solar_day",
                           resampling="average")
        v = ds["vv"].where(ds["vv"] > 0)
        v = v.rolling({d: 3 for d in v.dims if d != "time"}, center=True, min_periods=4).mean()
        return 10 * np.log10(v), ds.odc.geobox, sorted({str(i.datetime.date()) for i in items})

    ref, gb, f_ref = vv(*ev["ref"])
    eve, _, f_ev = vv(*ev["evento"])
    out = {k: l[k] for k in ("lugar", "lat", "lon", "fecha", "noticia", "fuente")}
    out["pasadas_evento"] = f_ev
    out["pasadas_despues_de_la_noticia"] = [f for f in f_ev if f >= l["fecha"]]
    if ref is None or eve is None:
        out["resultado"] = "sin imágenes"; return out
    r = ref.median("time").values
    e = eve.min("time").values
    z = odc.stac.load(cat.search(collections=["cop-dem-glo-30"], bbox=bbox).item_collection(), bands=["data"],
                      geobox=gb, resampling="bilinear")["data"].max("time").values.astype("float32")
    occ = odc.stac.load(cat.search(collections=["jrc-gsw"], bbox=bbox).item_collection(), bands=["occurrence"],
                        geobox=gb, resampling="nearest")["occurrence"].max("time").values.astype("float32")
    occ[occ > 100] = 0
    t, forma = gb.affine, r.shape
    px = km2_px(l["lat"])
    a = (e < -17) & np.isfinite(e) & np.isfinite(r)
    b = a & ((r - e) > 3)
    c = b & ~(occ >= 75)
    alto = z >= 250
    lad = pendiente(z, l["lat"]) >= 5
    d = c & ~alto & ~lad
    pub = recortar(R / "data" / "huellas" / "vivo.tif", t, forma)
    jrc = recortar(R / "data" / "exposicion" / "peligro_rp100.tif", t, forma)
    out.update({
        "altura_mediana_m": round(float(np.nanmedian(z)), 0),
        "pct_area_sobre_250m": round(float(alto.mean() * 100), 1),
        "pct_area_pendiente_mayor_5": round(float(lad.mean() * 100), 1),
        "km2_a_vv_menor_17": round(float(a.sum() * px), 2),
        "km2_b_mas_caida_3db": round(float(b.sum() * px), 2),
        "km2_c_sin_agua_permanente": round(float(c.sum() * px), 2),
        "km2_d_sin_sierra_ni_ladera": round(float(d.sum() * px), 2),
        "km2_quitado_por_altura_o_pendiente": round(float((c & (alto | lad)).sum() * px), 2),
        "km2_capa_publicada_bruta": round(float((pub == 1).sum() * px), 2),
        "km2_jrc_rp100": round(float((jrc > 0).sum() * px), 2),
        "caida_mediana_db_en_jrc": (round(float(np.nanmedian((r - e)[jrc > 0])), 1) if (jrc > 0).any() else None),
        "vv_evento_mediana_db_en_jrc": (round(float(np.nanmedian(e[jrc > 0])), 1) if (jrc > 0).any() else None),
    })
    return out


def main() -> None:
    from huellas import catalogo, eventos
    ev = eventos()["vivo"]
    cat = catalogo()
    res = {"ventana_vivo": ev["evento"], "referencia_seca": ev["ref"], "lado_cuadrado_km": round(2 * MEDIO * 111, 1),
           "lugares": []}
    for l in LUGARES:
        print(f"{l['lugar']} ...", flush=True)
        try:
            o = probar(cat, l, ev)
        except Exception as error:  # noqa: BLE001
            o = {"lugar": l["lugar"], "error": str(error)}
        res["lugares"].append(o)
        print(json.dumps(o, ensure_ascii=False), flush=True)
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
