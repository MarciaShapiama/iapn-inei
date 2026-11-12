"""Pruebas sin red de la prueba de falsas alarmas (herramientas/pruebas/prueba_aviso_temporada.py).

Usan los niveles ya guardados en docs/evidencia/aviso_temporada_niveles.txt; no llaman a Open-Meteo.
"""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "herramientas" / "pruebas"))

NIVELES = RAIZ / "docs" / "evidencia" / "aviso_temporada_niveles.txt"
SALIDA = RAIZ / "docs" / "evidencia" / "prueba_aviso_temporada.json"

pytestmark = pytest.mark.skipif(not NIVELES.exists(), reason="sin aviso_temporada_niveles.txt")


@pytest.fixture(scope="module")
def P():
    import prueba_aviso_temporada as m
    return m


@pytest.fixture(scope="module")
def niveles(P):
    return P.leer_niveles_compactos(NIVELES)


def test_niveles_cubren_las_dos_temporadas(niveles):
    assert niveles["k"].nunique() == 76
    assert niveles.groupby("temporada").size().to_dict() == {"2025_ene_abr": 76 * 120, "2026_oct_nov": 76 * 21}
    for c in ("lluvia_1d", "lluvia_2d", "lluvia_3d"):
        assert set(niveles[c]) <= {"n", "f", "e"}


def test_san_jacinto_1_de_noviembre(niveles):
    """Mismo caso del documento 3.1: 105,1 / 84,9 / 32,4 mm con p95 26,9 y p99 56,6."""
    f = niveles[(niveles.distrito == "San Jacinto") & (niveles.fecha == "2026-11-01")].iloc[0]
    assert (f.lluvia_1d, f.lluvia_2d, f.lluvia_3d) == ("e", "e", "f")


def test_resultado_publicado_es_coherente(P, niveles, tmp_path, monkeypatch):
    """Recalcula y compara con el JSON publicado; revisa que los conteos cuadren."""
    if not SALIDA.exists():
        pytest.skip("sin prueba_aviso_temporada.json")
    monkeypatch.setattr(P, "EVID", tmp_path)
    monkeypatch.setattr(P, "SALIDA", tmp_path / "s.json")
    monkeypatch.setattr(P, "SALIDA_DIST", tmp_path / "d.csv")
    nuevo = json.loads(json.dumps(P.evaluar(niveles, "x"), ensure_ascii=False, default=str))
    viejo = json.loads(SALIDA.read_text(encoding="utf-8"))
    assert nuevo["temporada_2025"] == viejo["temporada_2025"]
    # 2026: se compara el catálogo verificado, que es fijo. Las «noticias ubicadas» cambian con cada actualización
    # diaria de noticias, así que ese bloque no se exige idéntico al publicado.
    for nombre, var in viejo["temporada_2026"]["variantes"].items():
        assert nuevo["temporada_2026"]["variantes"][nombre]["eventos verificados"] == var["eventos verificados"], nombre
    for x in nuevo["temporada_2025"]["variantes"].values():
        for g in x.values():
            assert g["avisos_con_dano"] <= min(g["avisos"], g["danos"])
            assert g["falsas_alarmas"] == g["avisos"] - g["avisos_con_dano"]
    v = nuevo["temporada_2025"]["variantes"]
    # sumar el caudal nunca quita avisos
    assert v["lluvia o caudal conocido"]["todos los distritos"]["avisos"] >= \
        v["lluvia (1, 2 o 3 días antes)"]["todos los distritos"]["avisos"]
