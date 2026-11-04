"""Exposición potencial a inundaciones en Tumbes y Piura: población, edificaciones, colegios y salud.

Dos tipos de capa:
    radar    agua nueva que el satélite Sentinel-1 detectó en 2017, 2023 y los últimos 24 días (data/huellas/).
             Es un MÍNIMO y una detección automática: el radar no ve el agua entre edificios ni bajo árboles, y
             confunde el agua de inundación con riego por inundación (arrozales), humedales y arena muy lisa.
    peligro  zona que se inunda con una crecida de ríos de 1 en 10 y 1 en 100 años, con su profundidad
             (JRC CEMS-GloFAS v2, 90 m; data/exposicion/peligro_rp*.tif). Es un ESCENARIO, no un pronóstico.

Para cada capa (definiciones usadas en el tablero y en los CSV):
    poblacion_expuesta       WorldPop 2026 (100 m, modelada) × fracción de cada celda dentro de la mancha.
                             Es población POTENCIALMENTE EXPUESTA, no personas afectadas ni damnificadas.
    edificaciones            huellas de Google Open Buildings v3 (confianza ≥ 0,75) cuyo centro cae dentro de la
                             mancha. Son EDIFICACIONES (cualquier uso), no viviendas censales.
    colegios / salud         por distancia del local al borde de la mancha:
                               dentro            distancia = 0
                               anillo_0_500m     0 < d ≤ 500 m     (anillo, disjunto de "dentro")
                               anillo_500m_1km   500 < d ≤ 1000 m  (anillo, disjunto de los anteriores)
                               acum_500m         dentro + anillo_0_500m           (acumulado: d ≤ 500 m)
                               acum_1km          dentro + ambos anillos           (acumulado: d ≤ 1 km)
                             Siempre se cumple dentro ≤ acum_500m ≤ acum_1km.
    por distrito (UBIGEO)    km², población y edificaciones. Lo que cae fuera de los polígonos distritales
                             (mar, Ecuador, Lambayeque o bordes simplificados) va en "Sin distrito asignado",
                             para que la suma de distritos sea igual al total.
Se cruzan la población y las edificaciones de HOY con cada mancha: "¿cuánto quedaría expuesto hoy?".

Salidas: dashboard/data/inundacion.json, dashboard/data/capa_{clave}.geojson,
         dashboard/data/descargas/exposicion_distritos.csv (una fila por distrito y escenario)

Uso: python src/impacto.py
"""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd

from comun import ahora_lima, escribir_json, registrar_version
from config import DASH_DATA, DATA
from exposicion import CAJA, CARPETA as EXPO
from huellas import CARPETA as HUELLAS, eventos

LAT0 = (CAJA[1] + CAJA[3]) / 2
DESCARGAS = DASH_DATA / "descargas"
SIN_DISTRITO = "Sin distrito asignado"
VALIDACION = {"2017": {"Piura": 74348, "Tumbes": 11395,
                       "fuente": "INDECI, citado en OCHA, Perú: Temporada de lluvias, informe n.º 10 (10 may 2017)",
                       "url": "https://reliefweb.int/report/peru/peru-rainy-season-situation-report-no-10-10-may-2017",
                       "nota": ("INDECI cuenta VIVIENDAS afectadas por lluvias, inundaciones y huaicos; el tablero cuenta "
                                "EDIFICACIONES de Google Open Buildings. Las dos cifras miden cosas distintas: la "
                                "comparación es solo de orden de magnitud.")}}
PELIGROS = {"rp10": ("Zona inundable: crecida de 1 en 10 años", 10), "rp100": ("Zona inundable: crecida de 1 en 100 años", 100)}
ANILLOS = ("dentro", "anillo_0_500m", "anillo_500m_1km")
ETIQUETA_ESTADO = {"dentro": "Dentro de la mancha", "anillo_0_500m": "0–500 m del borde",
                   "anillo_500m_1km": "500 m–1 km del borde", "fuera": "Fuera"}


def metros(t) -> tuple[float, float]:
    return abs(t.a) * 111_320 * np.cos(np.radians(LAT0)), abs(t.e) * 110_600


def indices(lon, lat, t, forma):
    col = np.floor((np.asarray(lon) - t.c) / t.a).astype(int)
    fil = np.floor((np.asarray(lat) - t.f) / t.e).astype(int)
    ok = (fil >= 0) & (fil < forma[0]) & (col >= 0) & (col < forma[1])
    return fil, col, ok


