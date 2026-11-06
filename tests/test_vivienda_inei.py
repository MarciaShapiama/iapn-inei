"""Viviendas del Censo 2025 en la zona inundable y en el agua del radar (dashboard/data/viviendas_censo.json).

Verifican que la salida pública sea SOLO por distrito, que respete el mínimo de 10 viviendas por celda y que las
cifras sean coherentes entre sí.
"""
import json

import pytest

from conftest import RAIZ

RUTA = RAIZ / "dashboard" / "data" / "viviendas_censo.json"
CSV = RAIZ / "dashboard" / "data" / "descargas" / "viviendas_censo_distritos.csv"


@pytest.fixture(scope="module")
def viv():
    if not RUTA.exists():
        pytest.skip("todavía no se generó viviendas_censo.json")
    return json.load(open(RUTA, encoding="utf-8"))


def test_solo_nivel_distrito(viv):
    for ruta in (RUTA, CSV):
        if ruta.exists():
            texto = ruta.read_text(encoding="utf-8").lower()
            assert "idmanzana" not in texto and "manzana_id" not in texto and "zona_id" not in texto


def _distritos(viv):
    for e in viv["escenarios"].values():
        yield from e["distritos"]
    for e in viv.get("radar", {}).values():
        yield from e["distritos"]


def test_minimo_10_viviendas(viv):
    for d in _distritos(viv):
        assert d["viviendas"] >= 10, d
        assert len(d["ubigeo"]) == 6 and d["ubigeo"][:2] in ("20", "24")


def test_totales_coherentes(viv):
    t = viv["total_tumbes_piura"]
    assert sum(t["por_departamento"].values()) == t["viviendas_ocupadas"]
    for k, e in viv["escenarios"].items():
        assert abs(sum(e["por_departamento"].values()) - e["viviendas"]) <= 2, k
        assert sum(d["viviendas"] for d in e["distritos"]) <= e["viviendas"], k   # los distritos < 10 no se detallan
        for c in ("paredes_tierra", "paredes_precarias", "techo_precario", "piso_tierra", "viviendas_mas_1_5m"):
            assert 0 <= e[c] <= e["viviendas"], (k, c)
    assert viv["escenarios"]["rp10"]["viviendas"] <= viv["escenarios"]["rp100"]["viviendas"]
    for k, r in viv.get("radar", {}).items():
        assert 0 <= r["precarias"] <= r["viviendas"] <= t["viviendas_ocupadas"], k


def test_partes_menores_que_el_todo(viv):
    for d in _distritos(viv):
        for c in ("paredes_tierra", "paredes_precarias", "piso_tierra", "precarias"):
            if c in d:
                assert 0 <= d[c] <= d["viviendas"], (d["ubigeo"], c)


def test_personas_sin_celdas_pequenas(viv):
    """Ninguna cifra de personas (total, sexo o edad) menor a 10 dentro de un distrito publicado."""
    for d in _distritos(viv):
        for c in ("personas", "hombres", "mujeres", "edad_0_4", "edad_5_14", "edad_15_64", "edad_65_mas"):
            if d.get(c) is not None:
                assert d[c] >= 10, (d["ubigeo"], c)


def test_personas_coherentes(viv):
    for k, e in viv["escenarios"].items():
        if e.get("personas") is None:
            continue
        assert e["hombres"] + e["mujeres"] == e["personas"], k
        assert abs(e["edad_0_4"] + e["edad_5_14"] + e["edad_15_64"] + e["edad_65_mas"] - e["personas"]) <= 2, k
        assert e["en_centros_poblados"]["viviendas"] <= e["viviendas"], k
