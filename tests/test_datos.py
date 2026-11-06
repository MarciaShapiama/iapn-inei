"""Pruebas de integración y consistencia geoespacial sobre los archivos publicados en dashboard/data/.

Se ejecutan contra los datos del repositorio: si una actualización produce cifras incoherentes, fallan.
"""
import json

import numpy as np
import pandas as pd
import pytest

from conftest import RAIZ

DD = RAIZ / "dashboard" / "data"
SIN = "Sin distrito asignado"


@pytest.fixture(scope="module")
def inund():
    return json.load(open(DD / "inundacion.json", encoding="utf-8"))


def test_escenarios_presentes(inund):
    assert {"rp10", "rp100"} <= set(inund["eventos"])


@pytest.mark.parametrize("n", ["colegios", "salud"])
def test_acumulados_monotonos(inund, n):
    for k, e in inund["eventos"].items():
        c = e[n]
        assert c["dentro"] <= c["acum_500m"] <= c["acum_1km"], (k, c)
        assert c["acum_500m"] == c["dentro"] + c["anillo_0_500m"]
        assert c["acum_1km"] == c["acum_500m"] + c["anillo_500m_1km"]
        assert len(e[n + "_lista"]) == c["acum_1km"], "la lista debe tener exactamente los locales hasta 1 km"


def test_suma_de_departamentos_igual_al_total(inund):
    for k, e in inund["eventos"].items():
        pd_ = e["por_departamento"]
        assert sum(v["edificaciones"] for v in pd_.values()) == e["edificaciones"], k
        assert abs(sum(v["personas"] for v in pd_.values()) - e["personas"]) <= len(pd_) + 80, k   # redondeo por distrito


def test_edificaciones_cerca_contiene_dentro(inund):
    for k, e in inund["eventos"].items():
        assert e["edificaciones"] <= e["edificaciones_100m"] <= e["edificaciones_500m"], k
        assert e["personas"] <= e["personas_500m"], k


def test_rp100_contiene_a_rp10(inund):
    a, b = inund["eventos"]["rp10"], inund["eventos"]["rp100"]
    assert a["km2"] <= b["km2"] and a["edificaciones"] <= b["edificaciones"]
    assert a["colegios"]["dentro"] <= b["colegios"]["dentro"]


def test_sin_rotulos_engañosos(inund):
    # las definiciones pueden aclarar que "expuesto no equivale a damnificado"; las cifras no pueden llamarse así
    txt = json.dumps(inund["eventos"], ensure_ascii=False)
    assert "damnificad" not in txt.lower()
    assert '"viviendas"' not in txt, "las huellas de Open Buildings se rotulan como edificaciones"


def test_csv_por_distrito_concilia(inund):
    x = pd.read_csv(DD / "descargas" / "exposicion_distritos.csv", dtype={"ubigeo": str})
    for k, e in inund["eventos"].items():
        f = x[x.escenario == k]
        assert int(f["edificaciones"].sum()) == e["edificaciones"], k
        assert int(f["colegios_dentro"].sum()) == e["colegios"]["dentro"], k
    dist = x[(x.escenario == "rp100") & (x.departamento != SIN)]
    assert dist["ubigeo"].notna().all() and dist["ubigeo"].str.fullmatch(r"(20|24)\d{4}").all()
    assert dist["ubigeo"].is_unique


def test_capas_geojson_validas_y_dentro_de_la_caja(inund):
    o, s, e_, n = inund["caja"]
    for k, e in inund["eventos"].items():
        g = json.load(open(DD / e["capa"], encoding="utf-8"))
        assert g["type"] == "FeatureCollection" and len(g["features"]) > 0, k
        xy = np.array([c for f in g["features"][:200] for c in f["geometry"]["coordinates"][0]])
        assert (xy[:, 0] >= o - 0.01).all() and (xy[:, 0] <= e_ + 0.01).all(), k
        assert (xy[:, 1] >= s - 0.01).all() and (xy[:, 1] <= n + 0.01).all(), k


