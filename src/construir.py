"""Prepara los datos del tablero (dashboard/data/*.json) a partir del histórico guardado.

    mar.json        rejilla de anomalías de los últimos 20 días (para el mapa animado)
    regiones.json   por región costera y día: anomalía media, máxima, magnitud, tendencia y racha cálida
                    (usa TODO el histórico acumulado, no solo los 20 días)
    indices.json    regiones Niño (semanal) e ICEN (mensual)
    economia.json   producción por sector (INEI vía BCRP) y electricidad COES mensual y diaria
    picos.json      rejilla de los días pico de 1983, 1998, 2017 y 2023 para comparar
    resumen.json    titulares del día
    zonas.json      zonas afectadas (provincias costeras): mar de enfrente, lluvia, río e índice de alerta
    zonas.geojson   contorno de esas provincias

El mar de cada región costera son las celdas a menos de 150 km de su territorio (se asigna cada
celda a la región más cercana).

Uso: python src/construir.py
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


def _limite(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return max(a, min(b, x))


def zonas(mar: pd.DataFrame) -> tuple[dict, dict] | None:
    """Provincias costeras: mar a menos de 100 km, lluvia vs. normal, caudal del río vs. normal, alerta."""
    if not (DATA / "zonas_lluvia.csv").exists():
        return None
    from descargar_zonas import RIOS, ZONAS
    g = json.load(open(DATA / "provincias.geojson", encoding="utf-8"))
    formas = {(f["properties"]["departamento"], f["properties"]["provincia"]): f for f in g["features"]}
    pts = pd.read_csv(DATA / "zonas_puntos.csv")
    ll = pd.read_csv(DATA / "zonas_lluvia.csv")
    nl = leer_csv("normales/lluvia_diaria")
    q = leer_csv("rios_caudal")
    nq = leer_csv("normales/caudal_diario")
    celdas_rio = leer_csv("normales/rios_celdas")
    hoy = datetime.now(ZoneInfo("America/Lima")).date().isoformat()
    fechas = sorted(ll["fecha"].unique())
    fechas_mar = sorted(mar["fecha"].unique())[-DIAS_VENTANA:]
    ventana = mar[mar["fecha"].isin(fechas_mar)]
    celdas = ventana[["lat", "lon"]].drop_duplicates()
    salida, geo = [], {"type": "FeatureCollection", "features": []}
    for dep, prov in ZONAS:
        f = formas[(dep, prov)]
        forma = shape(f["geometry"])
        p = pts[pts["provincia"] == prov].iloc[0]
        # mar de enfrente: celdas a menos de 100 km del territorio de la provincia
        cerca = [(la, lo) for la, lo in zip(celdas["lat"], celdas["lon"]) if forma.distance(Point(lo, la)) * KM_GRADO <= 100]
        m = ventana.set_index(["lat", "lon"]).loc[cerca].reset_index() if cerca else ventana.iloc[0:0]
        mar_dia = m.groupby("fecha")["anom"].mean().reindex(fechas_mar)
        # lluvia y su normal (promedio 1991-2020 del mismo día del año)
        x = ll[ll["provincia"] == prov].set_index("fecha").reindex(fechas)
        normal = (nl[nl["provincia"] == prov].set_index("md")["lluvia_normal"] if nl is not None else pd.Series(dtype=float))
        x["normal"] = [normal.get(fe[5:], np.nan) for fe in fechas]
        obs = x[x.index < hoy]
        ll20, n20 = float(obs["lluvia_mm"].sum()), float(obs["normal"].sum())
        pron7 = float(x[x.index >= hoy]["lluvia_mm"].sum())
        # río más cercano (a menos de 60 km)
        rio = None
        if celdas_rio is not None and q is not None:
            dist = {r: forma.distance(Point(lo, la)) * KM_GRADO for r, (la, lo) in RIOS.items()}
            nombre, km = min(dist.items(), key=lambda t: t[1])
            if km <= 60 and nombre in set(q["rio"]):
                y = q[q["rio"] == nombre].set_index("fecha").reindex(fechas)
                nr = nq[nq["rio"] == nombre].set_index("md") if nq is not None else pd.DataFrame()
                y["normal"] = [nr["caudal_normal"].get(fe[5:], np.nan) if len(nr) else np.nan for fe in fechas]
                y["p90"] = [nr["caudal_p90"].get(fe[5:], np.nan) if len(nr) else np.nan for fe in fechas]
                c = celdas_rio[celdas_rio["rio"] == nombre].iloc[0]
                pasado = y[y.index < hoy]
                q_hoy = float(pasado["caudal_m3s"].dropna().iloc[-1]) if pasado["caudal_m3s"].notna().any() else None
                q_max = float(y["caudal_m3s"].max()) if y["caudal_m3s"].notna().any() else None
                rio = {"nombre": nombre, "lat": float(c["lat"]), "lon": float(c["lon"]),
                       "caudal": [None if pd.isna(v) else round(float(v), 1) for v in y["caudal_m3s"]],
                       "normal": [None if pd.isna(v) else round(float(v), 1) for v in y["normal"]],
                       "p90": [None if pd.isna(v) else round(float(v), 1) for v in y["p90"]],
                       "hoy": q_hoy, "max_27d": q_max,
                       "normal_hoy": None if pasado["normal"].dropna().empty else float(pasado["normal"].dropna().iloc[-1])}
        # índice de alerta (0-100): mar 50, lluvia 25, río 25 (lectura indicativa, ver Método)
        a_mar = _limite((float(mar_dia.dropna().iloc[-1]) if mar_dia.notna().any() else 0) / 4) * 50
        a_ll = _limite((ll20 + pron7 - n20) / 50) * 25
        a_rio = 0.0
        if rio and rio["max_27d"] is not None:
            p90 = max([v for v in rio["p90"] if v is not None] or [np.nan])
            if p90 and not np.isnan(p90):
                a_rio = _limite(rio["max_27d"] / p90 / 1.5) * 25
        indice = round(a_mar + a_ll + a_rio)
        nivel = "Alerta alta" if indice >= 60 else "Alerta" if indice >= 40 else "Vigilancia" if indice >= 20 else "Normal"
        b = forma.bounds
        salida.append({
            "departamento": dep, "provincia": prov, "lat": float(p["lat"]), "lon": float(p["lon"]),
            "bbox": [round(v, 3) for v in b],
            "mar": [None if pd.isna(v) else round(float(v), 2) for v in mar_dia],
            "mar_celdas": len(cerca),
            "lluvia": [None if pd.isna(v) else round(float(v), 1) for v in x["lluvia_mm"]],
            "lluvia_normal": [None if pd.isna(v) else round(float(v), 2) for v in x["normal"]],
            "tmax": [None if pd.isna(v) else round(float(v), 1) for v in x["tmax"]],
            "lluvia_20d": round(ll20, 1), "normal_20d": round(n20, 1), "pronostico_7d": round(pron7, 1),
            "rio": rio, "indice": indice, "nivel": nivel,
            "componentes": {"mar": round(a_mar), "lluvia": round(a_ll), "rio": round(a_rio)},
        })
        geo["features"].append({"type": "Feature", "properties": {"provincia": prov, "departamento": dep},
                                "geometry": json.loads(json.dumps(forma.simplify(0.003).__geo_interface__))})
    anios = sorted(int(x.name[:4]) for x in (DATA / "normales" / "lluvia_anios").glob("*.csv.gz"))
    rios_n = len(list((DATA / "normales" / "caudal_rios").glob("*.csv.gz")))
    normal = {"lluvia_anios": len(anios), "lluvia_desde": anios[0] if anios else None, "lluvia_hasta": anios[-1] if anios else None,
              "rios_con_normal": rios_n}
    return {"fechas": fechas, "hoy": hoy, "fechas_mar": fechas_mar, "zonas": salida, "normal": normal}, geo


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
    z = zonas(mar)
    if z:
        escribir("zonas", z[0])
        with open(DASH_DATA / "zonas.geojson", "w", encoding="utf-8") as f:
            json.dump(z[1], f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
