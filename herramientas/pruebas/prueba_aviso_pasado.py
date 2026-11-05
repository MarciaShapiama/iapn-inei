"""Prueba del aviso de lluvia con el pasado: ¿la lluvia fuerte o extrema aparece ANTES de los daños reportados?

Pedido: «jugar con el pasado». Si el aviso hubiera estado funcionando, ¿habría marcado lluvia fuerte o extrema en los
días previos a las inundaciones que salieron en las noticias y que registró INDECI? ¿Y cuántas veces habría avisado
sin que pasara nada?

Qué se usa (todo ya está en el repositorio, no necesita red):
    lluvia diaria observada por distrito 2001-2026, NASA POWER (satélite + reanálisis), punto en el centro del
        distrito: data/modelo/lluvia_distritos.csv (src/base_modelo.py)
    umbrales del MISMO dato: percentiles 95 y 99 de los días con lluvia (>= 1 mm) 2001-2020 de cada distrito
    emergencias de INDECI (SINPAD, datos abiertos) por distrito y semana 2003-2026:
        data/modelo/sinpad_tumbes_piura_semanal.csv
    eventos verificados con noticias: data/eventos/catalogo_verificado.csv, más dos desbordes del río Tumbes con
        noticias (29/4/2023 y 12/2/2025, docs/3_validacion/09_PRUEBA_DETECTOR_NOTICIAS.md)

Límite importante: se usa la lluvia que REALMENTE cayó, no la que se pronosticó. Mide si la regla del aviso (lluvia
de un día sobre el percentil 95 o 99 del lugar) separa los días de daño de los demás, suponiendo un pronóstico
perfecto. Es la mejor nota posible del aviso; con el pronóstico real será igual o peor.

Salida: docs/evidencia/prueba_aviso_pasado.json · Uso: python herramientas/pruebas/prueba_aviso_pasado.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[2]
SALIDA = R / "docs" / "evidencia" / "prueba_aviso_pasado.json"
LLUVIA = R / "data" / "modelo" / "lluvia_distritos.csv"
SINPAD = R / "data" / "modelo" / "sinpad_tumbes_piura_semanal.csv"
CATALOGO = R / "data" / "eventos" / "catalogo_verificado.csv"
CAUDAL = R / "data" / "modelo" / "caudal_rios.csv"      # GloFAS v4 (Open-Meteo), caudal diario 2001-2026
# Distritos de cada río con dato de caudal (mismas cuencas que el mapa 2D). Zarumilla no tiene punto GloFAS.
CUENCA = {"Piura": ["Piura", "Castilla", "Catacaos", "Cura Mori", "El Tallan", "La Arena", "La Union", "Bernal",
                    "Cristo Nos Valga", "Rinconada Llicuar", "Vice", "Bellavista de la Union", "Sechura",
                    "Veintiseis de Octubre", "Tambo Grande", "Chulucanas", "La Matanza", "Morropon", "Buenos Aires"],
          "Chira": ["Sullana", "Bellavista", "Miguel Checa", "Marcavelica", "Querecotillo", "Ignacio Escudero", "Lancones",
                    "Amotape", "Arenal", "La Huaca", "Tamarindo", "Vichayal", "Colan", "Paita"],
          "Tumbes": ["Tumbes", "Corrales", "San Juan de la Virgen", "Pampas de Hospital", "San Jacinto", "La Cruz"]}

LUGARES = R / "data" / "eventos" / "lugares.csv"
DIAS_ANTES = 3        # el aviso mira los próximos 3 días: cuenta si la lluvia fuerte cayó hasta 3 días antes del evento
EXTRA = [  # desbordes del río Tumbes con cultivos inundados varios días (noticias de Andina, ver documento 09)
    {"id": "2023-tumbes-cultivos", "fecha": "2023-04-29", "dep": "TUMBES", "distrito": "SAN JACINTO",
     "descripcion": "Desborde del río Tumbes: unas 1 600 ha de cultivo afectadas"},
    {"id": "2025-tumbes-cultivos", "fecha": "2025-02-12", "dep": "TUMBES", "distrito": "SAN JACINTO",
     "descripcion": "Desborde del río Tumbes: 1 284 ha de cultivo inundadas"},
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s.replace("Ñ", "N"))


def rio_de(dist: str) -> str | None:
    return next((r for r, ds in CUENCA.items() if norm(dist) in {norm(d) for d in ds}), None)


def cargar_caudal() -> tuple[pd.DataFrame, dict]:
    c = pd.read_csv(CAUDAL, parse_dates=["fecha"])
    b = c[(c.fecha.dt.year >= 2001) & (c.fecha.dt.year <= 2020)]
    u = {r: {"p90": float(np.percentile(g.caudal.dropna(), 90)), "p95": float(np.percentile(g.caudal.dropna(), 95)),
             "p99": float(np.percentile(g.caudal.dropna(), 99))} for r, g in b.groupby("rio")}
    return c, u


def caudal_evento(c, uc, rio, fecha) -> dict:
    if rio is None:
        return {"rio": None, "caudal": "sin punto de caudal (río sin dato GloFAS o sierra)"}
    f = pd.Timestamp(fecha)
    s = c[(c.rio == rio) & (c.fecha >= f - pd.Timedelta(days=DIAS_ANTES)) & (c.fecha <= f)].set_index("fecha")["caudal"]
    u = uc[rio]
    mx = float(s.max())
    return {"rio": rio, "caudal_max_m3s_3_dias_antes": round(mx), "caudal_p95_m3s": round(u["p95"]),
            "caudal_p99_m3s": round(u["p99"]),
            "caudal_nivel": "muy alto (> p99)" if mx > u["p99"] else "alto (> p95)" if mx > u["p95"] else "normal"}


def clave(dep: str, dist: str) -> str:
    return norm(dep) + norm(dist)


def cargar_lluvia() -> tuple[pd.DataFrame, pd.DataFrame]:
    ll = pd.read_csv(LLUVIA, parse_dates=["fecha"])
    ll = ll[ll["lluvia"] >= 0]
    base = ll[(ll.fecha.dt.year >= 2001) & (ll.fecha.dt.year <= 2020) & (ll.lluvia >= 1)]
    u = base.groupby("clave")["lluvia"].agg(p95=lambda x: np.percentile(x, 95), p99=lambda x: np.percentile(x, 99),
                                            dias_con_lluvia="size").reset_index()
    return ll, u


def nivel(mm: float, p95: float, p99: float) -> str:
    return "extremo" if mm > p99 else "fuerte" if mm > p95 else "normal"


def evento_puntual(ll: pd.DataFrame, u: pd.DataFrame, k: str, fecha: str) -> dict:
    f = pd.Timestamp(fecha)
    s = ll[(ll.clave == k) & (ll.fecha >= f - pd.Timedelta(days=10)) & (ll.fecha <= f)].set_index("fecha")["lluvia"]
    ub = u[u.clave == k]
    if s.empty or ub.empty:
        return {"resultado": "sin datos de lluvia para ese distrito"}
    p95, p99 = float(ub.p95.iloc[0]), float(ub.p99.iloc[0])
    ventana = s[s.index >= f - pd.Timedelta(days=DIAS_ANTES)]
    dia_max = ventana.idxmax()
    sobre = [d for d, v in ventana.items() if v > p95]
    return {"p95_mm": round(p95, 1), "p99_mm": round(p99, 1),
            "lluvia_10_dias_antes": {d.date().isoformat(): round(float(v), 1) for d, v in s.items()},
            "max_mm_3_dias_antes": round(float(ventana.max()), 1), "dia_max": dia_max.date().isoformat(),
            "nivel": nivel(float(ventana.max()), p95, p99),
            "dias_sobre_p95_en_los_3_dias_antes": [d.date().isoformat() for d in sobre]}


def prueba_eventos(ll, u, c, uc) -> list[dict]:
    lug = pd.read_csv(LUGARES, dtype={"ubigeo": str})
    out = []
    for _, e in pd.read_csv(CATALOGO, dtype=str).fillna("").iterrows():
        l = lug[(lug.nombre == e.lugar) & (lug.ubigeo == e.ubigeo)].iloc[0]
        k = clave(l.departamento, l.distrito)
        out.append({"id": e.id, "fecha": e.fecha, "distrito": l.distrito.title(), "tipo": e.tipo,
                    "descripcion": e.descripcion, "fuente": e.fuente, **evento_puntual(ll, u, k, e.fecha),
                    **caudal_evento(c, uc, rio_de(l.distrito), e.fecha)})
    for e in EXTRA:
        out.append({"id": e["id"], "fecha": e["fecha"], "distrito": e["distrito"].title(), "tipo": "desborde de río",
                    "descripcion": e["descripcion"], **evento_puntual(ll, u, clave(e["dep"], e["distrito"]), e["fecha"]),
                    **caudal_evento(c, uc, rio_de(e["distrito"]), e["fecha"])})
    return out


def prueba_sinpad(ll, u, c, uc) -> dict:
    """Todas las semanas-distrito 2003-2026 (hasta el último dato de SINPAD): ¿la semana con lluvia sobre el umbral
    trae más emergencias que la semana sin ella?"""
    s = pd.read_csv(SINPAD, parse_dates=["semana"])
    s["clave"] = [clave(d, x) for d, x in zip(s.departamento, s.distrito)]
    fin = s.semana.max() + pd.Timedelta(days=6)
    x = ll[(ll.fecha >= "2003-01-01") & (ll.fecha <= fin)].merge(u, on="clave")
    x["semana"] = x.fecha - pd.to_timedelta(x.fecha.dt.dayofweek, unit="D")
    sem = x.groupby(["clave", "semana"]).agg(mm_max=("lluvia", "max"), p95=("p95", "first"), p99=("p99", "first")).reset_index()
    # aviso previo: también cuenta la lluvia de los 3 últimos días de la semana anterior
    x["semana_sig"] = x.semana + pd.Timedelta(days=7)
    prev = x[x.fecha.dt.dayofweek >= 4].groupby(["clave", "semana_sig"])["lluvia"].max().rename("mm_prev").reset_index()
    sem = sem.merge(prev.rename(columns={"semana_sig": "semana"}), on=["clave", "semana"], how="left").fillna({"mm_prev": 0})
    sem = sem.merge(s[["clave", "semana", "eventos", "eventos_inundacion", "viv_afectadas", "viv_destruidas"]],
                    on=["clave", "semana"], how="left").fillna(0)
    sin_par = sorted(set(s.clave) - set(sem.clave))
    sem["mm_aviso"] = np.maximum(sem.mm_max, sem.mm_prev)
    # caudal del río del distrito: máximo de la semana y de los 3 últimos días de la anterior
    c = c.copy()
    c["semana"] = c.fecha - pd.to_timedelta(c.fecha.dt.dayofweek, unit="D")
    cs = c.groupby(["rio", "semana"])["caudal"].max().rename("q_sem").reset_index()
    c["semana_sig"] = c.semana + pd.Timedelta(days=7)
    cp = c[c.fecha.dt.dayofweek >= 4].groupby(["rio", "semana_sig"])["caudal"].max().rename("q_prev").reset_index()
    cs = cs.merge(cp.rename(columns={"semana_sig": "semana"}), on=["rio", "semana"], how="left")
    cs["q_aviso"] = cs[["q_sem", "q_prev"]].max(axis=1)
    cs["q_alto"] = [q > uc[r]["p95"] for r, q in zip(cs.rio, cs.q_aviso)]
    rios = {clave(d, x): rio_de(x) for d, x in zip(s.departamento, s.distrito)}
    sem["rio"] = sem.clave.map(rios)
    sem = sem.merge(cs[["rio", "semana", "q_aviso", "q_alto"]], on=["rio", "semana"], how="left")
    sem["q_alto"] = sem["q_alto"].fillna(False).astype(bool)
    res = {"semanas_distrito": int(len(sem)), "distritos": int(sem.clave.nunique()),
           "periodo": [sem.semana.min().date().isoformat(), sem.semana.max().date().isoformat()],
           "distritos_sinpad_sin_lluvia": sin_par, "definiciones": {}}
    etiquetas = {"inundacion": ("eventos_inundacion", "semana con al menos una emergencia por inundación en SINPAD"),
                 "viviendas": ("viv_afectadas", "semana con al menos una vivienda afectada en SINPAD (inundación o lluvia intensa)")}
    def senal(umbral, sub):
        if umbral == "caudal_p95":
            return sub.q_alto
        if umbral == "lluvia_o_caudal":
            return (sub.mm_aviso > sub.p95) | sub.q_alto
        return sub.mm_aviso > sub[umbral]
    for nombre_y, (col, desc) in etiquetas.items():
        res["definiciones"][nombre_y] = desc
        for umbral in ("p95", "p99", "caudal_p95", "lluvia_o_caudal"):
            sub = sem if umbral in ("p95", "p99") else sem[sem.rio.notna()]
            y = sub[col] > 0
            a = senal(umbral, sub)
            tp, fp, fn, tn = int((a & y).sum()), int((a & ~y).sum()), int((~a & y).sum()), int((~a & ~y).sum())
            r = {"ambito": "todos los distritos" if sub is sem else "solo distritos de los ríos Piura, Chira y Tumbes",
                 "avisos": int(a.sum()), "eventos": int(y.sum()), "aciertos": tp, "falsas_alarmas": fp, "no_avisados": fn,
                 "deteccion_pct": round(100 * tp / (tp + fn), 1) if tp + fn else None,
                 "falsa_alarma_pct": round(100 * fp / (tp + fp), 1) if tp + fp else None,
                 "prob_evento_con_aviso_pct": round(100 * tp / (tp + fp), 2) if tp + fp else None,
                 "prob_evento_sin_aviso_pct": round(100 * fn / (fn + tn), 2) if fn + tn else None}
            r["veces_mas_probable"] = (round(r["prob_evento_con_aviso_pct"] / r["prob_evento_sin_aviso_pct"], 1)
                                       if r["prob_evento_sin_aviso_pct"] else None)
            # de las viviendas afectadas, ¿qué parte cayó en semanas con aviso?
            r["viviendas_afectadas_en_semanas_con_aviso_pct"] = round(
                100 * sub.loc[a, "viv_afectadas"].sum() / max(sub.viv_afectadas.sum(), 1), 1)
            r["avisos_por_distrito_y_anio"] = round(int(a.sum()) / sub.clave.nunique() / (len(sub.semana.unique()) / 52.18), 2)
            res[f"{nombre_y}_{umbral}"] = r
    # mismas cuentas para los distritos de río con la señal de lluvia, para comparar en el mismo ámbito
    sub = sem[sem.rio.notna()]
    y = sub.eventos_inundacion > 0
    a = sub.mm_aviso > sub.p95
    res["rios_solo_lluvia_p95_inundacion"] = {"avisos": int(a.sum()), "eventos": int(y.sum()), "aciertos": int((a & y).sum()),
                                              "deteccion_pct": round(100 * (a & y).sum() / y.sum(), 1)}
    # por año: los años grandes
    y = sem.eventos_inundacion > 0
    a = sem.mm_aviso > sem.p95
    sem["_a"], sem["_y"] = a, y
    por_anio = sem.groupby(sem.semana.dt.year).agg(avisos=("_a", "sum"), eventos=("_y", "sum"),
                                                   aciertos=("_a", lambda v: int((v & sem.loc[v.index, "_y"]).sum())),
                                                   viv_afectadas=("viv_afectadas", "sum"))
    res["por_anio_inundacion_p95"] = {int(k): {c: int(v) for c, v in fila.items()} for k, fila in por_anio.iterrows()}
    # las 15 semanas-distrito con más viviendas afectadas: ¿hubo aviso?
    top = sem.sort_values("viv_afectadas", ascending=False).head(15)
    res["top15_viviendas_afectadas"] = [{"distrito": r.clave, "semana": r.semana.date().isoformat(),
                                         "viv_afectadas": int(r.viv_afectadas), "mm_max": round(r.mm_aviso, 1),
                                         "p95": round(r.p95, 1), "p99": round(r.p99, 1),
                                         "nivel": nivel(r.mm_aviso, r.p95, r.p99)} for r in top.itertuples()]
    return res


def main() -> None:
    ll, u = cargar_lluvia()
    c, uc = cargar_caudal()
    out = {"metodo": __doc__.split("Salida:")[0].strip(), "umbrales_distritos": int(len(u)),
           "umbrales_caudal_2001_2020": {r: {k: round(v) for k, v in x.items()} for r, x in uc.items()},
           "eventos_con_noticias": prueba_eventos(ll, u, c, uc), "sinpad": prueba_sinpad(ll, u, c, uc)}
    ev = [e for e in out["eventos_con_noticias"] if "nivel" in e]
    out["resumen_eventos"] = {n: sum(e["nivel"] == n for e in ev) for n in ("extremo", "fuerte", "normal")}
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("eventos con noticias:", out["resumen_eventos"])
    for e in ev:
        print(f"  {e['fecha']} {e['distrito']:<22} {e['tipo']:<24} max {e['max_mm_3_dias_antes']:>6} mm  p95 {e['p95_mm']:>5}  "
              f"p99 {e['p99_mm']:>5}  -> {e['nivel']:<8} | caudal {e.get('rio')} {e.get('caudal_max_m3s_3_dias_antes','')} "
              f"(p95 {e.get('caudal_p95_m3s','')}) {e.get('caudal_nivel','')}")
    s = out["sinpad"]
    print("ríos, solo lluvia:", s["rios_solo_lluvia_p95_inundacion"])
    for k in [f"{y}_{m}" for y in ("inundacion", "viviendas") for m in ("p95", "p99", "caudal_p95", "lluvia_o_caudal")]:
        print(k, {c: s[k][c] for c in ("avisos", "eventos", "aciertos", "deteccion_pct", "falsa_alarma_pct",
                                         "veces_mas_probable", "viviendas_afectadas_en_semanas_con_aviso_pct",
                                         "avisos_por_distrito_y_anio")})
    print("sin lluvia:", s["distritos_sinpad_sin_lluvia"])


if __name__ == "__main__":
    main()
