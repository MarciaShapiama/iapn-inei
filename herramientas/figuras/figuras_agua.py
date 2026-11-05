"""Figuras paso a paso: ¿de dónde sale el agua azul del mapa? (docs/6_presentacion/presentacion/figuras/agua_*.png)

Se usa una ventana pequeña del Bajo Piura (área de Copernicus EMS 10PIURA, marzo de 2017) y se repite, solo en esa
ventana, el mismo cálculo de src/huellas.py:
    1. referencia seca  = mediana de VV (Sentinel-1) de agosto a noviembre de 2016
    2. evento           = VV más bajo de febrero a abril de 2017
    3. agua nueva       = VV del evento < -17 dB  y  caída > 3 dB frente a la referencia,
                          sin agua permanente (JRC Global Surface Water >= 75 %), altura < 250 m, pendiente < 5°
Después se compara con la capa publicada (data/huellas/2017.tif), con el mapa oficial de Copernicus EMS y con la zona
inundable de JRC, y se cruza con las edificaciones de Google Open Buildings.

La descarga de Sentinel-1 (unos 60 MB) se guarda en data/validacion/ventana_bajo_piura_2017.npz; si ese archivo existe,
el script no usa la red.

Uso: python herramientas/figuras/figuras_agua.py
"""
from __future__ import annotations

import glob
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))
F = R / "docs" / "6_presentacion" / "presentacion" / "figuras"
F.mkdir(parents=True, exist_ok=True)
CACHE = R / "data" / "validacion" / "ventana_bajo_piura_2017.npz"
EMS = R / "data" / "validacion" / "ems2017"
RES = 0.0005
UMBRAL, CAIDA = -17.0, 3.0
REF, EVE = ("2016-08-01", "2016-11-30"), ("2017-02-01", "2017-04-30")
AZ, CEL, ROJO, NAR, GR = "#0b5d8f", "#9fd3f2", "#d4145a", "#e8710a", "#8a99a6"
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})


def ems_10piura():
    """Polígonos de agua y área de interés de Copernicus EMS (10PIURA, todas las fechas)."""
    import geopandas as gpd
    import pandas as pd
    agua, zona = [], []
    for z in sorted(EMS.glob("EMSR199_10PIURA_DELINEATION_*_vector.zip")):
        d = tempfile.mkdtemp()
        zipfile.ZipFile(z).extractall(d)
        c = glob.glob(d + "/**/*crisis_information_poly.shp", recursive=True)
        a = glob.glob(d + "/**/*area_of_interest.shp", recursive=True)
        if c:
            g = gpd.read_file(c[0]).to_crs(4326)
            if "interpret" in g:
                g = g[g["interpret"].astype(str).str.contains("Flood", case=False)]
            agua.append(g[["geometry"]])
        if a:
            zona.append(gpd.read_file(a[0]).to_crs(4326)[["geometry"]])
    return pd.concat(agua), pd.concat(zona)


def ventana(zona) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = zona.total_bounds
    return tuple(round(float(v), 3) for v in (x0, y0, x1, y1))


def descargar(bbox):
    """VV en dB (referencia: mediana; evento: mínimo y serie completa), DEM y agua permanente en la ventana."""
    import odc.stac
    from huellas import catalogo
    cat = catalogo()

    def vv(t0, t1):
        items = cat.search(collections=["sentinel-1-rtc"], bbox=bbox, datetime=f"{t0}/{t1}").item_collection()
        ds = odc.stac.load(items, bands=["vv"], crs="EPSG:4326", resolution=RES, bbox=bbox, groupby="solar_day",
                           resampling="average")
        v = ds["vv"].where(ds["vv"] > 0)
        v = v.rolling({d: 3 for d in v.dims if d != "time"}, center=True, min_periods=4).mean()
        return 10 * np.log10(v), ds

    ref, ds = vv(*REF)
    eve, _ = vv(*EVE)
    gb = ds.odc.geobox
    dem = odc.stac.load(cat.search(collections=["cop-dem-glo-30"], bbox=bbox).item_collection(), bands=["data"],
                        geobox=gb, resampling="bilinear")["data"].max("time").values.astype("float32")
    gsw = odc.stac.load(cat.search(collections=["jrc-gsw"], bbox=bbox).item_collection(), bands=["occurrence"],
                        geobox=gb, resampling="nearest")["occurrence"].max("time").values.astype("float32")
    gsw[gsw > 100] = 0
    t = gb.affine
    np.savez_compressed(CACHE, ref=ref.median("time").values.astype("float32"),
                        eve_min=eve.min("time").values.astype("float32"),
                        serie=eve.values.astype("float32"), serie_ref=ref.values.astype("float32"),
                        fechas=np.array([str(x)[:10] for x in eve.time.values]),
                        fechas_ref=np.array([str(x)[:10] for x in ref.time.values]),
                        dem=dem, gsw=gsw, transform=np.array([t.a, t.b, t.c, t.d, t.e, t.f]), bbox=np.array(bbox))


