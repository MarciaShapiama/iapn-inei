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
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

import pandas as pd
import requests
from shapely.geometry import shape

from config import DATA, DIAS_VENTANA

UA = {"User-Agent": "Monitor El Nino Costero (PEU-CD INEI)"}
PRESUPUESTO_S = 6 * 60      # tiempo máximo por corrida para CADA normal (sigue al día siguiente)
INICIO_RELOJ = time.time()


def queda_tiempo() -> bool:
    return time.time() - INICIO_RELOJ < PRESUPUESTO_S


def reiniciar_reloj() -> None:
    """Cada normal (lluvia y caudal) tiene su propio tiempo, para que una no deje sin tiempo a la otra."""
    global INICIO_RELOJ
    INICIO_RELOJ = time.time()
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
            if r.status_code == 429:  # límite por minuto: esperar y reintentar
                time.sleep(65)
                continue
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


def lluvia_normal(z: pd.DataFrame) -> pd.DataFrame | None:
    """Lluvia promedio 1991-2020 por día del año (suavizada ±7 días).

    Cada año se descarga una sola vez (todas las provincias) y se guarda en data/normales/lluvia_anios/.
    Si un día no alcanza el tiempo, sigue al día siguiente; la normal se calcula con los años que ya hay.
    """
    carpeta = DATA / "normales" / "lluvia_anios"; carpeta.mkdir(parents=True, exist_ok=True)
    for anio in ANIOS_NORMAL:
        ruta = carpeta / f"{anio}.csv.gz"
        if ruta.exists() or not queda_tiempo():
            continue
        j = pedir("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": ",".join(map(str, z["lat"])), "longitude": ",".join(map(str, z["lon"])),
            "start_date": f"{anio}-01-01", "end_date": f"{anio}-12-31", "daily": "precipitation_sum",
            "timezone": "America/Lima"}, intentos=2)
        filas = [{"provincia": z["provincia"][k], "fecha": f, "ll": v}
                 for k, loc in enumerate(como_lista(j or [])) for f, v in zip(loc["daily"]["time"], loc["daily"]["precipitation_sum"])]
        if filas:
            pd.DataFrame(filas).to_csv(ruta, index=False)
            print(f"  lluvia {anio}: listo")
        time.sleep(3)
    anios = sorted(carpeta.glob("*.csv.gz"))
    print(f"  normal de lluvia con {len(anios)} de {len(ANIOS_NORMAL)} años")
    if not anios:
        return None
    t = pd.concat(pd.read_csv(a) for a in anios)
    t["md"] = t["fecha"].str[5:]
    t = t[t["md"] != "02-29"]
    clim = t.groupby(["provincia", "md"])["ll"].mean().unstack("md")
    suave = pd.concat([clim.iloc[:, -7:], clim, clim.iloc[:, :7]], axis=1).T.rolling(15, center=True).mean().T.iloc[:, 7:-7]
    out = suave.stack().rename("lluvia_normal").reset_index().round(2)
    out.to_csv(DATA / "normales" / "lluvia_diaria.csv", index=False)
    return out


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


def caudal_normal(rios: pd.DataFrame) -> pd.DataFrame | None:
    """Mediana y percentil 90 del caudal 1991-2020 por día del año; cada río se baja una vez y se guarda."""
    carpeta = DATA / "normales" / "caudal_rios"; carpeta.mkdir(parents=True, exist_ok=True)
    primero = ["Tumbes", "Chira", "Piura"]                     # los ríos de Tumbes y Piura van primero
    rios = rios.assign(_o=rios["rio"].map(lambda x: primero.index(x) if x in primero else 9)).sort_values("_o")
    for _, r in rios.iterrows():
        ruta = carpeta / f"{r['rio']}.csv.gz"
        if ruta.exists() or not queda_tiempo():
            continue
        partes_rio = []
        for t0, t1 in (("1991-01-01", "2000-12-31"), ("2001-01-01", "2010-12-31"), ("2011-01-01", "2020-12-31")):
            j = pedir("https://flood-api.open-meteo.com/v1/flood", {
                "latitude": r["lat"], "longitude": r["lon"], "daily": "river_discharge",
                "start_date": t0, "end_date": t1}, intentos=2)
            if not j:
                break
            partes_rio.append(pd.DataFrame({"fecha": j["daily"]["time"], "q": j["daily"]["river_discharge"]}))
        if len(partes_rio) == 3:                       # solo se guarda si están los 30 años
            pd.concat(partes_rio).to_csv(ruta, index=False)
            print(f"  caudal {r['rio']}: listo")
        time.sleep(3)
    partes = []
    for ruta in carpeta.glob("*.csv.gz"):
        t = pd.read_csv(ruta); t["rio"] = ruta.name[:-7]; partes.append(t)
    print(f"  normal de caudal para {len(partes)} de {len(rios)} ríos")
    if not partes:
        return None
    t = pd.concat(partes); t["md"] = t["fecha"].str[5:]
    out = t.groupby(["rio", "md"])["q"].agg(caudal_normal="median", caudal_p90=lambda x: x.quantile(.9)).reset_index().round(2)
    out.to_csv(DATA / "normales" / "caudal_diario.csv", index=False)
    return out


def main() -> None:
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    inicio, fin = hoy - timedelta(days=DIAS_VENTANA), hoy + timedelta(days=PRONOSTICO)
    z = puntos_zonas()
    z.to_csv(DATA / "zonas_puntos.csv", index=False)
    ll = lluvia_reciente(z)
    print(f"Lluvia: {len(ll)} filas")
    rios = elegir_celdas_rio()
    q = caudal(rios) if len(rios) else pd.DataFrame()
    print(f"Caudal: {len(q)} filas")
    # lo de hoy primero (rápido); las normales después, con presupuesto de tiempo
    if len(ll):
        ll.to_csv(DATA / "zonas_lluvia.csv", index=False)
    if len(q):
        q.to_csv(DATA / "rios_caudal.csv", index=False)
    hist = DATA / "historico" / "zonas"; hist.mkdir(parents=True, exist_ok=True)
    if len(ll):  # copia del día (lo observado, no el pronóstico)
        ll[ll["fecha"] < hoy.isoformat()].to_csv(hist / f"{hoy.isoformat()}_lluvia.csv.gz", index=False)
    if len(q):
        q[q["fecha"] < hoy.isoformat()].to_csv(hist / f"{hoy.isoformat()}_caudal.csv.gz", index=False)
    reiniciar_reloj()
    if len(rios):
        caudal_normal(rios)          # primero el caudal: estaba en 0 de 24 ríos
    reiniciar_reloj()
    lluvia_normal(z)


if __name__ == "__main__":
    main()
