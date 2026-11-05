"""Consistencia de los totales de viviendas del INEI por distrito (dashboard/data/vivienda_inei_distritos.json).

Además verifican que la salida pública sea SOLO por distrito: ningún identificador ni cifra por manzana.
"""
import json

import pytest

from conftest import RAIZ

RUTA = RAIZ / "dashboard" / "data" / "vivienda_inei_distritos.json"
CAPAS = ("rp10", "rp100", "2017", "2023", "vivo")


@pytest.fixture(scope="module")
def viv():
    if not RUTA.exists():
        pytest.skip("todavía no se generó vivienda_inei_distritos.json")
    return json.load(open(RUTA, encoding="utf-8"))


def test_solo_nivel_distrito(viv):
    texto = RUTA.read_text(encoding="utf-8").lower()
    assert "idmanzana" not in texto and "manzana_id" not in texto and "zona_id" not in texto
    for d in viv["distritos"]:
        assert len(d["ubigeo"]) == 6 and d["ubigeo"][:2] in ("20", "24"), d["ubigeo"]


def test_ubigeos_unicos(viv):
    u = [d["ubigeo"] for d in viv["distritos"]]
    assert len(u) == len(set(u)) == 78


def test_totales_suman(viv):
    for dep, t in viv["totales"].items():
        ds = [d for d in viv["distritos"] if d["departamento"] == dep]
        for clave, valor in t.items():
            assert abs(sum(d[clave] for d in ds) - valor) <= len(ds), (dep, clave)


def test_partes_menores_que_el_todo(viv):
    for d in viv["distritos"]:
        n = d["viviendas_ocupadas"]
        assert n > 0
        for c in ("paredes_precarias", "techo_precario", "piso_tierra", "precarias"):
            assert 0 <= d[f"viviendas_{c}"] <= n, (d["ubigeo"], c)
            assert 0 <= d[f"pct_{c}"] <= 100
        for k in CAPAS:
            if f"viviendas_{k}" in d:
                assert 0 <= d[f"viviendas_precarias_{k}"] <= d[f"viviendas_{k}"] <= n, (d["ubigeo"], k)


def test_escenario_mayor_contiene_al_menor(viv):
    for d in viv["distritos"]:
        if "viviendas_rp10" in d and "viviendas_rp100" in d:
            # la mancha de 1 en 100 años contiene a la de 1 en 10 (tolerancia por manzanas en el borde)
            assert d["viviendas_rp10"] <= d["viviendas_rp100"] + 50, d["ubigeo"]
