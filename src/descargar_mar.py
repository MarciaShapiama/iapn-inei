"""Temperatura del mar día a día (NOAA OISST v2.1, anomalía en °C) frente al Perú.

Cada corrida revisa los últimos DIAS_VENTANA días y descarga los que aún no están guardados.
Cada día queda en su propio archivo data/historico/mar/AAAA-MM-DD.csv.gz (lat, lon, anom) y nunca se
borra: así se va formando el histórico. También guarda, una sola vez, los días pico de episodios pasados
(data/historico/picos/AAAA.csv.gz) para comparar.

Fuente: NOAA OISST v2.1 vía ERDDAP de NOAA CoastWatch o su espejo (versión de tiempo casi real; si no
responde, se usa la definitiva).

Uso: python src/descargar_mar.py
"""
from __future__ import annotations

import io
import time
from datetime import date, timedelta

import pandas as pd
import requests

from config import (DATA, DATASETS_HIST, DATASETS_SST, DIAS_VENTANA, ERDDAPS, HIST_MAR, LAT_MAX, LAT_MIN, LON_MAX,
                    LON_MIN, PASO, PICOS)


def consulta(servidor: str, dataset: str, t0: str, t1: str) -> str:
    return (f"{servidor}/{dataset}.csv?anom%5B({t0}):1:({t1})%5D%5B(0.0)%5D"
            f"%5B({LAT_MIN}):{PASO}:({LAT_MAX})%5D%5B({LON_MIN}):{PASO}:({LON_MAX})%5D")


def bajar(t0: str, t1: str, datasets: list[str] = DATASETS_SST) -> pd.DataFrame | None:
    """Prueba cada conjunto de datos en el servidor principal y en el espejo, con reintentos."""
    for dataset, servidor in [(d, s) for d in datasets for s in ERDDAPS]:
        for intento in range(3):
            try:
                r = requests.get(consulta(servidor, dataset, t0, t1), timeout=120)
                if r.status_code == 200:
                    d = pd.read_csv(io.StringIO(r.text), skiprows=[1])
                    d = d.rename(columns={"latitude": "lat", "longitude": "lon"}).dropna(subset=["anom"])
                    d["fecha"] = d["time"].str[:10]
                    print(f"  {dataset}: {d['fecha'].nunique()} días, {len(d)} celdas")
                    return d[["fecha", "lat", "lon", "anom"]]
                print(f"  {servidor[8:20]} {dataset} -> HTTP {r.status_code}: {r.text[:120]!r}")
                if 400 <= r.status_code < 500:
                    break  # no está en este servidor o conjunto: probar el siguiente
            except Exception as error:
                print(f"  {dataset} -> {error}, reintento {intento + 1}")
            time.sleep(10 * (intento + 1))
    return None


def ultimo_disponible() -> str | None:
    for dataset in DATASETS_SST:
        for servidor in ERDDAPS:
            try:
                r = requests.get(f"{servidor}/{dataset}.csv?time%5B(last)%5D", timeout=60)
                if r.status_code == 200:
                    return r.text.strip().splitlines()[-1][:10]
            except Exception:
                pass
    return None


def main() -> None:
    HIST_MAR.mkdir(parents=True, exist_ok=True)
    ultimo = ultimo_disponible() or (date.today() - timedelta(days=2)).isoformat()
    fin = date.fromisoformat(ultimo)
    dias = [(fin - timedelta(days=i)).isoformat() for i in range(DIAS_VENTANA)]
    faltan = sorted(d for d in dias if not (HIST_MAR / f"{d}.csv.gz").exists())
    print(f"Último día disponible: {ultimo}. Faltan {len(faltan)} de los últimos {DIAS_VENTANA} días.")
    if faltan:
        tabla = bajar(faltan[0], faltan[-1])
        if tabla is not None:
            for dia, grupo in tabla.groupby("fecha"):
                if dia in faltan:
                    grupo[["lat", "lon", "anom"]].round(2).to_csv(HIST_MAR / f"{dia}.csv.gz", index=False)
    picos = DATA / "historico" / "picos"
    picos.mkdir(parents=True, exist_ok=True)
    for anio, dia in PICOS.items():
        archivo = picos / f"{anio}.csv.gz"
        if not archivo.exists():
            d = date.fromisoformat(dia)  # promedio de 3 días alrededor del pico (versión definitiva)
            t = bajar((d - timedelta(days=1)).isoformat(), (d + timedelta(days=1)).isoformat(), DATASETS_HIST)
            if t is not None:
                t.groupby(["lat", "lon"], as_index=False)["anom"].mean().round(2).to_csv(archivo, index=False)
    print(f"Histórico: {len(list(HIST_MAR.glob('*.csv.gz')))} días guardados.")


if __name__ == "__main__":
    main()
