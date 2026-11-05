"""Validación externa: ¿los distritos con más exposición calculada son los que más daños registró INDECI?

Fuente independiente: tablas INDECI (SINPAD-COEN) 2003-2024 de afectados y damnificados por distrito y tipo de
peligro (data/modelo/indeci/*.xlsx). Se suman INUNDACIÓN + LLUVIA INTENSA. Se compara (correlación de Spearman y
coincidencia del top-15) con: población y edificaciones en la zona JRC 1 en 100, % del área inundable, agua de
radar 2017 y el índice de riesgo estimado del panel.

Límites: los registros INDECI acumulan 22 años, incluyen lluvia pluvial (no solo desborde) y dependen del reporte
de cada municipalidad; la exposición es de 2026. Es una validación de ORDEN (ranking), no de magnitudes.
Salida: docs/evidencia/validacion_indeci.json · Uso: python herramientas/pruebas/validacion_indeci.py
"""
import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

R = Path(__file__).resolve().parents[2]
IND = R / "data" / "modelo" / "indeci"
PROV = {"PIURA": ["AYABACA", "HUANCABAMBA", "MORROPON", "PAITA", "PIURA", "SECHURA", "SULLANA", "TALARA"],
        "TUMBES": ["CONTRALMIRANTE VILLAR", "TUMBES", "ZARUMILLA"]}


def norm(x):
    return "".join(c for c in unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper() if c.isalnum())


def tabla_distritos(archivo, dep, columnas=("INUNDACION", "LLUVIA INTENSA")):
    x = pd.read_excel(archivo, header=None)
    h = x.index[x.iloc[:, 0].astype(str).str.strip().str.upper() == "PROVINCIA/DISTRITO"][0]
    cols = [str(c).strip().upper() for c in x.iloc[h]]
    d = x.iloc[h + 1:].copy(); d.columns = cols
    d = d[d.iloc[:, 0].notna()]
    d = d[~d.iloc[:, 0].astype(str).str.contains("Fuente|Elaboraci|TOTAL", case=False)]
    provs = {norm(p) for p in PROV[dep]}
    filas, prov_actual, vistas = [], None, set()
    for _, r in d.iterrows():
        n = norm(r.iloc[0])
        if n in provs and n not in vistas:           # primera aparición: fila de provincia
            prov_actual = n; vistas.add(n); continue
        v = sum(pd.to_numeric(r.get(c), errors="coerce") or 0 for c in columnas if c in d.columns)
        filas.append({"dep": dep, "prov": prov_actual, "dist": n, "valor": float(np.nan_to_num(v))})
    return pd.DataFrame(filas)


def main():
    afect = pd.concat([tabla_distritos(IND / f"7162837-{d.lower()}_afect_prov_dist_peligro.xlsx", d) for d in PROV])
    damn = pd.concat([tabla_distritos(IND / f"7162767-{d.lower()}_damn_prov_dist_peligro.xlsx", d) for d in PROV])
    p = pd.read_csv(R / "dashboard/data/descargas/panel_distritos.csv", dtype={"ubigeo": str})
    p["k"] = [norm(a) + "|" + norm(c) + "|" + norm(b) for a, b, c in zip(p.departamento, p.distrito, p.provincia)]
    for nombre, t in (("afectados", afect), ("damnificados", damn)):
        t = t.assign(k=t.dep.map(norm) + "|" + t.prov + "|" + t.dist)
        p = p.merge(t[["k", "valor"]].rename(columns={"valor": f"indeci_{nombre}"}), on="k", how="left")
    emp = p[["indeci_afectados", "indeci_damnificados"]].notna().all(axis=1)
    q = p[emp]
    out = {"distritos_indeci": int(len(afect)), "distritos_panel": int(len(p)), "distritos_empatados_con_indeci": int(emp.sum()),
           "sin_empate": p.loc[~emp, "distrito"].tolist(), "correlaciones_spearman": {}}
    for y in ("indeci_afectados", "indeci_damnificados"):
        out["correlaciones_spearman"][y] = {}
        for x in ("personas_rp100", "edificaciones_rp100", "pct_area_rp100", "km2_radar_2017", "riesgo_estimado", "poblacion_worldpop_distrito"):
            s = q[[x, y]].dropna()
            rho, pv = spearmanr(s[x], s[y])
            out["correlaciones_spearman"][y][x] = {"rho": round(float(rho), 3), "p": round(float(pv), 4), "n": int(len(s))}
    top = 15
    a = set(q.nlargest(top, "indeci_afectados").distrito); b = set(q.nlargest(top, "personas_rp100").distrito)
    c = set(q.nlargest(top, "riesgo_estimado").distrito)
    out["top15"] = {"indeci_afectados": sorted(a), "personas_rp100": sorted(b), "riesgo_estimado": sorted(c),
                    "coinciden_afectados_y_personas": sorted(a & b), "coinciden_afectados_y_riesgo": sorted(a & c)}
    # normalizado por población: afectados por 1000 hab. frente a % de población expuesta
    s = q.assign(tasa=q.indeci_afectados / q.poblacion_2020_est * 1000)[["tasa", "pct_poblacion_rp100"]].dropna()
    rho, pv = spearmanr(s.tasa, s.pct_poblacion_rp100)
    out["tasa_afectados_por_mil_vs_pct_poblacion_expuesta"] = {"rho": round(float(rho), 3), "p": round(float(pv), 4), "n": int(len(s))}
    out["por_tipo_de_peligro_afectados"] = {}
    for etiqueta, cols in (("solo_inundacion", ("INUNDACION",)), ("solo_lluvia_intensa", ("LLUVIA INTENSA",))):
        t = pd.concat([tabla_distritos(IND / f"7162837-{d.lower()}_afect_prov_dist_peligro.xlsx", d, cols) for d in PROV])
        t = t.assign(k=t.dep.map(norm) + "|" + t.prov + "|" + t.dist)
        z = p.merge(t[["k", "valor"]], on="k")
        out["por_tipo_de_peligro_afectados"][etiqueta] = {
            x: {"rho": round(float(spearmanr(z[x], z.valor)[0]), 3), "p": round(float(spearmanr(z[x], z.valor)[1]), 4)}
            for x in ("personas_rp100", "edificaciones_rp100", "pct_area_rp100", "km2_radar_2017", "poblacion_worldpop_distrito")}
    q[["ubigeo", "departamento", "provincia", "distrito", "personas_rp100", "pct_poblacion_rp100", "riesgo_estimado",
       "indeci_afectados", "indeci_damnificados"]].to_csv(R / "docs/evidencia/validacion_indeci_distritos.csv", index=False, encoding="utf-8-sig")
    (R / "docs/evidencia/validacion_indeci.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=1))
