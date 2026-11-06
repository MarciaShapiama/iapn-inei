"""Modelo de alerta: ¿habrá emergencia por inundación o lluvias en el distrito en las próximas 4 semanas?

Base: data/modelo/base_distrito_semana.csv (75 distritos de Tumbes y Piura, una fila por semana): variables X.
Etiqueta: emergencia_1a4. Desde el 5/11/2026 sale del SINPAD del INDECI (fuente oficial, 2003-2025), construido
con src/etiqueta_sinpad.py: Y(d, t) = 1 si el SINPAD registra una emergencia por inundación o lluvia intensa en el
distrito d en alguna de las semanas t+1 a t+4. La versión anterior con DesInventar (hasta 2015, con marejadas) se
conserva para comparar:  python src/modelo_inundacion.py --fuente desinventar  -> data/modelo/resultados_desinventar/

Modelos comparados (los mismos datos y la misma validación):
    climatologia   frecuencia histórica del distrito en esa época del año (la referencia "sin modelo")
    logistica      regresión logística con variables estandarizadas y pesos para la clase rara
    lightgbm       árboles potenciados muy regularizados (árboles de 2 niveles, restricción "más lluvia o más
                   caudal = más riesgo"), porque hay pocos casos positivos
    log_clim       promedio de los rangos de logística y climatología

Validación honesta (origen móvil por años): se entrena con los años anteriores y se evalúa en el año siguiente,
para 2008, 2009, …, 2025 (SINPAD) o 2008-2015 (DesInventar). Ninguna variable usa información futura. Métricas:
PR-AUC (la principal con clases raras), ROC-AUC, Brier y "captura": % de emergencias que caen en el 5 % de
distrito-semanas con mayor riesgo. Con SINPAD, 2017 y 2023 se evalúan con métricas reales (fuera de muestra).

Después se entrena con todo lo etiquetado y se calcula el riesgo semanal de las semanas sin etiqueta (2026).

Salidas en data/modelo/resultados/ y dashboard/data/riesgo.json (solo con SINPAD).
Uso: python src/modelo_inundacion.py [--fuente sinpad|desinventar]
"""
from __future__ import annotations

import argparse
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
SINPAD_SEMANAL = DATA / "modelo" / "sinpad" / "sinpad_semanal.csv"
SINPAD_INICIO, SINPAD_FIN = "2003-01-06", "2025-12-29"     # primera y última semana con registros confiables


