"""Lo expuesto en Tumbes y Piura (se descarga una vez y se guarda en data/exposicion/).

    poblacion_100m.tif   WorldPop 2026, 100 m, restringida a zonas con edificaciones (recorte Tumbes-Piura)
    viviendas.parquet    centro de cada edificación de Google Open Buildings v3 (confianza ≥ 0,75)
    salud.csv            establecimientos de salud activos (RENIPRESS, SUSALUD): públicos y clínicas privadas con internamiento
    colegios.csv         locales educativos: padrón ESCALE (MINEDU) si se puede descargar; si no, OpenStreetMap
    distritos.geojson    los 78 distritos de Tumbes y Piura (límites oficiales del INEI, con UBIGEO)
    peligro_rp{N}.tif    profundidad de inundación de ríos con periodo de retorno N años (JRC CEMS-GloFAS v2, 90 m)

Método de viviendas y población tomado del repositorio del curso (alexanderquispe/incendios-peru).

Uso: python src/exposicion.py   (agregar --forzar para volver a descargar)
"""
from __future__ import annotations

import io
import json
import sys

import numpy as np
import pandas as pd
import requests

from config import DATA

CARPETA = DATA / "exposicion"
CAJA = (-81.40, -6.40, -79.15, -3.35)            # oeste, sur, este, norte: Tumbes + Piura
DEPARTAMENTOS = ["TUMBES", "PIURA"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}

WORLDPOP = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2026/PER/v1/100m/constrained/"
            "per_pop_2026_CN_100m_R2025A_v1.tif")
VIDA = "https://data.source.coop/vida/google-microsoft-open-buildings/geoparquet/by_country_s2/country_iso=PER/{}.parquet"
VIDA_CELDAS = ["10394307939971104768", "10466365534009032704", "10502394331027996672"]
RENIPRESS = "https://www.datosabiertos.gob.pe/sites/default/files/RENIPRESS_30-09-2026.csv"
# Límites distritales oficiales del INEI: servicio WFS de su Infraestructura de Datos Espaciales (https://ide.inei.gob.pe/,
# capa «Distrito», ig_distrito). La capa nacional tiene 1 890 distritos; se piden solo los de Piura (20) y Tumbes (24).
INEI_WFS = "https://geoespacial.inei.gob.pe/geoserver/Interoperabilidad/ows"
INEI_CAPA = "Interoperabilidad:ig_distrito"
INEI_FILTRO = "ccdd IN ('20','24')"
OVERPASS = "https://overpass-api.de/api/interpreter"


def bajar(url: str, timeout: int = 600) -> bytes:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.content


def poblacion(forzar: bool) -> None:
    import rasterio
    from rasterio.windows import from_bounds
    destino = CARPETA / "poblacion_100m.tif"
    if destino.exists() and not forzar:
        return
    tmp = CARPETA / "_worldpop.tif"
    tmp.write_bytes(bajar(WORLDPOP, 1200))
    from rasterio.windows import Window
    with rasterio.open(tmp) as src:
        # La caja sale del borde oeste del archivo de Perú (-81,33°). Sin recortar la ventana al ráster, rasterio
        # lee solo la parte que existe pero window_transform() conserva el origen pedido (-81,40°): la población
        # quedaba desplazada ~7,9 km al oeste (corregido 2026-11-04; ver docs/1_datos/1.1_AUDITORIA_TECNICA_Y_DATOS.md).
        ventana = from_bounds(*CAJA, transform=src.transform).round_offsets().round_lengths()
        ventana = ventana.intersection(Window(0, 0, src.width, src.height))
        datos = src.read(1, window=ventana)
        datos = np.where(datos < 0, 0, datos).astype("float32")
        perfil = src.profile | {"height": datos.shape[0], "width": datos.shape[1], "nodata": 0,
                                "transform": src.window_transform(ventana), "compress": "deflate", "predictor": 3}
    with rasterio.open(destino, "w", **perfil) as dst:
        dst.write(datos, 1)
    tmp.unlink()
    print(f"  población: {datos.sum():,.0f} personas en la caja Tumbes-Piura")


