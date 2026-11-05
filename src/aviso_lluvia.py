"""Aviso de lluvia por distrito para los próximos días (Tumbes y Piura).

El radar solo ve el agua cuando el satélite pasa y después de que ocurre. Para anticiparse se usa el pronóstico
de lluvia: para cada distrito se compara la lluvia pronosticada con lo que es extremo EN ESE MISMO LUGAR.

Umbrales (se guardan en data/normales/umbrales_lluvia_distritos.csv):
    reanálisis ERA5 1991-2020 (Open-Meteo) que el tablero ya guarda por provincia; días con lluvia (>= 1 mm);
    percentiles 95 y 99. Cada distrito usa el umbral de su provincia (bajar ERA5 para 76 puntos y 30 años supera
    el límite gratuito diario de Open-Meteo).
Pronóstico (cada día): Open-Meteo, lluvia diaria de los próximos 7 días en el mismo punto.
Niveles (por el día más lluvioso de los próximos 3 días):
    "extremo"  lluvia de un día por encima del percentil 99 del lugar
    "fuerte"   por encima del percentil 95
    "normal"   por debajo
Es un criterio por percentiles parecido al que usa SENAMHI para calificar la lluvia, pero NO es un aviso oficial.

Salida: dashboard/data/aviso_lluvia.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DASH_DATA, DATA  # noqa: E402
from descargar_zonas import pedir  # noqa: E402

UMBRALES = DATA / "normales" / "umbrales_lluvia_distritos.csv"
SALIDA = DASH_DATA / "aviso_lluvia.json"
DIAS = 7
VENTANA = 3            # días que cuentan para el nivel


def distritos() -> pd.DataFrame:
    from shapely.geometry import shape
    g = json.load(open(DATA / "exposicion" / "distritos.geojson", encoding="utf-8"))
    filas = []
    for f in g["features"]:
        p = shape(f["geometry"]).representative_point()
        pr = f["properties"]
        filas.append({"departamento": pr["departamento"], "provincia": pr["provincia"], "distrito": pr["distrito"],
                      "lat": round(p.y, 4), "lon": round(p.x, 4)})
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
    if np.isnan(p95):
        return "sin umbral"
    if mm > p99:
        return "extremo"
    if mm > p95:
        return "fuerte"
    return "normal"


def main() -> None:
    d = distritos()
    u = umbrales(d)
    pr = pronostico(d)
    expo = {}
    ruta = DASH_DATA / "descargas" / "exposicion_distritos.csv"
    if ruta.exists():
        e = pd.read_csv(ruta)
        e = e[e["escenario"] == "rp100"]
        expo = {(r.departamento, r.provincia, r.distrito): r for r in e.itertuples()}
    filas = []
    for r in u.itertuples():
        k = (r.departamento, r.provincia, r.distrito)
        if k not in pr:
            continue
        fechas, mm = pr[k]
        v = mm[:VENTANA]
        i = int(np.argmax(v))
        x = expo.get(k)
        filas.append({"departamento": r.departamento, "provincia": r.provincia, "distrito": r.distrito,
                      "nivel": nivel(v[i], r.p95, r.p99), "mm_dia_max": round(v[i], 1), "fecha_max": fechas[i],
                      "mm_7d": round(sum(mm), 1), "p95": r.p95, "p99": r.p99,
                      "lluvia_diaria": [round(y, 1) for y in mm], "fechas": fechas,
                      "personas_zona_inundable": None if x is None else int(x.personas),
                      "colegios_zona_inundable": None if x is None else int(x.colegios_dentro),
                      "salud_zona_inundable": None if x is None else int(x.salud_dentro)})
    orden = {"extremo": 0, "fuerte": 1, "normal": 2, "sin umbral": 3}
    filas.sort(key=lambda f: (orden[f["nivel"]], -(f["mm_dia_max"] / f["p99"] if f["p99"] else 0)))
    conteo = {n: sum(f["nivel"] == n for f in filas) for n in ("extremo", "fuerte", "normal")}
    salida = {"calculado": datetime.now(ZoneInfo("America/Lima")).isoformat(timespec="minutes"),
              "ventana_dias": VENTANA, "dias_pronostico": DIAS, "conteo": conteo, "distritos": filas,
              "fuente": "Pronóstico: Open-Meteo (modelos meteorológicos). Umbrales: ERA5 1991-2020 (Open-Meteo, archivo histórico), "
                        "percentiles 95 y 99 de los días con lluvia en el centro de cada distrito.",
              "nota": "Aviso propio del proyecto basado en percentiles; no reemplaza los avisos oficiales de SENAMHI."}
    json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("aviso de lluvia:", conteo, "· primeros:", [(f["distrito"], f["nivel"], f["mm_dia_max"]) for f in filas[:5]])


if __name__ == "__main__":
    main()
