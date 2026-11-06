"""Predicción por plazo: ¿habrá emergencia en el distrito en la semana t+h? (h = 1, 2, 3 y 4) y cuántas viviendas.

Pregunta: con lo que se sabe al terminar la semana t (lunes a domingo), ¿cuál es la probabilidad de que el SINPAD
registre una emergencia por inundación o lluvia intensa en el distrito exactamente en la semana t+h? Y si ocurre,
¿cuántas viviendas y personas podrían verse afectadas?

Datos (todo está en el repositorio):
    data/modelo/base_distrito_semana.csv     78 distritos × semanas: lluvia (NASA POWER), caudal (GloFAS), Niño 1+2,
                                             zona inundable (JRC) — src/base_modelo.py
    data/modelo/sinpad/sinpad_semanal.csv    emergencias del SINPAD por distrito y semana — src/etiqueta_sinpad.py
    data/modelo/lluvia_distritos.csv         lluvia diaria por distrito (NASA POWER), para los días sobre p95 y p99
    data/modelo/caudal_rios.csv              caudal diario de los ríos Piura, Chira y Tumbes (GloFAS v4)
    dashboard/data/viviendas_censo.json      viviendas y personas del Censo 2025 en la zona de 1 en 100 años
    data/exposicion/ubigeo_distritos.csv     superficie del distrito (para el % inundable)

Variables (todas se conocen al terminar la semana t; ninguna mira la semana que se predice):
    sin aviso   lluvia de 30 días, caudal frente a lo normal, Niño 1+2, época del año de la semana t+h (calendario),
                frecuencia histórica de emergencias del distrito (solo años de entrenamiento)
    con aviso   lo anterior + ¿hubo un día sobre el p95 o el p99 de lluvia del distrito en la semana t? (umbrales
                2001-2020 como en herramientas/pruebas/prueba_aviso_pasado.py), lluvia de 7 días, ¿el río pasó su
                p95 de caudal diario en la semana t? (distritos de la lista CUENCA de src/aviso_lluvia.py), % del
                distrito en zona inundable, viviendas y personas del censo en esa zona, ¿hubo emergencia en la semana t?

Validación por años: para cada año A de 2008 a 2025 se entrena con los ejemplos cuya semana objetivo t+h es anterior al
1 de enero de A y se prueba con los de A. Nunca se mezclan semanas de un mismo año.

Uso:
    python src/prediccion_semanal.py                 evalúa y escribe la predicción de la última semana
    python src/prediccion_semanal.py --sin-anio 2017 evalúa sin entrenar nunca con 2017 (sensibilidad)
Salidas:
    data/modelo/resultados_plazo/metricas_por_plazo.csv, metricas_por_anio.csv, predicciones_validacion.csv.gz
    dashboard/data/prediccion_semanal.json  (solo en la corrida normal)
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import GammaRegressor, LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from config import DASH_DATA, DATA  # noqa: E402
from ubigeo import clave_distrito  # noqa: E402

BASE = DATA / "modelo" / "base_distrito_semana.csv"
SINPAD = DATA / "modelo" / "sinpad" / "sinpad_semanal.csv"
LLUVIA = DATA / "modelo" / "lluvia_distritos.csv"
CAUDAL = DATA / "modelo" / "caudal_rios.csv"
CENSO = DASH_DATA / "viviendas_censo.json"
UBIGEO = DATA / "exposicion" / "ubigeo_distritos.csv"
SALIDA = DATA / "modelo" / "resultados_plazo"
JSON = DASH_DATA / "prediccion_semanal.json"

INICIO, FIN_ETIQUETA = "2003-01-06", "2025-12-29"   # semanas con etiqueta confiable del SINPAD
PLAZOS = (1, 2, 3, 4)
ANIOS_PRUEBA = list(range(2008, 2026))
SIN_AVISO = ["log_lluvia_30d", "log_caudal_razon", "nino12", "sen_obj", "cos_obj", "hist_frec"]
CON_AVISO = SIN_AVISO + ["lluvia_sobre_p95", "lluvia_sobre_p99", "log_lluvia_7d", "caudal_sobre_p95", "pct_inundable",
                         "log_censo_viviendas", "log_censo_personas", "emergencia_t"]


def plano(x) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


# ------------------------------------------------------------------------------------------------- 1. panel
def senales_lluvia() -> pd.DataFrame:
    """¿Hubo algún día de la semana con lluvia sobre el p95 o el p99 del distrito? Umbrales: días con >= 1 mm de
    2001-2020 del mismo distrito (igual que herramientas/pruebas/prueba_aviso_pasado.py)."""
    ll = pd.read_csv(LLUVIA, parse_dates=["fecha"])
    base = ll[ll.fecha.dt.year.between(2001, 2020) & (ll.lluvia >= 1)]
    u = base.groupby("clave")["lluvia"].agg(p95=lambda x: np.percentile(x, 95), p99=lambda x: np.percentile(x, 99))
    ll["semana"] = ll.fecha.dt.to_period("W-SUN").dt.start_time
    s = ll.groupby(["clave", "semana"])["lluvia"].max().rename("mm_max").reset_index().join(u, on="clave")
    s["lluvia_sobre_p95"] = (s.mm_max > s.p95).astype(float).where(s.mm_max.notna())
    s["lluvia_sobre_p99"] = (s.mm_max > s.p99).astype(float).where(s.mm_max.notna())
    return s[["clave", "semana", "lluvia_sobre_p95", "lluvia_sobre_p99"]]


def senales_caudal() -> pd.DataFrame:
    """¿El río pasó su percentil 95 de caudal diario (2001-2020) algún día de la semana?"""
    q = pd.read_csv(CAUDAL, parse_dates=["fecha"])
    p95 = q[q.fecha.dt.year.between(2001, 2020)].groupby("rio")["caudal"].quantile(0.95)
    q["semana"] = q.fecha.dt.to_period("W-SUN").dt.start_time
    s = q.groupby(["rio", "semana"])["caudal"].max().rename("q_max").reset_index().join(p95.rename("q_p95"), on="rio")
    s["caudal_sobre_p95"] = (s.q_max > s.q_p95).astype(float)
    return s[["rio", "semana", "caudal_sobre_p95"]].rename(columns={"rio": "rio_cuenca"})


def censo() -> pd.DataFrame:
    j = json.load(open(CENSO, encoding="utf-8"))
    c = pd.DataFrame(j["escenarios"]["rp100"]["distritos"])[["ubigeo", "viviendas", "personas"]]
    return c.rename(columns={"viviendas": "censo_viviendas", "personas": "censo_personas"}).astype({"ubigeo": str})


def panel() -> pd.DataFrame:
    from aviso_lluvia import rio_de
    b = pd.read_csv(BASE, parse_dates=["semana"], dtype={"ubigeo": str})
    b = b[["clave", "ubigeo", "departamento", "provincia", "distrito", "semana", "semana_anio", "lluvia_7d", "lluvia_30d",
           "caudal_razon", "nino12", "km2_inundable_rp100", "personas_rp100"]].copy()
    b = b[b.semana >= INICIO]
    s = pd.read_csv(SINPAD, parse_dates=["semana"])
    s["viviendas"] = s.viv_afectadas.fillna(0) + s.viv_destruidas.fillna(0)
    s = s.groupby(["clave", "semana"])[["eventos", "viviendas"]].sum().reset_index()
    b = b.merge(s, on=["clave", "semana"], how="left")
    dentro = b.semana <= FIN_ETIQUETA
    b["E"] = (b.eventos.fillna(0) > 0).astype(float).where(dentro)
    b["V"] = b.viviendas.fillna(0).where(dentro)
    b = b.merge(senales_lluvia(), on=["clave", "semana"], how="left")
    b["rio_cuenca"] = b.distrito.map(rio_de)
    b = b.merge(senales_caudal(), on=["rio_cuenca", "semana"], how="left")
    b["caudal_sobre_p95"] = b.caudal_sobre_p95.fillna(0.0).where(b.rio_cuenca.notna(), 0.0)
    sup = pd.read_csv(UBIGEO, dtype={"inei": str}).set_index("inei")["superficie"]
    b["pct_inundable"] = 100 * b.km2_inundable_rp100 / b.ubigeo.map(sup)
    b = b.merge(censo(), on="ubigeo", how="left")
    # El censo publica solo distritos con 10 o más viviendas en la zona: los demás quedan en 0 (pocas o ninguna).
    b[["censo_viviendas", "censo_personas"]] = b[["censo_viviendas", "censo_personas"]].fillna(0)
    b["log_lluvia_30d"] = np.log1p(b.lluvia_30d.clip(lower=0))
    b["log_lluvia_7d"] = np.log1p(b.lluvia_7d.clip(lower=0))
    b["log_caudal_razon"] = np.log(b.caudal_razon.clip(lower=0.05))
    b["log_censo_viviendas"] = np.log1p(b.censo_viviendas)
    b["log_censo_personas"] = np.log1p(b.censo_personas)
    b["emergencia_t"] = b.E
    return b.sort_values(["clave", "semana"]).reset_index(drop=True)


def ejemplos(p: pd.DataFrame, h: int) -> pd.DataFrame:
    """Una fila por distrito y semana t: variables de la semana t y objetivo de la semana t+h."""
    d = p.copy()
    g = d.groupby("clave")
    d["semana_obj"] = d.semana + pd.Timedelta(weeks=h)
    d["y"] = g["E"].shift(-h)
    d["v"] = g["V"].shift(-h)
    ang = 2 * np.pi * d.semana_obj.dt.isocalendar().week.astype(int).clip(1, 52) / 52
    d["sen_obj"], d["cos_obj"] = np.sin(ang), np.cos(ang)
    d["mes_obj"] = d.semana_obj.dt.month
    d["anio_obj"] = d.semana_obj.dt.year
    d["h"] = h
    return d


def con_historia(tr: pd.DataFrame, te: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Frecuencia de emergencias del distrito, de su mes y del mes en general, SOLO con el entrenamiento."""
    f = tr.groupby("clave")["y"].mean().rename("hist_frec")
    fm = tr.groupby(["clave", "mes_obj"])["y"].mean().rename("clim_distrito_mes")
    m = tr.groupby("mes_obj")["y"].mean().rename("clim_mes")
    vpos = tr[tr.y == 1].groupby("clave")["v"].mean().rename("v_media_evento")
    out = []
    for d in (tr, te):
        d = d.drop(columns=[c for c in ("hist_frec", "clim_distrito_mes", "clim_mes", "v_media_evento") if c in d])
        d = d.join(f, on="clave").join(fm, on=["clave", "mes_obj"]).join(m, on="mes_obj").join(vpos, on="clave")
        d["hist_frec"] = d.hist_frec.fillna(f.mean())
        d["clim_mes"] = d.clim_mes.fillna(tr.y.mean())
        d["clim_distrito_mes"] = (0.5 * d.clim_distrito_mes.fillna(d.clim_mes) + 0.5 * d.clim_mes)
        d["v_media_evento"] = d.v_media_evento.fillna(tr.loc[tr.y == 1, "v"].mean())
        out.append(d)
    return out[0], out[1]


