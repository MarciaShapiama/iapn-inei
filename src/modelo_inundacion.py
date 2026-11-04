"""Modelo de alerta: ¿habrá emergencia por inundación o lluvias en el distrito en las próximas 4 semanas?

Base: data/modelo/base_distrito_semana.csv (75 distritos de Tumbes y Piura, una fila por semana).
Etiqueta: emergencia_1a4 (DesInventar / INDECI, con fechas hasta 2015).

Modelos comparados (los mismos datos y la misma validación):
    climatologia   frecuencia histórica del distrito en esa época del año (la referencia "sin modelo")
    logistica      regresión logística con variables estandarizadas y pesos para la clase rara
    lightgbm       árboles potenciados muy regularizados (árboles de 2 niveles, restricción "más lluvia o más
                   caudal = más riesgo"), porque hay pocos casos positivos
    log_clim       promedio de los rangos de logística y climatología

Validación honesta (origen móvil por años): se entrena con los años anteriores y se evalúa en el año siguiente,
para 2008, 2009, …, 2015. Ninguna variable usa información futura. Métricas: PR-AUC (la principal con clases
raras), ROC-AUC, Brier y "captura": % de emergencias que caen en el 5 % de distrito-semanas con mayor riesgo.

Después se entrena con 2001-2015 y se calcula el riesgo semanal 2016-hoy (fuera de muestra) para revisar
2017 y 2023, que el modelo nunca vio.

Salidas en data/modelo/resultados/ y dashboard/data/riesgo.json
Uso: python src/modelo_inundacion.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import DASH_DATA, DATA

BASE = DATA / "modelo" / "base_distrito_semana.csv"
SALIDA = DATA / "modelo" / "resultados"
OBJETIVO = "emergencia_1a4"
VARIABLES = ["lluvia_7d", "lluvia_30d", "lluvia_90d", "lluvia_7d_anom", "lluvia_30d_anom", "lluvia_90d_anom",
             "lluvia_7d_prev", "caudal", "caudal_razon", "caudal_max_4s", "nino12", "nino34",
             "km2_inundable_rp10", "km2_inundable_rp100", "viviendas_rp10", "viviendas_rp100", "personas_rp100",
             "frecuencia_historica", "sen_semana", "cos_semana"]
# Modelo principal: logística simple con pocas variables en escala logarítmica. Con tan pocos casos, la versión
# con muchas variables de lluvia superpuestas daba signos negativos y no reconocía 2017 (lluvia récord).
SIMPLE = ["log_lluvia_30d", "log_caudal_razon", "nino12", "frecuencia_historica", "sen_semana", "cos_semana"]
ANIOS_PRUEBA = list(range(2008, 2016))
SEMILLA = 7


def cargar() -> pd.DataFrame:
    b = pd.read_csv(BASE, parse_dates=["semana"])
    b["anio"] = b["semana"].dt.year
    ang = 2 * np.pi * b["semana_anio"] / 52
    b["sen_semana"], b["cos_semana"] = np.sin(ang), np.cos(ang)
    b["temporada"] = ((b["semana_anio"] - 1) // 4)          # bloques de ~1 mes para la climatología
    b["log_lluvia_30d"] = np.log1p(b["lluvia_30d"].clip(lower=0))
    b["log_caudal_razon"] = np.log(b["caudal_razon"].clip(lower=0.05))
    return b


def con_historia(entreno: pd.DataFrame, otro: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Frecuencia histórica del distrito calculada SOLO con los años de entrenamiento (sin fuga)."""
    f = entreno.groupby("clave")["emergencia_sem"].mean().rename("frecuencia_historica")
    a = entreno.drop(columns="frecuencia_historica", errors="ignore").join(f, on="clave")
    b = otro.drop(columns="frecuencia_historica", errors="ignore").join(f, on="clave")
    b["frecuencia_historica"] = b["frecuencia_historica"].fillna(f.mean())
    return a, b


def climatologia(entreno: pd.DataFrame, prueba: pd.DataFrame) -> np.ndarray:
    tasa = entreno.groupby(["clave", "temporada"])[OBJETIVO].mean()
    global_t = entreno.groupby("temporada")[OBJETIVO].mean()
    p = prueba.join(tasa.rename("p"), on=["clave", "temporada"])["p"]
    p = p.fillna(prueba["temporada"].map(global_t))
    # suavizado: mezcla con la tasa de la temporada (pocos casos por distrito)
    return (0.5 * p + 0.5 * prueba["temporada"].map(global_t)).fillna(entreno[OBJETIVO].mean()).to_numpy()


