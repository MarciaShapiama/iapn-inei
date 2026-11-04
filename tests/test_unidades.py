"""Pruebas unitarias de las funciones puras (no usan red ni archivos grandes)."""
from datetime import date

import numpy as np
import pytest

from comun import descargar, estado_por_fecha
from huellas import eventos, otsu, referencia_seca
from impacto import clasificar_distancia, contar_anillos


# --- anillos y acumulados -------------------------------------------------------------------------
def test_anillos_disjuntos_y_acumulados_monotonos():
    d = np.array([0, 0, 10, 500, 501, 1000, 1001, np.nan])
    c = clasificar_distancia(d)
    assert list(c) == ["dentro", "dentro", "anillo_0_500m", "anillo_0_500m", "anillo_500m_1km", "anillo_500m_1km", "fuera", "fuera"]
    n = contar_anillos(c)
    assert n == {"dentro": 2, "anillo_0_500m": 2, "anillo_500m_1km": 2, "acum_500m": 4, "acum_1km": 6}
    assert n["dentro"] <= n["acum_500m"] <= n["acum_1km"]


# --- referencia seca del radar ---------------------------------------------------------------------
@pytest.mark.parametrize("hoy", [date(2026, 11, 4), date(2026, 8, 15), date(2027, 2, 20), date(2026, 12, 31), date(2026, 9, 10)])
def test_referencia_no_se_solapa_con_el_evento(hoy):
    for clave, ev in eventos(hoy).items():
        assert ev["ref"][1] < ev["evento"][0], (clave, ev)
        assert ev["ref"][0] < ev["ref"][1]


def test_referencia_noviembre_usa_agosto_a_dia_previo():
    assert referencia_seca(date(2026, 10, 11)) == ("2026-08-01", "2026-10-10")
    assert referencia_seca(date(2027, 2, 1)) == ("2026-08-01", "2026-11-30")
    assert referencia_seca(date(2026, 8, 10)) == ("2025-08-01", "2025-11-30")   # muy pocos días: año anterior


# --- umbral de Otsu ---------------------------------------------------------------------------------
def test_otsu_bimodal_encuentra_valle():
    rng = np.random.default_rng(0)
    v = np.concatenate([rng.normal(-22, 1.5, 20000), rng.normal(-9, 2, 60000)])
    u = otsu(v)
    assert u is not None and -18 < u < -13


def test_otsu_devuelve_none_sin_datos_o_fuera_de_limites():
    assert otsu(np.array([np.nan] * 10)) is None
    rng = np.random.default_rng(1)
    assert otsu(np.concatenate([rng.normal(-5, 1, 5000), rng.normal(0, 1, 5000)])) is None   # valle fuera de [-24,-14]


# --- estado de vigencia ----------------------------------------------------------------------------
def test_estado_por_fecha():
    hoy = date(2026, 11, 4)
    assert estado_por_fecha("2026-11-02", 3, hoy) == "vigente"
    assert estado_por_fecha("2026-10-20", 3, hoy) == "rezagado"
    assert estado_por_fecha("2026-08", 75, hoy) == "rezagado"         # mes sin día: se toma el 1.º
    assert estado_por_fecha(None, 3, hoy) == "no disponible"
    assert estado_por_fecha("2024-01-01", None, hoy) == "vigente"     # línea base estática


# --- descargas con reintentos ------------------------------------------------------------------------
class _Resp:
    def __init__(self, code):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Sesion:
    def __init__(self, codigos):
        self.codigos, self.llamadas = list(codigos), 0

    def request(self, *a, **k):
        self.llamadas += 1
        return _Resp(self.codigos.pop(0))


def test_descargar_reintenta_y_luego_funciona():
    esperas = []
    s = _Sesion([503, 502, 200])
    r = descargar("http://x", sesion=s, intentos=4, espera=1, dormir=esperas.append)
    assert r.status_code == 200 and s.llamadas == 3 and esperas == [1, 2]


def test_descargar_falla_tras_limite():
    s = _Sesion([500, 500, 500])
    with pytest.raises(RuntimeError, match="3 intentos"):
        descargar("http://x", sesion=s, intentos=3, espera=0, dormir=lambda _: None)
    assert s.llamadas == 3
