"""Pruebas sin red del aviso de lluvia y caudal (src/aviso_lluvia.py).

No llaman a Open-Meteo: arman el aviso con pronósticos de ejemplo y revisan la estructura del JSON, la regla del
nivel final, el motivo y qué pasa si el pronóstico de caudal no llega.
"""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

import aviso_lluvia as A

RAIZ = Path(__file__).resolve().parents[1]


def _umbrales():
    return pd.DataFrame([
        {"departamento": "Tumbes", "provincia": "Tumbes", "distrito": "San Jacinto", "p95": 26.9, "p99": 56.6},
        {"departamento": "Tumbes", "provincia": "Tumbes", "distrito": "Tumbes", "p95": 26.9, "p99": 56.6},
        {"departamento": "Tumbes", "provincia": "Zarumilla", "distrito": "Zarumilla", "p95": 28.1, "p99": 56.4},
        {"departamento": "Piura", "provincia": "Piura", "distrito": "Catacaos", "p95": 30.0, "p99": 60.0},
        {"departamento": "Piura", "provincia": "Ayabaca", "distrito": "Sapillica", "p95": 34.8, "p99": 54.8},
    ])


FECHAS = [f"2026-11-0{i}" for i in range(5, 10)] + ["2026-11-10", "2026-11-11"]


def _lluvia():
    mm = {"San Jacinto": [5, 10, 8], "Tumbes": [14, 51, 20], "Zarumilla": [18, 49, 8], "Catacaos": [2, 3, 1],
          "Sapillica": [66, 30, 50]}
    u = _umbrales()
    return {(r.departamento, r.provincia, r.distrito): (FECHAS, mm[r.distrito] + [0, 0, 0, 0]) for r in u.itertuples()}


UMB_C = {"Tumbes": {"p95": 764.2, "p99": 1277.9, "periodo": "2001-2020", "dias": 7305},
         "Piura": {"p95": 305.9, "p99": 854.0, "periodo": "2001-2020", "dias": 7305},
         "Chira": {"p95": 1387.7, "p99": 2419.8, "periodo": "2001-2020", "dias": 7305}}


def _rios(tumbes=(802.5, 711.9, 587.8), piura=(186.5, 171.2, 183.5)):
    return {"Tumbes": A.resumen_caudal(FECHAS, list(tumbes) + [500, 400, 300, 200], UMB_C["Tumbes"]),
            "Piura": A.resumen_caudal(FECHAS, list(piura) + [200, 200, 200, 200], UMB_C["Piura"])}


def _por_distrito(s):
    return {f["distrito"]: f for f in s["distritos"]}


def test_estructura_del_json():
    s = A.armar(_umbrales(), _lluvia(), _rios(), "ok", UMB_C, {})
    json.loads(json.dumps(s))                                  # serializable
    for k in ("calculado", "ventana_dias", "dias_pronostico", "conteo", "conteo_lluvia", "conteo_motivo",
              "distritos_con_rio", "distritos_solo_lluvia", "caudal", "distritos", "fuente", "nota"):
        assert k in s, k
    assert set(s["caudal"]) >= {"estado", "rios", "umbrales", "fuente", "distritos"}
    for f in s["distritos"]:
        for k in ("nivel", "nivel_lluvia", "nivel_caudal", "motivo", "mm_dia_max", "fecha_max", "p95", "p99",
                  "lluvia_diaria", "fechas", "caudal"):
            assert k in f, (f["distrito"], k)
        assert f["nivel"] in ("extremo", "fuerte", "normal", "sin umbral")
        assert f["motivo"] in (None, "lluvia", "caudal", "lluvia y caudal")
        assert "rio" in f["caudal"] and "estado" in f["caudal"]
    assert sum(s["conteo"].values()) == len(s["distritos"])


def test_nivel_final_y_motivo():
    d = _por_distrito(A.armar(_umbrales(), _lluvia(), _rios(), "ok", UMB_C, {}))
    # San Jacinto: lluvia normal, río Tumbes sobre su p95 -> fuerte por el caudal
    assert d["San Jacinto"]["nivel_lluvia"] == "normal" and d["San Jacinto"]["nivel_caudal"] == "fuerte"
    assert d["San Jacinto"]["nivel"] == "fuerte" and d["San Jacinto"]["motivo"] == "caudal"
    # Tumbes: lluvia fuerte y río fuerte
    assert d["Tumbes"]["motivo"] == "lluvia y caudal" and d["Tumbes"]["nivel"] == "fuerte"
    # Catacaos: río Piura bajo y poca lluvia
    assert d["Catacaos"]["nivel"] == "normal" and d["Catacaos"]["motivo"] is None
    assert d["Catacaos"]["caudal"]["rio"] == "Piura" and d["Catacaos"]["nivel_caudal"] == "normal"


def test_caudal_extremo_sube_el_nivel():
    d = _por_distrito(A.armar(_umbrales(), _lluvia(), _rios(tumbes=(900, 1300, 1000)), "ok", UMB_C, {}))
    assert d["Tumbes"]["nivel_caudal"] == "extremo" and d["Tumbes"]["nivel"] == "extremo"
    assert d["Tumbes"]["nivel_lluvia"] == "fuerte"


