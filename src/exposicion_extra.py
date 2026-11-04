"""Más datos de lo expuesto en Tumbes y Piura (se descargan una vez y se guardan en data/exposicion/).

    poblacion_0a4.tif     niños de 0 a 4 años (WorldPop 2026 por edad y sexo, 100 m, mismo recorte que la población)
    poblacion_65mas.tif   personas de 65 años o más
    cultivos_30m.tif      1 = cultivo según ESA WorldCover 2021 v200 (clase 40), remuestreado a ~30 m
    vias.geojson          carreteras principales (OpenStreetMap: troncales, primarias, secundarias y terciarias)
                          y puentes de esas vías
    enfen.json            último Comunicado Oficial del ENFEN (número, fecha, enlace y estado del sistema de alerta),
                          se renueva en cada corrida (va a dashboard/data/)

Uso: python src/exposicion_extra.py   (agregar --forzar para volver a descargar)
"""
from __future__ import annotations

import io
import json
import re
import sys

import numpy as np
import requests

from config import DASH_DATA
from exposicion import CAJA, CARPETA, UA

EDADES = ("https://data.worldpop.org/GIS/AgeSex_structures/Global_2015_2030/R2025A/2026/PER/v1/100m/constrained/"
          "per_{s}_{e}_2026_CN_100m_R2025A_v1.tif")
GRUPOS = {"poblacion_0a4": ["00", "01"], "poblacion_65mas": ["65", "70", "75", "80", "85", "90"]}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
ENFEN = "https://www.gob.pe/institucion/senamhi/colecciones/1308-comunicados-enfen"