def viviendas(forzar: bool) -> None:
    import duckdb
    destino = CARPETA / "viviendas.parquet"
    if destino.exists() and not forzar:
        return
    o, s, e, n = CAJA
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar=false;")
    archivos = [VIDA.format(c) for c in VIDA_CELDAS]
    df = con.execute(f"""
        SELECT (bbox.xmin + bbox.xmax) / 2 AS lon, (bbox.ymin + bbox.ymax) / 2 AS lat, area_in_meters AS area_m2
        FROM read_parquet({archivos})
        WHERE bbox.xmax >= {o} AND bbox.xmin <= {e} AND bbox.ymax >= {s} AND bbox.ymin <= {n}
          AND bf_source = 'google' AND confidence >= 0.75""").df()
    df.astype("float32").to_parquet(destino, index=False)
    print(f"  edificaciones: {len(df):,}")


PRIVADOS = {"PRIVADO", "OTRO"}


def salud(forzar: bool) -> None:
    destino = CARPETA / "salud.csv"
    if destino.exists() and not forzar:
        return
    r = pd.read_csv(io.BytesIO(bajar(RENIPRESS)), sep=";", encoding="utf-8-sig", dtype=str)
    r = r[r["DEPARTAMENTO"].str.upper().isin(DEPARTAMENTOS) & (r["ESTADO"] == "ACTIVO")].copy()
    r["lat"] = pd.to_numeric(r["NORTE"], errors="coerce")
    r["lon"] = pd.to_numeric(r["ESTE"], errors="coerce")
    r = r[r["lat"].between(CAJA[1], CAJA[3]) & r["lon"].between(CAJA[0], CAJA[2])]
    cat = r["CATEGORIA"].fillna("")
    r["tipo"] = np.select([cat.str.match(r"^(II|III)-"), cat.str.match(r"^I-[34]"), cat.str.match(r"^I-[12]")],
                          ["Hospital / clínica", "Centro de salud", "Posta de salud"], "Otro")
    r = r[r["tipo"] != "Otro"]
    # Solo servicios que atienden una emergencia: todos los públicos (gobierno regional, MINSA, EsSalud, sanidades,
    # municipales) y, de los privados, los que tienen internamiento (categorías II y III). Quedan fuera los consultorios
    # y centros privados de atención ambulatoria (dentales, ópticos, estéticos), que el registro también incluye.
    r = r[~r["INSTITUCION"].fillna("").str.upper().isin(PRIVADOS) | cat.loc[r.index].str.match(r"^(II|III)-")]
    r = r.rename(columns={"NOMBRE": "nombre", "CATEGORIA": "categoria", "INSTITUCION": "institucion",
                          "PROVINCIA": "provincia", "DISTRITO": "distrito", "DEPARTAMENTO": "departamento"})
    r[["nombre", "tipo", "categoria", "institucion", "departamento", "provincia", "distrito", "lat", "lon"]].to_csv(
        destino, index=False)
    print(f"  salud: {len(r)} establecimientos ({r['tipo'].value_counts().to_dict()})")


