"""Panel de decisiones: tabla priorizada de distritos para REVISIÓN por las autoridades competentes.

Cuatro dimensiones que NO se mezclan en una sola cifra sin mostrarlas por separado:
    peligro          qué tanto del distrito cubre la zona inundable 1 en 100 y 1 en 10 años (JRC) y cuánta agua
                     vio el radar en 2017 y 2023 (evidencia histórica, detección automática)
    exposición       población (WorldPop 2026) y edificaciones (Open Buildings) dentro de la zona 1 en 100 años;
                     colegios y establecimientos de salud dentro y a ≤ 1 km
    vulnerabilidad   pobreza monetaria total 2018 e IDH 2019 (contexto socioeconómico; ver metadatos)
    riesgo estimado  índice RELATIVO 0-100 = promedio de los percentiles de peligro (% área 1 en 100),
                     exposición (población expuesta) y vulnerabilidad (% pobreza). Solo ordena distritos de
                     Tumbes y Piura entre sí para priorizar revisión; NO es una evaluación de riesgo oficial
                     (EVAR / CENEPRED) ni autoriza reubicaciones.

Salidas: dashboard/data/panel_distritos.json y dashboard/data/descargas/panel_distritos.csv
Uso: python src/panel.py   (requiere haber corrido src/impacto.py)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from comun import ahora_lima, escribir_json, registrar_version
from config import DASH_DATA, DATA
from exposicion import CARPETA as EXPO

DESCARGAS = DASH_DATA / "descargas"
SIN = "Sin distrito asignado"


def area_km2(geom) -> float:
    """Área aproximada en km² (proyección equirectangular local; error < 1 % a esta latitud)."""
    import shapely
    from shapely.geometry import shape
    g = shape(geom)
    k = np.array([111.320 * np.cos(np.radians(g.centroid.y)), 110.574])
    return float(shapely.transform(g, lambda c: c * k).area)


def percentil(s: pd.Series) -> pd.Series:
    return 100 * s.rank(pct=True, method="average")


def construir() -> pd.DataFrame:
    x = pd.read_csv(DESCARGAS / "exposicion_distritos.csv", dtype={"ubigeo": str})
    x = x[x["departamento"] != SIN]
    g = json.load(open(EXPO / "distritos.geojson", encoding="utf-8"))
    areas = {(f["properties"]["departamento"], f["properties"]["provincia"], f["properties"]["distrito"]): area_km2(f["geometry"])
             for f in g["features"]}
    base = x[x.escenario == "rp100"][["ubigeo", "departamento", "provincia", "distrito", "poblacion_worldpop_distrito"]].copy()
    base["area_km2"] = [areas[(a, b, c)] for a, b, c in zip(base.departamento, base.provincia, base.distrito)]

    def col(esc, c, nuevo):
        t = x[x.escenario == esc].set_index(["departamento", "provincia", "distrito"])[c].rename(nuevo)
        return base.join(t, on=["departamento", "provincia", "distrito"])[nuevo].fillna(0).to_numpy()

    for esc in ("rp100", "rp10"):
        base[f"km2_{esc}"] = col(esc, "km2", "k")
        base[f"pct_area_{esc}"] = (100 * base[f"km2_{esc}"] / base["area_km2"]).round(2)
    for esc in ("2017", "2023"):
        base[f"km2_radar_{esc}"] = col(esc, "km2", "k") if (x.escenario == esc).any() else np.nan
    base["personas_rp100"] = col("rp100", "personas", "p")
    base["pct_poblacion_rp100"] = (100 * base["personas_rp100"] / base["poblacion_worldpop_distrito"].replace(0, np.nan)).round(1)
    base["edificaciones_rp100"] = col("rp100", "edificaciones", "e")
    for n in ("colegios", "salud"):
        if f"{n}_dentro" in x:
            base[f"{n}_dentro_rp100"] = col("rp100", f"{n}_dentro", "c")
            base[f"{n}_acum_1km_rp100"] = col("rp100", f"{n}_acum_1km", "c")
    try:
        from ubigeo import descargar_tabla
        u = descargar_tabla()[["inei", "pct_pobreza_total", "pct_pobreza_extrema", "idh_2019", "poblacion_2020_est"]]
        base = base.merge(u.rename(columns={"inei": "ubigeo"}), on="ubigeo", how="left")
    except Exception as error:  # noqa: BLE001
        print(f"  vulnerabilidad no disponible: {error}")
        for c in ("pct_pobreza_total", "pct_pobreza_extrema", "idh_2019", "poblacion_2020_est"):
            base[c] = np.nan
    base["p_peligro"] = percentil(base["pct_area_rp100"]).round(1)
    base["p_exposicion"] = percentil(base["personas_rp100"]).round(1)
    base["p_vulnerabilidad"] = percentil(base["pct_pobreza_total"]).round(1)
    completo = base[["p_peligro", "p_exposicion", "p_vulnerabilidad"]].notna().all(axis=1)
    base["riesgo_estimado"] = base[["p_peligro", "p_exposicion", "p_vulnerabilidad"]].mean(axis=1).where(completo).round(1)
    base["prioridad_revision"] = pd.cut(base["riesgo_estimado"], [-1, 40, 65, 101], labels=["Baja", "Media", "Alta"]).astype(str)
    base.loc[~completo, "prioridad_revision"] = "Sin dato suficiente"
    base["ficha"] = [ficha(r) for r in base.to_dict(orient="records")]
    return base.sort_values("riesgo_estimado", ascending=False, na_position="last")


def _n(v, d=0):
    return "s/d" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def ficha(r: dict) -> str:
    t = (f"{r['distrito']} ({r['provincia']}, {r['departamento']}; UBIGEO {r['ubigeo'] or 's/d'}). "
         f"Peligro: la zona inundable de 1 en 100 años cubre {_n(r['km2_rp100'], 1)} km² ({_n(r['pct_area_rp100'], 1)} % del distrito); "
         f"la de 1 en 10 años, {_n(r['pct_area_rp10'], 1)} %. ")
    if not np.isnan(r.get("km2_radar_2017", np.nan)):
        t += f"El radar detectó {_n(r['km2_radar_2017'], 1)} km² de agua nueva en 2017 y {_n(r.get('km2_radar_2023'), 1)} km² en 2023 (detección automática). "
    t += (f"Exposición: unas {_n(r['personas_rp100'])} personas ({_n(r['pct_poblacion_rp100'], 1)} % de la población modelada) y "
          f"{_n(r['edificaciones_rp100'])} edificaciones dentro de la zona 1 en 100 años; "
          f"{_n(r.get('colegios_dentro_rp100'))} locales escolares y {_n(r.get('salud_dentro_rp100'))} establecimientos de salud dentro "
          f"({_n(r.get('colegios_acum_1km_rp100'))} y {_n(r.get('salud_acum_1km_rp100'))} a ≤ 1 km). "
          f"Vulnerabilidad: pobreza monetaria {_n(r['pct_pobreza_total'], 1)} % (2018), IDH {_n(r['idh_2019'], 3)} (2019). "
          f"Prioridad de revisión: {r['prioridad_revision']} (índice relativo {_n(r['riesgo_estimado'], 0)}/100). "
          "Es una lectura estadística para priorizar estudios; no sustituye la evaluación de riesgo oficial.")
    return t


def main() -> None:
    p = construir()
    DESCARGAS.mkdir(parents=True, exist_ok=True)
    csv = DESCARGAS / "panel_distritos.csv"
    p.to_csv(csv, index=False, encoding="utf-8-sig")
    escribir_json(DASH_DATA / "panel_distritos.json", {
        "generado": ahora_lima(),
        "definiciones": {
            "peligro": "% del área del distrito en la zona inundable JRC 1 en 100 años (escenario).",
            "exposicion": "Población WorldPop 2026 dentro de la zona 1 en 100 años (potencialmente expuesta).",
            "vulnerabilidad": "% de pobreza monetaria total 2018 (INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2018; punto medio del intervalo al 95 %).",
            "riesgo_estimado": "Promedio de percentiles de las tres dimensiones, 0-100, relativo a los 78 distritos. "
                               "Ordena para revisión; no es una evaluación de riesgo oficial.",
            "prioridad_revision": "Alta ≥ 65, Media 40-65, Baja < 40 del índice relativo."},
        "distritos": json.loads(p.to_json(orient="records", force_ascii=False))}, indent=None)
    registrar_version([csv, DASH_DATA / "panel_distritos.json"], DATA / "versiones" / "manifiesto.csv", "panel")
    print(p[["distrito", "provincia", "pct_area_rp100", "personas_rp100", "pct_pobreza_total", "riesgo_estimado", "prioridad_revision"]]
          .head(12).to_string(index=False))
    print(f"{len(p)} distritos; prioridad: {p['prioridad_revision'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
