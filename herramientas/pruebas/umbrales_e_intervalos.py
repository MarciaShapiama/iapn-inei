"""Umbrales de aviso en fases e intervalos de confianza del modelo por plazo (src/prediccion_semanal.py).

Usa SOLO las predicciones fuera de muestra de la validación por años (2008-2025), sin volver a entrenar:
    data/modelo/resultados_plazo/predicciones_validacion.csv.gz
    data/modelo/resultados_plazo/metricas_por_anio.csv

1. Umbrales: para cada plazo y umbral de probabilidad (modelo calibrado, el que se publica), cuántos avisos habría
   dado, cuántos acertaron (precisión), qué parte de las emergencias tuvo aviso (captura), cuántas emergencias
   quedaron sin aviso y cuántos avisos por distrito y año. Con eso se eligen dos fases: «atención» y «alerta».
2. Intervalos: bootstrap por bloques de AÑOS (se sortean años completos con reemplazo, 2 000 veces), porque las
   semanas de un mismo año no son independientes. Para la diferencia de PR-AUC modelo − climatología y de BSS.
3. Por densidad: distritos en tercios por densidad de población (INEI 2020, data/exposicion/ubigeo_distritos.csv),
   como en Morales et al. (2026), que encontraron que estos modelos fallan donde hay pocos registros.

Salida: docs/evidencia/umbrales_e_intervalos.json · Uso: python herramientas/pruebas/umbrales_e_intervalos.py
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

R = Path(__file__).resolve().parents[2]
PRED = R / "data" / "modelo" / "resultados_plazo" / "predicciones_validacion.csv.gz"
ANUAL = R / "data" / "modelo" / "resultados_plazo" / "metricas_por_anio.csv"
UBIGEO = R / "data" / "exposicion" / "ubigeo_distritos.csv"
SALIDA = R / "docs" / "evidencia" / "umbrales_e_intervalos.json"
MODELO = "logística con variables del aviso"
CALIBRADO = "logística con aviso, calibrada"
CLIMA = "climatología distrito y mes"
UMBRALES = [0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30]
B = 2000
SEMILLA = 7


def plano(x) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


def tabla_umbrales(q: pd.DataFrame) -> list[dict]:
    n_dist, n_anios = q.clave.nunique(), q.anio.nunique()
    out = []
    for u in UMBRALES:
        a = q.p >= u
        tp = int((a & (q.y == 1)).sum())
        out.append({"umbral": u, "avisos": int(a.sum()), "aciertos": tp,
                    "precision_pct": round(100 * tp / a.sum(), 1) if a.sum() else None,
                    "captura_pct": round(100 * tp / q.y.sum(), 1),
                    "emergencias_sin_aviso": int(((~a) & (q.y == 1)).sum()),
                    "avisos_por_distrito_y_anio": round(a.sum() / n_dist / n_anios, 2)})
    return out


def bootstrap(p: pd.DataFrame, m: pd.DataFrame, h: int, rng) -> dict:
    mod = p[(p.h == h) & (p.modelo == MODELO)].sort_values(["clave", "semana_obj"]).reset_index(drop=True)
    cli = p[(p.h == h) & (p.modelo == CLIMA)].sort_values(["clave", "semana_obj"]).reset_index(drop=True)
    assert (mod.clave.values == cli.clave.values).all() and (mod.semana_obj.values == cli.semana_obj.values).all()
    anios = np.array(sorted(mod.anio.unique()))
    idx = {a: np.flatnonzero(mod.anio.values == a) for a in anios}
    ma = m[(m.h == h)].pivot_table(index="anio", columns="modelo", values=["brier", "brier_ref", "n"])
    dif_auc, dif_bss = [], []
    for _ in range(B):
        s = rng.choice(anios, size=len(anios), replace=True)
        ii = np.concatenate([idx[a] for a in s])
        y = mod.y.values[ii]
        if y.sum() == 0:
            continue
        dif_auc.append(average_precision_score(y, mod.p.values[ii]) - average_precision_score(y, cli.p.values[ii]))
        bss = {}
        for k in (CALIBRADO, CLIMA):
            n = ma[("n", k)].loc[s].values
            bss[k] = 1 - (ma[("brier", k)].loc[s].values * n).sum() / (ma[("brier_ref", k)].loc[s].values * n).sum()
        dif_bss.append(bss[CALIBRADO] - bss[CLIMA])
    dif_auc, dif_bss = np.array(dif_auc), np.array(dif_bss)
    base_auc = average_precision_score(mod.y, mod.p) - average_precision_score(cli.y, cli.p)
    r = lambda x: round(float(x), 3)  # noqa: E731
    return {"pr_auc_modelo_menos_climatologia": r(base_auc),
            "ic95": [r(np.percentile(dif_auc, 2.5)), r(np.percentile(dif_auc, 97.5))],
            "pct_replicas_modelo_gana": round(100 * float((dif_auc > 0).mean()), 1),
            "bss_calibrado_menos_climatologia_ic95": [r(np.percentile(dif_bss, 2.5)), r(np.percentile(dif_bss, 97.5))],
            "pct_replicas_bss_gana": round(100 * float((dif_bss > 0).mean()), 1)}


def por_densidad(p: pd.DataFrame, h: int, dens: pd.Series) -> list[dict]:
    out = []
    for nombre in ("baja", "media", "alta"):
        claves = set(dens[dens == nombre].index)
        fila = {"densidad": nombre, "distritos": len(claves)}
        for k, etq in ((MODELO, "modelo"), (CLIMA, "climatologia")):
            q = p[(p.h == h) & (p.modelo == k) & p.clave.isin(claves)]
            fila[f"pr_auc_{etq}"] = round(float(average_precision_score(q.y, q.p)), 3)
            fila["tasa"] = round(float(q.y.mean()), 4)
            fila["emergencias"] = int(q.y.sum())
        fila["veces_sobre_tasa"] = round(fila["pr_auc_modelo"] / fila["tasa"], 1)
        out.append(fila)
    return out


def main() -> None:
    p = pd.read_csv(PRED)
    p["anio"] = p.semana_obj.str[:4].astype(int)
    m = pd.read_csv(ANUAL)
    u = pd.read_csv(UBIGEO, dtype={"inei": str})
    u["clave"] = [plano(a) + plano(b) for a, b in zip(u.departamento, u.distrito)]
    d = u.set_index("clave")["pob_densidad_2020"]
    d = d[d.index.isin(p.clave.unique())]
    dens = pd.qcut(d, 3, labels=["baja", "media", "alta"]).astype(str)
    rng = np.random.default_rng(SEMILLA)
    out = {"metodo": __doc__.split("Salida:")[0].strip(), "anios_validacion": [int(p.anio.min()), int(p.anio.max())],
           "distritos_sin_densidad": sorted(set(p.clave.unique()) - set(dens.index)), "plazos": {}}
    for h in (1, 2, 3, 4):
        q = p[(p.h == h) & (p.modelo == CALIBRADO)]
        out["plazos"][f"h{h}"] = {"umbrales_modelo_calibrado": tabla_umbrales(q),
                                 "bootstrap_por_anios": bootstrap(p, m, h, rng),
                                 "por_densidad": por_densidad(p, h, dens)}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for h in (1, 2, 3, 4):
        x = out["plazos"][f"h{h}"]
        print(f"h{h}", x["bootstrap_por_anios"])
        print(pd.DataFrame(x["umbrales_modelo_calibrado"]).to_string(index=False))
        print(pd.DataFrame(x["por_densidad"]).to_string(index=False))


if __name__ == "__main__":
    main()
