"""Zonas afectadas: provincias costeras, día a día (últimos 20 días + pronóstico de 7).

Para cada provincia con litoral:
    lluvia diaria          Open-Meteo (modelos meteorológicos), últimos 20 días y pronóstico de 7
    lluvia normal          mismo periodo de cada año 1991-2020 (reanálisis ERA5 vía Open-Meteo), promedio
Para el río principal de cada cuenca costera:
    caudal diario          GloFAS v4 (Copernicus) vía Open-Meteo, últimos 20 días y pronóstico de 7
    caudal normal          mediana del mismo periodo 1991-2020 (reanálisis GloFAS)

Las normales se calculan una vez por periodo y se guardan en data/normales/ (no se recalculan).
Cada día queda guardado en data/historico/zonas/AAAA-MM-DD.csv (no se borra).

Uso: python src/descargar_zonas.py
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pandas as pd
import requests
from shapely.geometry import shape

from config import DATA, DIAS_VENTANA

UA = {"User-Agent": "Monitor El Nino Costero (PEU-CD INEI)"}
PRONOSTICO = 7
ANIOS_NORMAL = range(1991, 2021)

# Provincias con litoral (o con la ciudad principal en la llanura costera), de norte a sur.
ZONAS = [("Tumbes", "Zarumilla"), ("Tumbes", "Tumbes"), ("Tumbes", "Contralmirante Villar"),
         ("Piura", "Talara"), ("Piura", "Sullana"), ("Piura", "Paita"), ("Piura", "Piura"), ("Piura", "Sechura"),
         ("Lambayeque", "Lambayeque"), ("Lambayeque", "Chiclayo"),
         ("La Libertad", "Pacasmayo"), ("La Libertad", "Chepén"), ("La Libertad", "Ascope"),
         ("La Libertad", "Trujillo"), ("La Libertad", "Virú"),
         ("Áncash", "Santa"), ("Áncash", "Casma"), ("Áncash", "Huarmey"),
         ("Lima", "Barranca"), ("Lima", "Huaura"), ("Lima", "Huaral"), ("Lima", "Lima"), ("Callao", "Callao"),
         ("Lima", "Cañete"), ("Ica", "Chincha"), ("Ica", "Pisco"), ("Ica", "Ica"), ("Ica", "Nazca"),
         ("Arequipa", "Caravelí"), ("Arequipa", "Camaná"), ("Arequipa", "Islay"),
         ("Moquegua", "Ilo"), ("Tacna", "Jorge Basadre"), ("Tacna", "Tacna")]

# Ríos principales: punto aproximado en el curso bajo; se busca la celda de GloFAS con más caudal alrededor.
RIOS = {"Tumbes": (-3.62, -80.40), "Chira": (-4.88, -80.68), "Piura": (-5.18, -80.62),
        "Chancay-Lambayeque": (-6.70, -79.65), "Jequetepeque": (-7.25, -79.45), "Chicama": (-7.75, -79.20),
        "Moche": (-8.08, -78.95), "Santa": (-8.98, -78.55), "Casma": (-9.45, -78.25), "Huarmey": (-10.05, -78.10),
        "Pativilca": (-10.68, -77.72), "Huaura": (-11.08, -77.55), "Chancay-Huaral": (-11.50, -77.20),
        "Rímac": (-12.00, -76.95), "Cañete": (-13.05, -76.32), "San Juan (Chincha)": (-13.40, -76.05),
        "Pisco": (-13.70, -76.05), "Ica": (-14.05, -75.73), "Grande (Nazca)": (-14.80, -75.10),
        "Ocoña": (-16.35, -73.10), "Camaná-Majes": (-16.55, -72.65), "Tambo": (-17.05, -71.70),
        "Locumba": (-17.60, -70.80), "Caplina": (-17.95, -70.25)}


def pedir(url: str, params: dict, intentos: int = 4):
    for i in range(intentos):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=120)
            if r.status_code == 200:
                return r.json()
            print(f"  {url.split('/')[2]} HTTP {r.status_code}: {r.text[:120]}")
            if r.status_code == 400:
                return None
        except Exception as error:
            print(f"  {url.split('/')[2]}: {error}")
        time.sleep(20 * (i + 1))
    return None


def como_lista(j):
    return j if isinstance(j, list) else [j]


def puntos_zonas() -> pd.DataFrame:
    g = json.load(open(DATA / "provincias.geojson", encoding="utf-8"))
    formas = {(f["properties"]["departamento"], f["properties"]["provincia"]): shape(f["geometry"]) for f in g["features"]}
    filas = []
    for dep, prov in ZONAS:
        p = formas[(dep, prov)].representative_point()
        filas.append({"departamento": dep, "provincia": prov, "lat": round(p.y, 3), "lon": round(p.x, 3)})
    return pd.DataFrame(filas)


def lluvia_reciente(z: pd.DataFrame) -> pd.DataFrame:
    j = pedir("https://api.open-meteo.com/v1/forecast", {
        "latitude": ",".join(map(str, z["lat"])), "longitude": ",".join(map(str, z["lon"])),
        "daily": "precipitation_sum,temperature_2m_max", "past_days": DIAS_VENTANA,
        "forecast_days": PRONOSTICO + 1, "timezone": "America/Lima"})
    filas = []
    for k, loc in enumerate(como_lista(j or [])):
        d = loc["daily"]
        for f, ll, t in zip(d["time"], d["precipitation_sum"], d["temperature_2m_max"]):
            filas.append({"provincia": z["provincia"][k], "fecha": f, "lluvia_mm": ll, "tmax": t})
    return pd.DataFrame(filas)


def _ventana(inicio: date, fin: date, anio: int) -> tuple[str, str]:
    a = inicio.replace(year=anio) if not (inicio.month == 2 and inicio.day == 29) else inicio.replace(year=anio, day=28)
    return a.isoformat(), (a + (fin - inicio)).isoformat()


def lluvia_normal(z: pd.DataFrame, inicio: date, fin: date) -> pd.DataFrame:
    """Lluvia promedio 1991-2020 para cada día (mes-día) de la ventana. Se guarda y se reutiliza."""
    carpeta = DATA / "normales"; carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "lluvia_diaria.csv"
    previo = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(columns=["provincia", "md", "lluvia_normal"])
    mds = [(inicio + timedelta(days=i)).strftime("%m-%d") for i in range((fin - inicio).days + 1)]
    faltan = [m for m in mds if m not in set(previo["md"])]
    if not faltan:
        return previo
    a, b = date(2001, int(faltan[0][:2]), int(faltan[0][3:])), date(2001, int(faltan[-1][:2]), int(faltan[-1][3:]))
    if b < a:  # la ventana cruza el año nuevo: se calcula todo el bloque
        a, b = date(2001, 1, 1), date(2001, 12, 31)
    filas = []
    for anio in ANIOS_NORMAL:
        t0, t1 = _ventana(a, b, anio)
        j = pedir("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": ",".join(map(str, z["lat"])), "longitude": ",".join(map(str, z["lon"])),
            "start_date": t0, "end_date": t1, "daily": "precipitation_sum", "timezone": "America/Lima"})
        for k, loc in enumerate(como_lista(j or [])):
            for f, ll in zip(loc["daily"]["time"], loc["daily"]["precipitation_sum"]):
                filas.append({"provincia": z["provincia"][k], "md": f[5:], "ll": ll})
        time.sleep(1)
    if not filas:
        return previo
    nuevo = pd.DataFrame(filas).groupby(["provincia", "md"], as_index=False)["ll"].mean()
    nuevo = nuevo.rename(columns={"ll": "lluvia_normal"}).round(2)
    t = pd.concat([previo, nuevo[nuevo["md"].isin(faltan)]]).drop_duplicates(["provincia", "md"], keep="last")
    t.to_csv(ruta, index=False)
    return t


def elegir_celdas_rio() -> pd.DataFrame:
    """Para cada río, la celda de GloFAS (0,05°) con más caudal en un vecindario de ±0,1°."""
    ruta = DATA / "normales" / "rios_celdas.csv"
    if ruta.exists():
        return pd.read_csv(ruta)
    cand = [(rio, round(la + i * 0.05, 3), round(lo + j * 0.05, 3))
            for rio, (la, lo) in RIOS.items() for i in (-2, -1, 0, 1, 2) for j in (-2, -1, 0, 1, 2)]
    c = pd.DataFrame(cand, columns=["rio", "lat", "lon"])
    medias = []
    for k in range(0, len(c), 100):
        parte = c.iloc[k:k + 100]
        j = pedir("https://flood-api.open-meteo.com/v1/flood", {
            "latitude": ",".join(map(str, parte["lat"])), "longitude": ",".join(map(str, parte["lon"])),
            "daily": "river_discharge", "start_date": "2017-01-01", "end_date": "2017-04-30"})
        for loc in como_lista(j or []):
            v = [x for x in loc["daily"]["river_discharge"] if x is not None]
            medias.append(sum(v) / len(v) if v else 0)
        time.sleep(1)
    c["media_2017"] = medias + [0] * (len(c) - len(medias))
    mejor = c.loc[c.groupby("rio")["media_2017"].idxmax()].reset_index(drop=True)
    if mejor["media_2017"].gt(0).any():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        mejor.to_csv(ruta, index=False)
    return mejor


def caudal(rios: pd.DataFrame) -> pd.DataFrame:
    j = pedir("https://flood-api.open-meteo.com/v1/flood", {
        "latitude": ",".join(map(str, rios["lat"])), "longitude": ",".join(map(str, rios["lon"])),
        "daily": "river_discharge", "past_days": DIAS_VENTANA, "forecast_days": PRONOSTICO + 1})
    filas = []
    for k, loc in enumerate(como_lista(j or [])):
        for f, q in zip(loc["daily"]["time"], loc["daily"]["river_discharge"]):
            filas.append({"rio": rios["rio"][k], "fecha": f, "caudal_m3s": q})
    return pd.DataFrame(filas)


def caudal_normal(rios: pd.DataFrame, inicio: date, fin: date) -> pd.DataFrame:
    """Mediana 1991-2020 del caudal para cada día (mes-día) de la ventana; se guarda y reutiliza."""
    ruta = DATA / "normales" / "caudal_diario.csv"
    previo = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(columns=["rio", "md", "caudal_normal", "caudal_p90"])
    mds = [(inicio + timedelta(days=i)).strftime("%m-%d") for i in range((fin - inicio).days + 1)]
    faltan = [m for m in mds if m not in set(previo["md"])]
    if not faltan:
        return previo
    filas = []
    for _, r in rios.iterrows():  # un río por pedido (30 años de datos diarios)
        j = pedir("https://flood-api.open-meteo.com/v1/flood", {
            "latitude": r["lat"], "longitude": r["lon"], "daily": "river_discharge",
            "start_date": "1991-01-01", "end_date": "2020-12-31"})
        for loc in como_lista(j or []):
            for f, q in zip(loc["daily"]["time"], loc["daily"]["river_discharge"]):
                filas.append({"rio": r["rio"], "md": f[5:], "q": q})
        time.sleep(2)
    if not filas:
        return previo
    t = pd.DataFrame(filas)
    nuevo = t.groupby(["rio", "md"])["q"].agg(caudal_normal="median", caudal_p90=lambda x: x.quantile(.9)).reset_index()
    nuevo.round(2).to_csv(ruta, index=False)  # todo el año de una vez: no se vuelve a pedir
    return nuevo.round(2)


def main() -> None:
    hoy = date.today()
    inicio, fin = hoy - timedelta(days=DIAS_VENTANA), hoy + timedelta(days=PRONOSTICO)
    z = puntos_zonas()
    z.to_csv(DATA / "zonas_puntos.csv", index=False)
    ll = lluvia_reciente(z)
    print(f"Lluvia: {len(ll)} filas")
    nl = lluvia_normal(z, inicio, fin)
    print(f"Lluvia normal: {len(nl)} filas")
    rios = elegir_celdas_rio()
    q = caudal(rios) if len(rios) else pd.DataFrame()
    print(f"Caudal: {len(q)} filas")
    nq = caudal_normal(rios, inicio, fin) if len(rios) else pd.DataFrame()
    print(f"Caudal normal: {len(nq)} filas")
    if len(ll):
        ll.to_csv(DATA / "zonas_lluvia.csv", index=False)
    if len(q):
        q.to_csv(DATA / "rios_caudal.csv", index=False)
    hist = DATA / "historico" / "zonas"; hist.mkdir(parents=True, exist_ok=True)
    if len(ll):  # copia del día (lo observado, no el pronóstico)
        ll[ll["fecha"] < hoy.isoformat()].to_csv(hist / f"{hoy.isoformat()}_lluvia.csv.gz", index=False)
    if len(q):
        q[q["fecha"] < hoy.isoformat()].to_csv(hist / f"{hoy.isoformat()}_caudal.csv.gz", index=False)


if __name__ == "__main__":
    main()
