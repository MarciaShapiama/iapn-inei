"""Datos para la pestaña «¿Dónde actuar primero?», la historia de cada distrito y la comparación con 2017 y 2023.

No estima nada nuevo: ordena y cruza salidas que ya existen en el repositorio.
    dashboard/data/inundacion.json        colegios y establecimientos de salud dentro de la zona inundable 1 en 100 años
    dashboard/data/distritos_tumbes_piura.geojson   límites de los 78 distritos (para ubicar cada colegio y establecimiento)
    dashboard/data/panel_distritos.json   pobreza monetaria 2018 (INEI) por distrito
    data/modelo/base_distrito_semana.csv  lluvia, caudal y mar por distrito y semana
    data/modelo/sinpad/sinpad_semanal.csv emergencias del SINPAD por distrito y semana (la etiqueta del modelo)

Salida: dashboard/data/prioridades.json · Uso: python src/tablero_prioridades.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

R = Path(__file__).resolve().parents[1]
DD = R / "dashboard" / "data"
BASE = R / "data" / "modelo" / "base_distrito_semana.csv"
SINPAD = R / "data" / "modelo" / "sinpad" / "sinpad_semanal.csv"
SALIDA = DD / "prioridades.json"
ANIOS_COMPARAR = (2017, 2023)


def ubicar(puntos: list[dict], feats: list[dict]) -> list[str | None]:
    """UBIGEO del distrito que contiene cada punto (por coordenadas, no por el nombre escrito en el padrón)."""
    geoms = [shape(f["geometry"]) for f in feats]
    arbol = STRtree(geoms)
    out = []
    for p in puntos:
        pt = Point(p["lon"], p["lat"])
        idx = [i for i in arbol.query(pt) if geoms[i].covers(pt)]
        out.append(feats[idx[0]]["properties"]["ubigeo"] if idx else None)
    return out


def servicios(feats: list[dict]) -> dict:
    """Colegios (con alumnos) y establecimientos de salud dentro de la zona inundable, por distrito."""
    e = json.load(open(DD / "inundacion.json", encoding="utf-8"))["eventos"]["rp100"]
    out: dict[str, dict] = {}
    for clave, lista in (("colegios", e.get("colegios_lista", [])), ("salud", e.get("salud_lista", []))):
        dentro = [x for x in lista if x.get("clase") == "dentro"]
        for x, u in zip(dentro, ubicar(dentro, feats)):
            if not u:
                continue
            d = out.setdefault(u, {"colegios": 0, "alumnos": 0, "salud": 0, "colegios_mayores": [], "salud_lista": []})
            if clave == "colegios":
                d["colegios"] += 1
                d["alumnos"] += int(x.get("alumnos") or 0)
                d["colegios_mayores"].append([x["nombre"], int(x.get("alumnos") or 0)])
            else:
                d["salud"] += 1
                d["salud_lista"].append([x["nombre"].title(), x.get("categoria") or x.get("tipo") or ""])
    for d in out.values():
        d["colegios_mayores"] = sorted(d["colegios_mayores"], key=lambda z: -z[1])[:3]
        d["salud_lista"] = d["salud_lista"][:4]
    return out


def historia(b: pd.DataFrame) -> dict:
    """Emergencias por lluvia o inundación del SINPAD por año y distrito (2003-2025) y viviendas afectadas o destruidas.
    Es la misma etiqueta con que se entrena el modelo (data/modelo/sinpad/sinpad_semanal.csv)."""
    s = pd.read_csv(SINPAD, parse_dates=["semana"])
    s["ubigeo"] = s.clave.map(b.drop_duplicates("clave").set_index("clave").ubigeo)
    s["anio"] = s.semana.dt.year
    s["viviendas"] = s.viv_afectadas.fillna(0) + s.viv_destruidas.fillna(0)
    s = s[(s.anio >= 2003) & (s.anio <= 2025) & s.ubigeo.notna()]
    g = s.groupby(["ubigeo", "anio"]).agg(emergencias=("eventos", "sum"), viviendas=("viviendas", "sum"))
    anios = list(range(2003, 2026))
    out = {}
    for u, x in g.groupby(level=0):  # distritos sin ninguna emergencia quedan fuera: el tablero los muestra en cero
        x = x.droplevel(0).reindex(anios, fill_value=0)
        out[u] = {"emergencias": [int(v) for v in x.emergencias], "viviendas": [int(v) for v in x.viviendas]}
    return {"anios": anios, "distritos": out}


def comparacion(b: pd.DataFrame) -> dict:
    """Mar, lluvia y caudal semana a semana del año en curso frente a 2017 y 2023 (mismas semanas del año)."""
    actual = int(b.anio.max())
    # semana de referencia: la última semana completa del año en curso (con lluvia de 7 días en casi todos los distritos)
    completa = b[b.anio == actual].groupby("semana_anio").lluvia_7d.apply(lambda x: x.notna().mean())
    ref = int(completa[completa >= 0.9].index.max())
    out = {"anio_actual": actual, "anios": [*ANIOS_COMPARAR, actual], "semana_referencia": ref, "series": {}}
    for a in out["anios"]:
        x = b[(b.anio == a) & ((b.anio != actual) | (b.semana_anio <= ref))]   # el año en curso llega hasta la semana completa
        mar = x.groupby("semana_anio").nino12.first()
        lluvia = x.groupby(["semana_anio", "departamento"]).lluvia_30d.mean().unstack()
        rio = x[x.rio.notna()].groupby(["semana_anio", "rio"]).caudal_razon.median().unstack()
        sem = sorted(set(mar.index))
        r = lambda s, k: [None if k not in s or pd.isna(s[k].get(w)) else round(float(s[k].get(w)), 2) for w in sem]  # noqa: E731
        out["series"][str(a)] = {
            "semana_anio": [int(w) for w in sem],
            "nino12": [None if pd.isna(mar.get(w)) else round(float(mar.get(w)), 2) for w in sem],
            "lluvia_30d_piura": r(lluvia, "Piura"), "lluvia_30d_tumbes": r(lluvia, "Tumbes"),
            "caudal_razon": {str(rr): r(rio, rr) for rr in rio.columns}}
    return out


def main() -> None:
    feats = json.load(open(DD / "distritos_tumbes_piura.geojson", encoding="utf-8"))["features"]
    panel = json.load(open(DD / "panel_distritos.json", encoding="utf-8"))
    pobreza = {d["ubigeo"]: d.get("pct_pobreza_total") for d in panel["distritos"]}
    b = pd.read_csv(BASE, dtype={"ubigeo": str},
                    usecols=["clave", "ubigeo", "semana", "semana_anio", "departamento", "rio", "nino12", "lluvia_30d",
                             "lluvia_7d", "caudal_razon", "emergencias", "viv_afectadas"])
    b["ubigeo"] = b.ubigeo.str.zfill(6)
    b["anio"] = b.semana.str[:4].astype(int)
    serv = servicios(feats)
    out = {"distritos": {f["properties"]["ubigeo"]: {**serv.get(f["properties"]["ubigeo"], {"colegios": 0, "alumnos": 0, "salud": 0}),
                                                     "pobreza_pct": None if pobreza.get(f["properties"]["ubigeo"]) is None
                                                     else round(pobreza[f["properties"]["ubigeo"]], 1)}
                         for f in feats},
           "historia": historia(b), "comparacion": comparacion(b),
           "fuentes": {"colegios": "ESCALE (MINEDU), Censo Educativo 2025, locales dentro de la zona inundable JRC 1 en 100 años",
                       "salud": "RENIPRESS (SUSALUD), establecimientos dentro de la misma zona",
                       "pobreza": "INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2018",
                       "historia": "INDECI, SINPAD: emergencias por lluvia intensa o inundación, 2003-2025"}}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tot = out["distritos"].values()
    print(f"  {SALIDA.name}: {SALIDA.stat().st_size // 1024} KB · colegios {sum(d['colegios'] for d in tot)}, "
          f"alumnos {sum(d['alumnos'] for d in tot)}, salud {sum(d['salud'] for d in tot)}")


if __name__ == "__main__":
    main()
