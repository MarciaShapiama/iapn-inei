"""Auditoría de la variable dependiente construida con el SINPAD (src/etiqueta_sinpad.py).

Responde: ¿la Y es real y concuerda con lo que pasó? Cuatro pruebas, todas con datos del repositorio:
    1. Los 13 eventos verificados con noticias (data/eventos/catalogo_verificado.csv): ¿tienen un registro SINPAD de
       agua en el mismo distrito, a 7 o a 14 días?
    2. Coincidencia con DesInventar en 2003-2015 (misma semana y ±2 semanas).
    3. Distribución de Y por año, por mes y por distrito.
    4. Muestra aleatoria de 20 registros (semilla fija) con su código SINPAD, para revisarlos a mano.

Salida: docs/evidencia/auditoria_sinpad.json
Uso: python herramientas/pruebas/auditoria_sinpad.py   (antes: python src/etiqueta_sinpad.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
from etiqueta_sinpad import EVENTOS, FIN_ETIQUETA, FUSION, normal  # noqa: E402

SALIDA = RAIZ / "docs" / "evidencia" / "auditoria_sinpad.json"


def main() -> dict:
    ev = pd.read_csv(EVENTOS, dtype={"ubigeo": str, "ubigeo_modelo": str, "codigo": str}, parse_dates=["fecha", "semana"])
    out = {"registros_agua": len(ev), "periodo": [str(ev["fecha"].min().date()), str(ev["fecha"].max().date())]}

    # 1. eventos verificados con noticias
    cat = pd.read_csv(RAIZ / "data" / "eventos" / "catalogo_verificado.csv", dtype={"ubigeo": str}, parse_dates=["fecha"])
    filas = []
    for r in cat.itertuples():
        u = FUSION.get(r.ubigeo, r.ubigeo)
        cerca = ev[(ev["ubigeo_modelo"] == u) & ((ev["fecha"] - r.fecha).abs() <= pd.Timedelta(days=14))].copy()
        cerca["dias"] = (cerca["fecha"] - r.fecha).dt.days
        a7 = cerca[cerca["dias"].abs() <= 7]
        filas.append({"evento": r.id, "fecha_noticia": str(r.fecha.date()), "ubigeo": r.ubigeo,
                      "en_sinpad_7_dias": len(a7) > 0, "en_sinpad_14_dias": len(cerca) > 0,
                      "registros_sinpad": cerca.sort_values("dias")[["codigo", "fecha", "peligro", "dias"]]
                      .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d")).head(5).to_dict(orient="records")})
    out["eventos_verificados"] = {"total": len(filas), "con_registro_7_dias": sum(f["en_sinpad_7_dias"] for f in filas),
                                  "con_registro_14_dias": sum(f["en_sinpad_14_dias"] for f in filas), "detalle": filas}

    # 2. coincidencia con DesInventar 2003-2015
    b = pd.read_csv(RAIZ / "data" / "modelo" / "base_distrito_semana.csv", parse_dates=["semana"])
    di = b[(b["emergencia_sem"] == 1) & b["semana"].dt.year.between(2003, 2015)][["clave", "semana"]]
    si = set(zip(ev["clave"], ev["semana"]))
    misma = sum((c, s) in si for c, s in zip(di["clave"], di["semana"]))
    tol = sum(any((c, s + pd.Timedelta(weeks=k)) in si for k in range(-2, 3)) for c, s in zip(di["clave"], di["semana"]))
    sin_03_15 = ev[ev["fecha"].dt.year.between(2003, 2015)].groupby(["clave", "semana"]).ngroups
    out["comparacion_desinventar_2003_2015"] = {
        "semanas_con_registro_desinventar": len(di), "semanas_con_registro_sinpad": sin_03_15,
        "desinventar_en_sinpad_misma_semana": misma, "desinventar_en_sinpad_mas_menos_2_semanas": tol,
        "lectura": "Las fuentes registran cosas distintas: no se deben unir en una sola serie."}

    # 3. distribución de Y (la misma construcción que usa el modelo)
    from modelo_inundacion import cargar, OBJETIVO
    y = cargar("sinpad").dropna(subset=[OBJETIVO])
    y["anio"], y["mes"] = y["semana"].dt.year, y["semana"].dt.month
    out["distribucion_Y"] = {
        "filas": len(y), "y1": int(y[OBJETIVO].sum()), "pct_y1": round(100 * y[OBJETIVO].mean(), 2),
        "semanas_con_registro": int(y["emergencia_sem"].sum()), "fin_etiqueta": FIN_ETIQUETA,
        "por_anio": y.groupby("anio").agg(semanas_con_registro=("emergencia_sem", "sum"), y1=(OBJETIVO, "sum"))
                     .astype(int).to_dict(orient="index"),
        "semanas_con_registro_por_mes": y.groupby("mes")["emergencia_sem"].sum().astype(int).to_dict(),
        "top_distritos": y.groupby("distrito")["emergencia_sem"].sum().sort_values(ascending=False).head(15)
                          .astype(int).to_dict(),
        "distritos_sin_registro": int((y.groupby("clave")["emergencia_sem"].sum() == 0).sum()),
        "distritos": int(y["clave"].nunique())}

    # 4. muestra para revisión manual
    m = ev[ev["fecha"] <= FIN_ETIQUETA].sample(20, random_state=2026).sort_values("fecha")
    out["muestra_revision_manual"] = m[["codigo", "fecha", "dist", "prov", "peligro", "afectados", "viv_afectadas"]] \
        .assign(fecha=lambda d: d["fecha"].dt.strftime("%Y-%m-%d")).to_dict(orient="records")

    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    e = out["eventos_verificados"]
    c = out["comparacion_desinventar_2003_2015"]
    print(f"Eventos verificados con registro SINPAD: {e['con_registro_7_dias']}/{e['total']} a 7 días, "
          f"{e['con_registro_14_dias']}/{e['total']} a 14 días")
    print(f"DesInventar en SINPAD: {c['desinventar_en_sinpad_misma_semana']}/{c['semanas_con_registro_desinventar']} "
          f"misma semana, {c['desinventar_en_sinpad_mas_menos_2_semanas']} con ±2 semanas")
    d = out["distribucion_Y"]
    print(f"Y: {d['y1']:,} de {d['filas']:,} ({d['pct_y1']} %); distritos sin registro: {d['distritos_sin_registro']}/{d['distritos']}")
    return out


if __name__ == "__main__":
    main()
