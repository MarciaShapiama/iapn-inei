"""Estimación cuantitativa de la viabilidad de extender el piloto (Tumbes-Piura) al norte y a todo el Perú.

Usa: data/departamentos.geojson (límites departamentales), data/exposicion/ubigeo_peru_completo.csv (78 → 1874
distritos, superficie y densidad 2020; compilación MIT de jmcastagnetto/ubigeo-peru-aumentado) y los tamaños y
tiempos MEDIDOS en el piloto. El costo se escala con el área de la caja envolvente (lo que descargan WorldPop,
Open Buildings, JRC y Sentinel-1) y, para el radar, con el área de costa baja (< 250 m), que es donde aplica.
Salida: docs/evidencia/viabilidad_expansion.json · Uso: python herramientas/pruebas/viabilidad_expansion.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box, shape

R = Path(__file__).resolve().parents[2]
CAJA_PILOTO = (-81.40, -6.40, -79.15, -3.35)
NORTE = ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD", "CAJAMARCA", "ANCASH"]
NORTE_COSTA = ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD"]

# Medido en el piloto (4/11/2026, ver docs/01 y data/registro/)
MEDIDO = {"impacto_s": 22.6, "sentinel1_vivo_min": 40, "sentinel1_ram_gb": 4.0, "edificaciones_parquet_mb": 12.3,
          "poblacion_tif_mb": 3.5, "jrc_tif_mb": 2.85, "huellas_tif_mb": 1.9, "dashboard_data_mb": 11.0,
          "edificaciones_n": None}


def km2_caja(b):
    o, s, e, n = b
    return (e - o) * 111.32 * np.cos(np.radians((s + n) / 2)) * (n - s) * 110.57


def main():
    g = json.load(open(R / "data/departamentos.geojson", encoding="utf-8"))
    dep = {f["properties"]["NOMBDEP"]: shape(f["geometry"]) for f in g["features"]}
    u = pd.read_csv(R / "data/exposicion/ubigeo_peru_completo.csv", dtype={"inei": str})
    for c in ("superficie", "pob_densidad_2020"):
        u[c] = pd.to_numeric(u[c], errors="coerce")
    u["pob"] = u.superficie * u.pob_densidad_2020
    u["dep"] = u.departamento.str.upper().str.replace("Á", "A")
    a0 = km2_caja(CAJA_PILOTO)

    def escenario(nombre, deps):
        geom = None
        for d in deps:
            geom = dep[d] if geom is None else geom.union(dep[d])
        b = geom.bounds
        k = km2_caja(b) / a0
        sub = u[u.dep.isin([d.replace("Á", "A") for d in deps])]
        costa = [d for d in deps if d in NORTE_COSTA or d in ("LAMBAYEQUE", "ICA", "LIMA", "AREQUIPA", "MOQUEGUA", "TACNA", "CALLAO", "ANCASH")]
        return {"escenario": nombre, "departamentos": len(deps), "distritos": int(len(sub)),
                "poblacion_2020_est": int(sub.pob.sum()), "superficie_km2": int(sub.superficie.sum()),
                "caja_km2": int(km2_caja(b)), "factor_area_vs_piloto": round(k, 1),
                "estimacion": {
                    "edificaciones_parquet_mb": round(MEDIDO["edificaciones_parquet_mb"] * k * (sub.pob.sum() / u[u.dep.isin(["TUMBES", "PIURA"])].pob.sum()) / k, 0),
                    "rasteres_mb (poblacion+JRC 2 periodos)": round((MEDIDO["poblacion_tif_mb"] + 2 * MEDIDO["jrc_tif_mb"]) * k, 0),
                    "sentinel1_por_evento_min (1 caja, secuencial)": round(MEDIDO["sentinel1_vivo_min"] * k, 0),
                    "impacto_min": round(MEDIDO["impacto_s"] * k / 60, 1)}}

    out = {"piloto_caja_km2": int(a0), "medido_en_piloto": MEDIDO, "escenarios": [
        escenario("Piloto: Tumbes y Piura", ["TUMBES", "PIURA"]),
        escenario("Norte costero: + Lambayeque y La Libertad", NORTE_COSTA),
        escenario("Norte ampliado: + Cajamarca y Áncash", NORTE),
        escenario("Perú (25 departamentos)", list(dep))],
        "limites_gratuitos": {"github_actions_job_horas": 6, "runner_ram_gb": 16, "github_pages_sitio_gb": 1,
                              "github_archivo_mb": 100, "repo_recomendado_gb": 1}}
    (R / "docs/evidencia/viabilidad_expansion.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = main()
    for e in o["escenarios"]:
        print(e["escenario"], {k: e[k] for k in ("departamentos", "distritos", "poblacion_2020_est", "caja_km2", "factor_area_vs_piloto")}, e["estimacion"])
