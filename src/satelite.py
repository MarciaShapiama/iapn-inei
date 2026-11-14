"""Fotos satelitales antes y después (Sentinel-2 L2A, 10 m) de las zonas más golpeadas de Tumbes y Piura.

Basado en el comparador de Maykol Ramírez (FENOMENO-NI-O-PI): escena menos nubosa, realce de color e índice
de agua NDWI. Cambios: las fechas son las de los eventos (2017, 2023 y lo más reciente) y la nubosidad se mide
DENTRO de cada zona con la capa de clasificación de escena (SCL), no en toda la escena.

Para cada zona y periodo se elige la escena con menos nubes y sombras dentro de la caja (y casi sin bordes
vacíos); se guarda en color real y en agua (NDWI = (B03 − B08) / (B03 + B08)).

Salidas: dashboard/data/sat/{zona}_{periodo}_{rgb|agua}.jpg y dashboard/data/sat/satelite.json
Uso: python src/satelite.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from config import DASH_DATA

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
CARPETA = DASH_DATA / "sat"
LADO = 1400                      # píxeles de la imagen final
NUBE_SCL = {0, 1, 3, 8, 9, 10}   # sin dato, saturado, sombra de nube, nube media, nube alta, cirro
VERSION = 3                      # al cambiar la forma de elegir o dibujar las fotos, se vuelven a generar todas
NUBES_MAX_HOY = 0.20             # si la mejor foto reciente tiene más nubes que esto, se busca en un periodo más largo

ZONAS = {
    "bajo_piura": {"nombre": "Piura, Castilla y Bajo Piura", "nota": "Ciudad de Piura y valle bajo (Catacaos, Cura Mori)",
                   "caja": (-80.76, -5.40, -80.52, -5.14)},
    "tumbes": {"nombre": "Tumbes", "nota": "Ciudad de Tumbes y valle bajo del río Tumbes",
               "caja": (-80.58, -3.76, -80.36, -3.52)},
    "sechura": {"nombre": "Desierto de Sechura", "nota": "Depresión donde se forma la laguna La Niña",
                "caja": (-80.62, -6.05, -80.22, -5.65)},
}


def periodos() -> dict:
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    return {
        "antes_2017": ("Antes de 2017 (temporada seca 2016)", "2016-09-01", "2016-12-31"),
        "despues_2017": ("Después de las inundaciones de 2017", "2017-03-25", "2017-05-15"),
        "antes_2023": ("Antes de 2023 (temporada seca 2022)", "2022-09-01", "2022-12-31"),
        "despues_2023": ("Después del ciclón Yaku 2023", "2023-03-10", "2023-05-10"),
        "hoy": ("Lo más reciente (últimos 45 días)", (hoy - timedelta(days=45)).isoformat(), hoy.isoformat()),
    }


def catalogo():
    import planetary_computer as pc
    import pystac_client
    return pystac_client.Client.open(STAC, modifier=pc.sign_inplace)


def por_dia(items) -> list[list]:
    """Agrupa las escenas por día de pasada. Una zona puede caer en dos teselas de Sentinel-2: si se usa una sola,
    la parte que cae en la otra queda sin dato (una franja negra). Las teselas del mismo día se unen en un mosaico."""
    g: dict = {}
    for it in items:
        g.setdefault(it.datetime.date(), []).append(it)
    return list(g.values())


def nubosidad(grupo, caja) -> float:
    """Fracción de la caja con nubes, sombras o sin dato, según la capa SCL (60 m).
    «Sin dato» se comprueba también en la banda roja: fuera de la franja que barrió el satélite la imagen viene vacía
    (cero o no numérico) y la capa SCL no siempre lo marca."""
    import odc.stac
    ds = odc.stac.load(grupo, bands=["SCL", "B04"], crs="EPSG:4326", resolution=0.0006, bbox=caja, groupby="solar_day")
    scl = ds["SCL"].isel(time=0).values.astype("float32")
    b04 = ds["B04"].isel(time=0).values.astype("float32")
    vacio = ~np.isfinite(scl) | ~np.isfinite(b04) | (b04 <= 0)
    return float((np.isin(scl, list(NUBE_SCL)) | vacio).mean())


def mejor_escena(cat, caja, t0, t1):
    items = cat.search(collections=["sentinel-2-l2a"], bbox=caja, datetime=f"{t0}/{t1}",
                       query={"eo:cloud_cover": {"lt": 70}}).item_collection()
    nube_media = lambda g: sum(i.properties.get("eo:cloud_cover", 100) for i in g) / len(g)   # noqa: E731
    candidatos = sorted(por_dia(items), key=nube_media)[:12]
    mejor = None
    for g in candidatos:
        try:
            f = nubosidad(g, caja)
        except Exception as error:
            print(f"    {g[0].id}: {error}"); continue
        if mejor is None or f < mejor[1]:
            mejor = (g, f)
        if f < 0.02:
            break
    return mejor


def realce(rgb: np.ndarray, despejado: np.ndarray | None = None) -> np.ndarray:
    """Estiramiento por percentiles (2-98 %) común a las tres bandas + gamma, para que se lean cultivos, agua y ciudad.
    Los percentiles se calculan solo con los píxeles despejados: si entran las nubes (muy brillantes), el suelo sale
    oscuro y la foto no se puede comparar con la de la temporada seca."""
    ok = np.isfinite(rgb).all(axis=-1) & (rgb.sum(axis=-1) > 0)
    if despejado is not None and (ok & despejado).mean() > 0.05:
        ok &= despejado
    v = rgb[ok]
    if v.size == 0:
        return np.zeros(rgb.shape, dtype="uint8")
    lo, hi = np.percentile(v, 2), np.percentile(v, 98)
    x = np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1) ** (1 / 1.35)
    gris = x.mean(axis=-1, keepdims=True)
    x = np.clip(gris + 1.25 * (x - gris), 0, 1)                   # un poco más de saturación
    return (x * 255).astype("uint8")


def agua(b03: np.ndarray, b08: np.ndarray) -> np.ndarray:
    """NDWI en colores: azul intenso = agua, celeste = suelo húmedo, beige = seco, verde = vegetación."""
    nd = (b03 - b08) / np.maximum(b03 + b08, 1e-6)
    paleta = [(-1.0, (46, 110, 50)), (-0.35, (120, 160, 80)), (-0.15, (222, 206, 170)), (0.0, (180, 215, 235)),
              (0.15, (60, 140, 215)), (0.35, (10, 60, 160)), (1.0, (5, 30, 110))]
    out = np.zeros(nd.shape + (3,), dtype="float32")
    xs = [p[0] for p in paleta]
    for c in range(3):
        out[..., c] = np.interp(nd, xs, [p[1][c] for p in paleta])
    out[~np.isfinite(nd)] = 0
    return out.astype("uint8"), float(np.nanmean(nd > 0.1))


def guardar(arr: np.ndarray, ruta) -> None:
    from PIL import Image
    Image.fromarray(arr).save(ruta, quality=86, optimize=True, progressive=True)


def main() -> None:
    import odc.stac
    CARPETA.mkdir(parents=True, exist_ok=True)
    cat = catalogo()
    previo = json.load(open(CARPETA / "satelite.json", encoding="utf-8")) if (CARPETA / "satelite.json").exists() else {}
    salida = {"generado": datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M"), "zonas": []}
    for zid, z in ZONAS.items():
        anterior = {e["periodo"]: e for e in next((x["escenas"] for x in previo.get("zonas", []) if x["id"] == zid), [])}
        registro = {"id": zid, "nombre": z["nombre"], "nota": z["nota"], "caja": z["caja"], "escenas": []}
        for pid, (etiqueta, t0, t1) in periodos().items():
            if pid != "hoy" and pid in anterior and anterior[pid].get("version") == VERSION and (CARPETA / f"{zid}_{pid}_rgb.jpg").exists():
                registro["escenas"].append(anterior[pid]); continue          # los eventos pasados no cambian
            print(f"{zid} · {pid}: buscando escenas {t0} a {t1}")
            m = mejor_escena(cat, z["caja"], t0, t1)
            if pid == "hoy" and (m is None or m[1] > NUBES_MAX_HOY):
                t90 = (datetime.fromisoformat(t1) - timedelta(days=90)).date().isoformat()
                print(f"   lo mejor de 45 días tiene muchas nubes; se busca desde {t90}")
                m90 = mejor_escena(cat, z["caja"], t90, t1)
                if m90 is not None and (m is None or m90[1] < m[1]):
                    m, etiqueta = m90, "Lo más reciente con menos nubes (últimos 90 días)"
            if m is None:
                print("   sin escenas"); continue
            grupo, nube = m
            it = grupo[0]
            res = (z["caja"][2] - z["caja"][0]) / LADO
            ds = odc.stac.load(grupo, bands=["B04", "B03", "B02", "B08", "SCL"], crs="EPSG:4326", resolution=res,
                               bbox=z["caja"], resampling={"SCL": "nearest", "*": "bilinear"},
                               groupby="solar_day").isel(time=0)
            b = {k: ds[k].values.astype("float32") for k in ["B04", "B03", "B02", "B08"]}
            scl = ds["SCL"].values.astype("float32")
            despejado = np.isfinite(scl) & ~np.isin(scl, list(NUBE_SCL))
            guardar(realce(np.dstack([b["B04"], b["B03"], b["B02"]]), despejado), CARPETA / f"{zid}_{pid}_rgb.jpg")
            img_agua, frac_agua = agua(b["B03"], b["B08"])
            guardar(img_agua, CARPETA / f"{zid}_{pid}_agua.jpg")
            registro["escenas"].append({"periodo": pid, "etiqueta": etiqueta, "fecha": str(it.datetime.date()),
                                        "nubes_en_zona_pct": round(100 * nube, 1), "agua_pct": round(100 * frac_agua, 1),
                                        "escena": " + ".join(i.id for i in grupo), "version": VERSION})
            print(f"   {it.datetime.date()} · nubes en la zona {100 * nube:.1f} % · agua {100 * frac_agua:.1f} %")
        salida["zonas"].append(registro)
    json.dump(salida, open(CARPETA / "satelite.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