def clasificar_distancia(d: np.ndarray) -> np.ndarray:
    """Anillos disjuntos a partir de la distancia (m) al borde. NaN (fuera del ráster) = 'fuera'."""
    d = np.asarray(d, dtype="float64")
    return np.select([d <= 0, d <= 500, d <= 1000], list(ANILLOS), "fuera")


def contar_anillos(clase: np.ndarray) -> dict:
    n = {a: int((clase == a).sum()) for a in ANILLOS}
    n["acum_500m"] = n["dentro"] + n["anillo_0_500m"]
    n["acum_1km"] = n["acum_500m"] + n["anillo_500m_1km"]
    return n


def rasterizar_distritos(t, forma):
    from rasterio import features
    from shapely.geometry import shape
    g = json.load(open(EXPO / "distritos.geojson", encoding="utf-8"))
    nombres = [(f["properties"]["departamento"], f["properties"]["provincia"], f["properties"]["distrito"]) for f in g["features"]]
    r = features.rasterize(((shape(f["geometry"]), k + 1) for k, f in enumerate(g["features"])),
                           out_shape=forma, transform=t, fill=0, dtype="int32")
    return r, nombres


def tabla_ubigeo() -> dict:
    """{id_raster: fila con ubigeo y variables de contexto}; vacío si no hay tabla (no se inventa)."""
    try:
        from ubigeo import empatar
        e = empatar()
        return {int(r["id_raster"]): r for r in e.to_dict(orient="records")}
    except Exception as error:  # noqa: BLE001
        print(f"  UBIGEO no disponible: {error}")
        return {}


def cargar_capas():
    """Devuelve {clave: (nombre, tipo, profundidad_o_mascara, transform, meta)}."""
    import rasterio
    from scipy import ndimage as ndi
    capas = {}
    for clave, ev in eventos().items():
        ruta = HUELLAS / f"{clave}.tif"
        if not ruta.exists():
            continue
        with rasterio.open(ruta) as src:
            m, t = src.read(1), src.transform
        meta = json.load(open(HUELLAS / f"{clave}.json", encoding="utf-8"))
        dr, _ = rasterizar_distritos(t, m.shape)
        tierra = ndi.binary_erosion(dr > 0, iterations=4)       # solo tierra de Tumbes y Piura, sin la orilla del mar
        inund = (m == 1) & tierra
        lab, n = ndi.label(inund)                                # quita manchas sueltas (< 0,03 km²)
        if n:
            tam = np.bincount(lab.ravel()); ok = tam >= 10; ok[0] = False; inund = ok[lab]
        mx, my = metros(t)
        px_km2 = mx * my / 1e6
        km2_bruto = float((m == 1).sum() * px_km2)
        qa = {"km2_deteccion_bruta_caja": round(km2_bruto, 1),
              "km2_agua_permanente_tierra": round(float(((m == 2) & tierra).sum() * px_km2), 1),
              "km2_tras_mascara_tierra_y_limpieza": round(float(inund.sum() * px_km2), 1),
              "fraccion_retenida": round(float(inund.sum() * px_km2 / km2_bruto), 3) if km2_bruto else None,
              "umbral_db": meta.get("umbral_db", -17.0), "caida_db": meta.get("caida_db", 3.0),
              "compuesto_evento": meta.get("compuesto_evento", "minimo"),
              "referencia": meta.get("referencia"),
              "referencia_solapa_evento": bool(meta.get("referencia") and meta.get("periodo")
                                                and meta["referencia"][1] >= meta["periodo"][0])}
        capas[clave] = (ev["nombre"], "radar", inund.astype("float32"), t,
                        {"periodo": meta["periodo"], "imagenes": meta["imagenes_evento"], "qa": qa,
                         "calculado": meta.get("calculado")})
    for clave, (nombre, rp) in PELIGROS.items():
        ruta = EXPO / f"peligro_rp{rp}.tif"
        if ruta.exists():
            with rasterio.open(ruta) as src:
                v, tv = src.read(1).astype("float32"), src.transform
            # Solo Tumbes y Piura: el mapa de JRC también cubre Ecuador y Lambayeque dentro de la caja de estudio.
            dr_v, _ = rasterizar_distritos(tv, v.shape)
            v[dr_v == 0] = 0
            capas[clave] = (nombre, "peligro", v, tv,
                            {"periodo": None, "imagenes": [], "periodo_retorno": rp, "qa": {}})
    return capas


