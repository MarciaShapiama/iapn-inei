"""Modelo de viviendas afectadas por inundación y lluvia intensa en Tumbes y Piura (distrito y semana).

Responde la pregunta del profesor Alexander (reunión del 4/11/2026): predecir en serie de tiempo cuántas viviendas
pueden verse afectadas y dónde. La etiqueta real sale del SINPAD (INDECI), publicado como datos abiertos.

Dónde va: src/modelo_afectados.py del repositorio. Se corre desde la raíz del repositorio:

    python src/modelo_afectados.py                 # anticipación: solo datos de la semana anterior
    python src/modelo_afectados.py --lluvia-semana # usa la lluvia de la misma semana ("pronóstico perfecto")
    python src/modelo_afectados.py --descargar     # vuelve a bajar el SINPAD de datosabiertos.gob.pe

Entradas:
    data/modelo/base_distrito_semana.csv           variables X (ya están en el repositorio)
    data/modelo/sinpad_tumbes_piura_semanal.csv    etiqueta Y (se entrega junto con este archivo; si no está,
                                                   se arma con --descargar)
    dashboard/data/viviendas_censo.json            viviendas del Censo 2025 en zona inundable (totales por distrito)
    datos_inei/viviendas_distrito.csv              OPCIONAL, en la laptop: reemplaza al JSON anterior. Columnas:
                                                   ubigeo, viviendas_rp100, pct_fragiles. Nunca va a GitHub.

Salidas (data/modelo/resultados_afectados/):
    metricas_por_anio.csv, metricas_resumen.csv, predicciones_validacion.csv, ranking_2017_2023.csv

Dependencias: pandas, numpy, scikit-learn, scipy. lightgbm y statsmodels son opcionales: si están instalados se usan
(LightGBM con objetivo Poisson y binomial negativa con ceros inflados); si no, se usan equivalentes de scikit-learn.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, special, stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import GammaRegressor, LogisticRegression, PoissonRegressor
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "data" / "modelo"
SALIDA = MODELO / "resultados_afectados"
BASE = MODELO / "base_distrito_semana.csv"
SINPAD = MODELO / "sinpad_tumbes_piura_semanal.csv"
CENSO_PUBLICO = RAIZ / "dashboard" / "data" / "viviendas_censo.json"
CENSO_LOCAL = RAIZ / "datos_inei" / "viviendas_distrito.csv"
UBIGEO = RAIZ / "data" / "exposicion" / "ubigeo_distritos.csv"

# INDECI, "Emergencias y daños a nivel nacional por departamento" (datosabiertos.gob.pe, licencia ODC-By).
URL_SINPAD = ["https://www.datosabiertos.gob.pe/sites/default/files/BD_2003-2025_EMERGENCIAS.csv",
              "https://www.datosabiertos.gob.pe/sites/default/files/BD_2026_Semestre_I.csv"]
MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
         "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
# Los distritos creados después del mapa GADM se suman al distrito que los contenía en ese mapa.
FUSION = {"200115": "200101",   # Veintiséis de Octubre -> Piura (comprobado: su centro cae en el polígono Piura)
          "240203": "240201"}   # Canoas de Punta Sal -> Zorritos (comprobado con 4 puntos de su territorio)
ANIOS_PRUEBA = list(range(2012, 2026))
FIN_ETIQUETA = "2025-12-29"     # última semana completa con etiqueta confiable (el archivo 2026-I tiene un problema)


def normal(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


# ----------------------------------------------------------------------------------------------- etiqueta Y
def descargar_sinpad() -> pd.DataFrame:
    """Baja los dos CSV del INDECI, se queda con Tumbes y Piura, y con inundación y lluvia intensa."""
    import requests
    partes = []
    for url in URL_SINPAD:
        r = requests.get(url, timeout=600, headers={"User-Agent": "proyecto-integrador-peu-cd"})
        r.raise_for_status()
        t = pd.read_csv(io.StringIO(r.content.decode("latin-1")), sep=";", dtype=str)
        t.columns = range(t.shape[1])                     # los dos archivos nombran distinto las mismas columnas
        partes.append(t)
    t = pd.concat(partes, ignore_index=True)
    t = t.rename(columns={0: "codigo", 1: "fecha_txt", 2: "anio", 3: "mes", 4: "ubigeo", 8: "peligro",
                          14: "damnificados", 15: "afectados", 16: "viv_destruidas", 17: "viv_afectadas"})
    t = t[t["ubigeo"].str.match(r"^(20|24)\d{4}$", na=False)]
    t = t[t["peligro"].str.contains("INUND|LLUVI", case=False, na=False)].copy()
    t["fecha"] = [fecha_sinpad(f, m) for f, m in zip(t["fecha_txt"], t["mes"])]
    for c in ["damnificados", "afectados", "viv_destruidas", "viv_afectadas"]:
        t[c] = pd.to_numeric(t[c].str.replace(",", "."), errors="coerce").fillna(0)
    # 2026-I: en 132 de 302 registros VIVIENDAS DESTRUIDAS repite el valor de AFECTADOS (personas). No se usa.
    t.loc[t["fecha"] >= "2026-01-01", "viv_destruidas"] = 0
    t["inundacion"] = t["peligro"].str.contains("INUND", case=False).astype(int)
    t["semana"] = pd.to_datetime(t["fecha"]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    s = (t.groupby(["ubigeo", "semana"])
         .agg(eventos=("codigo", "size"), eventos_inundacion=("inundacion", "sum"), viv_afectadas=("viv_afectadas", "sum"),
              viv_destruidas=("viv_destruidas", "sum"), afectados=("afectados", "sum"), damnificados=("damnificados", "sum"))
         .reset_index())
    ub = pd.read_csv(UBIGEO, dtype={"inei": str}).rename(columns={"inei": "ubigeo"})
    s = s.merge(ub[["ubigeo", "departamento", "provincia", "distrito"]], on="ubigeo", how="left")
    s.to_csv(SINPAD, index=False)
    print(f"SINPAD: {len(t)} registros de inundación y lluvia intensa -> {len(s)} distrito-semanas en {SINPAD}")
    return s


def fecha_sinpad(texto: str, mes: str) -> str | None:
    """El archivo mezcla dd/mm/aaaa (2003-2024) y mm/dd/aa (2025-2026). La columna MES decide el orden."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", str(texto))
    if not m:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y = 2000 + y if y < 100 else y
    mm = MESES.get(str(mes).strip().upper())
    dia, mes_n = (a, b) if mm == b else (b, a)
    return f"{y:04d}-{mes_n:02d}-{dia:02d}"


