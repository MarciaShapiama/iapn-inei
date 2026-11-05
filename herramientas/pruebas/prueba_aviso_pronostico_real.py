"""Prueba del aviso de lluvia con PRONÓSTICOS REALES del pasado (lo que los modelos decían 1, 2 y 3 días antes).

La otra prueba (prueba_aviso_pasado.py) usa la lluvia que cayó: supone un pronóstico perfecto. Esta usa lo que
Open-Meteo pronosticaba ANTES de cada evento, con su archivo de corridas anteriores (Previous Runs API: guarda, para
cada hora, el pronóstico hecho 1, 2, ... días antes; disponible desde 2024). Así se ve qué habría dicho el tablero.

Para cada evento con noticia (2025-2026) y cada anticipación N = 1, 2, 3 días:
    lluvia pronosticada N días antes para el día del evento y el día previo (suma horaria por día, hora de Lima)
    nivel con los MISMOS umbrales del tablero (data/normales/umbrales_lluvia_distritos.csv: p95 y p99 de ERA5
    1991-2020 por provincia), en el punto central del distrito.
También se guarda la lluvia del modelo para esas horas (dato de la corrida más reciente, cercano a lo observado).

Salida: docs/evidencia/prueba_aviso_pronostico_real.json
Uso: python herramientas/pruebas/prueba_aviso_pronostico_real.py   (necesita red; corre en GitHub Actions)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))
from descargar_zonas import pedir  # noqa: E402

SALIDA = R / "docs" / "evidencia" / "prueba_aviso_pronostico_real.json"
API = "https://previous-runs-api.open-meteo.com/v1/forecast"
EVENTOS = [  # fecha, departamento, provincia, distrito, qué pasó (fuentes en docs/3_validacion/09 y data/eventos)
    ("2025-02-12", "Tumbes", "Tumbes", "San Jacinto", "Desborde del río Tumbes, 1 284 ha de cultivo inundadas"),
    ("2026-10-20", "Piura", "Piura", "Piura", "Calles de Piura amanecen inundadas por lluvias"),
    ("2026-10-20", "Piura", "Morropon", "Chulucanas", "Aguacero inunda calles y cierra el mercado modelo"),
    ("2026-10-25", "Piura", "Ayabaca", "Ayabaca", "Lluvias inundan calles y viviendas de Ayabaca"),
    ("2026-10-28", "Piura", "Piura", "Piura", "Calles de Piura amanecen bajo el agua"),
    ("2026-10-29", "Piura", "Huancabamba", "Canchaque", "Desborde del río Serrán aísla Canchaque"),
    ("2026-11-02", "Tumbes", "Zarumilla", "Aguas Verdes", "Desborde del río Zarumilla inunda Puerto Perú"),
    ("2026-11-02", "Tumbes", "Tumbes", "Tumbes", "Lluvias inundan calles y activan quebradas en Tumbes"),
    ("2026-11-02", "Tumbes", "Tumbes", "San Jacinto", "Se activa la quebrada Vaquería"),
    ("2026-11-02", "Piura", "Talara", "Mancora", "Lluvia de hora y media inunda calles de Máncora"),
]
N = (1, 2, 3)


def nivel(mm, p95, p99):
    if mm is None:
        return "sin dato"
    return "extremo" if mm > p99 else "fuerte" if mm > p95 else "normal"


def norm(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


def main() -> None:
    u = pd.read_csv(R / "data" / "normales" / "umbrales_lluvia_distritos.csv")
    u["k"] = [norm(p) + "|" + norm(d) for p, d in zip(u.provincia, u.distrito)]
    out = []
    for fecha, dep, prov, dist, que in EVENTOS:
        fila = u[u.k == norm(prov) + "|" + norm(dist)]
        if fila.empty:
            out.append({"fecha": fecha, "distrito": dist, "error": "distrito no está en los umbrales"})
            continue
        f = fila.iloc[0]
        d0 = (pd.Timestamp(fecha) - pd.Timedelta(days=1)).date().isoformat()
        vars_ = ["precipitation"] + [f"precipitation_previous_day{n}" for n in N]
        j = pedir(API, {"latitude": f.lat, "longitude": f.lon, "hourly": ",".join(vars_), "start_date": d0,
                        "end_date": fecha, "timezone": "America/Lima"})
        if j is None or "hourly" not in j:
            out.append({"fecha": fecha, "distrito": dist, "error": "Open-Meteo no respondió"})
            continue
        h = pd.DataFrame(j["hourly"])
        h["dia"] = h["time"].str[:10]
        dias = {}
        for v in vars_:
            s = h.groupby("dia")[v].apply(lambda x: None if x.isna().all() else round(float(x.sum(skipna=True)), 1))
            dias[v] = s.to_dict()
        fila_ev = {"fecha": fecha, "departamento": dep, "provincia": prov, "distrito": dist, "que_paso": que,
                   "p95_mm": float(f.p95), "p99_mm": float(f.p99), "lluvia_modelo_corrida_reciente": dias["precipitation"]}
        for n in N:
            v = dias[f"precipitation_previous_day{n}"]
            vals = [x for x in v.values() if x is not None]
            mx = max(vals) if vals else None
            fila_ev[f"pronostico_{n}_dias_antes"] = {"mm_por_dia": v, "max_mm": mx, "nivel": nivel(mx, f.p95, f.p99)}
        out.append(fila_ev)
        print(fecha, dist, "| p95", f.p95, "| observado modelo", dias["precipitation"],
              "|", {n: fila_ev[f"pronostico_{n}_dias_antes"]["max_mm"] for n in N},
              {n: fila_ev[f"pronostico_{n}_dias_antes"]["nivel"] for n in N}, flush=True)
    ok = [e for e in out if "error" not in e]
    resumen = {f"{n}_dias_antes": {k: sum(e[f"pronostico_{n}_dias_antes"]["nivel"] == k for e in ok)
                                   for k in ("extremo", "fuerte", "normal", "sin dato")} for n in N}
    SALIDA.write_text(json.dumps({"metodo": __doc__.split("Salida:")[0].strip(), "resumen": resumen, "eventos": out},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(resumen)


if __name__ == "__main__":
    main()
