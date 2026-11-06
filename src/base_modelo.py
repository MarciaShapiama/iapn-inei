"""Base distrito-semana para predecir emergencias por inundación en Tumbes y Piura.

Cada fila = un distrito en una semana (lunes a domingo). Columnas:
    etiqueta     emergencia_sem       1 si DesInventar (fuente INDECI) registra inundación, lluvias, desborde o
                                      avenida en el distrito esa semana
                 emergencia_1a4       1 si la hay en alguna de las 4 semanas SIGUIENTES (lo que se quiere predecir)
    lluvia       lluvia_7d, lluvia_30d, lluvia_90d (mm) y sus anomalías frente al promedio 2001-2020 de esa semana
                 NASA POWER (precipitación corregida, satélite + reanálisis), punto en el centro del distrito
    ríos         caudal semanal del río más cercano (GloFAS v4 vía Open-Meteo) y su razón frente a la mediana
    mar          Niño 1+2 semanal (NOAA CPC)
    exposición   % del distrito en zona inundable 1 en 10 y 1 en 100 años, viviendas y personas expuestas (fijo)
    historia     emergencias del distrito en los 5 años anteriores (memoria del lugar)

Nota de honestidad: las variables de cada semana usan solo información disponible hasta esa semana.

Salidas: data/modelo/base_distrito_semana.csv (+ emergencias_desinventar.csv, lluvia_distritos.csv)
Uso: python src/base_modelo.py
"""
from __future__ import annotations

import io
import json
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pandas as pd
import requests
from shapely.geometry import shape

from config import DASH_DATA, DATA
from descargar_zonas import RIOS

CARPETA = DATA / "modelo"
DESINVENTAR = "https://www.desinventar.net/DesInventar/download/DI_export_per.zip"
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
DEPARTAMENTOS = {"20": "PIURA", "24": "TUMBES"}
EVENTOS = ["inundaci", "lluvia", "desborde", "avenida", "aluvi", "huaico", "marejada", "tormenta"]
INICIO = "2001-01-01"
UA = {"User-Agent": "Monitor El Nino Costero (PEU-CD INEI)"}