def etiquetas(descargar: bool) -> pd.DataFrame:
    s = descargar_sinpad() if (descargar or not SINPAD.exists()) else pd.read_csv(SINPAD, dtype={"ubigeo": str})
    s["ubigeo"] = s["ubigeo"].replace(FUSION)
    ub = pd.read_csv(UBIGEO, dtype={"inei": str})
    ub["clave"] = ub["departamento"].map(normal) + ub["distrito"].map(normal)
    s = s.merge(ub[["inei", "clave"]].rename(columns={"inei": "ubigeo"}), on="ubigeo", how="left")
    y = s.groupby(["clave", "semana"])[["eventos", "viv_afectadas", "viv_destruidas"]].sum().reset_index()
    y["viviendas"] = y["viv_afectadas"] + y["viv_destruidas"]
    return y


# ------------------------------------------------------------------------------------------------ variables X
def tabla(lluvia_semana: bool) -> pd.DataFrame:
    b = pd.read_csv(BASE)
    y = etiquetas(descargar=ARGS.descargar)
    b = b.merge(y[["clave", "semana", "eventos", "viviendas"]], on=["clave", "semana"], how="left")
    b = b[(b["semana"] >= "2003-01-06") & (b["semana"] <= FIN_ETIQUETA)].copy()
    b[["eventos", "viviendas"]] = b[["eventos", "viviendas"]].fillna(0)
    b = b.sort_values(["clave", "semana"])
    g = b.groupby("clave")
    # Anticipación: todo lo dinámico se toma de la semana anterior (se conoce el lunes).
    for c in ["lluvia_7d", "lluvia_30d", "lluvia_90d", "lluvia_30d_anom", "caudal", "caudal_razon", "caudal_max_4s",
              "nino12"]:
        b[c + "_l1"] = g[c].shift(1)
    if lluvia_semana:   # techo: lo que daría un pronóstico perfecto de la lluvia de la semana
        b["lluvia_7d_l1"], b["lluvia_30d_l1"] = b["lluvia_7d"], b["lluvia_30d"]
    b["anio"] = b["semana"].str[:4].astype(int)
    b["sen"] = np.sin(2 * np.pi * b["semana_anio"] / 52)
    b["cos"] = np.cos(2 * np.pi * b["semana_anio"] / 52)
    b = b.merge(censo(), on="clave", how="left")
    b[["censo_viv_rp100", "censo_pct_fragiles"]] = b[["censo_viv_rp100", "censo_pct_fragiles"]].fillna(0)
    return b


