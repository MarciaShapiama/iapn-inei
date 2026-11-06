"""Códigos UBIGEO (INEI) y variables distritales de contexto para los distritos de Tumbes y Piura.

Los límites distritales del proyecto vienen del INEI (78 distritos) y ya traen su UBIGEO (src/exposicion.py). Aquí se
les suman variables de contexto de la tabla de equivalencias UBIGEO INEI/RENIEC compilada en
https://github.com/jmcastagnetto/ubigeo-peru-aumentado (licencia MIT, última actualización 2022-01). Si un mapa
no trae UBIGEO (versiones anteriores, GADM), se empata por nombre como antes.

Variables que se toman de esa tabla, con su origen declarado por el compilador (verificar contra la publicación
original antes de citarlas como cifra oficial):
    superficie           km² (INEI)
    pob_densidad_2020    hab/km² 2020 (estimación; población = superficie × densidad)
    pct_pobreza_total    % pobreza monetaria total (Mapa de pobreza distrital INEI 2018)
    pct_pobreza_extrema  % pobreza extrema (idem)
    idh_2019             Índice de Desarrollo Humano 2019 (PNUD)

Salida: data/exposicion/ubigeo_distritos.csv (se descarga una vez; --forzar para volver a bajar).
Uso: python src/ubigeo.py
"""
from __future__ import annotations

import io
import json
import sys
import unicodedata

import pandas as pd

from comun import descargar
from config import DATA

URL = "https://raw.githubusercontent.com/jmcastagnetto/ubigeo-peru-aumentado/main/ubigeo_distrito.csv"
CARPETA = DATA / "exposicion"
DESTINO = CARPETA / "ubigeo_distritos.csv"
COLUMNAS = ["inei", "departamento", "provincia", "distrito", "superficie", "pob_densidad_2020",
            "pct_pobreza_total", "pct_pobreza_extrema", "idh_2019"]
# Diferencias de escritura GADM -> INEI conocidas (clave normalizada)
ALIAS = {"TAMBOGRANDE": "TAMBOGRANDE", "LAMATANZA": "LAMATANZA", "SANTACATALINADEMOSSA": "SANTACATALINADEMOSSA",
         "CONTRALMIRANTEVILAR": "CONTRALMIRANTEVILLAR", "VEINTISEISDEOCTUBRE": "VEINTISEISDEOCTUBRE"}


def norm(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    x = "".join(c for c in x if c.isalnum())
    return ALIAS.get(x, x)


def _plano(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


def _repetidos() -> set[str]:
    """departamento+distrito que se repiten en Tumbes y Piura (hoy solo SALITRAL: Morropón y Sullana)."""
    n = pd.read_csv(CARPETA / "nombres_distritos.csv", dtype=str)
    k = n["departamento"].map(_plano) + n["distrito"].map(_plano)
    return set(k[k.duplicated(keep=False)])


def clave_distrito(departamento, provincia, distrito) -> str:
    """Clave de distrito que usan la base del modelo y los scripts: DEPARTAMENTO+DISTRITO sin tildes ni espacios.
    Si el nombre se repite en el departamento (los dos Salitral), se agrega _PROVINCIA para que no se mezclen."""
    k = _plano(departamento) + _plano(distrito)
    if k in REPETIDOS:
        k += "_" + _plano(provincia)
    return k


REPETIDOS = _repetidos() if (CARPETA / "nombres_distritos.csv").exists() else {"PIURASALITRAL"}


def descargar_tabla(forzar: bool = False) -> pd.DataFrame:
    if DESTINO.exists() and not forzar:
        return pd.read_csv(DESTINO, dtype={"inei": str})
    t = pd.read_csv(io.StringIO(descargar(URL).text), dtype={"inei": str, "reniec": str})
    t = t[t["departamento"].isin(["PIURA", "TUMBES"])][COLUMNAS].copy()
    for c in COLUMNAS[4:]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["poblacion_2020_est"] = (t["superficie"] * t["pob_densidad_2020"]).round()
    CARPETA.mkdir(parents=True, exist_ok=True)
    t.to_csv(DESTINO, index=False)
    return t


def empatar(distritos_geojson=None, tabla: pd.DataFrame | None = None) -> pd.DataFrame:
    """Devuelve una fila por distrito del mapa con su UBIGEO (o vacío si no empata)."""
    g = distritos_geojson or json.load(open(CARPETA / "distritos.geojson", encoding="utf-8"))
    t = tabla if tabla is not None else descargar_tabla()
    t = t.assign(k=[norm(a) + "|" + norm(b) + "|" + norm(c) for a, b, c in zip(t["departamento"], t["provincia"], t["distrito"])])
    t_dist = t.assign(kd=[norm(a) + "|" + norm(c) for a, c in zip(t["departamento"], t["distrito"])])
    por_k = t.set_index("k")
    filas = []
    for i, f in enumerate(g["features"], start=1):
        p = f["properties"]
        k = norm(p["departamento"]) + "|" + norm(p["provincia"]) + "|" + norm(p["distrito"])
        fila = {"id_raster": i, "departamento": p["departamento"], "provincia": p["provincia"], "distrito": p["distrito"]}
        if p.get("ubigeo"):                         # mapa del INEI: el UBIGEO viene en el propio límite
            fila["inei"] = p["ubigeo"]; fila["empate"] = "ubigeo_del_mapa"
        elif k in por_k.index:
            fila.update(por_k.loc[k, ["inei"]].to_dict()); fila["empate"] = "exacto"
        else:  # mismo departamento y distrito, provincia escrita distinto
            kd = norm(p["departamento"]) + "|" + norm(p["distrito"])
            c = t_dist[t_dist["kd"] == kd]
            if len(c) == 1:
                fila["inei"] = c["inei"].iloc[0]; fila["empate"] = "por_distrito"
            else:
                fila["inei"] = None; fila["empate"] = "sin_empate"
        filas.append(fila)
    out = pd.DataFrame(filas).rename(columns={"inei": "ubigeo"})
    return out.merge(t.drop(columns=["k", "departamento", "provincia", "distrito"]).rename(columns={"inei": "ubigeo"}),
                     on="ubigeo", how="left")


if __name__ == "__main__":
    tabla = descargar_tabla("--forzar" in sys.argv)
    e = empatar(tabla=tabla)
    print(f"Distritos del mapa: {len(e)}; empates: {e['empate'].value_counts().to_dict()}")
    print(f"Distritos INEI en la tabla: {len(tabla)}")
    sin = e[e["empate"] == "sin_empate"]
    if len(sin):
        print("Sin empate:", sin[["departamento", "provincia", "distrito"]].to_dict(orient="records"))