def personas(mascara, t, distritos, extra=None):
    import rasterio
    from rasterio.warp import Resampling, reproject
    with rasterio.open(EXPO / "poblacion_100m.tif") as src:
        pob, tp = src.read(1).astype("float64"), src.transform
    def frac(m):
        dst = np.zeros(pob.shape, dtype="float32")
        reproject(m.astype("float32"), dst, src_transform=t, src_crs="EPSG:4326", dst_transform=tp, dst_crs="EPSG:4326",
                  resampling=Resampling.average)
        return dst
    f = frac(mascara)
    dr = np.zeros(pob.shape, dtype="float32")
    reproject(distritos.astype("float32"), dr, src_transform=t, src_crs="EPSG:4326", dst_transform=tp, dst_crs="EPSG:4326",
              resampling=Resampling.nearest)
    por_d = pd.Series((pob * f).ravel()).groupby(dr.astype(int).ravel()).sum()
    por_d_total = pd.Series(pob.ravel()).groupby(dr.astype(int).ravel()).sum()   # población WorldPop por distrito
    return float((pob * f).sum()), (float((pob * frac(extra)).sum()) if extra is not None else None), por_d, por_d_total


def poligonos(clave: str, tipo: str, valor: np.ndarray, t) -> dict:
    """Capa del mapa en polígonos. Peligro: 4 clases de profundidad."""
    from affine import Affine
    from rasterio import features
    from shapely.geometry import mapping, shape
    k = 2
    h, w = (valor.shape[0] // k) * k, (valor.shape[1] // k) * k
    v = valor[:h, :w].reshape(h // k, k, w // k, k).max(axis=(1, 3))
    tk = t * Affine.scale(k)
    if tipo == "radar":
        clase = (v > 0).astype("uint8")
    else:
        clase = np.digitize(v, [0.0001, 0.5, 1.5, 3.0]).astype("uint8")       # 1: < 0,5 m … 4: > 3 m
    feats = []
    for geom, c in features.shapes(clase, mask=clase > 0, transform=tk):
        g = shape(geom).simplify(abs(tk.a) * 0.6, preserve_topology=True)
        if g.is_empty or g.area < (abs(tk.a) ** 2) * 1.5:
            continue
        m = json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 5))
        feats.append({"type": "Feature", "properties": {"c": int(c)}, "geometry": m})
    ruta = DASH_DATA / f"capa_{clave}.geojson"
    json.dump({"type": "FeatureCollection", "features": feats}, open(ruta, "w"), separators=(",", ":"))
    print(f"  capa_{clave}.geojson: {len(feats)} polígonos, {ruta.stat().st_size // 1024} KB")
    return {"capa": f"capa_{clave}.geojson"}