def logistica(entreno, prueba, variables=None):
    v = variables or VARIABLES
    m = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", C=0.3, max_iter=2000))
    med = entreno[v].median()
    m.fit(entreno[v].fillna(med), entreno[OBJETIVO])
    return m.predict_proba(prueba[v].fillna(med))[:, 1], m


def lightgbm(entreno, prueba):
    import lightgbm as lgb
    crece = {"lluvia_7d", "lluvia_30d", "lluvia_90d", "lluvia_7d_anom", "lluvia_30d_anom", "lluvia_90d_anom",
             "lluvia_7d_prev", "caudal", "caudal_razon", "caudal_max_4s", "frecuencia_historica"}
    m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=5, max_depth=2, min_child_samples=400,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=10.0, scale_pos_weight=3,
                           monotone_constraints=[1 if v in crece else 0 for v in VARIABLES], random_state=SEMILLA, verbose=-1)
    m.fit(entreno[VARIABLES], entreno[OBJETIVO])
    return m.predict_proba(prueba[VARIABLES])[:, 1], m


def captura(y, p, frac=0.05) -> float:
    n = max(1, int(len(p) * frac))
    top = np.argsort(-p)[:n]
    return float(y[top].sum() / max(1, y.sum()))


def metricas(y, p) -> dict:
    y = np.asarray(y); p = np.clip(np.asarray(p), 1e-6, 1 - 1e-6)
    return {"pr_auc": average_precision_score(y, p), "roc_auc": roc_auc_score(y, p) if 0 < y.sum() < len(y) else np.nan,
            "brier": brier_score_loss(y, p), "captura_top5": captura(y, p), "positivos": int(y.sum()), "n": len(y)}


def evaluar(b: pd.DataFrame) -> pd.DataFrame:
    filas, preds = [], []
    etiquetada = b.dropna(subset=[OBJETIVO])
    for anio in ANIOS_PRUEBA:
        entreno = etiquetada[etiquetada["anio"] < anio]
        # se descartan las 4 últimas semanas del entrenamiento: su etiqueta mira dentro del año de prueba
        entreno = entreno[entreno["semana"] < pd.Timestamp(anio, 1, 1) - pd.Timedelta(weeks=4)]
        prueba = etiquetada[etiquetada["anio"] == anio]
        entreno, prueba = con_historia(entreno, prueba)
        res = {"climatologia": climatologia(entreno, prueba), "logistica_simple": logistica(entreno, prueba, SIMPLE)[0],
               "logistica_completa": logistica(entreno, prueba)[0], "lightgbm": lightgbm(entreno, prueba)[0]}
        for m, p in res.items():
            if prueba[OBJETIVO].sum() > 0:
                filas.append({"anio": anio, "modelo": m, **metricas(prueba[OBJETIVO], p)})
        preds.append(prueba[["clave", "distrito", "provincia", "departamento", "semana", OBJETIVO]].assign(**res))
        print(f"  {anio}: positivos {int(prueba[OBJETIVO].sum())}, PR-AUC lightgbm "
              f"{average_precision_score(prueba[OBJETIVO], res['lightgbm']):.3f} vs climatología "
              f"{average_precision_score(prueba[OBJETIVO], res['climatologia']):.3f}")
    pd.concat(preds).to_csv(SALIDA / "predicciones_validacion.csv", index=False, float_format="%.5f")
    t = pd.DataFrame(filas)
    t.to_csv(SALIDA / "metricas_por_anio.csv", index=False, float_format="%.4f")
    todo = pd.concat(preds)
    resumen = pd.DataFrame([{"modelo": m, **metricas(todo[OBJETIVO], todo[m])}
                            for m in ["climatologia", "logistica_simple", "logistica_completa", "lightgbm"]])
    resumen.to_csv(SALIDA / "metricas_resumen.csv", index=False, float_format="%.4f")
    return resumen


def explicar(m, X: pd.DataFrame) -> pd.DataFrame:
    """Contribuciones SHAP de LightGBM (pred_contrib, sin paquetes extra)."""
    c = m.booster_.predict(X, pred_contrib=True)[:, :-1]
    imp = pd.DataFrame({"variable": VARIABLES, "shap_medio_abs": np.abs(c).mean(axis=0)})
    return imp.sort_values("shap_medio_abs", ascending=False)