def colegios(forzar: bool) -> None:
    destino = CARPETA / "colegios.csv"
    if destino.exists() and not forzar:
        return
    # ESCALE suele bloquear descargas automáticas; si el equipo sube el padrón a data/exposicion/padron_escale.csv
    # (columnas CODLOCAL, CEN_EDU, NLAT_IE, NLONG_IE, D_NIV_MOD, TALUMNO, D_DPTO), se usa ese.
    padron = CARPETA / "padron_escale.csv"
    if padron.exists():
        try:
            p = pd.read_csv(padron, dtype=str, encoding="utf-8")
        except UnicodeDecodeError:
            p = pd.read_csv(padron, dtype=str, encoding="latin1")
        p = p[p["D_DPTO"].str.upper().isin(DEPARTAMENTOS)].copy()
        p["lat"] = pd.to_numeric(p["NLAT_IE"], errors="coerce")
        p["lon"] = pd.to_numeric(p["NLONG_IE"], errors="coerce")
        p["alumnos"] = pd.to_numeric(p.get("TALUMNO"), errors="coerce")
        # El padrón de servicios no trae alumnos: se toman del Censo Educativo 2025 (ESCALE, archivo 00_Padron,
        # campo TALUM), guardado en data/exposicion/matricula_escale_2025.csv. Se suma por código modular
        # (incluye anexos) y se asigna una sola vez por código modular para no duplicar.
        mat = CARPETA / "matricula_escale_2025.csv"
        if mat.exists():
            m = pd.read_csv(mat, dtype={"COD_MOD": str, "ANEXO": str, "CODLOCAL": str})
            m["COD_MOD"] = m["COD_MOD"].str.zfill(7)
            m = m.groupby("COD_MOD")["TALUM"].sum()
            cod = p["COD_MOD"].astype(str).str.zfill(7)
            p["alumnos"] = cod.map(m).where(~cod.duplicated())
        # Un local escolar (CODLOCAL) puede tener varios servicios (inicial, primaria, secundaria) en el mismo
        # edificio: se cuenta una vez por local para no contar el mismo edificio varias veces.
        g = p.groupby("CODLOCAL")
        out = pd.DataFrame({
            "nombre": g["CEN_EDU"].first().str.strip().str.title().where(~g["CEN_EDU"].first().str.strip().str.fullmatch(r"\d+"),
                                                                       "I.E. N° " + g["CEN_EDU"].first().str.strip()),
            "nivel": g["D_NIV_MOD"].agg(lambda x: " · ".join(sorted(set(x.dropna())))),
            "servicios": g.size(),
            "alumnos": g["alumnos"].sum(min_count=1),
            "distrito": g["D_DIST"].first().str.title() if "D_DIST" in p else None,
            "lat": g["lat"].first(), "lon": g["lon"].first(),
            "fuente": "ESCALE (MINEDU): padrón de servicios educativos, corte 30-10-2026; alumnos del Censo Educativo 2025"}).reset_index(drop=True)
    else:
        o, s, e, n = CAJA
        q = (f'[out:json][timeout:300];(nwr["amenity"~"^(school|kindergarten|college)$"]({s},{o},{n},{e}););out center tags;')
        j = None
        for servidor in (OVERPASS, "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"):
            try:
                r = requests.post(servidor, data={"data": q}, headers=UA, timeout=400)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    j = r.json(); break
                print(f"  {servidor}: HTTP {r.status_code} {r.text[:100]!r}")
            except Exception as error:
                print(f"  {servidor}: {error}")
        if j is None:
            raise RuntimeError("OpenStreetMap no respondió")
        filas = []
        for el in j["elements"]:
            c = el.get("center", el)
            t = el.get("tags", {})
            filas.append({"nombre": t.get("name", "Local educativo sin nombre"), "nivel": t.get("isced:level") or t.get("amenity"),
                          "alumnos": None, "lat": c.get("lat"), "lon": c.get("lon"), "fuente": "OpenStreetMap"})
        out = pd.DataFrame(filas)
    out = out.dropna(subset=["lat", "lon"])
    out.to_csv(destino, index=False)
    print(f"  colegios: {len(out)} ({out['fuente'].iloc[0] if len(out) else '-'})")