# ---------------------------------------------------------------------------------------------- 2. modelos
def _x(d: pd.DataFrame, cols: list[str], med: pd.Series) -> np.ndarray:
    return d[cols].astype(float).fillna(med).fillna(0).to_numpy()


def logistica(tr, te, cols):
    med = tr[cols].median()
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=3000))
    m.fit(_x(tr, cols, med), tr.y.astype(int))
    return m.predict_proba(_x(te, cols, med))[:, 1], m, med


def lightgbm(tr, te, cols):
    import lightgbm as lgb
    med = tr[cols].median()
    m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=7, max_depth=3, min_child_samples=300,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=10.0, random_state=7,
                           verbose=-1, n_jobs=4)
    m.fit(_x(tr, cols, med), tr.y.astype(int))
    return m.predict_proba(_x(te, cols, med))[:, 1]


def viviendas_si_ocurre(tr, te, cols):
    """Etapa 2: viviendas afectadas si hay emergencia (Gamma con enlace log, entrenada con las semanas con evento)."""
    pos = tr[(tr.y == 1) & (tr.v > 0)]
    med = tr[cols].median()
    g = make_pipeline(StandardScaler(), GammaRegressor(alpha=1.0, max_iter=3000))
    g.fit(_x(pos, cols, med), pos.v)
    return g.predict(_x(te, cols, med)), g, med