def test_distritos_78_nombres_corregidos():
    g = json.load(open(DD / "distritos_tumbes_piura.geojson", encoding="utf-8"))
    nombres = {f["properties"]["distrito"] for f in g["features"]}
    assert len(g["features"]) == 78
    assert {"Miguel Checa", "Veintiséis de Octubre", "Canoas de Punta Sal", "Máncora", "Los Órganos"} <= nombres


def test_panel_dimensiones_separadas():
    p = json.load(open(DD / "panel_distritos.json", encoding="utf-8"))["distritos"]
    assert len(p) == 78
    for r in p:
        for k in ("p_peligro", "p_exposicion", "p_vulnerabilidad"):
            assert r[k] is None or 0 <= r[k] <= 100
        if r["riesgo_estimado"] is not None:
            assert abs(r["riesgo_estimado"] - np.mean([r["p_peligro"], r["p_exposicion"], r["p_vulnerabilidad"]])) < 0.11
        assert "no sustituye" in r["ficha"]


def test_metadatos_completos():
    m = json.load(open(DD / "metadatos.json", encoding="utf-8"))
    obligatorios = {"fuente", "definicion", "unidades", "cobertura", "periodo", "dato_mas_reciente", "frecuencia", "metodo",
                    "advertencias", "estado", "licencia", "version"}
    for c in m["capas"]:
        assert obligatorios <= set(c), c["id"]
        assert c["estado"] in ("vigente", "rezagado", "no disponible", "estimado"), c["id"]
    estados = {c["id"]: c["estado"] for c in m["capas"]}
    assert estados["peligro_rp100"] == "estimado" and estados["poblacion"] == "estimado"


def test_qa_radar_marca_solape_de_referencia(inund):
    m = {c["id"]: c for c in json.load(open(DD / "metadatos.json", encoding="utf-8"))["capas"]}
    for k in ("2017", "2023", "vivo"):
        if k in inund["eventos"]:
            qa = inund["eventos"][k]["qa"]
            if qa["referencia_solapa_evento"]:
                assert m[f"radar_{k}"]["estado"] == "no disponible"
                assert "CONTROL DE CALIDAD" in m[f"radar_{k}"]["advertencias"][0]


def test_poblacion_alineada_con_edificaciones():
    """El ráster WorldPop debe coincidir con la densidad de Open Buildings (fuente independiente): desplazamiento 0."""
    rasterio = pytest.importorskip("rasterio")
    from exposicion import CARPETA
    from reparar_poblacion import desplazamiento_optimo
    with rasterio.open(CARPETA / "poblacion_100m.tif") as s:
        pob, t = s.read(1).astype("float64"), s.transform
    dx, r = desplazamiento_optimo(pob, t, pd.read_parquet(CARPETA / "viviendas.parquet"), range(-6, 7, 2))
    assert dx == 0 and r > 0.7


def test_poblacion_distrital_plausible():
    """Población WorldPop por distrito frente a la estimación 2020: ningún distrito urbano grande fuera de 0,5x-2x."""
    p = pd.read_csv(DD / "descargas" / "panel_distritos.csv", dtype={"ubigeo": str})
    g = p[p.poblacion_2020_est > 50000]
    razon = g.poblacion_worldpop_distrito / g.poblacion_2020_est
    # Con el mapa del INEI (78 distritos) Piura ya no absorbe a Veintiséis de Octubre: se compara también.
    assert razon.between(0.5, 2.0).all(), g.assign(razon=razon)[["distrito", "razon"]]


def test_mapa_78_distritos_oficiales():
    """El mapa de distritos es el del INEI: 78 distritos (65 de Piura y 13 de Tumbes), con UBIGEO único."""
    import json
    from exposicion import CARPETA
    g = json.load(open(CARPETA / "distritos.geojson", encoding="utf-8"))
    ub = [f["properties"]["ubigeo"] for f in g["features"]]
    assert len(ub) == 78 and len(set(ub)) == 78
    assert sum(u.startswith("20") for u in ub) == 65 and sum(u.startswith("24") for u in ub) == 13
    assert {"200115", "240203"} <= set(ub)
    tabla = pd.read_csv(CARPETA / "ubigeo_peru_completo.csv", dtype=str)
    assert set(ub) <= set(tabla["inei"])
    for f in g["features"]:
        assert set(f["properties"]) == {"departamento", "provincia", "distrito", "ubigeo"}
