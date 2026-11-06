"""Viviendas del Censo 2025 (INEI) en la zona inundable y en el agua que vio el radar. Un solo cálculo para el tablero.

Entrada CONFIDENCIAL (no se sube; carpeta configurable con IAPN_INEI_MANZANAS, por defecto datos_inei/manzana/):
    manz_tumbes.csv, manz_piura.csv   una fila por manzana o centro poblado: viviendas ocupadas y proporción de cada
                                      material de paredes (S2_P1), techos (S2_P2) y pisos (S2_P3), según la cédula
    pob_tumbes.csv, pob_piura.csv     las mismas unidades: personas por sexo y grupo de edad (0-4, 5-14, 15-64, 65+)
    shp_piura_tumbes/manz_piura_tumbes.shp   polígono de cada manzana (WGS84)
    shp_ccpp_piura_tumbes/ccpp_piura_tumbes.shp   punto de cada centro poblado (los CCPP no tienen límites)
    idmanzana de 14-15 caracteres = manzana (ubigeo + zona + manzana); de 10 = centro poblado (ubigeo + codccpp), que
    agrupa las viviendas y personas que no están en manzanas (entrega del INEI del 6/11/2026).

Salidas públicas, SOLO totales (ninguna cifra por manzana):
    dashboard/data/viviendas_censo.json              lo que muestra el tablero
    dashboard/data/descargas/viviendas_censo_distritos.csv
Reglas de confidencialidad: un distrito con menos de 10 viviendas en una capa no se detalla (entra solo en el total), y
dentro de un distrito detallado no se publica ninguna cifra de personas (sexo o edad) menor a 10.

Método:
    - Cada manzana se ubica por un punto interior (representative_point); cada centro poblado, por su punto. Las
      viviendas de un centro poblado están dispersas alrededor de ese punto: su ubicación es aproximada.
    - Zona inundable: profundidad del mapa de JRC (1 en 10 y 1 en 100 años) en ese punto, tal como lo publica JRC
      (data/exposicion/peligro_rp*.tif). No se recorta con los polígonos de distrito: la manzana ya trae su UBIGEO.
    - Radar: el punto cae en el agua nueva tal como se publica en el mapa (src/impacto.py: sin agua permanente, sin la
      orilla del mar y sin manchas sueltas).
    - Viviendas por material = viviendas ocupadas de la manzana × proporción con ese material.
      "Precaria" = el mayor de (paredes de tierra o precarias) y (piso de tierra): cota inferior, porque no se sabe
      cuántas viviendas tienen las dos cosas.
Es exposición, no daño: no equivale a viviendas afectadas.

Si los archivos del INEI no están (por ejemplo en GitHub Actions), no hace nada y conserva la última salida.
Uso: python src/vivienda_inei.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import DASH_DATA, DATA, RAIZ  # noqa: E402

ENTRADA = Path(os.getenv("IAPN_INEI_MANZANAS", RAIZ / "datos_inei" / "manzana"))
SALIDA_JSON = DASH_DATA / "viviendas_censo.json"
SALIDA_CSV = DASH_DATA / "descargas" / "viviendas_censo_distritos.csv"
MINIMO = 10

GRUPOS = {
    "paredes_tierra": (1, (3, 4, 5, 6)),      # adobe, tapia, quincha, piedra con barro
    "paredes_precarias": (1, (7, 8)),         # madera; triplay, calamina o estera
    "techo_precario": (2, (5, 6, 7)),         # caña o estera con barro; triplay, estera o carrizo; paja u hoja de palmera
    "piso_tierra": (3, (6,)),
}
DEFINICIONES = {"paredes_tierra": "adobe, tapia, quincha o piedra con barro",
                "paredes_precarias": "madera, triplay, calamina o estera",
                "techo_precario": "caña o estera con barro, triplay, estera, carrizo o paja",
                "piso_tierra": "piso de tierra",
                "precarias": "paredes de tierra o precarias, o piso de tierra (se toma el mayor de los dos: cota inferior)"}
POB = {"personas": None, "hombres": ["h_0_4", "h_5_14", "h_15_64", "h_65plus"],
       "mujeres": ["m_0_4", "m_5_14", "m_15_64", "m_65plus"], "edad_0_4": ["h_0_4", "m_0_4"],
       "edad_5_14": ["h_5_14", "m_5_14"], "edad_15_64": ["h_15_64", "m_15_64"], "edad_65_mas": ["h_65plus", "m_65plus"]}
RADAR = {"2017": "Radar 2017 (Niño costero)", "2023": "Radar 2023 (ciclón Yaku)", "vivo": "Radar, últimos 24 días"}
DEP = {"20": "Piura", "24": "Tumbes"}


def norm(x: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper().split())


def nombres_con_tilde() -> dict:
    """Nombres de provincia y distrito como los escribe el tablero (con tildes), desde distritos.geojson."""
    g = json.load(open(DATA / "exposicion" / "distritos.geojson", encoding="utf-8"))
    out = {}
    for f in g["features"]:
        for k in ("provincia", "distrito"):
            out[norm(f["properties"][k])] = f["properties"][k]
    # distritos que el GeoJSON (GADM) escribe sin tilde o no trae
    for x in ("Veintiséis de Octubre", "La Unión", "Colán", "El Tallán", "Máncora", "Los Órganos", "Bellavista de la Unión"):
        out[norm(x)] = x
    return out


NOMBRES = nombres_con_tilde()


def leer() -> pd.DataFrame:
    import geopandas as gpd
    tipos = {"idmanzana": str, "ubigeo": str}
    m = pd.concat([pd.read_csv(ENTRADA / f"manz_{d}.csv", dtype=tipos) for d in ("piura", "tumbes")], ignore_index=True)
    archivos_pob = [ENTRADA / f"pob_{d}.csv" for d in ("piura", "tumbes")]
    if all(a.exists() for a in archivos_pob):
        pob = pd.concat([pd.read_csv(a, dtype=tipos) for a in archivos_pob], ignore_index=True)
        cols = ["idmanzana", "ubigeo", "pob_total"] + [c for c in pob.columns if c[:2] in ("h_", "m_")]
        # unión completa: hay unidades con personas y sin viviendas ocupadas (viviendas colectivas)
        m = m.merge(pob[cols], on="idmanzana", how="outer", suffixes=("", "_pob"), validate="one_to_one")
        m["ubigeo"] = m["ubigeo"].fillna(m.pop("ubigeo_pob"))
    m["unidad"] = np.where(m["idmanzana"].str.len() == 10, "centro poblado", "manzana")
    g = gpd.read_file(ENTRADA / "shp_piura_tumbes" / "manz_piura_tumbes.shp")[["idmanzana", "nombprov", "nombdist", "geometry"]]
    g["idmanzana"] = g["idmanzana"].astype(str)
    p = g.geometry.representative_point()
    ubic = [pd.DataFrame({"idmanzana": g.idmanzana, "provincia": g.nombprov, "distrito": g.nombdist, "lon": p.x, "lat": p.y})]
    ruta_cc = ENTRADA / "shp_ccpp_piura_tumbes" / "ccpp_piura_tumbes.shp"
    if ruta_cc.exists():
        c = gpd.read_file(ruta_cc)
        ubic.append(pd.DataFrame({"idmanzana": c.idccpp.astype(str), "provincia": c.nombprov, "distrito": c.nombdist,
                                  "lon": c.geometry.x, "lat": c.geometry.y}))
    m = m.merge(pd.concat(ubic, ignore_index=True), on="idmanzana", how="left", validate="many_to_one")
    sin = m["lon"].isna()
    if sin.any():
        print(f"  aviso: {int(sin.sum())} unidades sin ubicación ({m.loc[sin, 'n_viviendas_ocupadas'].astype(float).sum():.0f} "
              f"viviendas, {m.loc[sin, 'pob_total'].astype(float).sum() if 'pob_total' in m else 0:.0f} personas): "
              "cuentan en el total, no en las capas")
    n = m["n_viviendas_ocupadas"].astype(float).fillna(0)
    m["viviendas"] = n
    for k, (p_, cods) in GRUPOS.items():
        m[k] = n * m[[f"sh_s2_p{p_}_{c}" for c in cods]].astype(float).fillna(0).sum(axis=1)
    m["precarias"] = np.maximum(m.paredes_tierra + m.paredes_precarias, m.piso_tierra)
    if "pob_total" in m:
        for k, cols in POB.items():
            m[k] = (m["pob_total"].astype(float).fillna(0) if cols is None
                    else m[cols].astype(float).fillna(0).sum(axis=1))
    m["departamento"] = m["ubigeo"].str[:2].map(DEP)
    return m


def resumen_pob(t: pd.DataFrame) -> dict:
    return {k: round(float(t[k].sum())) for k in POB if k in t}


def muestrear(m: pd.DataFrame, ruta: Path) -> np.ndarray:
    import rasterio
    v = np.zeros(len(m), dtype="float32")
    ok = m["lon"].notna().to_numpy()
    with rasterio.open(ruta) as s:
        v[ok] = np.array([x[0] for x in s.sample(list(zip(m.lon[ok], m.lat[ok])))], dtype="float32")
    v[~np.isfinite(v)] = 0
    return v


def por_distrito(t: pd.DataFrame, cols: list[str]) -> list[dict]:
    d = t.groupby(["ubigeo", "departamento", "provincia", "distrito"])[cols].sum().round().astype(int).reset_index()
    d = d[d["viviendas"] >= MINIMO].sort_values("viviendas", ascending=False)
    # ninguna cifra de personas menor a 10 dentro de un distrito detallado
    for k in POB:
        if k in d:
            d[k] = d[k].astype(object).where(d[k] >= MINIMO, None)
    if "paredes_tierra" in d:
        d["pct_fragiles"] = ((d.paredes_tierra + d.paredes_precarias) / d.viviendas * 100).round(1)
    d["provincia"] = [NOMBRES.get(norm(p_), p_.title()) for p_ in d["provincia"]]
    d["distrito"] = [NOMBRES.get(norm(x), x.title()) for x in d["distrito"]]
    return d.to_dict(orient="records")


def main() -> None:
    if not (ENTRADA / "manz_piura.csv").exists():
        print(f"Sin datos del INEI en {ENTRADA}: se conserva {SALIDA_JSON.name}")
        return
    m = leer()
    mat = list(GRUPOS) + ["precarias"]
    pobc = [k for k in POB if k in m]
    esc = {}
    for k in ("rp10", "rp100"):
        v = muestrear(m, DATA / "exposicion" / f"peligro_{k}.tif")
        t = m[v > 0]
        esc[k] = {"viviendas": round(float(t.viviendas.sum())),
                  "por_departamento": {d: round(float(t.loc[t.departamento == d, "viviendas"].sum())) for d in ("Piura", "Tumbes")},
                  "viviendas_mas_1_5m": round(float(m.loc[v > 1.5, "viviendas"].sum())),
                  **{c: round(float(t[c].sum())) for c in mat},
                  **resumen_pob(t),
                  "en_centros_poblados": {"viviendas": round(float(t.loc[t.unidad == "centro poblado", "viviendas"].sum())),
                                          **({"personas": round(float(t.loc[t.unidad == "centro poblado", "personas"].sum()))}
                                             if "personas" in t else {})},
                  "distritos": por_distrito(t, ["viviendas", "paredes_tierra", "paredes_precarias", "piso_tierra", "precarias"]
                                            + pobc)}
        m[f"en_{k}"] = v > 0
    # Radar: la capa PUBLICADA (impacto.cargar_capas), no el .tif crudo: el crudo marca también agua permanente (2),
    # el mar y la orilla, que el tablero quita con la máscara de tierra y la limpieza de manchas pequeñas.
    from impacto import cargar_capas, indices
    radar = {}
    for k, (nombre_capa, tipo, valor, t_, meta) in cargar_capas().items():
        if tipo != "radar" or k not in RADAR:
            continue
        fil, col, ok = indices(m.lon.to_numpy(), m.lat.to_numpy(), t_, valor.shape)
        dentro = np.zeros(len(m), bool)
        dentro[ok] = valor[fil[ok], col[ok]] > 0
        t = m[dentro]
        radar[k] = {"nombre": RADAR[k], "periodo": meta.get("periodo"), "viviendas": round(float(t.viviendas.sum())),
                    "precarias": round(float(t.precarias.sum())), "manzanas": int((t.unidad == "manzana").sum()),
                    "centros_poblados": int((t.unidad == "centro poblado").sum()), **resumen_pob(t),
                    "distritos": por_distrito(t, ["viviendas", "precarias"] + [c for c in ("personas",) if c in t])}
    tot = {"viviendas_ocupadas": round(float(m.viviendas.sum())),
           "por_departamento": {d: round(float(m.loc[m.departamento == d, "viviendas"].sum())) for d in ("Piura", "Tumbes")},
           **{c: round(float(m[c].sum())) for c in mat}, **resumen_pob(m),
           "en_centros_poblados": {"viviendas": round(float(m.loc[m.unidad == "centro poblado", "viviendas"].sum())),
                                   **({"personas": round(float(m.loc[m.unidad == "centro poblado", "personas"].sum()))}
                                      if "personas" in m else {})},
           "unidades_sin_ubicacion": {"viviendas": round(float(m.loc[m.lon.isna(), "viviendas"].sum())),
                                      **({"personas": round(float(m.loc[m.lon.isna(), "personas"].sum()))}
                                         if "personas" in m else {})}}
    salida = {
        "fuente": "INEI, Censos Nacionales 2025: viviendas ocupadas, material predominante de paredes, techo y piso, y "
                  "personas por sexo y grupo de edad, por manzana y por centro poblado (datos entregados al proyecto por el "
                  "INEI; publicación de totales autorizada).",
        "metodo": "Cada manzana se ubica por un punto interior y cada centro poblado por su punto; se toma la profundidad "
                  "de la zona inundable de JRC en ese punto, o si cae en el agua nueva que vio el radar. Viviendas por "
                  "material = viviendas ocupadas × proporción con ese material. Solo se publican totales por distrito; los "
                  f"distritos con menos de {MINIMO} viviendas en una capa no se detallan y no se publica ninguna cifra de "
                  f"personas menor a {MINIMO}.",
        "limite": "Las viviendas fuera de manzanas están agrupadas en el punto de su centro poblado (los centros poblados no "
                  "tienen límites): si ese punto cae dentro o fuera de la zona inundable, todo el centro poblado cuenta "
                  "igual. Es una aproximación para la población rural.",
        "definiciones": DEFINICIONES, "total_tumbes_piura": tot, "escenarios": esc, "radar": radar,
        "generado_con": "src/vivienda_inei.py"}
    json.dump(salida, open(SALIDA_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    filas = []
    for k, e in esc.items():
        filas += [{"capa": k, **d} for d in e["distritos"]]
    for k, e in radar.items():
        filas += [{"capa": k, **d} for d in e["distritos"]]
    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabla = pd.DataFrame(filas)
    for c in tabla.columns:
        if c not in ("capa", "ubigeo", "departamento", "provincia", "distrito", "pct_fragiles"):
            tabla[c] = pd.to_numeric(tabla[c]).round().astype("Int64")   # vacío = celda con menos de 10 (no se publica)
    tabla.to_csv(SALIDA_CSV, index=False, encoding="utf-8")
    print("total:", tot["viviendas_ocupadas"], tot.get("personas"), "· rp10:", esc["rp10"]["viviendas"],
          esc["rp10"].get("personas"), "· rp100:", esc["rp100"]["viviendas"], esc["rp100"].get("personas"),
          esc["rp100"]["en_centros_poblados"], "· radar:", {k: (r["viviendas"], r.get("personas")) for k, r in radar.items()})


if __name__ == "__main__":
    main()