def etiqueta_sinpad(b: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza la etiqueta de DesInventar por la del SINPAD (src/etiqueta_sinpad.py)."""
    from etiqueta_sinpad import normal
    s = pd.read_csv(SINPAD_SEMANAL, parse_dates=["semana"])
    b = b.drop(columns=["emergencias", "emergencia_sem", "emergencia_1a4"], errors="ignore")
    # La clave departamento+distrito repite «PIURASALITRAL» (Morropón y Sullana): se separa con la provincia.
    b["prov_n"] = b["provincia"].map(normal)
    b = b[(b["semana"] >= SINPAD_INICIO)].merge(s[["clave", "prov_n", "semana", "eventos"]],
                                                on=["clave", "prov_n", "semana"], how="left")
    dentro = b["semana"] <= SINPAD_FIN
    b["emergencias"] = b["eventos"].fillna(0)
    b["emergencia_sem"] = (b["emergencias"] > 0).astype(float).where(dentro)
    b = b.sort_values(["clave", "prov_n", "semana"])
    fut = b.groupby(["clave", "prov_n"])["emergencia_sem"]
    b["emergencia_1a4"] = pd.concat([fut.shift(-k) for k in range(1, 5)], axis=1).max(axis=1, skipna=False)
    fuera = sorted(set(zip(s["clave"], s["prov_n"])) - set(zip(b["clave"], b["prov_n"])))
    if fuera:
        print(f"  Aviso: {len(fuera)} distritos del SINPAD no están en la base: {fuera}")
    usados = s[(s["semana"] >= SINPAD_INICIO) & (s["semana"] <= SINPAD_FIN)]["eventos"].sum()
    print(f"  SINPAD: {int(b.loc[dentro, 'emergencias'].sum()):,} de {int(usados):,} registros de agua unidos a la base")
    # clave única por distrito (separa los dos Salitral) para la historia y la climatología
    repetida = b.groupby("clave")["prov_n"].transform("nunique") > 1
    b.loc[repetida, "clave"] = b.loc[repetida, "clave"] + "_" + b.loc[repetida, "prov_n"]
    return b.drop(columns="eventos").reset_index(drop=True)


def cargar(fuente: str = "sinpad") -> pd.DataFrame:
    b = pd.read_csv(BASE, parse_dates=["semana"])
    if fuente == "sinpad":
        b = etiqueta_sinpad(b)
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
    if 2017 not in set(nuevo["semana"].dt.year):
        revision = revision_validacion(coef)
        return {"umbral_alerta": umbral, "importancia": imp, "riesgo": nuevo, "revision": revision, "coef": coef}
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


def revision_validacion(coef: dict) -> dict:
    """Con SINPAD, 2017 y 2023 tienen etiqueta: se revisan con las predicciones de la validación por años (cada año
    lo predice un modelo entrenado solo con los años anteriores, así que el modelo nunca vio ese año)."""
    p = pd.read_csv(SALIDA / "predicciones_validacion.csv", parse_dates=["semana"])
    m = pd.read_csv(SALIDA / "metricas_por_anio.csv")
    p["riesgo"] = 100 * p["logistica_simple"].rank(pct=True)
    ea = p[p["semana"].dt.month.between(1, 4) & (p["semana"].dt.year >= 2016)]
    por_anio = ea.groupby(ea["semana"].dt.year)["logistica_simple"].mean()
    rango = por_anio.rank(ascending=False)
    rev = {"metodo": "predicciones de la validación por años (fuera de muestra), enero a abril 2016-2025",
           "ranking_enero_abril": {int(k): round(float(v), 4) for k, v in por_anio.sort_values(ascending=False).items()},
           "puesto_2017": int(rango[2017]), "puesto_2023": int(rango[2023]), "anios_comparados": int(len(por_anio)),
           "coeficientes_estandarizados": coef}
    normales = [2016, 2018, 2019, 2021, 2022, 2024, 2025]
    normal = p[p["semana"].dt.year.isin(normales) & p["semana"].dt.month.between(1, 4)]
    for anio, (a, z) in {"2017": ("2017-01-15", "2017-04-30"), "2023": ("2023-02-15", "2023-04-30")}.items():
        ev = p[(p["semana"] >= a) & (p["semana"] <= z)]
        fila = m[(m["anio"] == int(anio)) & (m["modelo"] == "logistica_simple")]
        rev[anio] = {
            "riesgo_medio_evento": round(float(ev["riesgo"].mean()), 1),
            "riesgo_medio_anios_normales": round(float(normal["riesgo"].mean()), 1),
            "veces_mayor": round(float(ev["riesgo"].mean() / max(normal["riesgo"].mean(), 1e-9)), 1),
            "semanas_con_emergencia": int(ev[OBJETIVO].sum()),
            "pr_auc_del_anio": round(float(fila["pr_auc"].iloc[0]), 3) if len(fila) else None,
            "captura_top5_del_anio": round(float(fila["captura_top5"].iloc[0]), 3) if len(fila) else None,
            "top_distritos": ev.groupby("distrito")["riesgo"].max().sort_values(ascending=False).head(8).round(1).to_dict()}
    return rev


def tablero(resumen: pd.DataFrame, f: dict) -> None:
    r = f["riesgo"]
    ult = r["semana"].max()
    hoy = r[r["semana"] == ult].sort_values("riesgo", ascending=False)
    hist = r[["departamento", "semana", "riesgo"]]
    if "metodo" in f["revision"]:
        # 2016-2025: riesgo de la validación por años (fuera de muestra); después: modelo final
        p = pd.read_csv(SALIDA / "predicciones_validacion.csv", parse_dates=["semana"])
        p["riesgo"] = 100 * p["logistica_simple"].rank(pct=True)
        p = p[(p["semana"] >= "2016-01-01") & (p["semana"] < r["semana"].min())]
        hist = pd.concat([p[["departamento", "semana", "riesgo"]], hist])
    serie = hist.groupby(["departamento", "semana"])["riesgo"].mean().unstack(0).round(4)
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


def main(fuente: str = "sinpad") -> None:
    global SALIDA, ANIOS_PRUEBA
    if fuente == "desinventar":
        SALIDA = DATA / "modelo" / "resultados_desinventar"
    else:
        ANIOS_PRUEBA = list(range(2008, 2026))
    SALIDA.mkdir(parents=True, exist_ok=True)
    b = cargar(fuente)
    et = b.dropna(subset=[OBJETIVO])
    print(f"Fuente de Y: {fuente}. Filas con Y: {len(et):,}; Y = 1: {int(et[OBJETIVO].sum()):,} "
          f"({100 * et[OBJETIVO].mean():.2f} %); de {et['semana'].min().date()} a {et['semana'].max().date()}")
    print("Validación por años (entrena con el pasado, evalúa el año siguiente):")
    resumen = evaluar(b)
    print(resumen.round(3).to_string(index=False))
    f = final(b)
    print("Variables que más pesan (SHAP):", f["importancia"].head(8).round(4).to_dict(orient="records"))
    print("Revisión fuera de muestra:", json.dumps(f["revision"], ensure_ascii=False, indent=1))
    if fuente == "sinpad":
        tablero(resumen, f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuente", choices=["sinpad", "desinventar"], default="sinpad")
    main(ap.parse_args().fuente)