def pendiente(z, lat0):
    gy, gx = np.gradient(np.nan_to_num(z), RES * 110_600, RES * 111_320 * np.cos(np.radians(lat0)))
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def recorte(ruta, t, forma):
    """Lee un ráster del proyecto remuestreado a la grilla de la ventana."""
    import rasterio
    from rasterio.warp import Resampling, reproject
    dst = np.zeros(forma, dtype="float32")
    with rasterio.open(ruta) as src:
        reproject(rasterio.band(src, 1), dst, dst_transform=t, dst_crs="EPSG:4326", resampling=Resampling.nearest)
    return dst


def main() -> None:
    from affine import Affine
    from rasterio import features
    agua_ems, zona_ems = ems_10piura()
    bbox = ventana(zona_ems)
    if not CACHE.exists():
        print(f"Descargando Sentinel-1 para la ventana {bbox} ...")
        descargar(bbox)
    d = np.load(CACHE)
    t = Affine(*d["transform"])
    ref, eve, dem, gsw = d["ref"], d["eve_min"], d["dem"], d["gsw"]
    forma = ref.shape
    ext = (t.c, t.c + t.a * forma[1], t.f + t.e * forma[0], t.f)
    lat0 = (bbox[1] + bbox[3]) / 2

    regla1 = eve < UMBRAL
    regla2 = (ref - eve) > CAIDA
    permanente = gsw >= 75
    apto = (dem < 250) & (pendiente(dem, lat0) < 5)
    agua = regla1 & regla2 & apto & ~permanente & np.isfinite(eve) & np.isfinite(ref)
    publicada = recorte(R / "data" / "huellas" / "2017.tif", t, forma)
    jrc = recorte(R / "data" / "exposicion" / "peligro_rp100.tif", t, forma)
    ems = features.rasterize(((g, 1) for g in agua_ems.geometry if g is not None), out_shape=forma, transform=t,
                             fill=0, dtype="uint8").astype(bool)
    px = (RES * 111_320 * np.cos(np.radians(lat0))) * (RES * 110_600) / 1e6
    det = publicada == 1

    # ---------- 1. referencia, evento y caída ----------
    fig, ax = plt.subplots(1, 3, figsize=(12, 4.2))
    for a, img, tit, cm, lim in ((ax[0], ref, "1. Temporada seca (ago-nov 2016)\nmediana de VV", "gray", (-25, 0)),
                                 (ax[1], eve, "2. Evento (feb-abr 2017)\nVV más bajo", "gray", (-25, 0)),
                                 (ax[2], ref - eve, "3. Caída de la señal\n(seca - evento)", "magma", (0, 12))):
        im = a.imshow(img, extent=ext, cmap=cm, vmin=lim[0], vmax=lim[1])
        a.set_title(tit, fontsize=10); a.set_xticks([]); a.set_yticks([])
        fig.colorbar(im, ax=a, fraction=0.046, pad=0.02, label="dB")
    fig.suptitle("Lo que mide el radar Sentinel-1 en el Bajo Piura: oscuro = superficie lisa (agua calma)", fontsize=11)
    fig.tight_layout(); fig.savefig(F / "agua_1_radar.png", dpi=200); plt.close(fig)

    # ---------- 2. un píxel en el tiempo ----------
    serie, fechas = d["serie"], d["fechas"]
    serie_ref, fechas_ref = d["serie_ref"], d["fechas_ref"]
    caida = np.where(ems & agua, ref - eve, -np.inf)
    i, j = np.unravel_index(np.argmax(caida), caida.shape)
    fig, ax = plt.subplots(figsize=(9, 3.4))
    import pandas as pd
    fr, fe = pd.to_datetime(fechas_ref), pd.to_datetime(fechas)
    ax.plot(fr, serie_ref[:, i, j], "o-", color=GR, ms=3, label="temporada seca 2016")
    ax.plot(fe, serie[:, i, j], "o-", color=AZ, ms=3, label="febrero-abril 2017")
    ax.axhline(UMBRAL, color=ROJO, ls="--", lw=1); ax.text(fr[0], UMBRAL + 0.4, "umbral -17 dB", color=ROJO, fontsize=9)
    ax.axhline(ref[i, j], color=GR, ls=":", lw=1)
    ax.set_ylabel("VV (dB)"); ax.legend(frameon=False, fontsize=9, loc="lower left")
    lon, lat = t * (j + 0.5, i + 0.5)
    ax.set_title(f"Un píxel de 55 m en el Bajo Piura ({lat:.3f}; {lon:.3f}): cada punto es una pasada del satélite"
                 .replace(".", ","), fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(F / "agua_2_pixel.png", dpi=200); plt.close(fig)

    # ---------- 3. las reglas una por una ----------
    pasos = [(regla1, "a) VV del evento < -17 dB"), (regla1 & regla2, "b) + bajó más de 3 dB"),
             (regla1 & regla2 & ~permanente, "c) - agua permanente (JRC GSW)"), (agua, "d) - altura > 250 m y pendiente > 5°")]
    fig, ax = plt.subplots(1, 4, figsize=(13, 3.7))
    for a, (m, tit) in zip(ax, pasos):
        a.imshow(ref, extent=ext, cmap="gray", vmin=-25, vmax=0, alpha=0.55)
        a.imshow(np.where(m, 1, np.nan), extent=ext, cmap=ListedColormap([AZ]), vmin=0, vmax=1)
        a.set_title(f"{tit}\n{m.sum() * px:,.0f} km²".replace(",", " "), fontsize=9.5)
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle("Cada regla quita falsos positivos; lo que queda se pinta de azul", fontsize=11)
    fig.tight_layout(); fig.savefig(F / "agua_3_reglas.png", dpi=200); plt.close(fig)

    # ---------- 4. histograma ----------
    v = eve[apto & np.isfinite(eve)]
    fig, ax = plt.subplots(figsize=(6, 3.3))
    ax.hist(v, bins=np.arange(-30, 2, 0.5), color=GR)
    ax.hist(v[v < UMBRAL], bins=np.arange(-30, 2, 0.5), color=AZ)
    ax.axvline(UMBRAL, color=ROJO, ls="--"); ax.text(UMBRAL + 0.3, ax.get_ylim()[1] * 0.9, "-17 dB", color=ROJO)
    ax.set_xlabel("VV del evento (dB)"); ax.set_ylabel("píxeles")
    ax.set_title("Dos grupos: agua (izquierda) y suelo, cultivos, casas (derecha)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(F / "agua_4_histograma.png", dpi=200); plt.close(fig)

    # ---------- 5. radar vs. JRC vs. Copernicus ----------
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    for a, tit in ((ax[0], "Radar Sentinel-1 2017 (lo observado)"), (ax[1], "JRC: zona inundable 1 en 100 años (modelo)")):
        a.imshow(np.where(permanente, 1, np.nan), extent=ext, cmap=ListedColormap([CEL]), vmin=0, vmax=1)
        a.set_xticks([]); a.set_yticks([]); a.set_title(tit, fontsize=10)
        a.contour(ems.astype(float), levels=[0.5], colors=[ROJO], linewidths=0.8, extent=(ext[0], ext[1], ext[3], ext[2]),
                  origin="upper")
    ax[0].imshow(np.where(det, 1, np.nan), extent=ext, cmap=ListedColormap([AZ]), vmin=0, vmax=1)
    ax[1].imshow(np.where(jrc > 0, jrc, np.nan), extent=ext, cmap="Blues", vmin=0, vmax=4)
    ley = [Patch(color=CEL, label="agua permanente"), Patch(color=AZ, label="agua detectada / zona inundable"),
           Line2D([], [], color=ROJO, lw=1, label="Copernicus EMS (mapa oficial)")]
    fig.legend(handles=ley, loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(F / "agua_5_comparacion.png", dpi=200); plt.close(fig)

    # ---------- 6. cruce con edificaciones ----------
    import pandas as pd
    e = pd.read_parquet(R / "data" / "exposicion" / "viviendas.parquet")
    cx = [c for c in e.columns if c.lower() in ("lon", "longitude", "x")][0]
    cy = [c for c in e.columns if c.lower() in ("lat", "latitude", "y")][0]
    e = e[(e[cx] > ext[0]) & (e[cx] < ext[1]) & (e[cy] > ext[2]) & (e[cy] < ext[3])]
    col = np.floor((e[cx].to_numpy() - t.c) / t.a).astype(int)
    fil = np.floor((e[cy].to_numpy() - t.f) / t.e).astype(int)
    ok = (fil >= 0) & (fil < forma[0]) & (col >= 0) & (col < forma[1])
    dentro = np.zeros(len(e), bool)
    dentro[ok] = det[fil[ok], col[ok]]
    dentro_jrc = np.zeros(len(e), bool)
    dentro_jrc[ok] = jrc[fil[ok], col[ok]] > 0
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    for a, m, en, tit in ((ax[0], det, dentro, "Radar 2017 (observado)"),
                          (ax[1], jrc > 0, dentro_jrc, "JRC 1 en 100 años (escenario)")):
        a.scatter(e[cx][~en], e[cy][~en], s=0.2, color=GR, rasterized=True)
        a.imshow(np.where(m, 1, np.nan), extent=ext, cmap=ListedColormap([AZ]), vmin=0, vmax=1, alpha=0.55)
        a.scatter(e[cx][en], e[cy][en], s=0.6, color=NAR, rasterized=True)
        a.set_xlim(ext[0], ext[1]); a.set_ylim(ext[2], ext[3]); a.set_xticks([]); a.set_yticks([])
        a.set_title(f"{tit}\n{int(en.sum()):,} de {len(e):,} edificaciones con el centro dentro".replace(",", " "),
                    fontsize=10)
    fig.legend(handles=[Patch(color=AZ, alpha=0.55, label="agua / zona inundable"),
                        Patch(color=NAR, label="edificación potencialmente expuesta"),
                        Patch(color=GR, label="otra edificación (Google Open Buildings)")],
               loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(F / "agua_6_cruce.png", dpi=200); plt.close(fig)

    resumen = {"ventana": bbox, "imagenes_referencia": int(len(fechas_ref)), "imagenes_evento": int(len(fechas)),
               "km2_regla_a": round(float(regla1.sum() * px), 1), "km2_regla_b": round(float((regla1 & regla2).sum() * px), 1),
               "km2_sin_permanente": round(float((regla1 & regla2 & ~permanente).sum() * px), 1),
               "km2_final": round(float(agua.sum() * px), 1), "km2_publicada": round(float(det.sum() * px), 1),
               "km2_copernicus": round(float(ems.sum() * px), 1),
               "km2_publicada_y_copernicus": round(float((det & ems).sum() * px), 1),
               "pixel_ejemplo": {"lat": round(lat, 4), "lon": round(lon, 4), "ref_db": round(float(ref[i, j]), 1),
                                 "evento_db": round(float(eve[i, j]), 1)},
               "edificaciones_ventana": int(len(e)), "edificaciones_dentro_radar": int(dentro.sum()),
               "edificaciones_dentro_jrc_rp100": int(dentro_jrc.sum())}
    (F / "agua_resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))


if __name__ == "__main__":
    main()