def distritos(forzar: bool) -> None:
    """Los 78 distritos oficiales de Tumbes y Piura (INEI), con UBIGEO y nombres con tildes.

    Antes se usaba GADM 4.1, que tiene 76: no separa Veintiséis de Octubre (200115) de Piura ni Canoas de Punta Sal
    (240203) de Zorritos. Los nombres con tildes salen de data/exposicion/nombres_distritos.csv (nombre oficial del INEI
    en mayúsculas y su escritura con tildes; la columna tilde_agregada marca los 9 que se corrigieron).
    """
    import hashlib
    from datetime import datetime, timezone
    destino = CARPETA / "distritos.geojson"
    if destino.exists() and not forzar and '"ubigeo"' in destino.read_text(encoding="utf-8"):
        return
    r = requests.get(INEI_WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": INEI_CAPA,
                                       "outputFormat": "application/json", "CQL_FILTER": INEI_FILTRO}, headers=UA, timeout=600)
    r.raise_for_status()
    g = r.json()
    nombres = pd.read_csv(CARPETA / "nombres_distritos.csv", dtype=str).set_index("ubigeo")
    recibidos = {f["properties"]["ubigeo"] for f in g["features"]}
    if recibidos != set(nombres.index):
        raise RuntimeError(f"El INEI devolvió otros distritos: faltan {sorted(set(nombres.index) - recibidos)}, "
                           f"sobran {sorted(recibidos - set(nombres.index))}")
    from shapely.geometry import MultiPolygon, mapping, shape
    from shapely.geometry.polygon import orient

    def horario(geom):
        """Anillo exterior en sentido horario: así lo espera d3-geo (los mapas SVG del tablero). El INEI los entrega en
        sentido antihorario y d3 dibuja entonces «todo el mundo menos el distrito». Leaflet y deck.gl no dependen de esto."""
        if geom.geom_type == "Polygon":
            return orient(geom, sign=-1.0)
        return MultiPolygon([orient(p, sign=-1.0) for p in geom.geoms])
    feats = []
    for f in sorted(g["features"], key=lambda f: f["properties"]["ubigeo"]):
        ub = f["properties"]["ubigeo"]
        n = nombres.loc[ub]
        if n["nombre_inei"] != f["properties"]["nombdist"]:
            raise RuntimeError(f"{ub}: el INEI lo llama {f['properties']['nombdist']}, la tabla de nombres {n['nombre_inei']}")
        feats.append({"type": "Feature", "geometry": mapping(horario(shape(f["geometry"]).simplify(0.0015))),
                      "properties": {"departamento": n["departamento"], "provincia": n["provincia"],
                                     "distrito": n["distrito"], "ubigeo": ub}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(destino, "w", encoding="utf-8"), ensure_ascii=False)
    q = g["features"][0]["properties"]
    proc = {"fuente": "INEI, Infraestructura de Datos Espaciales, capa «Distrito» (ig_distrito)",
            "portal": "https://ide.inei.gob.pe/", "servicio": INEI_WFS, "capa": INEI_CAPA, "filtro": INEI_FILTRO,
            "campo_fuente_del_inei": q.get("fuente"), "fecha_registro_del_inei": q.get("fec_reg"),
            "descargado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sha256_respuesta": hashlib.sha256(r.content).hexdigest(), "distritos": len(feats),
            "simplificacion_grados": 0.0015,
            "licencia": "El portal del INEI no declara una licencia; uso con cita a la fuente (ver LEEME)."}
    (CARPETA / "distritos_procedencia.json").write_text(json.dumps(proc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  distritos: {len(feats)} (INEI)")

JRC = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/"


def peligro(forzar: bool, periodos=(10, 100)) -> None:
    """Mapa de peligro de inundación del JRC (profundidad en m), recortado a Tumbes-Piura."""
    import rasterio
    from rasterio.merge import merge
    from shapely.geometry import box, shape
    if all((CARPETA / f"peligro_rp{rp}.tif").exists() for rp in periodos) and not forzar:
        return
    ext = requests.get(JRC + "tile_extents.geojson", headers=UA, timeout=120).json()
    caja = box(*CAJA)
    teselas = [f["properties"] for f in ext["features"] if shape(f["geometry"]).intersects(caja)]
    print(f"  JRC: {len(teselas)} teselas: {teselas[:3]}")
    for rp in periodos:
        rutas = []
        for props in teselas:
            for valor in (f"ID{props.get('id')}_{props.get('name')}", props.get("name"), f"ID{props.get('id')}"):
                url = f"{JRC}RP{rp}/{valor}_RP{rp}_depth.tif"
                r = requests.get(url, headers=UA, timeout=900)
                if r.status_code == 200 and r.content[:2] in (b"II", b"MM"):
                    ruta = CARPETA / f"_jrc_{valor}_{rp}.tif"; ruta.write_bytes(r.content); rutas.append(ruta)
                    print(f"  JRC RP{rp}: {valor} ({len(r.content) // 1_000_000} MB)")
                    break
                print(f"  JRC RP{rp}: {url} -> HTTP {r.status_code}")
        if not rutas:
            print(f"  JRC RP{rp}: no se encontraron teselas"); continue
        fuentes = [rasterio.open(x) for x in rutas]
        datos, t = merge(fuentes, bounds=CAJA, nodata=0)
        perfil = fuentes[0].profile | {"height": datos.shape[1], "width": datos.shape[2], "transform": t, "nodata": 0,
                                       "compress": "deflate", "dtype": "float32", "count": 1}
        with rasterio.open(CARPETA / f"peligro_rp{rp}.tif", "w", **perfil) as dst:
            dst.write(np.nan_to_num(datos[0]).clip(0, 50).astype("float32"), 1)
        for f in fuentes:
            f.close()
        for x in rutas:
            x.unlink()
        print(f"  JRC RP{rp}: {(datos[0] > 0).sum():,} píxeles con peligro")


if __name__ == "__main__":
    CARPETA.mkdir(parents=True, exist_ok=True)
    forzar = "--forzar" in sys.argv
    for paso in (distritos, salud, colegios, poblacion, viviendas, peligro):
        try:
            paso(forzar)
        except Exception as error:  # una fuente caída no detiene las demás
            print(f"  {paso.__name__}: ERROR {error}")
