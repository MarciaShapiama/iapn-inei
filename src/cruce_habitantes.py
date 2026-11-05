"""Cruce de los habitantes del Censo 2025 (INEI) con la zona inundable y con el aviso de lluvia.

Dónde va: src/cruce_habitantes.py del repositorio. Se corre SOLO en la laptop que tiene los datos del INEI:

    python src/cruce_habitantes.py              # calcula y guarda los resultados privados
    python src/cruce_habitantes.py --publicar   # además escribe dashboard/data/habitantes_censo.json

Reglas de confidencialidad (no se cambian):
    - Los archivos del INEI viven en datos_inei/, que está en .gitignore. Nunca se suben.
    - Solo salen totales por distrito. Ningún archivo de salida tiene idmanzana ni coordenadas.
    - Un distrito con menos de 10 viviendas en la zona se oculta (supresión primaria). Si en un departamento queda un
      solo distrito oculto, se oculta también el siguiente más chico, para que no se pueda despejar por resta
      (supresión secundaria).

ANTES DE CORRER: revise el bloque CONFIGURACIÓN. Es lo único que cambia cuando llega el archivo del INEI.
Dependencias: pandas, numpy; geopandas y rasterio solo si hay que ubicar las manzanas en el mapa
(ya están en requirements-inundaciones.txt).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
INEI = RAIZ / "datos_inei"
PRIVADO = INEI / "resultados"                       # salidas privadas, también fuera de GitHub
EXPO = RAIZ / "data" / "exposicion"
DASH = RAIZ / "dashboard" / "data"

# =============================================================================================== CONFIGURACIÓN
# 1. Archivo de habitantes que mande el INEI (CSV o Excel). Puede venir de tres formas; elija NIVEL:
#    "persona"  -> una fila por persona, con sexo y edad
#    "vivienda" -> una fila por vivienda, con conteos por sexo y grupo de edad
#    "manzana"  -> una fila por manzana, con conteos por sexo y grupo de edad
ARCHIVO_HABITANTES = INEI / "habitantes*.*"          # se acepta un patrón; se leen y juntan todos los que coincidan
NIVEL = "persona"
SEPARADOR = None                                     # None = lo detecta solo; o ";" / ","
CODIFICACION = "utf-8"                               # el INEI suele usar "latin-1"

# 2. Nombres de columnas en ese archivo (cambie el texto de la derecha; deje None lo que no venga).
COL = {
    "idmanzana": "idmanzana",          # llave con el mapa de manzanas. Si no viene, se arma con las tres siguientes
    "ubigeo": "ubigeo", "zona": "zona_id", "manzana": "manzana_id",
    # NIVEL == "persona"
    "sexo": "sexo",                    # valores en CODIGOS_SEXO
    "edad": "edad",                    # años cumplidos
    # NIVEL == "vivienda" o "manzana": conteos ya sumados
    "personas": None, "hombres": None, "mujeres": None,
    "edad_0_4": None, "edad_65_mas": None,
    "viviendas": None,                 # viviendas ocupadas, si el archivo las trae
}
CODIGOS_SEXO = {"1": "hombre", "2": "mujer", "H": "hombre", "M": "mujer",
                "HOMBRE": "hombre", "MUJER": "mujer", "MASCULINO": "hombre", "FEMENINO": "mujer"}

# 3. Archivos que el INEI ya envió (correo del 4/11/2026: manzanas.zip).
MANZANAS_CSV = INEI / "manzanas" / "*.csv"           # trae n_viviendas_ocupadas por idmanzana
MANZANAS_MAPA = INEI / "manzanas" / "*.shp"          # polígonos de las manzanas
# Atajo: si el cruce de viviendas ya dejó la profundidad por manzana, se usa y no se necesita geopandas.
# Columnas: idmanzana, prof_rp10, prof_rp100 (metros; 0 = fuera de la zona).
PROFUNDIDAD_CSV = INEI / "manzanas_profundidad.csv"

MINIMO_VIVIENDAS = 10                                # regla de supresión
# =========================================================================================== FIN CONFIGURACIÓN

FUSION = {"200115": "200101", "240203": "240201"}   # distritos nuevos -> polígono GADM que los contiene (aviso)


def normal(x) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


def leer(patron: Path, **kw) -> pd.DataFrame:
    rutas = sorted(glob.glob(str(patron)))
    if not rutas:
        sys.exit(f"No encontré {patron}. Revise la CONFIGURACIÓN.")
    partes = []
    for r in rutas:
        if r.lower().endswith((".xlsx", ".xls")):
            partes.append(pd.read_excel(r, dtype=str))
        else:
            partes.append(pd.read_csv(r, sep=SEPARADOR, engine="python", dtype=str, encoding=CODIFICACION, **kw))
    print(f"  leídos {len(rutas)} archivo(s) de {patron.name}: {sum(len(p) for p in partes):,} filas")
    return pd.concat(partes, ignore_index=True)


def llave(d: pd.DataFrame) -> pd.Series:
    if COL["idmanzana"] and COL["idmanzana"] in d:
        return d[COL["idmanzana"]].astype(str).str.strip()
    return (d[COL["ubigeo"]].astype(str).str.zfill(6) + d[COL["zona"]].astype(str).str.strip()
            + d[COL["manzana"]].astype(str).str.strip())


# ------------------------------------------------------------------------------------- 1. habitantes por manzana
def habitantes_por_manzana() -> pd.DataFrame:
    h = leer(ARCHIVO_HABITANTES)
    faltan = [v for k, v in COL.items() if v and k in ("sexo", "edad") and NIVEL == "persona" and v not in h]
    if faltan:
        sys.exit(f"El archivo no tiene las columnas {faltan}. Columnas que sí tiene: {list(h.columns)}")
    h["idmanzana"] = llave(h)
    if NIVEL == "persona":
        sexo = h[COL["sexo"]].astype(str).str.strip().str.upper().map(CODIGOS_SEXO)
        edad = pd.to_numeric(h[COL["edad"]], errors="coerce")
        print(f"  sexo sin código conocido: {sexo.isna().sum():,} · edad vacía: {edad.isna().sum():,}")
        m = pd.DataFrame({"idmanzana": h["idmanzana"], "personas": 1, "hombres": (sexo == "hombre").astype(int),
                          "mujeres": (sexo == "mujer").astype(int), "edad_0_4": edad.between(0, 4).astype(int),
                          "edad_65_mas": (edad >= 65).astype(int)})
    else:
        m = pd.DataFrame({"idmanzana": h["idmanzana"]})
        for k in ("personas", "hombres", "mujeres", "edad_0_4", "edad_65_mas", "viviendas"):
            if COL.get(k):
                m[k] = pd.to_numeric(h[COL[k]], errors="coerce").fillna(0)
        if "personas" not in m:
            m["personas"] = m.get("hombres", 0) + m.get("mujeres", 0)
    m = m.groupby("idmanzana").sum(numeric_only=True).reset_index()
    print(f"  {len(m):,} manzanas con habitantes · {int(m['personas'].sum()):,} personas")
    return m


# -------------------------------------------------------------------- 2. viviendas y distrito de cada manzana
def viviendas_por_manzana() -> pd.DataFrame:
    v = leer(MANZANAS_CSV)
    v["idmanzana"] = v["idmanzana"].astype(str).str.strip()
    v["viviendas"] = pd.to_numeric(v["n_viviendas_ocupadas"], errors="coerce").fillna(0)
    v["ubigeo"] = v["ubigeo"].astype(str).str.zfill(6)
    return v.groupby(["idmanzana", "ubigeo"], as_index=False)["viviendas"].sum()


# ------------------------------------------------------------------------- 3. profundidad del agua por manzana
def profundidad_por_manzana() -> pd.DataFrame:
    """Mismo método del cruce de viviendas: un punto interior por manzana y la profundidad JRC en ese punto."""
    if PROFUNDIDAD_CSV.exists():
        p = pd.read_csv(PROFUNDIDAD_CSV, dtype={"idmanzana": str})
        print(f"  profundidad leída de {PROFUNDIDAD_CSV.name}")
        return p[["idmanzana", "prof_rp10", "prof_rp100"]]
    import geopandas as gpd
    import rasterio
    rutas = sorted(glob.glob(str(MANZANAS_MAPA)))
    if not rutas:
        sys.exit(f"No encontré el mapa de manzanas ({MANZANAS_MAPA}) ni {PROFUNDIDAD_CSV}.")
    g = pd.concat([gpd.read_file(r) for r in rutas], ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=gpd.read_file(rutas[0]).crs).to_crs(4326)
    pt = g.geometry.representative_point()
    out = pd.DataFrame({"idmanzana": g["idmanzana"].astype(str).str.strip()})
    for esc in ("rp10", "rp100"):
        with rasterio.open(EXPO / f"peligro_{esc}.tif") as r:
            vals = np.array([x[0] for x in r.sample(zip(pt.x, pt.y))], dtype="float64")
            if r.nodata is not None:
                vals[vals == r.nodata] = 0
        out[f"prof_{esc}"] = np.nan_to_num(vals, nan=0.0).clip(min=0)
    out = out.groupby("idmanzana", as_index=False).max()
    out.to_csv(PROFUNDIDAD_CSV, index=False)            # queda en datos_inei/ para la próxima vez
    print(f"  profundidad calculada para {len(out):,} manzanas y guardada en {PROFUNDIDAD_CSV}")
    return out


# ------------------------------------------------------------------------------ 4. totales y supresión
CIFRAS = ["viviendas", "personas", "hombres", "mujeres", "edad_0_4", "edad_65_mas"]


def totales(m: pd.DataFrame) -> pd.DataFrame:
    filas = []
    zonas = {"distrito_total": pd.Series(True, index=m.index),
             "rp10": m["prof_rp10"] > 0, "rp100": m["prof_rp100"] > 0, "rp100_mas_1_5m": m["prof_rp100"] > 1.5}
    for esc, dentro in zonas.items():
        t = m[dentro].groupby("ubigeo")[CIFRAS].sum().reindex(m["ubigeo"].unique(), fill_value=0)
        t["escenario"] = esc
        filas.append(t.reset_index().rename(columns={"index": "ubigeo"}))
    t = pd.concat(filas, ignore_index=True)
    ub = pd.read_csv(EXPO / "ubigeo_distritos.csv", dtype={"inei": str}).rename(columns={"inei": "ubigeo"})
    return t.merge(ub[["ubigeo", "departamento", "provincia", "distrito"]], on="ubigeo", how="left")


def suprimir(t: pd.DataFrame) -> pd.DataFrame:
    t = t.copy()
    t["reservado"] = t["viviendas"] < MINIMO_VIVIENDAS
    t.loc[t["viviendas"] == 0, "reservado"] = False      # un cero no revela nada
    for (esc, dep), g in t.groupby(["escenario", "departamento"]):
        ocultos = g[g["reservado"]]
        if len(ocultos) == 1:                              # supresión secundaria
            visibles = g[~g["reservado"] & (g["viviendas"] > 0)]
            if len(visibles):
                t.loc[visibles["viviendas"].idxmin(), "reservado"] = True
    t.loc[t["reservado"], CIFRAS] = np.nan
    return t


# ----------------------------------------------------------------------------------- 5. cruce con el aviso
def con_aviso(t: pd.DataFrame) -> pd.DataFrame:
    a = json.load(open(DASH / "aviso_lluvia.json", encoding="utf-8"))
    av = pd.DataFrame(a["distritos"])[["departamento", "provincia", "distrito", "nivel", "mm_dia_max", "fecha_max"]]
    av["clave"] = av["departamento"].map(normal) + av["distrito"].map(normal)
    z = t[t["escenario"] == "rp100"].copy()
    z["ubigeo_mapa"] = z["ubigeo"].replace(FUSION)        # el aviso usa los 76 polígonos GADM
    ub = pd.read_csv(EXPO / "ubigeo_distritos.csv", dtype={"inei": str})
    ub["clave"] = ub["departamento"].map(normal) + ub["distrito"].map(normal)
    z = z.merge(ub[["inei", "clave"]].rename(columns={"inei": "ubigeo_mapa"}), on="ubigeo_mapa", how="left")
    z = z.groupby("clave", as_index=False).agg({**{c: lambda s: s.sum(min_count=len(s)) for c in CIFRAS},
                                               "reservado": "max"})
    r = av.merge(z, on="clave", how="left").drop(columns="clave")
    r["nota"] = np.where(r["reservado"].fillna(False), "cifras reservadas (menos de 10 viviendas)", "")
    orden = {"extremo": 0, "fuerte": 1, "normal": 2}
    return r.sort_values(["nivel", "personas"], key=lambda s: s.map(orden) if s.name == "nivel" else -s.fillna(0))


# ---------------------------------------------------------------------------------------------------- main
def main() -> None:
    PRIVADO.mkdir(parents=True, exist_ok=True)
    print("1. Habitantes"); h = habitantes_por_manzana()
    print("2. Viviendas"); v = viviendas_por_manzana()
    print("3. Profundidad"); p = profundidad_por_manzana()
    m = v.merge(h.drop(columns=[c for c in ("viviendas",) if c in h]), on="idmanzana", how="left")
    m = m.merge(p, on="idmanzana", how="left")
    sin_hab = m["personas"].isna().sum()
    m[CIFRAS[1:]] = m[CIFRAS[1:]].fillna(0)
    m[["prof_rp10", "prof_rp100"]] = m[["prof_rp10", "prof_rp100"]].fillna(0)
    print(f"  manzanas sin habitantes en el archivo: {sin_hab:,} · personas por vivienda: "
          f"{m['personas'].sum() / max(m['viviendas'].sum(), 1):.2f}")

    t0 = totales(m)
    t = suprimir(t0)
    assert "idmanzana" not in t.columns
    t.to_csv(PRIVADO / "habitantes_distrito.csv", index=False)
    a = con_aviso(t)
    a.to_csv(PRIVADO / "aviso_con_habitantes.csv", index=False)

    z = t[t["escenario"] == "rp100"]
    print("\nZona inundable 1 en 100 años (todos los distritos, antes de ocultar):")
    print(m[m["prof_rp100"] > 0][CIFRAS].sum().astype(int).to_string())
    print(f"Distritos ocultos (rp100): {int(z['reservado'].sum())}")
    print("\nDistritos con aviso fuerte o extremo:")
    print(a[a["nivel"].isin(["extremo", "fuerte"])][["distrito", "nivel", "fecha_max", "personas", "edad_0_4",
                                                     "edad_65_mas", "nota"]].to_string(index=False))

    if ARGS.publicar:
        pub = {"fuente": "INEI, Censos Nacionales 2025: personas por sexo y edad, sumadas por distrito. Publicación de "
                         "totales autorizada por el profesor del curso; datos por manzana no publicados.",
               "metodo": "Cada manzana se ubica por un punto interior y se toma la profundidad de la zona inundable "
                         "de JRC en ese punto. Se suman las personas de las manzanas dentro de la zona.",
               "reserva": f"Se ocultan los distritos con menos de {MINIMO_VIVIENDAS} viviendas en la zona y, si en un "
                          "departamento queda uno solo oculto, también el siguiente más chico.",
               "escenarios": {}}
        for esc, g in t[t["escenario"] != "distrito_total"].groupby("escenario"):
            g2 = g.replace({np.nan: None})
            pub["escenarios"][esc] = {
                "total": {c: int(t0.loc[t0["escenario"] == esc, c].sum()) for c in CIFRAS},
                "distritos": g2[["ubigeo", "departamento", "provincia", "distrito", "reservado"] + CIFRAS]
                .to_dict(orient="records")}
        ruta = DASH / "habitantes_censo.json"
        json.dump(pub, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nPublicable: {ruta} (solo totales por distrito)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--publicar", action="store_true", help="escribe el JSON de totales por distrito para el tablero")
    ARGS = ap.parse_args()
    main()