def censo() -> pd.DataFrame:
    """Viviendas ocupadas del Censo 2025 en la zona 1 en 100 años y % con paredes frágiles, por distrito."""
    ub = pd.read_csv(UBIGEO, dtype={"inei": str})
    ub["clave"] = ub["departamento"].map(normal) + ub["distrito"].map(normal)
    if CENSO_LOCAL.exists():
        c = pd.read_csv(CENSO_LOCAL, dtype={"ubigeo": str})
        c = c.rename(columns={"viviendas_rp100": "censo_viv_rp100", "pct_fragiles": "censo_pct_fragiles"})
    else:
        j = json.load(open(CENSO_PUBLICO, encoding="utf-8"))
        c = pd.DataFrame(j["escenarios"]["rp100"]["distritos"])
        c = c.rename(columns={"viviendas": "censo_viv_rp100", "pct_fragiles": "censo_pct_fragiles"})
    c["ubigeo"] = c["ubigeo"].astype(str).replace(FUSION)
    c = c.merge(ub[["inei", "clave"]].rename(columns={"inei": "ubigeo"}), on="ubigeo", how="left")
    return (c.groupby("clave").apply(lambda d: pd.Series({
        "censo_viv_rp100": d["censo_viv_rp100"].sum(),
        "censo_pct_fragiles": np.average(d["censo_pct_fragiles"], weights=d["censo_viv_rp100"].clip(lower=1))}),
        include_groups=False).reset_index())


DINAMICAS = ["lluvia_7d_l1", "lluvia_30d_l1", "lluvia_90d_l1", "lluvia_30d_anom_l1", "caudal_razon_l1",
             "caudal_max_4s_l1", "nino12_l1", "sen", "cos"]
FIJAS = ["km2_inundable_rp100", "personas_rp100", "censo_viv_rp100", "censo_pct_fragiles"]