def main() -> None:
    from scipy import ndimage as ndi
    DASH_DATA.mkdir(parents=True, exist_ok=True)
    DESCARGAS.mkdir(parents=True, exist_ok=True)
    edif = pd.read_parquet(EXPO / "viviendas.parquet")      # nombre de archivo heredado: son edificaciones
    tablas = {n: pd.read_csv(EXPO / f"{n}.csv") for n in ("salud", "colegios") if (EXPO / f"{n}.csv").exists()}
    ubi = tabla_ubigeo()
    salida = {"caja": CAJA, "eventos": {}, "validacion": VALIDACION, "calculado": ahora_lima(),
              "definiciones": {
                  "poblacion_expuesta": "Población modelada (WorldPop 2026) dentro de la mancha. No equivale a afectados ni damnificados.",
                  "edificaciones": "Huellas de Google Open Buildings v3 (confianza ≥ 0,75) con su centro dentro de la mancha. Cualquier uso; no son viviendas censales.",
                  "anillos": "dentro (d = 0), anillo_0_500m (0 < d ≤ 500 m), anillo_500m_1km (500 < d ≤ 1000 m); acum_500m y acum_1km son acumulados.",
                  "sin_distrito": "Lo que cae dentro de la caja de estudio pero fuera de los 76 polígonos distritales (GADM 4.1)."},
              "fuentes_exposicion": {"poblacion": "WorldPop 2026, 100 m (R2025A, constrained)",
                                     "edificaciones": "Google Open Buildings v3 (confianza ≥ 0,75), vía VIDA / source.coop",
                                     "salud": "RENIPRESS (SUSALUD), corte 30-09-2026",
                                     "colegios": tablas["colegios"]["fuente"].iloc[0] if "colegios" in tablas else None,
                                     "peligro": "JRC CEMS-GloFAS flood hazard v2 (90 m)",
                                     "distritos": "GADM 4.1 (76 distritos; faltan 200115 Veintiséis de Octubre y 240203 Canoas de Punta Sal)",
                                     "ubigeo": "Tabla UBIGEO INEI compilada por jmcastagnetto/ubigeo-peru-aumentado (MIT)"}}
    filas_csv = []
    for clave, (nombre, tipo, valor, t, meta) in cargar_capas().items():
        inund = valor > 0
        mx, my = metros(t)
        dist = ndi.distance_transform_edt(~inund, sampling=(my, mx)).astype("float32")
        dr, nombres = rasterizar_distritos(t, inund.shape)
        p, p500, por_d, pob_d = personas(inund, t, dr, (dist <= 500) & (dr > 0))
        fil, col, ok = indices(edif["lon"], edif["lat"], t, inund.shape)
        dv = np.full(len(edif), np.inf, dtype="float32"); dv[ok] = dist[fil[ok], col[ok]]
        prof = np.zeros(len(edif), dtype="float32"); prof[ok] = valor[fil[ok], col[ok]]
        dist_d = np.zeros(len(edif), dtype=int); dist_d[ok] = dr[fil[ok], col[ok]]
        en_tp = dist_d > 0                                         # edificaciones dentro de Tumbes y Piura
        dv[~en_tp] = np.inf
        dentro = dv <= 0
        r = {"nombre": nombre, "tipo": tipo, "periodo": meta["periodo"], "imagenes": meta["imagenes"],
             "periodo_retorno": meta.get("periodo_retorno"), "qa": meta.get("qa", {}),
             "km2": round(float(inund.sum() * mx * my / 1e6), 1), **poligonos(clave, tipo, valor, t),
             "personas": round(p), "personas_500m": round(p500),
             "edificaciones": int(dentro.sum()), "edificaciones_100m": int((dv <= 100).sum()),
             "edificaciones_500m": int((dv <= 500).sum())}
        if tipo == "peligro":
            r["edificaciones_profundidad"] = {"hasta 0,5 m": int((dentro & (prof <= 0.5)).sum()),
                                              "0,5 a 1,5 m": int((dentro & (prof > 0.5) & (prof <= 1.5)).sum()),
                                              "más de 1,5 m": int((dentro & (prof > 1.5)).sum())}
        muestra = edif[dentro] if dentro.sum() else edif[dv <= 100]
        if len(muestra) > 25000:
            muestra = muestra.sample(25000, random_state=1)
        r["edificaciones_puntos"] = np.round(muestra[["lon", "lat"]].to_numpy(), 4).tolist()
        r["edificaciones_puntos_muestra"] = bool(int(dentro.sum()) > len(muestra))
        r["edificaciones_puntos_cerca"] = bool(not dentro.sum())
        conteos_d = {}
        for n, tabla in tablas.items():
            f2, c2, ok2 = indices(tabla["lon"], tabla["lat"], t, inund.shape)
            d = np.full(len(tabla), np.nan); d[ok2] = dist[f2[ok2], c2[ok2]]
            clase = clasificar_distancia(d)
            x = tabla.assign(dist_m=np.round(d), clase=clase, estado=[ETIQUETA_ESTADO[c] for c in clase])
            r[n] = contar_anillos(clase)
            if "alumnos" in x and x["alumnos"].notna().any():
                al = pd.to_numeric(x["alumnos"], errors="coerce").fillna(0)
                s_ = {a: int(al[clase == a].sum()) for a in ANILLOS}
                r[n]["alumnos"] = {"dentro": s_["dentro"], "acum_500m": s_["dentro"] + s_["anillo_0_500m"],
                                   "acum_1km": s_["dentro"] + s_["anillo_0_500m"] + s_["anillo_500m_1km"],
                                   "locales_sin_dato_dentro": int((x["alumnos"].isna() & (clase == "dentro")).sum())}
            dd = np.zeros(len(tabla), dtype=int); dd[ok2] = dr[f2[ok2], c2[ok2]]
            if "distrito" not in x:   # OpenStreetMap no trae distrito: se asigna por el polígono que lo contiene
                x["distrito"] = [nombres[k - 1][2] if k > 0 else SIN_DISTRITO for k in dd]
            conteos_d[n] = {a: pd.Series(dd[clase == a]).value_counts() for a in ANILLOS}
            cols = [c for c in ["nombre", "tipo", "categoria", "nivel", "alumnos", "distrito", "lat", "lon", "dist_m", "clase", "estado"] if c in x]
            r[n + "_lista"] = json.loads(x[x["clase"] != "fuera"].sort_values("dist_m")[cols].to_json(orient="records", force_ascii=False))
        area = pd.Series(inund.ravel()).groupby(dr.ravel()).sum() * mx * my / 1e6
        cuenta = pd.Series(dist_d[dentro]).value_counts()
        cuenta500 = pd.Series(dist_d[dv <= 500]).value_counts()
        filas = []
        for k, (dep, prov, dis) in [(0, (SIN_DISTRITO, SIN_DISTRITO, SIN_DISTRITO))] + list(enumerate(nombres, start=1)):
            u = ubi.get(k, {})
            fila = {"ubigeo": u.get("ubigeo"), "departamento": dep, "provincia": prov, "distrito": dis,
                    "km2": round(float(area.get(k, 0)), 2),
                    "personas": round(float(por_d.get(k, 0))), "poblacion_worldpop_distrito": round(float(pob_d.get(k, 0))),
                    "edificaciones": int(cuenta.get(k, 0)), "edificaciones_500m": int(cuenta500.get(k, 0))}
            for n in conteos_d:
                for a in ANILLOS:
                    fila[f"{n}_{a}"] = int(conteos_d[n][a].get(k, 0))
                fila[f"{n}_acum_1km"] = sum(fila[f"{n}_{a}"] for a in ANILLOS)
            filas.append(fila)
            filas_csv.append({"escenario": clave, "tipo": tipo, **fila})
        r["distritos"] = sorted([f for f in filas if f["km2"] > 0 or f["edificaciones_500m"] > 0],
                                key=lambda f: (-f["edificaciones"], -f["edificaciones_500m"]))
        por_dep = {}
        for f in filas:
            d0 = por_dep.setdefault(f["departamento"], {"edificaciones": 0, "edificaciones_500m": 0, "personas": 0, "km2": 0.0})
            d0["edificaciones"] += f["edificaciones"]; d0["edificaciones_500m"] += f["edificaciones_500m"]
            d0["personas"] += f["personas"]; d0["km2"] = round(d0["km2"] + f["km2"], 2)
        r["por_departamento"] = por_dep
        r["conciliacion"] = {
            "edificaciones_total": r["edificaciones"],
            "edificaciones_suma_departamentos": sum(v["edificaciones"] for v in por_dep.values()),
            "edificaciones_sin_distrito": por_dep.get(SIN_DISTRITO, {}).get("edificaciones", 0),
            "personas_total": r["personas"], "personas_suma_departamentos": sum(v["personas"] for v in por_dep.values())}
        salida["eventos"][clave] = r
        print(f"{clave}: {r['km2']} km², {r['personas']:,} personas, {r['edificaciones']:,} edificaciones "
              f"(sin distrito {r['conciliacion']['edificaciones_sin_distrito']:,}), colegios {r.get('colegios')}")
    shutil.copy(EXPO / "distritos.geojson", DASH_DATA / "distritos_tumbes_piura.geojson")
    for n, tabla in tablas.items():
        cols = [c for c in ["nombre", "tipo", "nivel", "alumnos", "distrito", "lat", "lon"] if c in tabla]
        tabla[cols].to_json(DASH_DATA / f"{n}_tumbes_piura.json", orient="records", force_ascii=False)
    for viejo in list(DASH_DATA.glob("huella_*.png")) + list(DASH_DATA.glob("capa_*.png")) + list(DASH_DATA.glob("_test*.png")):
        viejo.unlink()
    escribir_json(DASH_DATA / "inundacion.json", salida, indent=None, separators=(",", ":"))
    csv = DESCARGAS / "exposicion_distritos.csv"
    pd.DataFrame(filas_csv).to_csv(csv, index=False, encoding="utf-8-sig")
    registrar_version([DASH_DATA / "inundacion.json", csv], DATA / "versiones" / "manifiesto.csv", "impacto")
    print(f"inundacion.json: {(DASH_DATA / 'inundacion.json').stat().st_size // 1024} KB · {csv.name}: {len(filas_csv)} filas")


if __name__ == "__main__":
    main()
