"""Prepara los datos del tablero (dashboard/data/*.json) a partir del histórico guardado.

    mar.json        rejilla de anomalías de los últimos 20 días (para el mapa animado)
    regiones.json   por región costera y día: anomalía media, máxima, magnitud, tendencia y racha cálida
                    (usa TODO el histórico acumulado, no solo los 20 días)
    indices.json    regiones Niño (semanal) e ICEN (mensual)
    economia.json   producción por sector (INEI vía BCRP) y electricidad COES mensual y diaria
    picos.json      rejilla de los días pico de 1983, 1998, 2017 y 2023 para comparar
    resumen.json    titulares del día

El mar de cada región costera son las celdas a menos de 150 km de su territorio (se asigna cada
celda a la región más cercana).

Uso: python src/construir.py
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape

from config import (COSTEROS, DASH_DATA, DATA, DIAS_VENTANA, DIST_MAX_KM, HIST_MAR, MAGNITUDES, PICOS,
                    SERIES_BCRP, magnitud)

KM_GRADO = 111.0
NOMBRES = {"LA LIBERTAD": "La Libertad"}


def bonito(n: str) -> str:
    return NOMBRES.get(n, n.title())


def leer_csv(nombre: str) -> pd.DataFrame | None:
    ruta = DATA / f"{nombre}.csv"
    return pd.read_csv(ruta) if ruta.exists() else None


def cargar_mar() -> pd.DataFrame:
    partes = []
    for ruta in sorted(HIST_MAR.glob("*.csv.gz")):
        d = pd.read_csv(ruta)
        d["fecha"] = ruta.name[:10]
        partes.append(d)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["lat", "lon", "anom", "fecha"])


def asignar_celdas(celdas: pd.DataFrame) -> pd.Series:
    """Región costera más cercana a cada celda de mar (o vacío si está a más de DIST_MAX_KM)."""
    geo = json.load(open(DATA / "departamentos.geojson", encoding="utf-8"))
    formas = {f["properties"]["NOMBDEP"]: shape(f["geometry"]) for f in geo["features"]
              if f["properties"]["NOMBDEP"] in COSTEROS}
    region = []
    for lat, lon in zip(celdas["lat"], celdas["lon"]):
        p = Point(lon, lat)
        esc = math.cos(math.radians(lat))
        dist = {n: f.distance(p) * KM_GRADO * (0.5 + 0.5 * esc) for n, f in formas.items()}
        n, km = min(dist.items(), key=lambda x: x[1])
        region.append(n if km <= DIST_MAX_KM else "")
    return pd.Series(region, index=celdas.index)


def racha(valores: list[float], umbral: float = 0.4) -> int:
    n = 0
    for v in reversed(valores):
        if v is None or not v >= umbral:
            break
        n += 1
    return n


def regiones(mar: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    celdas = mar[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    celdas["region"] = asignar_celdas(celdas)
    m = mar.merge(celdas, on=["lat", "lon"])
    m = m[m["region"] != ""]
    g = m.groupby(["region", "fecha"])["anom"]
    t = pd.DataFrame({"media": g.mean(), "max": g.max(), "p_calido": g.apply(lambda x: (x >= 0.4).mean()),
                      "celdas": g.size()}).reset_index()
    salida = {}
    orden = [r for r in COSTEROS if r in set(t["region"])]
    for r in orden:
        x = t[t["region"] == r].sort_values("fecha")
        ult = x.tail(DIAS_VENTANA)
        y = ult["media"].to_numpy()
        pend = float(np.polyfit(np.arange(len(y)), y, 1)[0] * 7) if len(y) >= 5 else None  # °C por semana
        salida[r] = {
            "nombre": bonito(r),
            "fechas": x["fecha"].tolist(),
            "media": x["media"].round(2).tolist(),
            "max": x["max"].round(2).tolist(),
            "p_calido": (100 * x["p_calido"]).round(0).tolist(),
            "hoy": round(float(y[-1]), 2),
            "max_hoy": round(float(ult["max"].iloc[-1]), 2),
            "magnitud": magnitud(float(y[-1])),
            "tendencia_semana": None if pend is None else round(pend, 2),
            "racha_calida": racha(x["media"].tolist()),
            "celdas": int(ult["celdas"].iloc[-1]),
        }
    return {"orden": orden, "regiones": salida}, celdas


def rejilla(mar: pd.DataFrame, celdas: pd.DataFrame) -> dict:
    fechas = sorted(mar["fecha"].unique())[-DIAS_VENTANA:]
    lats = sorted(mar["lat"].unique())
    lons = sorted(mar["lon"].unique())
    piv = {}
    for f in fechas:
        p = mar[mar["fecha"] == f].pivot_table(index="lat", columns="lon", values="anom")
        p = p.reindex(index=lats, columns=lons)
        piv[f] = [[None if pd.isna(v) else round(float(v), 2) for v in fila] for fila in p.to_numpy()]
    reg = celdas.pivot_table(index="lat", columns="lon", values="region", aggfunc="first").reindex(
        index=lats, columns=lons)
    return {"fechas": fechas, "lats": [float(v) for v in lats], "lons": [float(v) for v in lons],
            "paso": float(lats[1] - lats[0]) if len(lats) > 1 else 0.5, "anom": piv,
            "region": [[(v if isinstance(v, str) else "") for v in fila] for fila in reg.to_numpy()]}


def picos(lats: list, lons: list, celdas: pd.DataFrame) -> dict:
    salida = {}
    for anio, dia in PICOS.items():
        ruta = DATA / "historico" / "picos" / f"{anio}.csv.gz"
        if not ruta.exists():
            continue
        d = pd.read_csv(ruta)
        p = d.pivot_table(index="lat", columns="lon", values="anom").reindex(index=lats, columns=lons)
        x = d.merge(celdas, on=["lat", "lon"])
        x = x[x["region"] != ""]
        salida[anio] = {"fecha": dia,
                        "anom": [[None if pd.isna(v) else round(float(v), 2) for v in f] for f in p.to_numpy()],
                        "regiones": {r: round(float(v), 2) for r, v in x.groupby("region")["anom"].mean().items()}}
    return salida


def indices() -> dict:
    out = {}
    n = leer_csv("noaa_semanal")
    if n is not None:
        n = n[n["semana"] >= "2014-01-01"]
        out["semanal"] = {"semana": n["semana"].tolist(),
                          **{c: n[c].round(2).tolist() for c in ["nino12", "nino3", "nino34", "nino4"]}}
    i = leer_csv("icen")
    if i is not None:
        i = i[i["fecha"] >= "1980-01"]
        out["icen"] = {"fecha": i["fecha"].tolist(), "valor": i["icen"].round(2).tolist()}
    return out


def economia() -> dict:
    out = {}
    b = leer_csv("bcrp_sectores")
    if b is not None:
        b = b[b["fecha"] >= "2014-01"]
        fechas = sorted(b["fecha"].unique())
        out["sectores"] = {"fechas": fechas, "series": {
            nombre: b[b["codigo"] == cod].set_index("fecha")["valor"].reindex(fechas).round(2)
            .where(lambda s: s.notna(), None).tolist()
            for cod, nombre in SERIES_BCRP.items() if cod in set(b["codigo"])}}
    c = leer_csv("coes_mensual")
    if c is not None:
        c = c[c["fecha"] >= "2016-01"]
        out["coes_mensual"] = {"fecha": c["fecha"].tolist(), "var12": [None if pd.isna(v) else v for v in c["var12"]],
                               "gwh": [None if pd.isna(v) else round(v / 1000, 1) for v in c["mwh"]]}
    d = leer_csv("coes_diario")
    if d is not None:
        out["coes_diario"] = {k: [None if pd.isna(v) else (round(v / 1000, 2) if k != "fecha" and k != "var_pct" else v)
                                  for v in d[col]]
                              for k, col in [("fecha", "fecha"), ("gwh", "mwh"), ("gwh_anterior", "mwh_anio_anterior"),
                                             ("var_pct", "var_pct")]}
    return out


def resumen(reg: dict, idx: dict, eco: dict, n_dias: int) -> dict:
    r = reg["regiones"]
    norte = [x for x in ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"] if x in r]
    peor = max(r, key=lambda k: r[k]["hoy"]) if r else None
    icen = idx.get("icen", {})
    sem = idx.get("semanal", {})
    return {
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "ultimo_dia_mar": r[peor]["fechas"][-1] if peor else None,
        "dias_historico": n_dias,
        "region_mas_calida": peor and {"region": r[peor]["nombre"], "anom": r[peor]["hoy"],
                                       "magnitud": r[peor]["magnitud"]},
        "norte_media": round(float(np.mean([r[x]["hoy"] for x in norte])), 2) if norte else None,
        "regiones_calidas": sum(1 for x in r.values() if x["hoy"] >= 0.4),
        "regiones_total": len(r),
        "nino12_semana": sem and {"semana": sem["semana"][-1], "valor": sem["nino12"][-1]},
        "nino34_semana": sem and {"semana": sem["semana"][-1], "valor": sem["nino34"][-1]},
        "icen_ultimo": icen and {"fecha": icen["fecha"][-1], "valor": icen["valor"][-1],
                                 "magnitud": magnitud(icen["valor"][-1])},
        "magnitudes": [{"desde": lo, "hasta": hi, "nombre": n} for lo, hi, n in MAGNITUDES],
    }


def escribir(nombre: str, obj) -> None:
    DASH_DATA.mkdir(parents=True, exist_ok=True)
    with open(DASH_DATA / f"{nombre}.json", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  {nombre}.json: {(DASH_DATA / f'{nombre}.json').stat().st_size // 1024} KB")


def main() -> None:
    mar = cargar_mar()
    print(f"Histórico del mar: {mar['fecha'].nunique()} días")
    idx, eco = indices(), economia()
    escribir("indices", idx)
    escribir("economia", eco)
    if mar.empty:
        escribir("resumen", resumen({"regiones": {}}, idx, eco, 0))
        return
    reg, celdas = regiones(mar)
    rj = rejilla(mar, celdas)
    escribir("regiones", reg)
    escribir("mar", rj)
    escribir("picos", picos(rj["lats"], rj["lons"], celdas))
    escribir("resumen", resumen(reg, idx, eco, int(mar["fecha"].nunique())))


if __name__ == "__main__":
    main()