def regla(tr, te, columna: str) -> np.ndarray:
    """Una regla simple vuelta probabilidad: frecuencia de emergencias en el entrenamiento según el valor de la regla."""
    t = tr.groupby(tr[columna].fillna(-1))["y"].mean()
    return te[columna].fillna(-1).map(t).fillna(tr.y.mean()).to_numpy()


def evaluar_anio(tr, te) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Devuelve {modelo: (probabilidad, viviendas esperadas)} para el año de prueba."""
    v_cond, _, _ = viviendas_si_ocurre(tr, te, CON_AVISO)
    v_hist = te.v_media_evento.to_numpy()
    res = {}
    for nombre, p in {
        "regla: emergencia en la semana t": regla(tr, te, "emergencia_t"),
        "regla: mes del año": te.clim_mes.to_numpy(),
        "regla: lluvia sobre p95 en la semana t": regla(tr, te, "lluvia_sobre_p95"),
        "climatología distrito y mes": te.clim_distrito_mes.to_numpy(),
    }.items():
        res[nombre] = (p, p * v_hist)
    p0, _, _ = logistica(tr, te, SIN_AVISO)
    p1, _, _ = logistica(tr, te, CON_AVISO)
    p2 = lightgbm(tr, te, CON_AVISO)
    res["logística sin variables del aviso"] = (p0, p0 * v_cond)
    res["logística con variables del aviso"] = (p1, p1 * v_cond)
    res["LightGBM con variables del aviso"] = (p2, p2 * v_cond)
    return res


# ---------------------------------------------------------------------------------------------- 3. métricas
def top10(te: pd.DataFrame, esperado: np.ndarray) -> float:
    r = te.assign(e=esperado).groupby("clave").agg(real=("v", "sum"), pred=("e", "sum"))
    reales = set(r[r.real > 0].nlargest(10, "real").index)
    if not reales:
        return np.nan
    return len(reales & set(r.nlargest(10, "pred").index)) / len(reales)


def correr(sin_anio: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p = panel()
    filas, preds = [], []
    for h in PLAZOS:
        e = ejemplos(p, h)
        e = e[e.y.notna() & (e.semana_obj <= FIN_ETIQUETA)]
        for anio in ANIOS_PRUEBA:
            if anio == sin_anio:
                continue
            tr = e[e.semana_obj < pd.Timestamp(anio, 1, 1)]
            if sin_anio is not None:
                tr = tr[tr.anio_obj != sin_anio]
            te = e[e.anio_obj == anio]
            assert tr.semana_obj.max() < te.semana_obj.min() and (te.semana < te.semana_obj).all()
            tr, te = con_historia(tr, te)
            prev = tr.y.mean()
            for modelo, (prob, esp) in evaluar_anio(tr, te).items():
                y = te.y.to_numpy()
                bs, bs_ref = brier_score_loss(y, prob), brier_score_loss(y, np.full(len(y), prev))
                filas.append({"h": h, "anio": anio, "modelo": modelo, "n": len(y), "positivos": int(y.sum()),
                              "tasa": float(y.mean()), "pr_auc": float(average_precision_score(y, prob)) if y.any() else np.nan,
                              "brier": bs, "brier_ref": bs_ref, "bss": 1 - bs / bs_ref,
                              "top10": top10(te, esp), "v_real": float(te.v.sum()), "v_pred": float(esp.sum())})
                preds.append(pd.DataFrame({"h": h, "modelo": modelo, "clave": te.clave.to_numpy(),
                                           "semana_obj": te.semana_obj.to_numpy(), "y": y, "v": te.v.to_numpy(),
                                           "p": prob, "v_esperadas": esp}))
        print(f"  plazo {h}: listo", flush=True)
    m = pd.DataFrame(filas)
    pr = pd.concat(preds, ignore_index=True)
    return m, pr, resumen(m, pr)


def resumen(m: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for (h, modelo), g in pr.groupby(["h", "modelo"]):
        mm = m[(m.h == h) & (m.modelo == modelo)]
        tasa = g.y.mean()
        auc = average_precision_score(g.y, g.p)
        err = 100 * (mm.v_pred - mm.v_real) / mm.v_real.where(mm.v_real > 0)
        fila = {"h": h, "modelo": modelo, "pr_auc": auc, "tasa_sin_modelo": tasa, "pr_auc_sobre_tasa": auc / tasa,
                "bss": 1 - (mm.brier * mm.n).sum() / (mm.brier_ref * mm.n).sum(),
                "top10_promedio": mm.top10.mean(), "error_total_viviendas_mediana_abs_pct": err.abs().median()}
        for a in (2017, 2023):
            x = mm[mm.anio == a]
            if len(x):
                fila[f"pr_auc_{a}"] = float(x.pr_auc.iloc[0])
                fila[f"top10_{a}"] = float(x.top10.iloc[0])
                fila[f"error_viviendas_{a}_pct"] = float(100 * (x.v_pred.iloc[0] - x.v_real.iloc[0]) / x.v_real.iloc[0])
        filas.append(fila)
    return pd.DataFrame(filas)


# ------------------------------------------------------------------------------------------ 4. predicción hoy
def prediccion_actual(res: pd.DataFrame, m: pd.DataFrame) -> dict:
    """Entrena con todo lo etiquetado (semana objetivo hasta FIN_ETIQUETA) y predice desde la última semana con datos."""
    p = panel()
    ok = p.groupby("semana")["lluvia_30d"].apply(lambda s: s.notna().mean())
    t = ok[ok >= 0.9].index.max()
    salida = {"semana_base": str(t.date()), "distritos": {}}
    j = json.load(open(CENSO, encoding="utf-8"))
    tot = j["escenarios"]["rp100"]
    pers_por_viv = tot["personas"] / tot["viviendas"]
    for h in PLAZOS:
        e = ejemplos(p, h)
        tr = e[e.y.notna() & (e.semana_obj <= FIN_ETIQUETA)]
        hoy = e[e.semana == t].copy()
        tr, hoy = con_historia(tr, hoy)
        prob, _, _ = logistica(tr, hoy, CON_AVISO)
        vc, _, _ = viviendas_si_ocurre(tr, hoy, CON_AVISO)
        hist = tr[(tr.y == 1) & (tr.v > 0)].groupby("clave")["v"]
        q10, q90 = hist.quantile(0.1), hist.quantile(0.9)
        for r, pr_, v in zip(hoy.itertuples(), prob, vc):
            d = salida["distritos"].setdefault(r.ubigeo, {"ubigeo": r.ubigeo, "departamento": r.departamento,
                                                          "provincia": r.provincia, "distrito": r.distrito})
            d[f"prob_h{h}"] = round(float(pr_), 4)
            if h == 1:
                ppv = (r.censo_personas / r.censo_viviendas) if r.censo_viviendas > 0 else pers_por_viv
                lo, hi = q10.get(r.clave, np.nan), q90.get(r.clave, np.nan)
                d["viviendas_si_ocurre"] = round(float(v))
                d["viviendas_rango_historico"] = [None if np.isnan(lo) else round(float(lo)), None if np.isnan(hi) else round(float(hi))]
                d["personas_si_ocurre"] = round(float(v * ppv))
                d["personas_por_vivienda"] = round(float(ppv), 2)
    salida["distritos"] = sorted(salida["distritos"].values(), key=lambda d: -d["prob_h1"])
    salida["semana_objetivo"] = {f"h{h}": str((t + pd.Timedelta(weeks=h)).date()) for h in PLAZOS}
    cal = res[res.modelo == "logística con variables del aviso"].set_index("h")
    ref = res[res.modelo == "climatología distrito y mes"].set_index("h")
    anual = m.pivot_table(index=["h", "anio"], columns="modelo", values="pr_auc")
    mod, cli = anual["logística con variables del aviso"], anual["climatología distrito y mes"]
    salida["calidad_por_plazo"] = [{"h": int(h), "pr_auc": round(float(cal.loc[h, "pr_auc"]), 3),
                                    "tasa_sin_modelo": round(float(cal.loc[h, "tasa_sin_modelo"]), 3),
                                    "pr_auc_climatologia": round(float(ref.loc[h, "pr_auc"]), 3),
                                    "pr_auc_promedio_anual": round(float(mod.loc[h].mean()), 3),
                                    "pr_auc_promedio_anual_climatologia": round(float(cli.loc[h].mean()), 3),
                                    "anios_que_gana": int((mod.loc[h] > cli.loc[h]).sum()), "anios": int(mod.loc[h].size),
                                    "bss": round(float(cal.loc[h, "bss"]), 3),
                                    "top10_promedio": round(float(cal.loc[h, "top10_promedio"]), 2)} for h in PLAZOS]
    salida["modelo"] = ("Regresión logística con variables del aviso (lluvia sobre p95/p99, lluvia de 7 y 30 días, caudal "
                        "sobre p95, Niño 1+2, % inundable, censo, emergencia de la semana t, época, historia del distrito). "
                        "Etiqueta: SINPAD (INDECI) 2003-2025.")
    salida["como_leer"] = ("prob_hN = probabilidad de que el SINPAD registre una emergencia por inundación o lluvia intensa en "
                           "la semana objetivo hN. viviendas_si_ocurre: estimación si ocurre (modelo Gamma); el rango es el "
                           "10 % y 90 % de las viviendas afectadas en las emergencias pasadas del distrito. Personas = "
                           "viviendas × personas por vivienda del censo en la zona inundable del distrito. No es una alerta oficial.")
    salida["limites"] = ["El SINPAD publica cada seis meses: la variable «emergencia en la semana t» no se conoce en tiempo real.",
                         "La lluvia de NASA POWER llega con unos días de retraso; por eso la semana base puede ser anterior a hoy.",
                         "Ver docs/2_modelo/21_MODELO_POR_PLAZO.md para la calidad por plazo."]
    return salida


def main(sin_anio: int | None) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    m, pr, res = correr(sin_anio)
    sufijo = f"_sin_{sin_anio}" if sin_anio else ""
    m.to_csv(SALIDA / f"metricas_por_anio{sufijo}.csv", index=False, float_format="%.5f")
    res.to_csv(SALIDA / f"metricas_por_plazo{sufijo}.csv", index=False, float_format="%.4f")
    if not sin_anio:
        pr.to_csv(SALIDA / "predicciones_validacion.csv.gz", index=False, float_format="%.5f")
        out = prediccion_actual(res, m)
        JSON.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  {JSON.name}: semana base {out['semana_base']}, {len(out['distritos'])} distritos")
    pd.set_option("display.width", 220)
    print(res[["h", "modelo", "pr_auc", "tasa_sin_modelo", "pr_auc_sobre_tasa", "bss", "top10_promedio",
               "error_total_viviendas_mediana_abs_pct"]].round(3).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sin-anio", type=int, default=None, help="evaluar sin entrenar nunca con ese año (p. ej. 2017)")
    main(ap.parse_args().sin_anio)