def test_distritos_sin_rio_siguen_solo_con_lluvia():
    s = A.armar(_umbrales(), _lluvia(), _rios(), "ok", UMB_C, {})
    d = _por_distrito(s)
    for n in ("Zarumilla", "Sapillica"):
        assert d[n]["caudal"]["rio"] is None and d[n]["nivel_caudal"] is None
        assert "solo lluvia" in d[n]["caudal"]["estado"]
        assert d[n]["nivel"] == d[n]["nivel_lluvia"]
    assert d["Sapillica"]["nivel"] == "extremo" and d["Sapillica"]["motivo"] == "lluvia"
    assert s["distritos_solo_lluvia"] == 2 and s["distritos_con_rio"] == 3


def test_si_no_llega_el_caudal_queda_la_lluvia():
    s = A.armar(_umbrales(), _lluvia(), {}, "sin dato: Open-Meteo Flood no respondió; aviso solo con lluvia", UMB_C, {})
    assert s["caudal"]["estado"].startswith("sin dato")
    for f in s["distritos"]:
        assert f["nivel"] == f["nivel_lluvia"]
        assert f["nivel_caudal"] is None
        assert f["motivo"] in (None, "lluvia")
    assert s["conteo"] == s["conteo_lluvia"]
    assert _por_distrito(s)["San Jacinto"]["nivel"] == "normal"


def test_pronostico_de_caudal_vacio():
    r = A.resumen_caudal(FECHAS, [None] * 7, UMB_C["Tumbes"])
    assert r["nivel"] is None and r["estado"].startswith("sin dato")


def test_main_no_se_cae_si_falla_flood(monkeypatch, tmp_path):
    """Simula Open-Meteo Flood caído: main() debe escribir el aviso con lluvia y anotar que faltó el caudal."""
    u = _umbrales()
    monkeypatch.setattr(A, "distritos", lambda: u[["departamento", "provincia", "distrito"]].assign(lat=-4.0, lon=-80.0))
    monkeypatch.setattr(A, "umbrales", lambda d: u)
    monkeypatch.setattr(A, "pronostico", lambda d: _lluvia())
    monkeypatch.setattr(A, "umbrales_caudal", lambda: UMB_C)
    monkeypatch.setattr(A, "celdas_rios", lambda: pd.DataFrame({"rio": ["Tumbes"], "lat": [-3.52], "lon": [-80.5]}))

    def caido(_):
        raise RuntimeError("Open-Meteo Flood no respondió")
    monkeypatch.setattr(A, "pronostico_caudal", caido)
    monkeypatch.setattr(A, "SALIDA", tmp_path / "aviso.json")
    monkeypatch.setattr(A, "DASH_DATA", tmp_path)
    A.main()
    s = json.loads((tmp_path / "aviso.json").read_text(encoding="utf-8"))
    assert "Open-Meteo Flood no respondió" in s["caudal"]["estado"]
    assert s["conteo"] == s["conteo_lluvia"]


def test_cuenca_igual_a_la_prueba_del_pasado():
    """La lista de distritos de cada río debe ser la misma que usa la prueba con 24 años de emergencias."""
    texto = (RAIZ / "herramientas" / "pruebas" / "prueba_aviso_pasado.py").read_text(encoding="utf-8")
    bloque = texto[texto.index("CUENCA = {"):texto.index("}", texto.index("CUENCA = {")) + 1]
    otra = eval(bloque.split("=", 1)[1])                          # noqa: S307  diccionario literal del propio repo
    assert otra == A.CUENCA


@pytest.mark.skipif(not (RAIZ / "data" / "modelo" / "caudal_rios.csv").exists(), reason="sin caudal_rios.csv")
def test_umbrales_de_caudal_desde_el_repositorio():
    u = A.umbrales_caudal()
    assert set(u) == {"Piura", "Chira", "Tumbes"}
    for r, x in u.items():
        assert 0 < x["p95"] < x["p99"], r
        assert x["periodo"] == "2001-2020" and x["dias"] >= 7000


@pytest.mark.skipif(not (RAIZ / "data" / "normales" / "rios_celdas.csv").exists(), reason="sin rios_celdas.csv")
def test_celdas_de_los_rios():
    c = A.celdas_rios()
    assert set(c["rio"]) == {"Piura", "Chira", "Tumbes"}
    assert c["lat"].between(-6.5, -3.0).all() and c["lon"].between(-81.5, -79.0).all()


def test_aviso_publicado_es_compatible():
    """El aviso que está en el tablero (con o sin caudal) tiene los campos que lee dashboard/index.html."""
    ruta = RAIZ / "dashboard" / "data" / "aviso_lluvia.json"
    if not ruta.exists():
        pytest.skip("sin aviso publicado")
    s = json.loads(ruta.read_text(encoding="utf-8"))
    assert {"conteo", "ventana_dias", "calculado", "distritos"} <= set(s)
    assert all(re.match(r"\d{4}-\d{2}-\d{2}", f["fecha_max"]) for f in s["distritos"])
