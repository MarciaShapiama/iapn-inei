"""Datos para el tablero del modelo (dashboard/modelo.html): cómo funciona y si acierta.

No entrena nada: lee las salidas de src/prediccion_semanal.py y de herramientas/pruebas/umbrales_e_intervalos.py.
    data/modelo/resultados_plazo/metricas_por_plazo.csv      comparación de modelos por plazo
    data/modelo/resultados_plazo/metricas_por_anio.csv       PR-AUC año por año
    data/modelo/resultados_plazo/predicciones_validacion.csv.gz   predicciones fuera de muestra 2008-2025
    docs/evidencia/umbrales_e_intervalos.json                 fases y margen de error
    data/modelo/base_distrito_semana.csv                      rango de las variables en el entrenamiento

Salida: dashboard/data/modelo_explicado.json · Uso: python src/tablero_modelo.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

R = Path(__file__).resolve().parents[1]
RES = R / "data" / "modelo" / "resultados_plazo"
BASE = R / "data" / "modelo" / "base_distrito_semana.csv"
EVID = R / "docs" / "evidencia" / "umbrales_e_intervalos.json"
SALIDA = R / "dashboard" / "data" / "modelo_explicado.json"
MODELO = "logística con variables del aviso"
CALIBRADO = "logística con aviso, calibrada"
CLIMA = "climatología distrito y mes"
NOMBRES = {MODELO: "Regresión logística con variables del aviso (el modelo publicado)",
           "LightGBM con variables del aviso": "LightGBM (árboles) con variables del aviso",
           "logística sin variables del aviso": "Regresión logística sin variables del aviso",
           CLIMA: "Historia del distrito en ese mes (climatología)",
           "regla: mes del año": "Regla: mes del año",
           "regla: emergencia en la semana t": "Regla: hubo emergencia la semana anterior",
           "regla: lluvia sobre p95 en la semana t": "Regla: llovió fuerte la semana anterior"}
r3 = lambda x: round(float(x), 3)  # noqa: E731


def comparacion() -> list[dict]:
    res = pd.read_csv(RES / "metricas_por_plazo.csv")
    out = []
    for k, nombre in NOMBRES.items():
        f = res[res.modelo == k].set_index("h")
        out.append({"modelo": nombre, "publicado": k == MODELO,
                    "pr_auc": {f"h{h}": r3(f.loc[h, "pr_auc"]) for h in (1, 2, 3, 4)}})
    tasa = res[res.modelo == MODELO].set_index("h").tasa_sin_modelo
    return out, {f"h{h}": r3(tasa.loc[h]) for h in (1, 2, 3, 4)}


def anual() -> dict:
    m = pd.read_csv(RES / "metricas_por_anio.csv")
    out = {}
    for h in (1, 2, 3, 4):
        x = m[m.h == h].pivot_table(index="anio", columns="modelo", values="pr_auc")
        out[f"h{h}"] = [{"anio": int(a), "modelo": r3(x.loc[a, CALIBRADO]), "climatologia": r3(x.loc[a, CLIMA])}
                        for a in x.index]
    return out


def calibracion(p: pd.DataFrame) -> list[dict]:
    """Frecuencia observada por rango de probabilidad, a 1 semana, años con calibración (2010-2025)."""
    cortes = [0, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0]
    out = []
    for k, etq in ((MODELO, "sin_calibrar"), (CALIBRADO, "calibrado")):
        q = p[(p.h == 1) & (p.modelo == k) & (p.anio >= 2010)]
        q = q.assign(b=pd.cut(q.p, cortes, include_lowest=True))
        g = q.groupby("b", observed=True).agg(dijo=("p", "mean"), paso=("y", "mean"), n=("y", "size"))
        for (b, f) in g.iterrows():
            out.append({"version": etq, "rango": f"{int(b.left * 100)}-{int(b.right * 100)} %",
                        "dijo": round(100 * f.dijo, 1), "paso": round(100 * f.paso, 1), "n": int(f.n)})
    return out


def curva_pr(p: pd.DataFrame) -> dict:
    out = {}
    for k, etq in ((MODELO, "modelo"), (CLIMA, "climatologia")):
        q = p[(p.h == 1) & (p.modelo == k)]
        pre, rec, _ = precision_recall_curve(q.y, q.p)
        # precisión interpolada: la mejor precisión posible capturando al menos esa fracción de emergencias
        objetivo = np.linspace(0.025, 1, 40)
        out[etq] = [[round(float(r), 3), round(float(pre[rec >= r].max()), 3)] for r in objetivo]
    return out


def repaso(p: pd.DataFrame, base: pd.DataFrame) -> dict:
    """Lo que el modelo calibrado habría dicho cada semana (una semana antes) en 2017 y 2023, de enero a mayo."""
    clave_ubigeo = base.drop_duplicates("clave").set_index("clave").ubigeo.astype(str).str.zfill(6)
    out = {}
    for a in (2017, 2023):
        q = p[(p.h == 1) & (p.modelo == CALIBRADO) & (p.anio == a) & (p.semana_obj.str[5:7] <= "05")].copy()
        q["ubigeo"] = q.clave.map(clave_ubigeo)
        semanas = sorted(q.semana_obj.unique())
        prob = q.pivot_table(index="ubigeo", columns="semana_obj", values="p").reindex(columns=semanas)
        y = q.pivot_table(index="ubigeo", columns="semana_obj", values="y").reindex(columns=semanas)
        out[str(a)] = {"semanas": semanas,
                       "prob": {u: [None if pd.isna(v) else round(float(v), 3) for v in fila] for u, fila in prob.iterrows()},
                       "emergencia": {u: [0 if pd.isna(v) else int(v) for v in fila] for u, fila in y.iterrows()}}
    return out


def rangos(base: pd.DataFrame) -> dict:
    """Rango de las variables con que se entrenó (hasta 2025): para avisar si hoy hay valores nunca vistos."""
    b = base[base.semana <= "2025-12-31"]
    return {"nino12_max": r3(b.nino12.max()), "nino12_anio_max": int(b.loc[b.nino12.idxmax(), "semana"][:4]),
            "lluvia_7d_p99": r3(b.lluvia_7d.quantile(0.99))}


def main() -> None:
    p = pd.read_csv(RES / "predicciones_validacion.csv.gz")
    p["anio"] = p.semana_obj.str[:4].astype(int)
    base = pd.read_csv(BASE, usecols=["clave", "ubigeo", "semana", "nino12", "lluvia_7d"])
    comp, tasa = comparacion()
    ev = json.load(open(EVID, encoding="utf-8"))
    out = {"comparacion": comp, "tasa_sin_modelo": tasa, "anual": anual(), "calibracion": calibracion(p),
           "curva_pr_h1": curva_pr(p), "repaso": repaso(p, base), "rangos_entrenamiento": rangos(base),
           "por_densidad_h1": ev["plazos"]["h1"]["por_densidad"],
           "anios_validacion": [int(p.anio.min()), int(p.anio.max())]}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # límites de provincias y departamentos: unión de los polígonos de los distritos, para que calcen exacto
    from shapely.geometry import MultiPolygon, Polygon, mapping, shape
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    d = json.load(open(SALIDA.parent / "distritos_tumbes_piura.geojson", encoding="utf-8"))["features"]
    feats = []
    for nivel in ("provincia", "departamento"):
        for nombre in sorted({f["properties"][nivel] for f in d}):
            u = unary_union([shape(f["geometry"]).buffer(0.0008) for f in d if f["properties"][nivel] == nombre]).buffer(-0.0008)
            # sin huecos ni astillas internas: solo el contorno exterior de cada parte
            partes = [u] if u.geom_type == "Polygon" else list(u.geoms)
            u = MultiPolygon([Polygon(x.exterior) for x in partes if x.area > 1e-5])
            u = (u.geoms[0] if len(u.geoms) == 1 else u).simplify(0.0006)
            u = orient(u, -1.0) if u.geom_type == "Polygon" else MultiPolygon([orient(x, -1.0) for x in u.geoms])  # sentido de d3
            geo = json.loads(json.dumps(mapping(u)), parse_float=lambda x: round(float(x), 4))
            feats.append({"type": "Feature", "properties": {"nivel": nivel, "nombre": nombre}, "geometry": geo})
    (SALIDA.parent / "limites_tumbes_piura.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")), encoding="utf-8")
    print(f"  {SALIDA.name}: {SALIDA.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
