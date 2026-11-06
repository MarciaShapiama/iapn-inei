"""Antes y después del cambio de mapa de distritos (GADM 4.1, 76 distritos -> INEI, 78 distritos).

Compara, en las zonas inundables de 1 en 10 y 1 en 100 años (JRC), por distrito y en total: personas (WorldPop),
edificaciones (Open Buildings), colegios y centros de salud dentro de la zona, y km² inundables. El «antes» es el
dashboard/data/inundacion.json calculado con el mapa GADM (se pasa como argumento); el «después», el actual.

Los dos distritos nuevos se comparan sumados con el distrito que los contenía en GADM:
    Piura (200101) + Veintiséis de Octubre (200115)  frente a  Piura de GADM
    Zorritos (240201) + Canoas de Punta Sal (240203) frente a  Zorritos de GADM

Uso: python herramientas/pruebas/comparar_mapa_distritos.py <inundacion_antes.json> [salida.csv]
Salida: tabla por distrito (CSV) y totales en pantalla.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
CIFRAS = ["km2", "personas", "edificaciones", "colegios_dentro", "salud_dentro"]
JUNTOS = {"200115": "200101", "240203": "240201"}


def plano(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


def tabla(ruta: Path, evento: str) -> pd.DataFrame:
    j = json.load(open(ruta, encoding="utf-8"))
    d = pd.DataFrame(j["eventos"][evento]["distritos"])
    d = d[d["departamento"] != "Sin distrito asignado"].copy()
    d["k"] = d["departamento"].map(plano) + "|" + d["provincia"].map(plano) + "|" + d["distrito"].map(plano)
    return d


def comparar(antes: Path, despues: Path, evento: str) -> tuple[pd.DataFrame, dict]:
    a, b = tabla(antes, evento), tabla(despues, evento)
    b["ubigeo"] = b["ubigeo"].astype(str)
    llave = b.set_index("ubigeo")["k"]
    b["k_comparable"] = [llave[JUNTOS.get(u, u)] for u in b["ubigeo"]]
    bb = b.groupby("k_comparable")[CIFRAS].sum()
    aa = a.groupby("k")[CIFRAS].sum()
    t = aa.join(bb, lsuffix="_antes", rsuffix="_despues", how="outer").fillna(0)
    for c in CIFRAS:
        t[f"{c}_dif_pct"] = (100 * (t[f"{c}_despues"] - t[f"{c}_antes"]) / t[f"{c}_antes"].where(t[f"{c}_antes"] != 0)).round(1)
    t.insert(0, "evento", evento)
    tot = {c: (float(a[c].sum()), float(b[c].sum())) for c in CIFRAS}
    ja, jb = (json.load(open(x, encoding="utf-8"))["eventos"][evento] for x in (antes, despues))
    tot["sin_distrito_personas"] = tuple(float(sum(f["personas"] for f in x["distritos"] if f["departamento"] == "Sin distrito asignado"))
                                          for x in (ja, jb))
    tot["total_evento_personas"] = (float(ja["personas"]), float(jb["personas"]))
    tot["total_evento_edificaciones"] = (float(ja["edificaciones"]), float(jb["edificaciones"]))
    t.index.name = "distrito"
    return t.reset_index(), tot


def main() -> None:
    antes = Path(sys.argv[1])
    despues = RAIZ / "dashboard" / "data" / "inundacion.json"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    partes = []
    for ev in ("rp10", "rp100"):
        t, tot = comparar(antes, despues, ev)
        partes.append(t)
        print(f"\n== {ev} (suma de distritos; antes -> después, diferencia)")
        for c, (x, y) in tot.items():
            print(f"  {c}: {x:,.1f} -> {y:,.1f} ({100 * (y - x) / x if x else 0:+.2f} %)")
        g = t[[f"{c}_dif_pct" for c in CIFRAS]].abs().max(axis=1)
        print(f"  distritos con alguna cifra que cambia más de 1 %: {int((g > 1).sum())} de {len(t)}")
    out = pd.concat(partes, ignore_index=True)
    if salida:
        out.to_csv(salida, index=False, float_format="%.1f")
        print(f"\nTabla por distrito: {salida}")


if __name__ == "__main__":
    main()
