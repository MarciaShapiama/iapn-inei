"""Actualiza SOLO las columnas de exposición (fijas por distrito) de data/modelo/base_distrito_semana.csv con el
inundacion.json vigente, sin volver a descargar lluvia, caudal ni emergencias (útil tras corregir la población).
Guarda antes una copia fechada en data/versiones/. Uso: python src/actualizar_exposicion_base.py
"""
import shutil

import pandas as pd

from base_modelo import exposicion_distrito
from comun import ahora_lima, registrar_version
from config import DATA

BASE = DATA / "modelo" / "base_distrito_semana.csv"
COLS = ["km2_inundable_rp10", "viviendas_rp10", "personas_rp10", "km2_inundable_rp100", "viviendas_rp100", "personas_rp100"]

if __name__ == "__main__":
    copia = DATA / "versiones" / f"base_distrito_semana_{ahora_lima()[:10]}_antes_exposicion.csv.gz"
    copia.parent.mkdir(parents=True, exist_ok=True)
    b = pd.read_csv(BASE)
    if not copia.exists():
        b.to_csv(copia, index=False, compression="gzip")
    e = exposicion_distrito().set_index("clave")[COLS]
    antes = b.groupby("clave")["personas_rp100"].first()
    b = b.drop(columns=COLS).join(e, on="clave")
    b[COLS] = b[COLS].fillna(0)
    b = b[pd.read_csv(BASE, nrows=0).columns]
    b.to_csv(BASE, index=False, float_format="%.3f")
    despues = b.groupby("clave")["personas_rp100"].first()
    print(f"distritos: {b['clave'].nunique()} · sin empate de exposición: {int((~b['clave'].isin(e.index)).groupby(b['clave']).first().sum())}")
    print(pd.DataFrame({"antes": antes, "despues": despues}).sort_values("antes", ascending=False).head(8))
    registrar_version([BASE], DATA / "versiones" / "manifiesto.csv", "exposicion_base_modelo")