def historia(tr: pd.DataFrame, te: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Promedio de viviendas afectadas del distrito y del distrito en ese mes, SOLO con los años de entrenamiento."""
    tr, te = tr.copy(), te.copy()
    for d in (tr, te):
        d["mes"] = pd.to_datetime(d["semana"]).dt.month
    m1 = tr.groupby("clave")["viviendas"].mean().rename("hist_distrito")
    m2 = tr.groupby(["clave", "mes"])["viviendas"].mean().rename("hist_distrito_mes")
    p1 = tr.groupby("clave")["eventos"].apply(lambda s: (s > 0).mean()).rename("hist_frec")
    for d in (tr, te):
        d.drop(columns=[c for c in ("hist_distrito", "hist_distrito_mes", "hist_frec") if c in d], inplace=True)
    tr = tr.join(m1, on="clave").join(m2, on=["clave", "mes"]).join(p1, on="clave")
    te = te.join(m1, on="clave").join(m2, on=["clave", "mes"]).join(p1, on="clave")
    for d in (tr, te):
        d[["hist_distrito", "hist_distrito_mes", "hist_frec"]] = d[["hist_distrito", "hist_distrito_mes",
                                                                    "hist_frec"]].fillna(0)
    return tr, te


def matriz(d: pd.DataFrame) -> np.ndarray:
    cols = DINAMICAS + FIJAS + ["hist_distrito", "hist_frec"]
    x = d[cols].astype(float).fillna(d[cols].median(numeric_only=True)).fillna(0)
    for c in ["lluvia_7d_l1", "lluvia_30d_l1", "lluvia_90d_l1", "caudal_max_4s_l1", "km2_inundable_rp100",
              "personas_rp100", "censo_viv_rp100", "hist_distrito"]:
        x[c] = np.log1p(x[c].clip(lower=0))
    return x.to_numpy()


# ---------------------------------------------------------------------------------------------------- modelos
def cero(tr, te):
    return np.zeros(len(te))


def climatologia(tr, te):
    return te["hist_distrito_mes"].to_numpy()


def poisson(tr, te):
    m = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=3000))
    m.fit(matriz(tr), tr["viviendas"])
    return m.predict(matriz(te))


def dos_etapas(tr, te):
    """Etapa 1: ¿hay viviendas afectadas? (logística). Etapa 2: ¿cuántas, si las hay? (Gamma con enlace log)."""
    xtr, xte = matriz(tr), matriz(te)
    s = StandardScaler().fit(xtr)
    hay = (tr["viviendas"] > 0).astype(int)
    p = LogisticRegression(C=0.1, max_iter=3000).fit(s.transform(xtr), hay).predict_proba(s.transform(xte))[:, 1]
    pos = tr["viviendas"] > 0
    g = GammaRegressor(alpha=1.0, max_iter=3000).fit(s.transform(xtr[pos.to_numpy()]), tr.loc[pos, "viviendas"])
    return p * g.predict(s.transform(xte))


def binomial_negativa(tr, te):
    """NB2 con penalización L2, ajustada por máxima verosimilitud con scipy (no requiere statsmodels)."""
    s = StandardScaler().fit(matriz(tr))
    x = np.column_stack([np.ones(len(tr)), s.transform(matriz(tr))])
    xt = np.column_stack([np.ones(len(te)), s.transform(matriz(te))])
    y = tr["viviendas"].to_numpy(dtype=float)
    lam = 10.0
    tope = np.log(y.max() + 1)              # evita predicciones mayores que el máximo visto en entrenamiento

    def nll(th):
        b, la = th[:-1], th[-1]
        a = np.exp(la)                       # dispersión
        mu = np.exp(np.clip(x @ b, -30, tope))
        r = 1 / a
        ll = (special.gammaln(y + r) - special.gammaln(r) - special.gammaln(y + 1)
              + r * np.log(r / (r + mu)) + y * np.log(mu / (r + mu)))
        return -ll.sum() + lam * np.sum(b[1:] ** 2)

    th0 = np.zeros(x.shape[1] + 1)
    th0[0] = np.log(y.mean() + 1e-9)
    res = optimize.minimize(nll, th0, method="L-BFGS-B", options={"maxiter": 500})
    return np.exp(np.clip(xt @ res.x[:-1], -30, tope))


def boosting_poisson(tr, te):
    try:
        import lightgbm as lgb
        m = lgb.LGBMRegressor(objective="poisson", n_estimators=300, learning_rate=0.03, num_leaves=15,
                              min_child_samples=200, reg_lambda=5.0, subsample=0.8, subsample_freq=1, verbose=-1)
    except ImportError:
        m = HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.03, max_leaf_nodes=15,
                                          min_samples_leaf=200, l2_regularization=5.0, random_state=0)
    m.fit(matriz(tr), tr["viviendas"])
    return m.predict(matriz(te))


def zinb(tr, te):
    """Binomial negativa con ceros inflados (statsmodels). Si no está instalado, se omite."""
    try:
        from statsmodels.discrete.count_model import ZeroInflatedNegativeBinomialP
    except ImportError:
        return None
    s = StandardScaler().fit(matriz(tr))
    x = np.column_stack([np.ones(len(tr)), s.transform(matriz(tr))])
    xt = np.column_stack([np.ones(len(te)), s.transform(matriz(te))])
    m = ZeroInflatedNegativeBinomialP(tr["viviendas"].to_numpy(), x, exog_infl=x, p=2)
    r = m.fit_regularized(alpha=1.0, maxiter=300, disp=0)
    return r.predict(xt, exog_infl=xt)


MODELOS = {"R00 siempre cero": cero, "R0 climatologia (sin modelo)": climatologia, "M1 Poisson": poisson, "M2 dos etapas": dos_etapas,
           "M3 binomial negativa": binomial_negativa, "M4 boosting Poisson": boosting_poisson,
           "M5 binomial negativa con ceros inflados": zinb}


# --------------------------------------------------------------------------------------------------- métricas
def metricas(te: pd.DataFrame, pred: np.ndarray) -> dict:
    y = te["viviendas"].to_numpy()
    real = te.assign(p=pred).groupby("clave").agg(real=("viviendas", "sum"), pred=("p", "sum"))
    top_r = set(real.nlargest(10, "real").index[real.nlargest(10, "real")["real"] > 0])
    top_p = set(real.nlargest(10, "pred").index)
    return {"mae_distrito_semana": float(np.mean(np.abs(y - pred))),
            "mae_log": float(np.mean(np.abs(np.log1p(y) - np.log1p(pred)))),
            "total_real": float(y.sum()), "total_predicho": float(pred.sum()),
            "error_total_pct": float(100 * (pred.sum() - y.sum()) / max(y.sum(), 1)),
            "spearman_distritos": float(stats.spearmanr(real["real"], real["pred"]).statistic)
            if real["real"].nunique() > 1 else np.nan,
            "acierto_top10": float(len(top_r & top_p) / len(top_r)) if top_r else np.nan,
            "pr_auc_hay_evento": float(average_precision_score(y > 0, pred)) if (y > 0).any() and np.ptp(pred) > 0
            else np.nan,
            "tasa_semanas_con_evento": float((y > 0).mean())}


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    b = tabla(ARGS.lluvia_semana)
    print(f"Base: {len(b):,} distrito-semanas, {b['clave'].nunique()} distritos, "
          f"{int((b['viviendas'] > 0).sum())} con viviendas afectadas (Y > 0)")
    filas, preds = [], []
    for anio in ANIOS_PRUEBA:
        tr, te = historia(b[b["anio"] < anio], b[b["anio"] == anio])
        for nombre, f in MODELOS.items():
            p = f(tr, te)
            if p is None:
                continue
            p = np.clip(np.nan_to_num(p), 0, None)
            filas.append({"anio": anio, "modelo": nombre, **metricas(te, p)})
            preds.append(te[["clave", "semana", "viviendas"]].assign(modelo=nombre, prediccion=p))
        print(f"  {anio}: listo")
    m = pd.DataFrame(filas)
    m.to_csv(SALIDA / "metricas_por_anio.csv", index=False, float_format="%.4f")
    pd.concat(preds).to_csv(SALIDA / "predicciones_validacion.csv", index=False, float_format="%.3f")
    res = m.groupby("modelo").agg(mae=("mae_distrito_semana", "mean"), mae_log=("mae_log", "mean"),
                                  error_total_pct_abs=("error_total_pct",
                                                                                            lambda s: s.abs().median()),
                                  spearman=("spearman_distritos", "mean"), top10=("acierto_top10", "mean"),
                                  pr_auc=("pr_auc_hay_evento", "mean")).reset_index()
    res.to_csv(SALIDA / "metricas_resumen.csv", index=False, float_format="%.4f")
    clave = m[m["anio"].isin([2017, 2023])][["anio", "modelo", "total_real", "total_predicho", "error_total_pct",
                                             "spearman_distritos", "acierto_top10", "pr_auc_hay_evento"]]
    clave.to_csv(SALIDA / "ranking_2017_2023.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 200)
    print("\nResumen 2012-2025 (promedio por año de prueba):\n", res.round(3).to_string(index=False))
    print("\n2017 y 2023:\n", clave.round(3).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lluvia-semana", action="store_true", help="usar la lluvia de la misma semana (techo)")
    ap.add_argument("--descargar", action="store_true", help="volver a bajar el SINPAD del INDECI")
    ARGS = ap.parse_args()
    sys.exit(main())