def normal(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(ch for ch in x if ch.isalnum())


def emergencias() -> pd.DataFrame:
    ruta = CARPETA / "emergencias_desinventar.csv"
    z = zipfile.ZipFile(io.BytesIO(requests.get(DESINVENTAR, headers=UA, timeout=600).content))
    xml = z.open([n for n in z.namelist() if n.endswith(".xml")][0])
    filas, campos = [], ["serial", "level2", "name0", "name1", "name2", "evento", "fechano", "fechames", "fechadia",
                         "muertos", "afectados", "damnificados", "vivdest", "vivafec", "nescuelas", "nhospitales", "fuentes"]
    for _, el in ET.iterparse(xml, events=("end",)):
        if el.tag != "TR":
            continue
        d = {c: (el.findtext(c) or "").strip() for c in campos}
        el.clear()
        if d["level2"][:2] not in DEPARTAMENTOS or not d["fechano"]:
            continue
        filas.append(d)
    t = pd.DataFrame(filas)
    print(f"  DesInventar Tumbes y Piura: {len(t)} registros, eventos: {t['evento'].value_counts().head(12).to_dict()}")
    t["tipo_inundacion"] = t["evento"].str.lower().apply(lambda e: any(k in e for k in EVENTOS))
    for c in ["fechano", "fechames", "fechadia"]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["fechadia"] = t["fechadia"].fillna(15).clip(1, 28).where(t["fechadia"] > 0, 15)
    t["fechames"] = t["fechames"].where(t["fechames"].between(1, 12))
    t = t.dropna(subset=["fechames"])
    t["fecha"] = pd.to_datetime(dict(year=t["fechano"], month=t["fechames"], day=t["fechadia"]), errors="coerce")
    for c in ["muertos", "afectados", "damnificados", "vivdest", "vivafec", "nescuelas", "nhospitales"]:
        t[c] = pd.to_numeric(t[c], errors="coerce").fillna(0)
    t.to_csv(ruta, index=False)
    print(f"  años: {int(t['fechano'].min())}-{int(t['fechano'].max())}; por año (inundación y lluvias): "
          f"{t[t['tipo_inundacion']].groupby('fechano').size().tail(15).to_dict()}")
    return t


def distritos() -> pd.DataFrame:
    """Los 78 distritos de Tumbes y Piura (mapa del INEI) con su UBIGEO, su punto interior y su clave."""
    from ubigeo import clave_distrito
    g = json.load(open(DATA / "exposicion" / "distritos.geojson", encoding="utf-8"))
    filas = []
    for f in g["features"]:
        p = f["properties"]
        c = shape(f["geometry"]).representative_point()
        filas.append({"departamento": p["departamento"], "provincia": p["provincia"], "distrito": p["distrito"],
                      "ubigeo": p.get("ubigeo"), "lat": round(c.y, 3), "lon": round(c.x, 3),
                      "clave": clave_distrito(p["departamento"], p["provincia"], p["distrito"])})
    return pd.DataFrame(filas)


def lluvia(d: pd.DataFrame) -> pd.DataFrame:
    ruta = CARPETA / "lluvia_distritos.csv"
    previo = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(columns=["clave", "fecha", "lluvia"])
    hoy = pd.Timestamp.today().strftime("%Y%m%d")
    partes = [previo]
    for _, r in d.iterrows():
        ya = previo[previo["clave"] == r["clave"]]
        inicio = (pd.to_datetime(ya["fecha"]).max() + pd.Timedelta(days=1)).strftime("%Y%m%d") if len(ya) else INICIO.replace("-", "")
        if inicio >= hoy:
            continue
        for intento in range(3):
            try:
                j = requests.get(POWER, params={"parameters": "PRECTOTCORR", "community": "AG", "latitude": r["lat"],
                                                "longitude": r["lon"], "start": inicio, "end": hoy, "format": "JSON"},
                                 headers=UA, timeout=180).json()
                serie = j["properties"]["parameter"]["PRECTOTCORR"]
                partes.append(pd.DataFrame({"clave": r["clave"], "fecha": pd.to_datetime(list(serie), format="%Y%m%d").strftime("%Y-%m-%d"),
                                            "lluvia": list(serie.values())}))
                break
            except Exception as error:
                print(f"  POWER {r['distrito']}: {error}"); time.sleep(10 * (intento + 1))
        time.sleep(0.5)
    t = pd.concat(partes, ignore_index=True)
    t["lluvia"] = pd.to_numeric(t["lluvia"], errors="coerce")
    t.loc[t["lluvia"] < 0, "lluvia"] = np.nan                       # -999 = sin dato en POWER
    t = t.drop_duplicates(["clave", "fecha"], keep="last")
    t.to_csv(ruta, index=False)
    return t


def caudal_historico() -> pd.DataFrame:
    ruta = CARPETA / "caudal_rios.csv"
    if ruta.exists():
        previo = pd.read_csv(ruta)
        if pd.to_datetime(previo["fecha"]).max() >= pd.Timestamp.today() - pd.Timedelta(days=10):
            return previo
    celdas = pd.read_csv(DATA / "normales" / "rios_celdas.csv") if (DATA / "normales" / "rios_celdas.csv").exists() else \
        pd.DataFrame([(k, *v) for k, v in RIOS.items()], columns=["rio", "lat", "lon"])
    celdas = celdas[celdas["rio"].isin(["Tumbes", "Chira", "Piura"])]
    partes = []
    hoy = pd.Timestamp.today()
    tramos = [(pd.Timestamp(a, 1, 1), min(pd.Timestamp(a + 4, 12, 31), hoy)) for a in range(2001, hoy.year + 1, 5)]
    for _, r in celdas.iterrows():
        for t0, t1 in tramos:                      # de 5 en 5 años: pedidos más livianos
            for intento in range(4):
                try:
                    j = requests.get(FLOOD, params={"latitude": r["lat"], "longitude": r["lon"], "daily": "river_discharge",
                                                    "start_date": t0.strftime("%Y-%m-%d"), "end_date": t1.strftime("%Y-%m-%d")},
                                     headers=UA, timeout=180).json()
                    partes.append(pd.DataFrame({"rio": r["rio"], "fecha": j["daily"]["time"], "caudal": j["daily"]["river_discharge"]}))
                    break
                except Exception as error:
                    print(f"  caudal {r['rio']} {t0.year}: {error}"); time.sleep(20 * (intento + 1))
            time.sleep(2)
    t = pd.concat(partes, ignore_index=True)
    t.to_csv(ruta, index=False)
    return t


def exposicion_distrito() -> pd.DataFrame:
    j = json.load(open(DASH_DATA / "inundacion.json", encoding="utf-8"))
    filas = {}
    for clave_ev, sufijo in (("rp10", "rp10"), ("rp100", "rp100")):
        ev = j["eventos"].get(clave_ev)
        if not ev:
            continue
        for f in ev["distritos"]:
            if f["departamento"] == "Sin distrito asignado":
                continue
            from ubigeo import clave_distrito
            k = clave_distrito(f["departamento"], f.get("provincia", ""), f["distrito"])
            fila = filas.setdefault(k, {"clave": k})
            fila[f"km2_inundable_{sufijo}"] = f["km2"]
            # nombre de columna heredado ("viviendas_*"); son edificaciones de Open Buildings
            fila[f"viviendas_{sufijo}"] = f.get("edificaciones", f.get("viviendas"))
            fila[f"personas_{sufijo}"] = f["personas"]
    return pd.DataFrame(list(filas.values()))


TABLAS_INDECI = ["7162639-tabla-1-emergencias-y-danos-2003-2024-indeci", "7162698-tabla-2-peligros-2003-2024-indeci",
                  "7162767-tabla-3-damnificados-2003-2024-indeci", "7162837-tabla-4-afectados-2003-2024-indeci"]


def tablas_indeci() -> None:
    """Tablas estadísticas del INDECI 2003-2024 (totales por provincia y distrito, sin fechas) de Tumbes y Piura.
    Se guardan tal cual en data/modelo/indeci/ para validar DÓNDE ocurren más emergencias."""
    import re
    destino = CARPETA / "indeci"; destino.mkdir(exist_ok=True)
    nav = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    for pagina in TABLAS_INDECI:
        try:
            html = requests.get(f"https://www.gob.pe/institucion/indeci/informes-publicaciones/{pagina}", headers=nav, timeout=120).text
            for url in sorted(set(re.findall(r'https://cdn\.www\.gob\.pe/uploads/document/file/[^"?]+', html))):
                nombre = url.rsplit("/", 1)[-1].lower()
                if ("piura" in nombre or "tumbes" in nombre) and not (destino / nombre).exists():
                    (destino / nombre).write_bytes(requests.get(url, headers=nav, timeout=180).content)
                    print(f"  INDECI: {nombre}")
        except Exception as error:
            print(f"  INDECI {pagina}: {error}")


def main() -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    tablas_indeci()
    em = emergencias()
    d = distritos()
    from ubigeo import clave_distrito
    em["clave"] = [clave_distrito(a, b, c) for a, b, c in zip(em["name0"], em["name1"], em["name2"])]
    sin = sorted(set(em["clave"]) - set(d["clave"]))
    print(f"  registros cuyo distrito no se encontró en el mapa: {em['clave'].isin(sin).sum()} ({sin[:8]})")
    ll = lluvia(d)
    q = caudal_historico()
    # --- semanas ---
    ll["fecha"] = pd.to_datetime(ll["fecha"])
    ll["semana"] = ll["fecha"].dt.to_period("W-SUN").dt.start_time
    sem = ll.groupby(["clave", "semana"])["lluvia"].sum(min_count=4).rename("lluvia_7d").reset_index()
    sem = sem.sort_values(["clave", "semana"])
    g = sem.groupby("clave")["lluvia_7d"]
    sem["lluvia_30d"] = g.transform(lambda s: s.rolling(4, min_periods=3).sum())
    sem["lluvia_90d"] = g.transform(lambda s: s.rolling(13, min_periods=10).sum())
    sem["lluvia_7d_prev"] = g.shift(1)
    sem["semana_anio"] = sem["semana"].dt.isocalendar().week.astype(int).clip(1, 52)
    base = sem[(sem["semana"] >= "2001-01-01") & (sem["semana"] < "2021-01-01")]
    for c in ["lluvia_7d", "lluvia_30d", "lluvia_90d"]:
        clim = base.groupby(["clave", "semana_anio"])[c].mean().rename(c + "_normal")
        sem = sem.join(clim, on=["clave", "semana_anio"])
        sem[c + "_anom"] = sem[c] - sem[c + "_normal"]
    # ríos: el más cercano a cada distrito (entre Tumbes, Chira y Piura)
    q["fecha"] = pd.to_datetime(q["fecha"])
    q["semana"] = q["fecha"].dt.to_period("W-SUN").dt.start_time
    qs = q.groupby(["rio", "semana"])["caudal"].mean().reset_index()
    qs["semana_anio"] = qs["semana"].dt.isocalendar().week.astype(int).clip(1, 52)
    med = qs[qs["semana"] < "2021-01-01"].groupby(["rio", "semana_anio"])["caudal"].median().rename("caudal_mediana")
    qs = qs.join(med, on=["rio", "semana_anio"])
    qs["caudal_razon"] = qs["caudal"] / qs["caudal_mediana"].clip(lower=0.5)
    qs["caudal_max_4s"] = qs.groupby("rio")["caudal"].transform(lambda s: s.rolling(4, min_periods=1).max())
    pos = {k: v for k, v in RIOS.items() if k in ("Tumbes", "Chira", "Piura")}
    d["rio"] = d.apply(lambda r: min(pos, key=lambda k: (pos[k][0] - r["lat"]) ** 2 + (pos[k][1] - r["lon"]) ** 2), axis=1)
    sem = sem[sem["clave"].isin(d["clave"])]          # lluvia_distritos.csv puede guardar claves antiguas
    sem = sem.merge(d[["clave", "ubigeo", "departamento", "provincia", "distrito", "rio"]], on="clave", how="left")
    sem = sem.merge(qs[["rio", "semana", "caudal", "caudal_razon", "caudal_max_4s"]], on=["rio", "semana"], how="left")
    # mar
    n = pd.read_csv(DATA / "noaa_semanal.csv")
    n["semana"] = pd.to_datetime(n["semana"]).dt.to_period("W-SUN").dt.start_time
    sem = sem.merge(n[["semana", "nino12", "nino34"]], on="semana", how="left")
    sem[["nino12", "nino34"]] = sem.groupby("clave")[["nino12", "nino34"]].ffill()
    # exposición (fija)
    sem = sem.merge(exposicion_distrito(), on="clave", how="left")
    for c in [c for c in sem if c.startswith(("km2_inundable", "viviendas_rp", "personas_rp"))]:
        sem[c] = sem[c].fillna(0)
    # etiquetas
    e = em[em["tipo_inundacion"] & em["fecha"].notna()].copy()
    e["semana"] = e["fecha"].dt.to_period("W-SUN").dt.start_time
    ev = e.groupby(["clave", "semana"]).agg(emergencias=("serial", "count"), viv_afectadas=("vivafec", "sum"),
                                             viv_destruidas=("vivdest", "sum"), damnificados=("damnificados", "sum")).reset_index()
    sem = sem.merge(ev, on=["clave", "semana"], how="left")
    for c in ["emergencias", "viv_afectadas", "viv_destruidas", "damnificados"]:
        sem[c] = sem[c].fillna(0)
    sem["emergencia_sem"] = (sem["emergencias"] > 0).astype(int)
    sem = sem.sort_values(["clave", "semana"])
    fut = sem.groupby("clave")["emergencia_sem"]
    sem["emergencia_1a4"] = pd.concat([fut.shift(-k) for k in range(1, 5)], axis=1).max(axis=1)
    sem["emergencias_5anios_previos"] = fut.transform(lambda s: s.shift(1).rolling(260, min_periods=1).sum())
    ultimo = e["fecha"].max()
    sem.loc[sem["semana"] > ultimo - pd.Timedelta(days=28), "emergencia_1a4"] = np.nan   # aún no se sabe
    sem.loc[sem["semana"] > ultimo, ["emergencia_sem", "emergencias_5anios_previos"]] = np.nan
    sem = sem[sem["semana"] >= "2001-04-01"]
    sem.to_csv(CARPETA / "base_distrito_semana.csv", index=False, float_format="%.3f")
    con = sem.dropna(subset=["emergencia_1a4"])
    print(f"Base: {len(sem):,} filas ({sem['clave'].nunique()} distritos × {sem['semana'].nunique()} semanas). "
          f"Con etiqueta: {len(con):,}; semanas con emergencia: {int(con['emergencia_sem'].sum()):,} "
          f"({100 * con['emergencia_sem'].mean():.1f} %). Última emergencia registrada: {ultimo.date()}")


if __name__ == "__main__":
    main()
