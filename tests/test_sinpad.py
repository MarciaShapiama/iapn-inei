"""Pruebas de la variable dependiente construida con el SINPAD (src/etiqueta_sinpad.py)."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from etiqueta_sinpad import EVENTOS, FIN_ETIQUETA, PROCEDENCIA, SEMANAL, fecha_sinpad  # noqa: E402


@pytest.mark.parametrize("texto,mes,esperado", [
    ("17/02/2003", "FEBRERO", "2003-02-17"),     # DD/MM/AAAA (2003-2024)
    ("01/15/26", "ENERO", "2026-01-15"),         # MM/DD/AA (2026)
    ("03/04/2025", "ABRIL", "2025-04-03"),       # ambiguo: lo decide la columna MES
    ("03/04/2025", "MARZO", "2025-03-04"),
    ("31/02/2010", "FEBRERO", None),             # fecha imposible
    ("05/06/2010", "ENERO", None),               # no coincide con MES
])
def test_fecha_sinpad(texto, mes, esperado):
    assert fecha_sinpad(texto, mes) == esperado


def test_procedencia_trazable():
    p = json.loads(PROCEDENCIA.read_text(encoding="utf-8"))
    assert p["dataset"].startswith("https://www.datosabiertos.gob.pe/")
    for a in p["archivos"].values():
        assert len(a["sha256"]) == 64 and a["bytes"] > 0
    conteos = [x["registros"] for x in p["pasos"]]
    assert conteos[:5] == sorted(conteos[:5], reverse=True), "cada filtro solo puede quitar registros"


def test_eventos_solo_agua_y_concilian():
    ev = pd.read_csv(EVENTOS, dtype={"codigo": str})
    assert ev["peligro"].str.contains("INUND|LLUVI", case=False).all()
    assert not ev["peligro"].str.contains("MAREJ|OLEAJE|SISMO|INCENDIO", case=False).any()
    assert ev["codigo"].is_unique
    s = pd.read_csv(SEMANAL)
    assert s["eventos"].sum() == len(ev), "las semanas deben sumar todos los registros"
    p = json.loads(PROCEDENCIA.read_text(encoding="utf-8"))
    assert len(ev) == p["pasos"][4]["registros"]


def test_y_binaria_y_sin_futuro():
    from modelo_inundacion import OBJETIVO, cargar
    b = cargar("sinpad")
    y = b.dropna(subset=[OBJETIVO])
    assert set(y[OBJETIVO].unique()) <= {0.0, 1.0}
    assert y["semana"].max() <= pd.Timestamp(FIN_ETIQUETA) - pd.Timedelta(weeks=4)
    # Y(t) = 1 si y solo si hay registro en t+1..t+4
    assert not b.duplicated(["clave", "prov_n", "semana"]).any()
    for clave in ["TUMBESTUMBES", "PIURASALITRAL"]:          # Salitral: dos distritos con el mismo nombre
        for _, d in b[b["clave"] == clave].groupby("prov_n"):
            d = d.sort_values("semana").reset_index(drop=True)
            for i in range(len(d) - 4):
                if pd.notna(d.loc[i, OBJETIVO]):
                    assert d.loc[i, OBJETIVO] == d.loc[i + 1:i + 4, "emergencia_sem"].max()
