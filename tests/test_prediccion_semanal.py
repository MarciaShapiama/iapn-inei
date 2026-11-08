"""Pruebas del modelo por plazo (src/prediccion_semanal.py): sin fuga de información y salida coherente."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
P = pytest.importorskip("prediccion_semanal")


@pytest.fixture(scope="module")
def panel():
    return P.panel()


@pytest.mark.parametrize("h", [1, 2, 3, 4])
def test_objetivo_es_la_semana_t_mas_h(panel, h):
    e = P.ejemplos(panel, h)
    assert ((e.semana_obj - e.semana) == pd.Timedelta(weeks=h)).all()
    # el objetivo de la fila (clave, t) es la emergencia de (clave, t+h) en el panel
    m = e.merge(panel[["clave", "semana", "E"]].rename(columns={"semana": "semana_obj", "E": "E_obj"}),
                on=["clave", "semana_obj"], how="left")
    ok = m.y.notna()
    assert (m.loc[ok, "y"] == m.loc[ok, "E_obj"]).all()


def test_variables_son_de_la_semana_t(panel):
    """Cambiar el futuro (semanas > t) no cambia ninguna variable de la fila t."""
    e1 = P.ejemplos(panel, 1)
    p2 = panel.copy()
    corte = pd.Timestamp("2017-03-06")
    futuro = p2.semana > corte
    for c in ["lluvia_7d", "lluvia_30d", "log_lluvia_30d", "log_lluvia_7d", "caudal_razon", "log_caudal_razon", "nino12",
              "lluvia_sobre_p95", "lluvia_sobre_p99", "caudal_sobre_p95", "emergencia_t", "E"]:
        p2.loc[futuro, c] = -999
    e2 = P.ejemplos(p2, 1)
    fila1 = e1[e1.semana == corte].set_index("clave")
    fila2 = e2[e2.semana == corte].set_index("clave")
    for c in P.CON_AVISO:
        if c in ("hist_frec",):        # se calcula después, solo con el entrenamiento
            continue
        assert np.allclose(fila1[c].astype(float).fillna(0), fila2[c].astype(float).fillna(0)), c


def test_historia_solo_con_entrenamiento(panel):
    e = P.ejemplos(panel, 1)
    e = e[e.y.notna()]
    tr, te = e[e.semana_obj < "2017-01-01"], e[e.anio_obj == 2017]
    a, _ = P.con_historia(tr, te)
    b, _ = P.con_historia(tr, te.assign(y=1 - te.y))       # cambiar el año de prueba no cambia la historia
    assert np.allclose(a.hist_frec, b.hist_frec)


def test_salida_json():
    ruta = RAIZ / "dashboard" / "data" / "prediccion_semanal.json"
    if not ruta.exists():
        pytest.skip("sin prediccion_semanal.json")
    j = json.loads(ruta.read_text(encoding="utf-8"))
    assert len(j["distritos"]) == 78
    for d in j["distritos"]:
        for h in (1, 2, 3, 4):
            assert 0 <= d[f"prob_h{h}"] <= 1
        assert d["viviendas_si_ocurre"] >= 0
    assert [c["h"] for c in j["calidad_por_plazo"]] == [1, 2, 3, 4]


def test_fases_y_margen_publicados():
    import json
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[1] / "dashboard" / "data" / "prediccion_semanal.json"
    if not ruta.exists():
        return
    p = json.loads(ruta.read_text(encoding="utf-8"))
    f = p["fases"]["umbrales"]
    assert 0 < f["atencion"] < f["alerta"] < 1
    for c in p["calidad_por_plazo"]:
        ic = c.get("ventaja_sobre_climatologia_ic95")
        if ic:
            assert ic[0] <= ic[1]
