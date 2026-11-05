"""Viviendas ocupadas del INEI por distrito: vulnerabilidad física y exposición a inundaciones.

Entrada (no se sube al repositorio; carpeta configurable con IAPN_INEI_MANZANAS):
    docs_recibidos/manzanas/manzana/manz_tumbes.csv, manz_piura.csv
        una fila por manzana: viviendas ocupadas y proporción de cada material de paredes (S2_P1),
        techos (S2_P2) y pisos (S2_P3), según la cédula del INEI (docs_recibidos/preguntas_vivienda.xlsx)
    docs_recibidos/manzanas/manzana/shp_piura_tumbes/manz_piura_tumbes.shp
        polígono de cada manzana (WGS84)

Salida pública, SOLO totales por distrito (ninguna cifra por manzana):
    dashboard/data/vivienda_inei_distritos.json
    dashboard/data/descargas/vivienda_inei_distritos.csv

Criterios (de trabajo, a validar con el equipo):
    paredes precarias   adobe, tapia, quincha, piedra con barro, madera, triplay/calamina/estera (S2_P1 = 3-8)
    techo precario      caña o estera con barro, triplay/estera/carrizo, paja u hoja de palmera (S2_P2 = 5-7)
    piso de tierra      S2_P3 = 6
    expuesta            el punto interior de la manzana cae en la zona inundable de JRC (1/10 o 1/100 años) o en el agua
                        nueva que detectó el radar (2017, 2023, últimos 24 días), con las mismas capas y máscaras que
                        src/impacto.py. Es exposición, no daño: no equivale a viviendas afectadas.

Si los archivos del INEI no están (por ejemplo en GitHub Actions), no hace nada y conserva la última salida.
Uso: python src/vivienda_inei.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from comun import ahora_lima, escribir_json
from config import DASH_DATA, RAIZ

ENTRADA = Path(os.getenv("IAPN_INEI_MANZANAS", RAIZ / "docs_recibidos" / "manzanas" / "manzana"))
SALIDA_JSON = DASH_DATA / "vivienda_inei_distritos.json"
SALIDA_CSV = DASH_DATA / "descargas" / "vivienda_inei_distritos.csv"

PAREDES_PRECARIAS = (3, 4, 5, 6, 7, 8)
TECHO_PRECARIO = (5, 6, 7)
PISO_TIERRA = (6,)
DEPARTAMENTO = {"20": "PIURA", "24": "TUMBES"}


def leer_manzanas() -> pd.DataFrame:
    tipos = {"idmanzana": str, "ubigeo": str, "zona_id": str, "manzana_id": str}
    m = pd.concat([pd.read_csv(ENTRADA / f, dtype=tipos) for f in ("manz_tumbes.csv", "manz_piura.csv")],
                  ignore_index=True)
    n = m["n_viviendas_ocupadas"].astype(float)
    suma = lambda p, codigos: m[[f"sh_s2_{p}_{k}" for k in codigos]].sum(axis=1)  # noqa: E731
    m["viv_paredes_precarias"] = n * suma("p1", PAREDES_PRECARIAS)
    m["viv_techo_precario"] = n * suma("p2", TECHO_PRECARIO)
    m["viv_piso_tierra"] = n * suma("p3", PISO_TIERRA)
    m["viv_precaria"] = n * np.maximum(suma("p1", PAREDES_PRECARIAS), suma("p3", PISO_TIERRA))   # cota inferior
    return m


def puntos_manzana() -> pd.DataFrame:
    import geopandas as gpd
    g = gpd.read_file(ENTRADA / "shp_piura_tumbes" / "manz_piura_tumbes.shp", columns=["idmanzana", "nombdist"])
    p = g.geometry.representative_point()
    return pd.DataFrame({"idmanzana": g["idmanzana"].astype(str), "nombdist": g["nombdist"], "lon": p.x, "lat": p.y})


def marcar_exposicion(m: pd.DataFrame) -> list[str]:
    """Agrega una columna booleana por capa: ¿la manzana cae dentro?"""
    from impacto import cargar_capas, indices
    claves = []
    for clave, (_nombre, _tipo, valor, t, _meta) in cargar_capas().items():
        fil, col, ok = indices(m["lon"].to_numpy(), m["lat"].to_numpy(), t, valor.shape)
        dentro = np.zeros(len(m), bool)
        dentro[ok] = valor[fil[ok], col[ok]] > 0
        m[f"en_{clave}"] = dentro
        claves.append(clave)
    return claves


def main() -> None:
    if not (ENTRADA / "manz_piura.csv").exists():
        print(f"Sin datos del INEI en {ENTRADA}: se conserva {SALIDA_JSON.name}")
        return
    m = leer_manzanas()
    pts = puntos_manzana()
    m = m.merge(pts, on="idmanzana", how="left", validate="one_to_one")
    sin_geo = int(m["lon"].isna().sum())
    if sin_geo:
        raise SystemExit(f"ERROR: {sin_geo} manzanas del CSV sin polígono")
    claves = marcar_exposicion(m)

    cols_viv = ["viv_paredes_precarias", "viv_techo_precario", "viv_piso_tierra", "viv_precaria"]
    agg = {"manzanas": ("idmanzana", "size"), "viviendas_ocupadas": ("n_viviendas_ocupadas", "sum"),
           **{c: (c, "sum") for c in cols_viv}}
    for k in claves:
        m[f"viv_{k}"] = m["n_viviendas_ocupadas"] * m[f"en_{k}"]
        m[f"viv_precaria_{k}"] = m["viv_precaria"] * m[f"en_{k}"]
        agg[f"viviendas_{k}"] = (f"viv_{k}", "sum")
        agg[f"viviendas_precarias_{k}"] = (f"viv_precaria_{k}", "sum")
    d = m.groupby("ubigeo").agg(**agg).reset_index()
    nombres = m.groupby("ubigeo")["nombdist"].first()
    d.insert(1, "departamento", d["ubigeo"].str[:2].map(DEPARTAMENTO))
    d.insert(2, "distrito", d["ubigeo"].map(nombres).str.title())
    num = [c for c in d.columns if c not in ("ubigeo", "departamento", "distrito")]
    d[num] = d[num].round().astype(int)
    d = d.rename(columns={"viv_paredes_precarias": "viviendas_paredes_precarias",
                          "viv_techo_precario": "viviendas_techo_precario",
                          "viv_piso_tierra": "viviendas_piso_tierra", "viv_precaria": "viviendas_precarias"})
    for c in ("paredes_precarias", "techo_precario", "piso_tierra", "precarias"):
        d[f"pct_{c}"] = (100 * d[f"viviendas_{c}"] / d["viviendas_ocupadas"]).round(1)
    d = d.sort_values("ubigeo").reset_index(drop=True)

    tot = d.groupby("departamento")[[c for c in d.columns if c.startswith("viviendas")]].sum()
    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(SALIDA_CSV, index=False, encoding="utf-8")
    escribir_json(SALIDA_JSON, {
        "generado": ahora_lima(),
        "fuente": "INEI, viviendas ocupadas por manzana con material de paredes, techos y pisos (Tumbes y Piura), "
                  "entregado al equipo del PEU-CD en noviembre de 2026. Año de referencia y método de recolección "
                  "por confirmar con el INEI.",
        "nivel": "distrito (suma de manzanas); no se publican cifras por manzana",
        "definiciones": {
            "viviendas_precarias": "viviendas con paredes precarias o piso de tierra (se toma el mayor de los dos "
                                   "porcentajes de la manzana: es una cota inferior)",
            "paredes_precarias": "adobe, tapia, quincha, piedra con barro, madera o triplay/calamina/estera",
            "techo_precario": "caña o estera con barro, triplay/estera/carrizo, paja u hoja de palmera",
            "viviendas_<capa>": "viviendas de manzanas cuyo punto interior cae en esa capa: rp10/rp100 = zona "
                                "inundable de JRC (escenario, no pronóstico); 2017/2023/vivo = agua detectada por "
                                "radar. Es exposición, no viviendas afectadas.",
        },
        "capas": claves,
        "totales": {k: {c: int(v) for c, v in fila.items()} for k, fila in tot.iterrows()},
        "distritos": d.to_dict(orient="records"),
    })
    print(f"{len(d)} distritos, {int(d['viviendas_ocupadas'].sum()):,} viviendas ocupadas")
    print(tot.T.to_string())


if __name__ == "__main__":
    sys.exit(main())