def final(b: pd.DataFrame) -> dict:
    etiquetada = b.dropna(subset=[OBJETIVO])
    nuevo = b[b["semana"] > etiquetada["semana"].max()].copy()
    entreno, nuevo = con_historia(etiquetada, nuevo)
    p_lgb, m = lightgbm(entreno, nuevo)
    p_log, mlog = logistica(entreno, nuevo, SIMPLE)
    coef = dict(zip(SIMPLE, np.round(mlog[-1].coef_[0], 3)))
    # índice 0-100: percentil del riesgo frente a TODAS las distrito-semanas 2001-2015 (modelo principal)
    ref = np.sort(logistica(entreno, entreno, SIMPLE)[0])
    nuevo["riesgo"] = 100 * np.searchsorted(ref, p_log) / len(ref)
    nuevo["riesgo_logistica"], nuevo["riesgo_lightgbm"] = p_log, p_lgb
    umbral = 95.0                     # alerta: riesgo en el 5 % más alto de la historia
    nuevo["alerta"] = nuevo["riesgo"] >= umbral
    imp = explicar(m, entreno[VARIABLES])
    imp.to_csv(SALIDA / "importancia_shap.csv", index=False, float_format="%.5f")
    cols = ["clave", "departamento", "provincia", "distrito", "semana", "riesgo", "riesgo_lightgbm", "riesgo_logistica",
            "alerta", "lluvia_30d", "caudal_razon", "nino12"]
    nuevo[cols].to_csv(SALIDA / "riesgo_2016_hoy.csv", index=False, float_format="%.5f")
    # revisión fuera de muestra: ¿2017 y 2023 salen como los años más riesgosos entre enero y abril?
    ea = nuevo[nuevo["semana"].dt.month.between(1, 4)]
    por_anio = ea.groupby(ea["semana"].dt.year)["riesgo_logistica"].mean()
    revision = {"ranking_enero_abril": {int(k): round(float(v), 4) for k, v in por_anio.sort_values(ascending=False).items()},
                "puesto_2017": int(por_anio.rank(ascending=False)[2017]), "puesto_2023": int(por_anio.rank(ascending=False)[2023]),
                "anios_comparados": int(len(por_anio)), "coeficientes_estandarizados": coef}
    for anio, (a, z) in {"2017": ("2017-01-15", "2017-04-30"), "2023": ("2023-02-15", "2023-04-30")}.items():
        ev = nuevo[(nuevo["semana"] >= a) & (nuevo["semana"] <= z)]
        normal = nuevo[(nuevo["semana"].dt.year.isin([2016, 2018, 2019, 2021, 2022, 2024, 2025]))
                       & nuevo["semana"].dt.month.between(1, 4)]                  # mismas fechas, años sin evento
        revision[anio] = {
            "riesgo_medio_evento": round(float(ev["riesgo"].mean()), 1),
            "riesgo_medio_anios_normales": round(float(normal["riesgo"].mean()), 1),
            "veces_mayor": round(float(ev["riesgo"].mean() / max(normal["riesgo"].mean(), 1e-9)), 1),
            "distritos_en_alerta": int(ev.groupby("clave")["alerta"].any().sum()),
            "distritos_total": int(ev["clave"].nunique()),
            "primera_semana_alerta": str(ev[ev["alerta"]]["semana"].min().date()) if ev["alerta"].any() else None,
            "top_distritos": ev.groupby("distrito")["riesgo"].max().sort_values(ascending=False).head(8).round(1).to_dict()}
    return {"umbral_alerta": umbral, "importancia": imp, "riesgo": nuevo, "revision": revision, "coef": coef}


def tablero(resumen: pd.DataFrame, f: dict) -> None:
    r = f["riesgo"]
    ult = r["semana"].max()
    hoy = r[r["semana"] == ult].sort_values("riesgo", ascending=False)
    serie = r.groupby(["departamento", "semana"])["riesgo"].mean().unstack(0).round(4)
    salida = {
        "metricas": resumen.round(4).to_dict(orient="records"),
        "umbral_alerta": f["umbral_alerta"], "modelo_principal": "logistica_simple", "coeficientes": f["coef"],
        "importancia": f["importancia"].head(12).round(5).to_dict(orient="records"),
        "revision": f["revision"],
        "semana_actual": str(ult.date()),
        "distritos_hoy": hoy[["departamento", "provincia", "distrito", "riesgo", "alerta", "lluvia_30d", "caudal_razon"]]
                         .round(4).to_dict(orient="records"),
        "serie": {"semana": [str(s.date()) for s in serie.index],
                  **{k: [None if pd.isna(v) else v for v in serie[k]] for k in serie.columns}},
    }
    json.dump(salida, open(DASH_DATA / "riesgo.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"),
              default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o))


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    b = cargar()
    print("Validación por años (entrena con el pasado, evalúa el año siguiente):")
    resumen = evaluar(b)
    print(resumen.round(3).to_string(index=False))
    f = final(b)
    print("Variables que más pesan (SHAP):", f["importancia"].head(8).round(4).to_dict(orient="records"))
    print("Revisión fuera de muestra:", json.dumps(f["revision"], ensure_ascii=False, indent=1))
    tablero(resumen, f)


if __name__ == "__main__":
    main()
