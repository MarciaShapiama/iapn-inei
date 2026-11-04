"""Evaluación complementaria del experimento de alerta (src/modelo_inundacion.py), sin reentrenar nada.

Usa solo data/modelo/resultados/predicciones_validacion.csv (predicciones fuera de muestra, origen móvil por años
2008-2015) y responde:
    1. Incertidumbre: intervalos bootstrap al 90 % de PR-AUC y ROC-AUC remuestreando AÑOS completos (bloques),
       y de la diferencia de cada modelo frente a la climatología. Con 8 años de prueba los intervalos son anchos.
    2. Calibración: Brier y tabla de confiabilidad por deciles; recalibración isotónica "dejando un año fuera"
       (se ajusta con 7 años y se evalúa en el octavo) para ver si las probabilidades pueden interpretarse.
    3. Falsos negativos: emergencias que quedaron fuera del 5 % de distrito-semanas con mayor riesgo; ¿en qué
       distritos, meses y años se concentran?
Salidas: data/modelo/resultados/evaluacion_extra.json y docs/evidencia/ml_evaluacion.json
Uso: python src/ml_evaluacion.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from comun import ahora_lima, escribir_json
from config import DATA, RAIZ

PRED = DATA / "modelo" / "resultados" / "predicciones_validacion.csv"
Y = "emergencia_1a4"
MODELOS = ["climatologia", "logistica_simple", "logistica_completa", "lightgbm"]
B = 2000
SEMILLA = 11


def bootstrap_por_anio(p: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEMILLA)
    anios = np.array(sorted(p["anio"].unique()))
    grupos = {a: p[p["anio"] == a] for a in anios}
    res = {m: {"pr": [], "roc": []} for m in MODELOS}
    dif = {m: [] for m in MODELOS if m != "climatologia"}
    for _ in range(B):
        muestra = pd.concat([grupos[a] for a in rng.choice(anios, len(anios), replace=True)])
        y = muestra[Y].to_numpy()
        if y.sum() == 0:
            continue
        pr = {m: average_precision_score(y, muestra[m]) for m in MODELOS}
        for m in MODELOS:
            res[m]["pr"].append(pr[m]); res[m]["roc"].append(roc_auc_score(y, muestra[m]))
        for m in dif:
            dif[m].append(pr[m] - pr["climatologia"])
    q = lambda v: [round(float(np.quantile(v, 0.05)), 3), round(float(np.quantile(v, 0.95)), 3)]
    y = p[Y].to_numpy()
    out = {m: {"pr_auc": round(float(average_precision_score(y, p[m])), 3), "pr_auc_ic90": q(res[m]["pr"]),
               "roc_auc": round(float(roc_auc_score(y, p[m])), 3), "roc_auc_ic90": q(res[m]["roc"])} for m in MODELOS}
    for m in dif:
        out[m]["dif_pr_auc_vs_climatologia_ic90"] = q(dif[m])
        out[m]["prob_supera_climatologia"] = round(float(np.mean(np.array(dif[m]) > 0)), 3)
    out["_nota"] = (f"{B} remuestreos de los {len(anios)} años de prueba (bloques anuales). "
                    f"Tasa base de positivos: {y.mean():.4f} (PR-AUC de un modelo al azar ≈ tasa base).")
    return out


def calibracion(p: pd.DataFrame) -> dict:
    out = {}
    for m in MODELOS:
        y, s = p[Y].to_numpy(), p[m].clip(1e-6, 1 - 1e-6).to_numpy()
        cal = np.zeros_like(s)
        for a in p["anio"].unique():           # isotónica dejando un año fuera
            tr, te = (p["anio"] != a).to_numpy(), (p["anio"] == a).to_numpy()
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(s[tr], y[tr])
            cal[te] = iso.predict(s[te])
        dec = pd.qcut(pd.Series(s).rank(method="first"), 10, labels=False)
        tabla = pd.DataFrame({"dec": dec, "s": s, "c": cal, "y": y}).groupby("dec").agg(
            prob_media=("s", "mean"), prob_recalibrada=("c", "mean"), tasa_observada=("y", "mean"), n=("y", "size"))
        out[m] = {"brier": round(float(brier_score_loss(y, s)), 4), "brier_recalibrado_loyo": round(float(brier_score_loss(y, cal)), 4),
                  "brier_referencia_tasa_base": round(float(brier_score_loss(y, np.full_like(s, y.mean()))), 4),
                  "deciles": tabla.round(4).reset_index().to_dict(orient="records")}
    return out


def falsos_negativos(p: pd.DataFrame, modelo: str = "logistica_simple", frac: float = 0.05) -> dict:
    corte = p[modelo].quantile(1 - frac)
    pos = p[p[Y] == 1].copy()
    pos["capturado"] = pos[modelo] >= corte
    pos["mes"] = pd.to_datetime(pos["semana"]).dt.month
    fn = pos[~pos["capturado"]]
    return {"modelo": modelo, "umbral_top": frac, "positivos": int(len(pos)), "capturados": int(pos["capturado"].sum()),
            "falsos_negativos": int(len(fn)),
            "fn_por_mes": fn["mes"].value_counts().sort_index().to_dict(),
            "fn_por_anio": fn["anio"].value_counts().sort_index().to_dict(),
            "fn_top_distritos": fn["distrito"].value_counts().head(10).to_dict(),
            "captura_por_mes": pos.groupby("mes")["capturado"].mean().round(3).to_dict(),
            "fn_por_departamento": fn["departamento"].value_counts().to_dict(),
            "captura_por_departamento": pos.groupby("departamento")["capturado"].mean().round(3).to_dict(),
            "lectura": lectura(pos, fn)}


def lectura(pos: pd.DataFrame, fn: pd.DataFrame) -> str:
    """Resumen escrito a partir de los datos (no a mano)."""
    meses = fn["mes"].value_counts()
    lluvia = fn["mes"].between(1, 4).mean()
    dep = fn["departamento"].value_counts(normalize=True)
    cap = pos.groupby("departamento")["capturado"].mean()
    return (f"{len(fn)} de {len(pos)} emergencias ({len(fn) / len(pos):.0%}) quedan fuera del 5 % de mayor riesgo. "
            f"El {lluvia:.0%} de esos falsos negativos ocurre entre enero y abril (meses con más casos: "
            f"{', '.join(str(m) for m in meses.index[:3])}), es decir, en plena temporada de lluvias, no fuera de ella. "
            f"Por departamento: {', '.join(f'{k} {v:.0%} de los falsos negativos (captura {cap[k]:.0%})' for k, v in dep.items())}.")


def main() -> dict:
    p = pd.read_csv(PRED, parse_dates=["semana"])
    p["anio"] = p["semana"].dt.year
    out = {"calculado": ahora_lima(), "archivo": str(PRED.relative_to(RAIZ)), "n": int(len(p)), "positivos": int(p[Y].sum()),
           "incertidumbre": bootstrap_por_anio(p), "calibracion": calibracion(p), "falsos_negativos": falsos_negativos(p)}
    escribir_json(DATA / "modelo" / "resultados" / "evaluacion_extra.json", out)
    escribir_json(RAIZ / "docs" / "evidencia" / "ml_evaluacion.json", out)
    return out


if __name__ == "__main__":
    o = main()
    for m, v in o["incertidumbre"].items():
        print(m, v)
    for m, v in o["calibracion"].items():
        print(m, {k: v[k] for k in ("brier", "brier_recalibrado_loyo", "brier_referencia_tasa_base")})
    print(json.dumps(o["falsos_negativos"], ensure_ascii=False))
