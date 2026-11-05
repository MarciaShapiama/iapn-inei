"""Índices del mar, producción por sector y electricidad diaria.

    NOAA CPC   anomalía semanal de las regiones Niño 1+2, 3, 3.4 y 4 (desde 1990)
    IGP/ENFEN  Índice Costero El Niño (ICEN), mensual
    BCRPData   producción nacional y sus 9 sectores, var. % interanual (cifras del INEI), una serie por vez
    COES       producción eléctrica del SEIN: mensual desde 2015 y diaria de los últimos 20 días
               (mismos días del año anterior para comparar)

Cada descarga se guarda también fechada en data/historico/economia/ (no se borra).

Uso: python src/descargar_indicadores.py
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta

from zoneinfo import ZoneInfo

import pandas as pd
import requests

from config import DATA, DIAS_VENTANA, HIST_ECON, SERIES_BCRP

UA = {"User-Agent": "Mozilla/5.0 (Monitor El Nino Costero, PEU-CD INEI)"}
COES = "https://www.coes.org.pe/Portal/portalinformacion/Generacion"
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9,
         "set": 9, "oct": 10, "nov": 11, "dic": 12}


def noaa_semanal() -> pd.DataFrame:
    txt = requests.get("https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for", headers=UA, timeout=60).text
    filas = []
    for linea in txt.splitlines():
        m = re.match(r"\s*(\d{2}[A-Z]{3}\d{4})(.*)", linea)
        if not m:
            continue
        n = [float(x) for x in re.findall(r"-?\d+\.\d+", m.group(2))]
        if len(n) >= 8:
            filas.append({"semana": pd.to_datetime(m.group(1), format="%d%b%Y").date().isoformat(),
                          "nino12": n[1], "nino3": n[3], "nino34": n[5], "nino4": n[7]})
    return pd.DataFrame(filas)


def icen() -> pd.DataFrame:
    txt = requests.get("http://met.igp.gob.pe/datos/ICEN.txt", headers=UA, timeout=60).text
    filas = []
    for linea in txt.splitlines():
        p = linea.split()
        if len(p) >= 3 and p[0].isdigit() and p[1].isdigit():
            try:
                filas.append({"fecha": f"{int(p[0])}-{int(p[1]):02d}", "icen": float(p[2])})
            except ValueError:
                pass
    return pd.DataFrame(filas)


def bcrp() -> pd.DataFrame:
    filas = []
    for codigo, nombre in SERIES_BCRP.items():
        url = f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/1995-1/{date.today().year}-12/esp"
        for intento in range(3):
            try:
                j = requests.get(url, headers=UA, timeout=60).json()
                break
            except Exception:
                time.sleep(5)
        else:
            print(f"  {codigo}: no se pudo descargar"); continue
        for p in j.get("periods", []):
            m = re.match(r"([A-Za-z]{3})\.?(\d{4})", p["name"])
            try:
                valor = float(p["values"][0])
            except (ValueError, TypeError):
                continue
            filas.append({"fecha": f"{m.group(2)}-{MESES[m.group(1).lower()]:02d}", "codigo": codigo,
                          "serie": nombre, "valor": round(valor, 3)})
    return pd.DataFrame(filas)


def coes_total(inicio: date, fin: date) -> float | None:
    datos = {"fechaInicial": inicio.strftime("%d/%m/%Y"), "fechaFinal": fin.strftime("%d/%m/%Y"), "indicador": 0}
    for intento in range(3):
        try:
            r = requests.post(COES, data=datos, headers={**UA, "X-Requested-With": "XMLHttpRequest"}, timeout=90)
            total = sum(float(x.get("Meditotal") or 0) for x in (r.json().get("ListadoPorEmpresa") or []))
            return round(total, 1) if total > 0 else None
        except Exception:
            time.sleep(3 * (intento + 1))
    return None


def coes_diario() -> pd.DataFrame:
    """Últimos DIAS_VENTANA días (SCADA, MWh) y los mismos días del año anterior."""
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    filas = []
    for i in range(1, DIAS_VENTANA + 1):
        d = hoy - timedelta(days=i)
        hace_un_anio = d.replace(year=d.year - 1)
        filas.append({"fecha": d.isoformat(), "mwh": coes_total(d, d),
                      "mwh_anio_anterior": coes_total(hace_un_anio, hace_un_anio)})
        time.sleep(0.3)
    t = pd.DataFrame(filas).sort_values("fecha")
    t["var_pct"] = (100 * (t["mwh"] / t["mwh_anio_anterior"] - 1)).round(2)
    return t


def coes_mensual(desde: str = "2015-01") -> pd.DataFrame:
    archivo = DATA / "coes_mensual.csv"
    previo = pd.read_csv(archivo) if archivo.exists() else pd.DataFrame(columns=["fecha", "mwh", "dias"])
    hoy = datetime.now(ZoneInfo("America/Lima")).date()
    meses = pd.period_range(desde, pd.Period(hoy, "M") - 1, freq="M")
    ya = set(previo["fecha"].astype(str)) - {str(meses[-1])}
    nuevas = []
    for p in meses:
        if str(p) in ya:
            continue
        nuevas.append({"fecha": str(p), "mwh": coes_total(p.start_time.date(), p.end_time.date()),
                       "dias": p.days_in_month})
        time.sleep(0.3)
    t = pd.concat([previo[previo["fecha"].astype(str).isin(ya)], pd.DataFrame(nuevas)]).sort_values("fecha")
    t = t.reset_index(drop=True)
    t["var12"] = (100 * (t["mwh"] / t["mwh"].shift(12) - 1)).round(2)
    return t


def guardar(tabla: pd.DataFrame, nombre: str) -> None:
    tabla.to_csv(DATA / f"{nombre}.csv", index=False)
    HIST_ECON.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(HIST_ECON / f"{nombre}_{datetime.now():%Y%m%d}.csv.gz", index=False)
    print(f"  {nombre}: {len(tabla)} filas")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    # BCRP y COES eran del proyecto anterior (radar macroeconómico) y el tablero de inundaciones no los usa.
    for nombre, funcion in [("noaa_semanal", noaa_semanal), ("icen", icen)]:
        try:
            guardar(funcion(), nombre)
        except Exception as error:  # una fuente caída no detiene las demás
            print(f"  {nombre}: ERROR {error}")
