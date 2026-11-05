"""Falsas alarmas del aviso con PRONÓSTICOS REALES, todos los días de una temporada (documento 18, sección C).

La prueba A del documento 18 solo miró días con daño: no mide falsas alarmas. Esta mira TODOS los días y TODOS los
distritos de dos temporadas:
    enero a abril de 2025 (temporada de lluvias completa; daños = SINPAD del INDECI)
    15 de octubre al 4 de noviembre de 2026 (inicio de El Niño costero; daños = catálogo verificado + noticias)
y responde: ¿cuántos avisos habría dado el tablero?, ¿cuántos fueron seguidos de daño?, ¿cuántos daños tuvieron aviso
antes?, con y sin el caudal de los ríos.

LLUVIA. Lo que Open-Meteo pronosticaba 1, 2 y 3 días antes (Previous Runs API: precipitation_previous_day1..3), suma
    horaria por día en hora de Lima, en el punto central de cada distrito (data/normales/umbrales_lluvia_distritos.csv),
    con los MISMOS umbrales del tablero (p95 y p99 de ERA5 1991-2020 por provincia). Nivel: fuerte > p95, extremo > p99.
CAUDAL (distritos de los ríos Piura, Chira y Tumbes, lista CUENCA de src/aviso_lluvia.py). Open-Meteo NO guarda los
    pronósticos de caudal tal como se emitieron (solo el reanálisis/serie continua de GloFAS). Por eso se dan dos
    versiones que encierran al pronóstico real:
      "caudal conocido": el caudal GloFAS del día en que se habría emitido el aviso (T-n): lo que ya se sabía,
                         sin pronóstico del río.
      "caudal real":     el caudal GloFAS del mismo día T: un pronóstico perfecto del río (cota alta).
    Umbrales: p95 y p99 del caudal diario 2001-2020 (data/modelo/caudal_rios.csv). El aviso usa p95 para «fuerte»;
    las variantes «sobre p99» muestran qué pasaría si el río solo avisara cuando pasa su p99.

DAÑOS
    2025: SINPAD (INDECI, datos abiertos) por distrito y semana, data/modelo/sinpad_tumbes_piura_semanal.csv:
          semanas con registro de lluvia intensa o inundación (y, aparte, con viviendas afectadas o destruidas).
          Unidad distrito-semana, como la prueba B: una semana tiene aviso si algún día de ella o de los 3 últimos
          días de la semana anterior tuvo aviso.
    2026: SINPAD aún no publica el segundo semestre. Se usan data/eventos/catalogo_verificado.csv (revisado por el
          equipo) y los titulares de data/eventos/noticias_registro.csv que src/noticias.py ubicó por distrito
          (dashboard/data/eventos_reportados.json, origen «noticias (automático)»). Unidad distrito-día: un aviso para
          el día T es «seguido de daño» si hubo evento el día T o T+1; un daño del día E «tuvo aviso previo» si hubo
          aviso para E o E-1.

Pasos y archivos
    1. descargar(): Previous Runs API por bloques de distritos, con pausas; cada bloque se guarda en
       data/cache/aviso_temporada/ y no se vuelve a pedir. Arma docs/evidencia/aviso_temporada_pronosticos.csv.
    2. niveles(): nivel por distrito, día y anticipación.
       (Alternativa sin red: --niveles ARCHIVO lee el formato compacto de docs/evidencia/aviso_temporada_niveles.txt,
       con el que se hizo la corrida del 5/11/2026 desde el navegador; ver leer_niveles_compactos().)
    3. evaluar(): tablas con y sin caudal → docs/evidencia/prueba_aviso_temporada.json y
       docs/evidencia/prueba_aviso_temporada_distritos.csv (por distrito y temporada: semanas en 2025, días en 2026)

Uso:  python herramientas/pruebas/prueba_aviso_temporada.py                  (necesita red la primera vez)
      python herramientas/pruebas/prueba_aviso_temporada.py --niveles docs/evidencia/aviso_temporada_niveles.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))

UMBRALES = R / "data" / "normales" / "umbrales_lluvia_distritos.csv"
CAUDAL = R / "data" / "modelo" / "caudal_rios.csv"
SINPAD = R / "data" / "modelo" / "sinpad_tumbes_piura_semanal.csv"
CATALOGO = R / "data" / "eventos" / "catalogo_verificado.csv"
NOTICIAS = R / "dashboard" / "data" / "eventos_reportados.json"
UBIGEO = R / "data" / "exposicion" / "ubigeo_distritos.csv"
CACHE = R / "data" / "cache" / "aviso_temporada"
EVID = R / "docs" / "evidencia"
PRONOSTICOS = EVID / "aviso_temporada_pronosticos.csv"
SALIDA = EVID / "prueba_aviso_temporada.json"
SALIDA_DIST = EVID / "prueba_aviso_temporada_distritos.csv"

API = "https://previous-runs-api.open-meteo.com/v1/forecast"
TEMPORADAS = {"2025_ene_abr": ("2025-01-01", "2025-04-30"), "2026_oct_nov": ("2026-10-15", "2026-11-04")}
N = (1, 2, 3)
BLOQUE = 10          # distritos por consulta (Open-Meteo cuenta cada punto)
PAUSA_S = 6          # entre consultas, para no pasar el límite por minuto
FUSION = {"200115": "200101", "240203": "240201"}   # distritos que el mapa GADM incluye en otro


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s)


def clave(prov, dist) -> str:
    return norm(prov) + "|" + norm(dist)


# --------------------------------------------------------------------------------------------- 1. descargar
def descargar() -> pd.DataFrame:
    from descargar_zonas import pedir
    u = pd.read_csv(UMBRALES)
    CACHE.mkdir(parents=True, exist_ok=True)
    vars_ = ["precipitation"] + [f"precipitation_previous_day{n}" for n in N]
    filas = []
    for tem, (a, b) in TEMPORADAS.items():
        for i in range(0, len(u), BLOQUE):
            b_ = u.iloc[i:i + BLOQUE]
            ruta = CACHE / f"{tem}_{i:03d}.json"
            if ruta.exists():
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            else:
                j = pedir(API, {"latitude": ",".join(map(str, b_.lat)), "longitude": ",".join(map(str, b_.lon)),
                                "hourly": ",".join(vars_), "start_date": a, "end_date": b, "timezone": "America/Lima"})
                if j is None:
                    raise RuntimeError(f"Open-Meteo no respondió ({tem}, bloque {i}); vuelva a correr: lo ya bajado queda")
                j = j if isinstance(j, list) else [j]
                datos = []
                for loc in j:   # se guarda ya sumado por día (pesa 24 veces menos que el horario)
                    h = pd.DataFrame(loc["hourly"])
                    h["dia"] = h["time"].str[:10]
                    d = h.groupby("dia")[vars_].agg(lambda x: None if x.isna().all() else round(float(x.sum(skipna=True)), 1))
                    datos.append(d.reset_index().to_dict(orient="list"))
                ruta.write_text(json.dumps(datos), encoding="utf-8")
                print(f"  {tem} bloque {i}: {len(datos)} distritos", flush=True)
                time.sleep(PAUSA_S)
            for (_, r), d in zip(b_.iterrows(), datos):
                for k, dia in enumerate(d["dia"]):
                    filas.append({"temporada": tem, "departamento": r.departamento, "provincia": r.provincia,
                                  "distrito": r.distrito, "fecha": dia, "mm_reciente": d["precipitation"][k],
                                  **{f"mm_{n}d": d[f"precipitation_previous_day{n}"][k] for n in N}})
    p = pd.DataFrame(filas)
    EVID.mkdir(parents=True, exist_ok=True)
    p.to_csv(PRONOSTICOS, index=False)
    return p


# ------------------------------------------------------------------------------------------------ 2. niveles
def nivel(mm, p95, p99) -> str:
    if mm is None or (isinstance(mm, float) and np.isnan(mm)):
        return "x"
    return "e" if mm > p99 else "f" if mm > p95 else "n"


def niveles(p: pd.DataFrame) -> pd.DataFrame:
    u = pd.read_csv(UMBRALES)
    u["k"] = [clave(a, b) for a, b in zip(u.provincia, u.distrito)]
    p = p.copy()
    p["k"] = [clave(a, b) for a, b in zip(p.provincia, p.distrito)]
    p = p.merge(u[["k", "p95", "p99"]], on="k", how="left")
    for n in N:
        p[f"lluvia_{n}d"] = [nivel(m, a, b) for m, a, b in zip(p[f"mm_{n}d"], p.p95, p.p99)]
    return p[["temporada", "provincia", "distrito", "k", "fecha"] + [f"lluvia_{n}d" for n in N]]


def leer_niveles_compactos(ruta: Path) -> pd.DataFrame:
    """Formato de docs/evidencia/aviso_temporada_niveles.txt, una línea por temporada y distrito:
        t2025|<i>:<primera fecha>:<días>:<grupos separados por ;>
    <i> es la fila del distrito en umbrales_lluvia_distritos.csv. Cada grupo es un número (tantos días seguidos
    en «nnn») o tres letras con el nivel pronosticado 1, 2 y 3 días antes (n normal, f fuerte, e extremo)."""
    u = pd.read_csv(UMBRALES)
    tem = {"t2025": "2025_ene_abr", "t2026": "2026_oct_nov"}
    filas = []
    for linea in ruta.read_text(encoding="utf-8").strip().splitlines():
        cab, ini, ndias, cuerpo = linea.split(":")
        t, i = cab.split("|")
        r = u.iloc[int(i)]
        dias = []
        for tok in cuerpo.split(";"):
            dias += ["nnn"] * int(tok) if tok.isdigit() else [tok]
        assert len(dias) == int(ndias), linea[:40]
        fechas = pd.date_range(ini, periods=len(dias)).strftime("%Y-%m-%d")
        for f, g in zip(fechas, dias):
            filas.append({"temporada": tem[t], "provincia": r.provincia, "distrito": r.distrito,
                          "k": clave(r.provincia, r.distrito), "fecha": f,
                          **{f"lluvia_{n}d": g[n - 1] for n in N}})
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------------------------- caudal
def agregar_caudal(nv: pd.DataFrame) -> pd.DataFrame:
    from aviso_lluvia import CUENCA, ANIOS_UMBRAL_CAUDAL
    c = pd.read_csv(CAUDAL, parse_dates=["fecha"])
    a0, a1 = ANIOS_UMBRAL_CAUDAL
    base = c[(c.fecha.dt.year >= a0) & (c.fecha.dt.year <= a1)]
    p95 = {r: float(np.percentile(g.caudal.dropna(), 95)) for r, g in base.groupby("rio")}
    p99 = {r: float(np.percentile(g.caudal.dropna(), 99)) for r, g in base.groupby("rio")}
    serie = {r: g.set_index(g.fecha.dt.strftime("%Y-%m-%d"))["caudal"].to_dict() for r, g in c.groupby("rio")}
    rio_de = {norm(d): r for r, ds in CUENCA.items() for d in ds}
    nv = nv.copy()
    nv["rio"] = nv["distrito"].map(lambda d: rio_de.get(norm(d)))
    fecha = pd.to_datetime(nv["fecha"])

    def alto(rio, f, u):
        if not isinstance(rio, str):
            return False
        q = serie.get(rio, {}).get(f)
        return q is not None and not np.isnan(q) and q > u[rio]
    for sufijo, u in (("", p95), ("_p99", p99)):
        nv[f"caudal_real{sufijo}"] = [alto(r, f, u) for r, f in zip(nv.rio, nv.fecha)]
        for n in N:
            prev = (fecha - pd.Timedelta(days=n)).dt.strftime("%Y-%m-%d")
            nv[f"caudal_conocido{sufijo}_{n}d"] = [alto(r, f, u) for r, f in zip(nv.rio, prev)]
    return nv, {"p95": {r: round(v, 1) for r, v in p95.items()}, "p99": {r: round(v, 1) for r, v in p99.items()}}


def senales(nv: pd.DataFrame) -> dict:
    """Columnas booleanas «hay aviso para el día» de cada variante."""
    ll = {n: nv[f"lluvia_{n}d"].isin(["f", "e"]) for n in N}
    cualquiera = ll[1] | ll[2] | ll[3]
    conocido = nv["caudal_conocido_1d"] | nv["caudal_conocido_2d"] | nv["caudal_conocido_3d"]
    conocido99 = nv["caudal_conocido_p99_1d"] | nv["caudal_conocido_p99_2d"] | nv["caudal_conocido_p99_3d"]
    return {"lluvia, 1 día antes": ll[1], "lluvia, 2 días antes": ll[2], "lluvia, 3 días antes": ll[3],
            "lluvia (1, 2 o 3 días antes)": cualquiera,
            "lluvia o caudal conocido": cualquiera | conocido,
            "lluvia o caudal real (cota alta)": cualquiera | nv["caudal_real"],
            "lluvia o caudal conocido sobre p99": cualquiera | conocido99,
            "lluvia o caudal real sobre p99 (cota alta)": cualquiera | nv["caudal_real_p99"]}


# --------------------------------------------------------------------------------------------- 3. evaluar
def danos_2025() -> pd.DataFrame:
    s = pd.read_csv(SINPAD, dtype={"ubigeo": str})
    s["ubigeo"] = s["ubigeo"].replace(FUSION)
    ub = pd.read_csv(UBIGEO, dtype={"inei": str})
    ub["k"] = [clave(a, b) for a, b in zip(ub.provincia, ub.distrito)]
    s = s.merge(ub[["inei", "k"]].rename(columns={"inei": "ubigeo"}), on="ubigeo", how="left")
    s["viviendas"] = s["viv_afectadas"].fillna(0) + s["viv_destruidas"].fillna(0)
    return s.groupby(["k", "semana"], as_index=False)[["eventos", "viviendas"]].sum()


def danos_2026() -> tuple[pd.DataFrame, pd.DataFrame]:
    ub = pd.read_csv(UBIGEO, dtype={"inei": str})
    ub["k"] = [clave(a, b) for a, b in zip(ub.provincia, ub.distrito)]
    kmap = dict(zip(ub.inei, ub.k))
    cat = pd.read_csv(CATALOGO, dtype={"ubigeo": str})
    cat = cat[cat.fecha.between(*TEMPORADAS["2026_oct_nov"])]
    ver = pd.DataFrame({"k": cat.ubigeo.replace(FUSION).map(kmap), "fecha": cat.fecha, "origen": "verificado", "id": cat.id})
    no = []
    if NOTICIAS.exists():
        for e in json.loads(NOTICIAS.read_text(encoding="utf-8"))["eventos"]:
            if e.get("origen", "").startswith("noticias") and TEMPORADAS["2026_oct_nov"][0] <= e["fecha"] <= TEMPORADAS["2026_oct_nov"][1]:
                no.append({"k": kmap.get(FUSION.get(e["ubigeo"], e["ubigeo"])), "fecha": e["fecha"], "origen": "noticias",
                           "id": e.get("id") or e["titulo"][:60]})
    todos = pd.concat([ver, pd.DataFrame(no)], ignore_index=True).drop_duplicates(["k", "fecha"])
    return ver.drop_duplicates(["k", "fecha"]), todos


def tabla(aviso: pd.Series, dano: pd.Series) -> dict:
    a, d = aviso.astype(bool), dano.astype(bool)
    av, da, ambos = int(a.sum()), int(d.sum()), int((a & d).sum())
    return {"avisos": av, "danos": da, "avisos_con_dano": ambos, "unidades": int(len(a)),
            "pct_unidades_con_dano": round(100 * da / len(a), 1) if len(a) else None,
            "pct_avisos_seguidos_de_dano": round(100 * ambos / av, 1) if av else None,
            "pct_danos_con_aviso_previo": round(100 * ambos / da, 1) if da else None,
            "falsas_alarmas": av - ambos}


def evaluar_2025(nv: pd.DataFrame) -> dict:
    t = nv[nv.temporada == "2025_ene_abr"].copy()
    t["fecha_d"] = pd.to_datetime(t["fecha"])
    t["semana"] = t["fecha_d"].dt.to_period("W-SUN").dt.start_time
    # el aviso de los 3 últimos días de una semana también cuenta para la siguiente
    t["semana_sig"] = (t["fecha_d"] + pd.Timedelta(days=7)).dt.to_period("W-SUN").dt.start_time
    t["cuenta_sig"] = t["fecha_d"].dt.dayofweek >= 4                        # viernes a domingo
    sen = senales(t)
    sem = sorted(t["semana"].unique())
    dist = sorted(t["k"].unique())
    idx = pd.MultiIndex.from_product([dist, sem], names=["k", "semana"])
    s = danos_2025()
    s["semana"] = pd.to_datetime(s["semana"])
    s = s.set_index(["k", "semana"]).reindex(idx, fill_value=0)
    out = {"unidad": "distrito-semana", "semanas": len(sem), "distritos": len(dist), "variantes": {},
           "por_distrito": {}}
    rio = t.groupby("k")["rio"].first()
    for nombre, col in sen.items():
        t["_a"] = col.values
        a1 = t[t["_a"]].groupby(["k", "semana"]).size()
        a2 = t[t["_a"] & t["cuenta_sig"]].groupby(["k", "semana_sig"]).size()
        a2.index.names = ["k", "semana"]
        aviso = pd.Series(False, index=idx)
        for a in (a1, a2):
            aviso.loc[aviso.index.intersection(a.index)] = True
        dano = s["eventos"] > 0
        dano_viv = s["viviendas"] > 0
        con_rio = np.array([isinstance(rio.get(k), str) for k in idx.get_level_values("k")])
        out["variantes"][nombre] = {
            "todos los distritos": {**tabla(aviso, dano), "dias_con_aviso": int(col.sum()),
                                    "dias_con_aviso_por_distrito": round(col.sum() / len(dist), 1),
                                    "semanas_con_aviso_por_distrito": round(aviso.sum() / len(dist), 1),
                                    "con_viviendas": tabla(aviso, dano_viv)},
            "distritos de los ríos Piura, Chira y Tumbes": {**tabla(aviso[con_rio], dano[con_rio]),
                                                            "con_viviendas": tabla(aviso[con_rio], dano_viv[con_rio])}}
        por = pd.DataFrame({"aviso": aviso, "dano": dano}).groupby(level="k").agg(
            con_aviso=("aviso", "sum"), con_dano=("dano", "sum"),
            aviso_y_dano=("aviso", lambda x: int((x & dano.loc[x.index]).sum())))
        out["por_distrito"][nombre] = por
    return out


def evaluar_2026(nv: pd.DataFrame) -> dict:
    t = nv[nv.temporada == "2026_oct_nov"].copy()
    ver, todos = danos_2026()
    sen = senales(t)
    out = {"unidad": "distrito-día", "dias": t["fecha"].nunique(), "distritos": t["k"].nunique(), "variantes": {},
           "por_distrito": {}, "eventos": {"verificados": ver.to_dict(orient="records"), "con_noticias": todos.to_dict(orient="records")}}
    f = pd.to_datetime(t["fecha"])
    for nombre, col in sen.items():
        res = {}
        for etiqueta, ev in (("eventos verificados", ver), ("verificados y noticias ubicadas", todos)):
            evs = set(zip(ev.k, ev.fecha))
            dano_sig = [(k, d.strftime("%Y-%m-%d")) in evs or (k, (d + pd.Timedelta(days=1)).strftime("%Y-%m-%d")) in evs
                        for k, d in zip(t.k, f)]
            avisos = set(zip(t.k[col.values], t.fecha[col.values]))
            con_previo = [(k, e) in avisos or (k, (pd.Timestamp(e) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")) in avisos
                          for k, e in zip(ev.k, ev.fecha)]
            av, ad = int(col.sum()), int((col.values & np.array(dano_sig)).sum())
            res[etiqueta] = {"avisos": av, "avisos_seguidos_de_dano": ad,
                             "pct_avisos_seguidos_de_dano": round(100 * ad / av, 1) if av else None,
                             "danos": len(ev), "danos_con_aviso_previo": int(sum(con_previo)),
                             "pct_danos_con_aviso_previo": round(100 * sum(con_previo) / len(ev), 1) if len(ev) else None,
                             "dias_con_aviso_por_distrito": round(av / t["k"].nunique(), 1)}
            if etiqueta == "eventos verificados":
                por = pd.DataFrame({"k": t.k.values, "aviso": col.values, "dano": dano_sig})
                por["aviso_y_dano"] = por.aviso & por.dano
                cuenta = ev.groupby("k").size()
                por = por.groupby("k").agg(con_aviso=("aviso", "sum"), aviso_y_dano=("aviso_y_dano", "sum"))
                por.insert(1, "con_dano", [int(cuenta.get(k, 0)) for k in por.index])
                out["por_distrito"][nombre] = por
        out["variantes"][nombre] = res
    return out


def evaluar(nv: pd.DataFrame, origen: str) -> dict:
    nv, p95 = agregar_caudal(nv)
    r25 = evaluar_2025(nv)
    r26 = evaluar_2026(nv)
    filas = []
    for temporada, r, unidad in (("2025_ene_abr", r25, "semanas"), ("2026_oct_nov", r26, "días")):
        for nombre in ("lluvia (1, 2 o 3 días antes)", "lluvia o caudal conocido", "lluvia o caudal real (cota alta)",
                       "lluvia o caudal conocido sobre p99"):
            d = r["por_distrito"][nombre].reset_index()
            d.insert(0, "temporada", temporada)
            d.insert(2, "variante", nombre)
            d.insert(3, "unidad", unidad)
            filas.append(d)
        r.pop("por_distrito")
    # con_aviso / con_dano / aviso_y_dano: semanas (2025) o días (2026; daño = evento verificado)
    pd.concat(filas).to_csv(SALIDA_DIST, index=False)
    salida = {"metodo": __doc__.split("Pasos y archivos")[0].strip(), "origen_de_los_pronosticos": origen,
              "umbrales_caudal_m3s": p95, "temporada_2025": r25, "temporada_2026": r26}
    EVID.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return salida


def resumen(s: dict) -> None:
    print("\n2025, enero a abril (distrito-semana, SINPAD):")
    for v, x in s["temporada_2025"]["variantes"].items():
        a = x["todos los distritos"]
        print(f"  {v:36s} avisos {a['avisos']:4d} · seguidos de daño {a['pct_avisos_seguidos_de_dano']} % · "
              f"daños con aviso {a['pct_danos_con_aviso_previo']} % · semanas con aviso por distrito {a['semanas_con_aviso_por_distrito']}")
    print("\n2026, 15/10 al 4/11 (distrito-día, eventos verificados):")
    for v, x in s["temporada_2026"]["variantes"].items():
        a = x["eventos verificados"]
        print(f"  {v:36s} avisos {a['avisos']:4d} · seguidos de daño {a['pct_avisos_seguidos_de_dano']} % · "
              f"daños con aviso {a['danos_con_aviso_previo']}/{a['danos']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--niveles", help="evaluar desde el archivo compacto de niveles (sin red)")
    args = ap.parse_args()
    if args.niveles:
        nv = leer_niveles_compactos(Path(args.niveles))
        origen = f"niveles leídos de {args.niveles}"
    else:
        nv = niveles(descargar())
        origen = "Open-Meteo Previous Runs API (descarga propia, data/cache/aviso_temporada/)"
    resumen(evaluar(nv, origen))


if __name__ == "__main__":
    main()