def recorte(url: str):
    """Descarga el ráster de Perú y lee solo la caja de Tumbes-Piura (el servidor no admite lectura parcial)."""
    import rasterio
    from rasterio.windows import Window, from_bounds
    tmp = CARPETA / "_edad.tif"
    with requests.get(url, headers=UA, timeout=1200, stream=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
    with rasterio.open(tmp) as src:
        v = from_bounds(*CAJA, transform=src.transform).round_offsets().round_lengths()
        v = v.intersection(Window(0, 0, src.width, src.height))   # misma corrección que poblacion_100m.tif
        d = src.read(1, window=v).astype("float32")
        salida = (np.where(d < 0, 0, d), src.window_transform(v), src.crs)
    tmp.unlink()
    return salida


def edades(forzar: bool) -> None:
    import rasterio
    for nombre, grupos in GRUPOS.items():
        destino = CARPETA / f"{nombre}.tif"
        if destino.exists() and not forzar:
            continue
        total, t, crs = None, None, None
        for e in grupos:
            for s in ("f", "m"):
                d, t, crs = recorte(EDADES.format(s=s, e=e))
                total = d if total is None else total + d
        perfil = {"driver": "GTiff", "height": total.shape[0], "width": total.shape[1], "count": 1, "dtype": "float32",
                  "crs": crs, "transform": t, "nodata": 0, "compress": "deflate", "predictor": 3}
        with rasterio.open(destino, "w", **perfil) as dst:
            dst.write(total, 1)
        print(f"  {nombre}: {total.sum():,.0f} personas en la caja")
    # control: deben caer en las mismas celdas que la población total
    with rasterio.open(CARPETA / "poblacion_100m.tif") as a, rasterio.open(CARPETA / "poblacion_0a4.tif") as b:
        print(f"  mismo origen que la población total: {a.transform == b.transform} · "
              f"correlación con la población total: {np.corrcoef(a.read(1).ravel(), b.read(1).ravel())[0, 1]:.3f}")


def cultivos(forzar: bool) -> None:
    import odc.stac
    import planetary_computer as pc
    import pystac_client
    import rasterio
    from affine import Affine
    destino = CARPETA / "cultivos_30m.tif"
    if destino.exists() and not forzar:
        return
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    items = [i for i in cat.search(collections=["esa-worldcover"], bbox=CAJA).item_collection() if "2021" in i.id]
    res = 0.0003
    ds = odc.stac.load(items, bands=["map"], crs="EPSG:4326", resolution=res, bbox=CAJA, resampling="mode",
                       chunks={"latitude": 2048, "longitude": 2048})
    clase = ds["map"].max("time").compute().values
    m = (clase == 40).astype("uint8")
    t = ds.odc.geobox.affine
    with rasterio.open(destino, "w", driver="GTiff", height=m.shape[0], width=m.shape[1], count=1, dtype="uint8",
                       crs="EPSG:4326", transform=t, nodata=255, compress="deflate") as dst:
        dst.write(m, 1)
    ha = m.sum() * (res * 111_320 * np.cos(np.radians(-4.9))) * (res * 110_600) / 1e4
    print(f"  cultivos: {ha:,.0f} ha en la caja Tumbes-Piura (ESA WorldCover 2021)")


def vias(forzar: bool) -> None:
    destino = CARPETA / "vias.geojson"
    if destino.exists() and not forzar:
        return
    import time
    o, s, e, n = CAJA
    cab = {"User-Agent": "MonitorInundacionesTumbesPiura/1.0 (proyecto academico PEU-CD INEI)", "Accept": "*/*"}
    elementos, vistos = [], set()
    medio_x, medio_y = (o + e) / 2, (s + n) / 2
    for (a, b, c, d) in [(o, s, medio_x, medio_y), (medio_x, s, e, medio_y), (o, medio_y, medio_x, n), (medio_x, medio_y, e, n)]:
        q = (f'[out:json][timeout:180];way["highway"~"^(motorway|trunk|primary|secondary|tertiary)$"]({b},{a},{d},{c});'
             'out tags geom;')
        j = None
        for url in OVERPASS:
            for intento in range(2):
                try:
                    r = requests.post(url, data={"data": q}, headers=cab, timeout=300)
                    if r.status_code == 200 and r.text.lstrip().startswith("{"):
                        j = r.json(); break
                    print(f"  {url}: HTTP {r.status_code}")
                except Exception as error:
                    print(f"  {url}: {error}")
                time.sleep(15)
            if j is not None:
                break
        if j is None:
            raise RuntimeError("OpenStreetMap no respondió")
        for w in j["elements"]:
            if w["id"] not in vistos:
                vistos.add(w["id"]); elementos.append(w)
        time.sleep(5)
    feats = []
    for w in elementos:
        if "geometry" not in w:
            continue
        t = w.get("tags", {})
        feats.append({"type": "Feature", "properties": {"tipo": t.get("highway"), "nombre": t.get("name") or t.get("ref") or "",
                                                         "ref": t.get("ref", ""), "puente": t.get("bridge") in ("yes", "viaduct")},
                      "geometry": {"type": "LineString", "coordinates": [[round(p["lon"], 5), round(p["lat"], 5)] for p in w["geometry"]]}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(destino, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  vías: {len(feats)} tramos, {sum(f['properties']['puente'] for f in feats)} puentes")


def enfen() -> None:
    """Último Comunicado Oficial del ENFEN. Solo se guarda lo que se lee en el propio comunicado."""
    nav = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    html = requests.get(ENFEN, headers=nav, timeout=120).text
    enlaces = re.findall(r'/institucion/[a-z]+/informes-publicaciones/\d+-comunicado-oficial-enfen-n-(\d+)-(\d{4})', html)
    if not enlaces:
        raise RuntimeError("no se encontró la lista de comunicados")
    num, anio = max(enlaces, key=lambda x: (int(x[1]), int(x[0])))
    ruta = re.search(rf'/institucion/[a-z]+/informes-publicaciones/\d+-comunicado-oficial-enfen-n-{num}-{anio}', html).group(0)
    pagina = requests.get("https://www.gob.pe" + ruta, headers=nav, timeout=120).text
    pdf = re.search(r'https://cdn\.www\.gob\.pe/uploads/document/file/[^"?]+\.pdf', pagina)
    salida = {"numero": f"{int(num)}-{anio}", "enlace": "https://www.gob.pe" + ruta, "pdf": pdf.group(0) if pdf else None,
              "estado": None, "fecha": None}
    if pdf:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(requests.get(pdf.group(0), headers=nav, timeout=180).content)) as p:
            texto = " ".join((pg.extract_text() or "") for pg in p.pages[:2])
        texto = re.sub(r"\s+", " ", texto)
        enc = re.search(r"COMUNICADO OFICIAL ENFEN N°\s*\d+\s*-\s*\d{4}\s+(\d{1,2}(?: de)? [a-záéíóú]+(?: de)? \d{4})", texto, flags=re.I)
        if enc:
            salida["fecha"] = enc.group(1)
        est = re.search(r"(Alerta de (?:El Niño|La Niña) Coster[oa]|Vigilancia de (?:El Niño|La Niña) Coster[oa]|No activo)",
                        texto[:900], flags=re.I)
        if est:
            salida["estado"] = est.group(1)
        tit = re.search(r"Coster[oa]\s*\d?\s+([A-ZÁÉÍÓÚÑ0-9 ,.\-]{20,160}?)\s+[A-Z][a-záéíóú]", texto)
        if tit:
            t = tit.group(1).strip().capitalize()
            salida["titular"] = re.sub(r"\bniño\b", "Niño", re.sub(r"\bniña\b", "Niña", t))
        mag = re.search(r"mantendría una magnitud ([a-záéíóú]+)\d?\s+hasta ([a-záéíóú]+ de \d{4})", texto)
        if mag:
            salida["magnitud_esperada"] = f"{mag.group(1)} hasta {mag.group(2)}"
        salida["extracto"] = texto[:600]
    json.dump(salida, open(DASH_DATA / "enfen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  ENFEN: comunicado {salida['numero']} · {salida['fecha']} · estado: {salida['estado']} · "
          f"{salida.get('titular')} · magnitud: {salida.get('magnitud_esperada')}")


def padron_minedu() -> None:
    """Busca el padrón de instituciones educativas (MINEDU) en la Plataforma Nacional de Datos Abiertos."""
    nav = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    pag = requests.get("https://www.datosabiertos.gob.pe/dataset/padr%C3%B3n-de-instituciones-educativas", headers=nav, timeout=120).text
    archivos = sorted(set(re.findall(r'https?://[^"\']+\.(?:csv|zip|xlsx|xls)', pag)))
    print(f"  padrón MINEDU, archivos en la página: {archivos[:8]}")
    print("  título:", re.findall(r"<h1[^>]*>([^<]+)", pag)[:2], "| fecha:", re.findall(r"(\d{2}/\d{2}/\d{4})", pag)[:3])


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    forzar = "--forzar" in sys.argv
    if "--solo-enfen" in sys.argv:          # corrida diaria: solo el comunicado del ENFEN
        try:
            enfen()
        except Exception as error:
            print(f"  ERROR {error}")
        raise SystemExit(0)
    for paso in (enfen, padron_minedu, lambda: edades(forzar), lambda: cultivos(forzar), lambda: vias(forzar)):
        try:
            paso()
        except Exception as error:
            print(f"  ERROR {error}")
