"""Aviso de lluvia y caudal por distrito para los próximos días (Tumbes y Piura).

El radar solo ve el agua cuando el satélite pasa y después de que ocurre. Para anticiparse se usan dos pronósticos:

1. LLUVIA (todos los distritos). Para cada distrito se compara la lluvia pronosticada con lo que es extremo EN ESE
   MISMO LUGAR.
   Umbrales (se guardan en data/normales/umbrales_lluvia_distritos.csv): reanálisis ERA5 1991-2020 (Open-Meteo) que
   el tablero ya guarda por provincia; días con lluvia (>= 1 mm); percentiles 95 y 99. Cada distrito usa el umbral de
   su provincia (bajar ERA5 para 78 puntos y 30 años supera el límite gratuito diario de Open-Meteo).
   Pronóstico (cada día): Open-Meteo, lluvia diaria de los próximos 7 días en el punto central del distrito.

2. CAUDAL (solo los distritos de los valles de los ríos Piura, Chira y Tumbes, lista CUENCA). Muchas crecidas vienen
   de la lluvia aguas arriba (en Tumbes, de Ecuador), no de la que cae en el distrito: el desborde del río Tumbes de
   febrero de 2025 no tuvo aviso de lluvia (docs/3_validacion/3.1_PRUEBA_AVISO_CON_EL_PASADO.md).
   Pronóstico (cada día): GloFAS v4 (Open-Meteo Flood API, river_discharge) de los próximos 7 días en la misma celda
   del río que usan src/descargar_zonas.py y data/modelo/caudal_rios.csv (data/normales/rios_celdas.csv).
   Umbrales: percentiles 95 y 99 del caudal diario 2001-2020 de esa celda (data/modelo/caudal_rios.csv).
   Zarumilla no tiene celda GloFAS con dato y la sierra no está en CUENCA: siguen solo con lluvia, y la salida lo dice.

Niveles (por el día más alto de los próximos 3 días):
    "extremo"  por encima del percentil 99 del lugar
    "fuerte"   por encima del percentil 95
    "normal"   por debajo
Nivel final del distrito = el mayor entre el de la lluvia y el del caudal. Se guardan los dos y el motivo
("lluvia", "caudal" o "lluvia y caudal"). Si Open-Meteo Flood no responde, el aviso sigue solo con lluvia y lo anota.

Es un criterio por percentiles parecido al que usa SENAMHI para calificar la lluvia, pero NO es un aviso oficial.

Salida: dashboard/data/aviso_lluvia.json
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DASH_DATA, DATA  # noqa: E402


def pedir(url: str, params: dict):
    """La misma función de descargas del proyecto (src/descargar_zonas.py), importada recién al usar la red: así las
    pruebas sin red no necesitan las librerías de mapas que carga descargar_zonas."""
    from descargar_zonas import pedir as _pedir
    return _pedir(url, params)

UMBRALES = DATA / "normales" / "umbrales_lluvia_distritos.csv"
CAUDAL_HIST = DATA / "modelo" / "caudal_rios.csv"           # GloFAS v4, caudal diario 2001-hoy (src/base_modelo.py)
CELDAS = DATA / "normales" / "rios_celdas.csv"              # celda GloFAS de cada río (src/descargar_zonas.py)
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
SALIDA = DASH_DATA / "aviso_lluvia.json"
DIAS = 7
VENTANA = 3            # días que cuentan para el nivel
ANIOS_UMBRAL_CAUDAL = (2001, 2020)
ORDEN = {"normal": 0, "fuerte": 1, "extremo": 2}

# Distritos de cada río con dato de caudal. Es la misma lista de herramientas/pruebas/prueba_aviso_pasado.py
# (tests/test_aviso_caudal.py comprueba que no se separen). Zarumilla no tiene punto GloFAS.
CUENCA = {"Piura": ["Piura", "Castilla", "Catacaos", "Cura Mori", "El Tallan", "La Arena", "La Union", "Bernal",
                    "Cristo Nos Valga", "Rinconada Llicuar", "Vice", "Bellavista de la Union", "Sechura",
                    "Veintiseis de Octubre", "Tambo Grande", "Chulucanas", "La Matanza", "Morropon", "Buenos Aires"],
          "Chira": ["Sullana", "Bellavista", "Miguel Checa", "Marcavelica", "Querecotillo", "Ignacio Escudero", "Lancones",
                    "Amotape", "Arenal", "La Huaca", "Tamarindo", "Vichayal", "Colan", "Paita"],
          "Tumbes": ["Tumbes", "Corrales", "San Juan de la Virgen", "Pampas de Hospital", "San Jacinto", "La Cruz"]}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s)


def rio_de(distrito: str) -> str | None:
    return next((r for r, ds in CUENCA.items() if norm(distrito) in {norm(d) for d in ds}), None)


# ------------------------------------------------------------------------------------------------------- lluvia
def distritos() -> pd.DataFrame:
    from shapely.geometry import shape
    g = json.load(open(DATA / "exposicion" / "distritos.geojson", encoding="utf-8"))
    filas = []
    for f in g["features"]:
        p = shape(f["geometry"]).representative_point()
        pr = f["properties"]
        filas.append({"departamento": pr["departamento"], "provincia": pr["provincia"], "distrito": pr["distrito"],
                      "ubigeo": pr.get("ubigeo"), "lat": round(p.y, 4), "lon": round(p.x, 4)})
    return pd.DataFrame(filas)


def en_bloques(df, n=10):
    for i in range(0, len(df), n):
        yield df.iloc[i:i + n]


def umbrales(d: pd.DataFrame) -> pd.DataFrame:
    """Percentiles 95 y 99 de los días con lluvia (>= 1 mm) de 1991 a 2020, con el reanálisis ERA5 (Open-Meteo) que el
    tablero ya guarda por provincia en data/normales/lluvia_anios/. Cada distrito usa el umbral de su provincia.
    No necesita red."""
    import glob
    l = pd.concat(pd.read_csv(f) for f in sorted(glob.glob(str(DATA / "normales" / "lluvia_anios" / "*.csv.gz"))))
    l = l[l["fecha"].between("1991-01-01", "2020-12-31")]
    por_prov = {}
    for prov, g in l.groupby("provincia"):
        h = g["ll"].to_numpy(dtype=float)
        h = h[h >= 1.0]
        por_prov[prov] = (len(h), np.percentile(h, 95) if len(h) >= 30 else np.nan,
                          np.percentile(h, 99) if len(h) >= 30 else np.nan, g["ll"].max(), g["fecha"].min()[:4], g["fecha"].max()[:4])
    filas = []
    for _, r in d.iterrows():
        n, p95, p99, mx, a0, a1 = por_prov.get(r.provincia, (0, np.nan, np.nan, np.nan, "", ""))
        filas.append({**r.to_dict(), "dias_con_lluvia": int(n), "p95": round(float(p95), 1), "p99": round(float(p99), 1),
                      "max_diaria": round(float(mx), 1), "periodo": f"{a0}-{a1}"})
    u = pd.DataFrame(filas)
    UMBRALES.parent.mkdir(parents=True, exist_ok=True)
    u.to_csv(UMBRALES, index=False)
    return u


def pronostico(d: pd.DataFrame) -> dict:
    out = {}
    for b in en_bloques(d, 25):
        j = pedir("https://api.open-meteo.com/v1/forecast", {
            "latitude": ",".join(map(str, b.lat)), "longitude": ",".join(map(str, b.lon)),
            "daily": "precipitation_sum", "forecast_days": DIAS, "timezone": "America/Lima"})
        if j is None:
            raise RuntimeError("Open-Meteo (pronóstico) no respondió")
        j = j if isinstance(j, list) else [j]
        for (_, r), x in zip(b.iterrows(), j):
            out[(r.departamento, r.provincia, r.distrito)] = (x["daily"]["time"], [0.0 if y is None else float(y)
                                                                                   for y in x["daily"]["precipitation_sum"]])
    return out


def nivel(mm: float, p95: float, p99: float) -> str:
    if mm is None or p95 is None or np.isnan(p95):
        return "sin umbral"
    if mm > p99:
        return "extremo"
    if mm > p95:
        return "fuerte"
    return "normal"


# ------------------------------------------------------------------------------------------------------- caudal
def umbrales_caudal() -> dict:
    """{río: {"p95", "p99", "periodo", "dias"}} con el caudal diario 2001-2020 de data/modelo/caudal_rios.csv."""
    if not CAUDAL_HIST.exists():
        return {}
    c = pd.read_csv(CAUDAL_HIST, parse_dates=["fecha"])
    a0, a1 = ANIOS_UMBRAL_CAUDAL
    c = c[(c["fecha"].dt.year >= a0) & (c["fecha"].dt.year <= a1)].dropna(subset=["caudal"])
    return {r: {"p95": round(float(np.percentile(g["caudal"], 95)), 1),
                "p99": round(float(np.percentile(g["caudal"], 99)), 1),
                "periodo": f"{a0}-{a1}", "dias": int(len(g))}
            for r, g in c.groupby("rio") if r in CUENCA}


def celdas_rios() -> pd.DataFrame:
    """Celda GloFAS de los ríos de CUENCA: la misma de src/descargar_zonas.py y de caudal_rios.csv."""
    c = pd.read_csv(CELDAS)
    return c[c["rio"].isin(list(CUENCA))][["rio", "lat", "lon"]].reset_index(drop=True)


def pronostico_caudal(celdas: pd.DataFrame) -> dict:
    """{río: (fechas, m3/s)} de los próximos DIAS días. Lanza RuntimeError si Open-Meteo Flood no responde."""
    j = pedir(FLOOD, {"latitude": ",".join(map(str, celdas["lat"])), "longitude": ",".join(map(str, celdas["lon"])),
                      "daily": "river_discharge", "forecast_days": DIAS})
    if j is None:
        raise RuntimeError("Open-Meteo Flood no respondió")
    j = j if isinstance(j, list) else [j]
    out = {}
    for (_, r), x in zip(celdas.iterrows(), j):
        out[r["rio"]] = (x["daily"]["time"], [None if q is None else float(q) for q in x["daily"]["river_discharge"]])
    return out


def resumen_caudal(fechas: list, valores: list, u: dict) -> dict:
    """Nivel del río por el día de más caudal en los próximos VENTANA días."""
    v = [(f, q) for f, q in zip(fechas[:VENTANA], valores[:VENTANA]) if q is not None]
    if not v:
        return {"estado": "sin dato: el pronóstico de caudal vino vacío", "nivel": None}
    f, q = max(v, key=lambda t: t[1])
    return {"estado": "ok", "nivel": nivel(q, u["p95"], u["p99"]), "m3s_max": round(q, 1), "fecha_max": f,
            "p95": u["p95"], "p99": u["p99"], "fechas": fechas, "m3s": [None if x is None else round(x, 1) for x in valores],
            "veces_p95": round(q / u["p95"], 2) if u["p95"] else None}


def motivo_de(n_lluvia: str, n_caudal: str | None) -> str | None:
    l = ORDEN.get(n_lluvia, 0) > 0
    c = n_caudal is not None and ORDEN.get(n_caudal, 0) > 0
    return "lluvia y caudal" if (l and c) else "lluvia" if l else "caudal" if c else None


def final(n_lluvia: str, n_caudal: str | None) -> str:
    if n_caudal is None or n_lluvia == "sin umbral" and n_caudal not in ORDEN:
        return n_lluvia
    if n_lluvia == "sin umbral":
        return n_caudal
    return max((n_lluvia, n_caudal), key=lambda n: ORDEN.get(n, -1))


# --------------------------------------------------------------------------------------------------------- armar
def armar(u: pd.DataFrame, pr: dict, rios: dict, estado_caudal: str, umbr_caudal: dict, expo: dict) -> dict:
    """Arma la salida sin usar la red (se prueba en tests/test_aviso_caudal.py).
    u: umbrales de lluvia por distrito; pr: {(dep, prov, dist): (fechas, mm)}; rios: {río: resumen_caudal(...)}."""
    filas = []
    for r in u.itertuples():
        k = (r.departamento, r.provincia, r.distrito)
        if k not in pr:
            continue
        fechas, mm = pr[k]
        v = mm[:VENTANA]
        i = int(np.argmax(v))
        n_ll = nivel(v[i], r.p95, r.p99)
        rio = rio_de(r.distrito)
        if rio is None:
            caudal = {"rio": None, "estado": "sin río con dato de caudal: solo lluvia", "nivel": None}
        elif rio in rios and rios[rio].get("estado") == "ok":
            caudal = {"rio": rio, **{a: b for a, b in rios[rio].items() if a not in ("fechas", "m3s")}}
        else:
            caudal = {"rio": rio, "estado": (rios.get(rio) or {}).get("estado") or estado_caudal, "nivel": None}
        n_c = caudal.get("nivel")
        x = expo.get(k)
        filas.append({"departamento": r.departamento, "provincia": r.provincia, "distrito": r.distrito,
                      "nivel": final(n_ll, n_c), "nivel_lluvia": n_ll, "nivel_caudal": n_c, "motivo": motivo_de(n_ll, n_c),
                      "mm_dia_max": round(v[i], 1), "fecha_max": fechas[i],
                      "mm_7d": round(sum(mm), 1), "p95": r.p95, "p99": r.p99,
                      "lluvia_diaria": [round(y, 1) for y in mm], "fechas": fechas,
                      "caudal": caudal,
                      "personas_zona_inundable": None if x is None else int(x.personas),
                      "colegios_zona_inundable": None if x is None else int(x.colegios_dentro),
                      "salud_zona_inundable": None if x is None else int(x.salud_dentro)})
    orden = {"extremo": 0, "fuerte": 1, "normal": 2, "sin umbral": 3}

    def fuerza(f):   # dentro del mismo nivel: primero lo que más supera su umbral
        ll = f["mm_dia_max"] / f["p99"] if f["p99"] else 0
        c = (f["caudal"].get("m3s_max") or 0) / f["caudal"]["p99"] if f["caudal"].get("p99") else 0
        return max(ll, c)
    filas.sort(key=lambda f: (orden[f["nivel"]], -fuerza(f)))
    cuenta = lambda campo: {n: sum(f[campo] == n for f in filas) for n in ("extremo", "fuerte", "normal")}  # noqa: E731
    con_rio = [f for f in filas if f["caudal"]["rio"]]
    return {"calculado": datetime.now(ZoneInfo("America/Lima")).isoformat(timespec="minutes"),
            "ventana_dias": VENTANA, "dias_pronostico": DIAS,
            "conteo": cuenta("nivel"), "conteo_lluvia": cuenta("nivel_lluvia"),
            "conteo_motivo": {m: sum(f["motivo"] == m for f in filas) for m in ("lluvia", "caudal", "lluvia y caudal")},
            "distritos_con_rio": len(con_rio), "distritos_solo_lluvia": len(filas) - len(con_rio),
            "caudal": {"estado": estado_caudal, "rios": rios, "umbrales": umbr_caudal,
                       "fuente": "Pronóstico: GloFAS v4 (Open-Meteo Flood API, river_discharge) en la celda de cada río "
                                 "(data/normales/rios_celdas.csv). Umbrales: percentiles 95 y 99 del caudal diario "
                                 f"{ANIOS_UMBRAL_CAUDAL[0]}-{ANIOS_UMBRAL_CAUDAL[1]} de la misma celda (data/modelo/caudal_rios.csv).",
                       "distritos": {r: ds for r, ds in CUENCA.items()}},
            "distritos": filas,
            "fuente": "Pronóstico: Open-Meteo (modelos meteorológicos). Umbrales: ERA5 1991-2020 (Open-Meteo, archivo histórico), "
                      "percentiles 95 y 99 de los días con lluvia en el centro de cada distrito.",
            "nota": "Aviso propio del proyecto basado en percentiles; no reemplaza los avisos oficiales de SENAMHI. En los "
                    "distritos de valle también cuenta el caudal pronosticado del río; Zarumilla y la sierra usan solo lluvia."}


def main() -> None:
    d = distritos()
    u = umbrales(d)
    pr = pronostico(d)
    umbr_c = umbrales_caudal()
    rios, estado = {}, "ok"
    if not umbr_c:
        estado = "sin dato: no hay data/modelo/caudal_rios.csv para calcular los umbrales; aviso solo con lluvia"
    else:
        try:
            pc = pronostico_caudal(celdas_rios())
            for rio, (fechas, vals) in pc.items():
                if rio in umbr_c:
                    rios[rio] = resumen_caudal(fechas, vals, umbr_c[rio])
            if not any(x.get("estado") == "ok" for x in rios.values()):
                estado = "sin dato: el pronóstico de caudal vino vacío; aviso solo con lluvia"
        except Exception as error:  # noqa: BLE001  el aviso de lluvia no debe caerse por el caudal
            estado = f"sin dato: {error}; aviso solo con lluvia"
            print(f"  caudal: {error}")
    expo = {}
    ruta = DASH_DATA / "descargas" / "exposicion_distritos.csv"
    if ruta.exists():
        e = pd.read_csv(ruta)
        e = e[e["escenario"] == "rp100"]
        expo = {(r.departamento, r.provincia, r.distrito): r for r in e.itertuples()}
    salida = armar(u, pr, rios, estado, umbr_c, expo)
    json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("aviso:", salida["conteo"], "· solo lluvia:", salida["conteo_lluvia"], "· motivo:", salida["conteo_motivo"],
          "· caudal:", estado, {r: (x.get("nivel"), x.get("m3s_max"), x.get("p95")) for r, x in rios.items()})


if __name__ == "__main__":
    main()
