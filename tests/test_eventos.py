"""Inundaciones reportadas (dashboard/data/eventos_reportados.json, src/noticias.py).

Lo central: TODO evento verificado del catálogo tiene que estar en el tablero, con su fuente y su veredicto del radar,
aunque el radar no lo vea (por ejemplo, el desborde del río Serrán en Canchaque, a 1 188 m de altura).
"""
import json
import sys

import pandas as pd
import pytest

from conftest import RAIZ

sys.path.insert(0, str(RAIZ / "src"))
RUTA = RAIZ / "dashboard" / "data" / "eventos_reportados.json"
CATALOGO = RAIZ / "data" / "eventos" / "catalogo_verificado.csv"
CAJA = (-81.40, -6.40, -79.15, -3.35)
VEREDICTOS = {"detectado", "no detectado", "fuera de alcance", "sin pasada", "sin radar"}


@pytest.fixture(scope="module")
def evr():
    if not RUTA.exists():
        pytest.skip("todavía no se generó eventos_reportados.json")
    return json.load(open(RUTA, encoding="utf-8"))


def test_catalogo_completo_en_el_tablero(evr):
    ids = {e["id"] for e in evr["eventos"]}
    faltan = set(pd.read_csv(CATALOGO, dtype=str)["id"]) - ids
    assert not faltan, f"eventos verificados que no aparecen en el tablero: {faltan}"


def test_serran_visible_aunque_el_radar_no_lo_vea(evr):
    e = next(e for e in evr["eventos"] if e["id"] == "2026-serran")
    assert e["departamento"] == "Piura" and e["provincia"] == "Huancabamba"
    assert e["radar"]["veredicto"] == "fuera de alcance"
    assert "250 m" in e["radar"]["explicacion"]


def test_cada_evento_es_trazable_y_esta_en_la_zona(evr):
    for e in evr["eventos"]:
        assert e["articulos"] and all(a["url"].startswith("http") for a in e["articulos"]), e["id"]
        assert e["departamento"] in ("Piura", "Tumbes"), e["id"]
        assert CAJA[0] <= e["lon"] <= CAJA[2] and CAJA[1] <= e["lat"] <= CAJA[3], e["id"]
        assert e["radar"]["veredicto"] in VEREDICTOS and e["radar"]["explicacion"], e["id"]
        assert e["fecha"] <= e["fecha_fin"]


def test_resumen_cuadra(evr):
    assert sum(evr["resumen_radar"].values()) == evr["n"] == len(evr["eventos"])


@pytest.mark.parametrize("titulo,fecha,esperado", [
    ("Lluvias inundan Máncora y Chulucanas", "2026-11-03", True),
    ("Desborde del río Zarumilla afecta a Puerto Perú y Tomás Arizola", "2026-11-02", True),
    ("Senamhi advierte riesgo de inundación en Piura", "2026-11-03", False),
    ("Ejecutan acciones para reducir riesgos de inundación ante lluvias en Piura", "2026-11-01", False),
    ("Atlético Grau sorprende con uniforme manchado por las inundaciones de 2017", "2026-11-04", False),
    ("Videos de inundaciones en Piura son de febrero, no de octubre - AFP Factual", "2026-10-22", False),
])
def test_filtro_de_hechos(titulo, fecha, esperado):
    from noticias import es_hecho
    assert es_hecho(titulo, "Medio", fecha) is esperado


def test_ubicacion_respeta_el_departamento():
    from noticias import LUGARES, Nomenclator
    nom = Nomenclator(pd.read_csv(LUGARES, dtype={"ubigeo": str}))
    lugares = [l["nombre"] for l, _ in nom.ubicar("Lluvias intensas activaron la quebrada Corralitos en Tumbes")]
    assert "LA QUEBRADA" not in lugares                         # homónimo de Piura
    l, _ = nom.ubicar("Desborde del río Tumbes inunda Vaquería, en San Jacinto (Tumbes)")[0]
    assert l["departamento"] == "TUMBES"
    assert [l["nombre"] for l, _ in nom.ubicar("Piura: Lluvias inundan Máncora y Chulucanas")] == ["CHULUCANAS", "MANCORA"]
