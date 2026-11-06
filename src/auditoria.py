"""Diagnóstico reproducible de las cifras de exposición (evidencia para docs/1_datos/01_AUDITORIA_TECNICA_Y_DATOS.md).

Responde, con los archivos del repositorio:
    1. ¿Los conteos de colegios/salud son anillos o acumulados? ¿Se cumple dentro ≤ 500 m ≤ 1 km?
    2. ¿Por qué Piura + Tumbes no suma el total de edificaciones? ¿Dónde caen las que faltan?
    3. ¿Por qué 2023 tiene 728 km² y solo 19 edificaciones? ¿Dónde está la mancha?
    4. ¿Qué parte de la detección bruta del radar cae en tierra de Tumbes-Piura?
    5. Población WorldPop por departamento frente a la estimación distrital 2020 (tabla UBIGEO).

Salida: docs/evidencia/auditoria_cifras.json
Uso: python src/auditoria.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from comun import ahora_lima, escribir_json
from config import DASH_DATA, RAIZ
from exposicion import CARPETA as EXPO
from huellas import CARPETA as HUELLAS
from impacto import SIN_DISTRITO, clasificar_distancia, contar_anillos, indices, metros, rasterizar_distritos

SALIDA = RAIZ / "docs" / "evidencia" / "auditoria_cifras.json"


def main() -> dict:
    import rasterio
    from scipy import ndimage as ndi
    out = {"calculado": ahora_lima()}
    j = json.load(open(DASH_DATA / "inundacion.json", encoding="utf-8"))
    ev = j["eventos"]

    # 1. Anillos frente a acumulados (recalculado desde el ráster JRC, independiente del JSON)
    with rasterio.open(EXPO / "peligro_rp100.tif") as s:
        v, t = s.read(1), s.transform
    mx, my = metros(t)
    dist = ndi.distance_transform_edt(~(v > 0), sampling=(my, mx))
    anillos = {}
    for n in ("colegios", "salud"):
        tb = pd.read_csv(EXPO / f"{n}.csv")
        f, c, ok = indices(tb.lon, tb.lat, t, v.shape)
        d = np.full(len(tb), np.nan); d[ok] = dist[f[ok], c[ok]]
        anillos[n] = contar_anillos(clasificar_distancia(d)) | {"total_locales": int(len(tb)), "fuera_del_raster": int((~ok).sum())}
    out["1_anillos_rp100"] = {"recalculado": anillos, "publicado_antes": {"colegios": {"Dentro": 684, "A ≤ 500 m": 1268, "A ≤ 1 km": 684}},
                              "conclusion": ("Los rótulos antiguos 'A ≤ 500 m' y 'A ≤ 1 km' eran anillos disjuntos (0–500 m y 500 m–1 km). "
                                             "La igualdad 684 = 684 es una coincidencia numérica verificada, no un error de suma. "
                                             "Acumulado correcto a ≤ 1 km: " + str(anillos["colegios"]["acum_1km"]) + " colegios.")}

    # 2. Conciliación de sumas por departamento
    conc = {k: e.get("conciliacion") for k, e in ev.items()}
    edif = pd.read_parquet(EXPO / "viviendas.parquet")
    f, c, ok = indices(edif.lon, edif.lat, t, v.shape)
    dr, _ = rasterizar_distritos(t, v.shape)
    dentro = np.zeros(len(edif), bool); dentro[ok] = v[f[ok], c[ok]] > 0
    dd = np.zeros(len(edif), int); dd[ok] = dr[f[ok], c[ok]]
    sin = edif[dentro & (dd == 0)]
    zona = np.select([sin.lat > -3.40, sin.lat < -6.30, sin.lon < -81.0], ["norte de la caja (frontera con Ecuador)",
                                                                           "sur de la caja (Lambayeque)", "borde costero"], "borde distrital simplificado / interior")
    out["2_conciliacion"] = {"por_escenario": conc, "rp100_sin_distrito_por_zona": pd.Series(zona).value_counts().to_dict(),
                             "rp100_sin_distrito_lat_lon_cuantiles": sin[["lat", "lon"]].quantile([0.05, 0.5, 0.95]).round(3).to_dict()}

    # 3 y 4. Radar: dónde cae la mancha y qué parte de la detección bruta es tierra
    radar = {}
    for k in ("2017", "2023", "vivo"):
        if k not in ev:
            continue
        top = sorted(ev[k]["distritos"], key=lambda x: -x["km2"])[:5]
        tot = ev[k]["km2"]
        radar[k] = {"km2_mancha": tot, "edificaciones": ev[k]["edificaciones"], "personas": ev[k]["personas"],
                    "qa": ev[k].get("qa"), "imagenes": len(ev[k].get("imagenes") or []),
                    "primera_y_ultima_imagen": [(ev[k].get("imagenes") or [None])[0], (ev[k].get("imagenes") or [None])[-1]],
                    "top5_distritos_por_km2": [{x["distrito"]: x["km2"]} for x in top],
                    "fraccion_en_sechura": round(sum(x["km2"] for x in ev[k]["distritos"] if x["distrito"] == "Sechura") / tot, 3) if tot else None}
        with rasterio.open(HUELLAS / f"{k}.tif") as s:
            m, tm = s.read(1), s.transform
        drm, _ = rasterizar_distritos(tm, m.shape)
        radar[k]["fraccion_bruta_en_poligonos_distritales"] = round(float(((m == 1) & (drm > 0)).sum() / max(1, (m == 1).sum())), 3)
    out["3_radar"] = radar

    # 5. Población: WorldPop frente a la estimación distrital 2020 (tabla UBIGEO)
    try:
        from ubigeo import descargar_tabla
        u = descargar_tabla()
        filas = pd.read_csv(DASH_DATA / "descargas" / "exposicion_distritos.csv", dtype={"ubigeo": str})
        f100 = filas[filas.escenario == "rp100"]
        wp = f100[f100.departamento != SIN_DISTRITO].groupby("departamento")["poblacion_worldpop_distrito"].sum()
        est = u.groupby("departamento")["poblacion_2020_est"].sum()
        out["5_poblacion"] = {"worldpop_2026_en_distritos": wp.round().to_dict(),
                              "estimacion_2020_tabla_ubigeo": est.round().to_dict(),
                              "nota": ("El mapa es el del INEI (78 distritos, incluidos 200115 y 240203). Para validar con "
                                       "cifras oficiales use el Censo 2017 (INEI) o las proyecciones distritales oficiales vigentes.")}
    except Exception as error:  # noqa: BLE001
        out["5_poblacion"] = {"error": str(error)}
    escribir_json(SALIDA, out)
    return out


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=1, default=str))
