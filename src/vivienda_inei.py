"""Viviendas del Censo 2025 (INEI) en la zona inundable y en el agua que vio el radar. Un solo cálculo para el tablero.

Entrada CONFIDENCIAL (no se sube; carpeta configurable con IAPN_INEI_MANZANAS, por defecto datos_inei/manzana/):
    manz_tumbes.csv, manz_piura.csv   una fila por manzana: viviendas ocupadas y proporción de cada material de
                                      paredes (S2_P1), techos (S2_P2) y pisos (S2_P3), según la cédula del INEI
    shp_piura_tumbes/manz_piura_tumbes.shp   polígono de cada manzana (WGS84)

Salidas públicas, SOLO totales (ninguna cifra por manzana):
    dashboard/data/viviendas_censo.json              lo que muestra el tablero
    dashboard/data/descargas/viviendas_censo_distritos.csv
Regla de confidencialidad: un distrito con menos de 10 viviendas en una capa no se detalla (entra solo en el total).

Método:
    - Cada manzana se ubica por un punto interior (representative_point).
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
    g = gpd.read_file(ENTRADA / "shp_piura_tumbes" / "manz_piura_tumbes.shp")[["idmanzana", "nombprov", "nombdist", "geometry"]]
    g["idmanzana"] = g["idmanzana"].astype(str)
    p = g.geometry.representative_point()
    g = pd.DataFrame({"idmanzana": g.idmanzana, "provincia": g.nombprov, "distrito": g.nombdist, "lon": p.x, "lat": p.y})
    m = m.merge(g, on="idmanzana", how="left", validate="one_to_one")
    if m["lon"].isna().any():
        raise SystemExit(f"ERROR: {int(m['lon'].isna().sum())} manzanas del CSV sin polígono")
    n = m["n_viviendas_ocupadas"].astype(float)
    m["viviendas"] = n
    for k, (p_, cods) in GRUPOS.items():
        m[k] = n * m[[f"sh_s2_p{p_}_{c}" for c in cods]].astype(float).sum(axis=1)
    m["precarias"] = np.maximum(m.paredes_tierra + m.paredes_precarias, m.piso_tierra)
    m["departamento"] = m["ubigeo"].str[:2].map(DEP)
    return m


def muestrear(m: pd.DataFrame, ruta: Path) -> np.ndarray:
    import rasterio
    with rasterio.open(ruta) as s:
        v = np.array([x[0] for x in s.sample(list(zip(m.lon, m.lat)))], dtype="float32")
    v[~np.isfinite(v)] = 0
    return v


def por_distrito(t: pd.DataFrame, cols: list[str]) -> list[dict]:
    d = t.groupby(["ubigeo", "departamento", "provincia", "distrito"])[cols].sum().round().astype(int).reset_index()
    d = d[d["viviendas"] >= MINIMO].sort_values("viviendas", ascending=False)
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
    esc = {}
    for k in ("rp10", "rp100"):
        v = muestrear(m, DATA / "exposicion" / f"peligro_{k}.tif")
        t = m[v > 0]
        esc[k] = {"viviendas": round(float(t.viviendas.sum())),
                  "por_departamento": {d: round(float(t.loc[t.departamento == d, "viviendas"].sum())) for d in ("Piura", "Tumbes")},
                  "viviendas_mas_1_5m": round(float(m.loc[v > 1.5, "viviendas"].sum())),
                  **{c: round(float(t[c].sum())) for c in mat},
                  "distritos": por_distrito(t, ["viviendas", "paredes_tierra", "paredes_precarias", "piso_tierra", "precarias"])}
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
                    "precarias": round(float(t.precarias.sum())), "manzanas": int(dentro.sum()),
                    "distritos": por_distrito(t, ["viviendas", "precarias"])}
    tot = {"viviendas_ocupadas": round(float(m.viviendas.sum())),
           "por_departamento": {d: round(float(m.loc[m.departamento == d, "viviendas"].sum())) for d in ("Piura", "Tumbes")},
           **{c: round(float(m[c].sum())) for c in mat}}
    salida = {
        "fuente": "INEI, Censos Nacionales 2025: viviendas ocupadas por manzana y material predominante de paredes, techo y "
                  "piso (datos entregados al proyecto por el INEI; publicación de totales autorizada).",
        "metodo": "Cada manzana se ubica por un punto interior y se toma la profundidad de la zona inundable de JRC en ese "
                  "punto, o si cae en el agua nueva que vio el radar. Viviendas por material = viviendas ocupadas de la "
                  "manzana × proporción con ese material. Solo se publican totales por distrito; los distritos con menos de "
                  f"{MINIMO} viviendas en una capa no se detallan.",
        "limite": "Solo incluye viviendas en manzanas (zonas urbanas y centros poblados); la vivienda rural dispersa no está, "
                  "así que las cifras son un mínimo.",
        "definiciones": DEFINICIONES, "total_tumbes_piura": tot, "escenarios": esc, "radar": radar,
        "generado_con": "src/vivienda_inei.py"}
    json.dump(salida, open(SALIDA_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    filas = []
    for k, e in esc.items():
        filas += [{"capa": k, **d} for d in e["distritos"]]
    for k, e in radar.items():
        filas += [{"capa": k, **d} for d in e["distritos"]]
    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filas).to_csv(SALIDA_CSV, index=False, encoding="utf-8")
    print("total:", tot["viviendas_ocupadas"], "· rp10:", esc["rp10"]["viviendas"], "· rp100:", esc["rp100"]["viviendas"],
          "· radar:", {k: (r["viviendas"], r["precarias"]) for k, r in radar.items()})


if __name__ == "__main__":
    main()
