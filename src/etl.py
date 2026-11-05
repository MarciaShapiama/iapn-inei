"""Orquestador del flujo ETL con registro de fallos y degradación controlada.

Cada paso corre en su propio proceso. Si un paso falla:
    - se registra (código de salida, duración, últimas líneas del error) en data/registro/AAAA-MM-DDTHHMM.json;
    - NO se borran ni sobrescriben las salidas anteriores de ese paso: el tablero sigue mostrando el último
      resultado válido y src/metadatos.py lo rotula como 'rezagado' según la fecha real del dato;
    - los pasos siguientes siguen corriendo (una fuente caída no detiene las demás).
Al final se escribe dashboard/data/estado_actualizacion.json (lo lee el tablero) y, en GitHub Actions, se emiten
anotaciones ::warning:: por cada paso fallido.

Perfiles:
    local       solo cálculos con los datos ya descargados (impacto, panel, metadatos, auditoría). No usa red.
    diario      descargas diarias (mar, índices, lluvia/caudal) + construir + aviso de lluvia + inundaciones reportadas en noticias (noticias.py) + metadatos.
    inundacion  exposición + huellas Sentinel-1 + impacto + panel + metadatos + auditoría.
Uso: python src/etl.py [local|diario|inundacion]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from comun import ahora_lima, escribir_json
from config import DASH_DATA, DATA, RAIZ

PERFILES = {
    "local": ["impacto.py", "panel.py", "metadatos.py", "auditoria.py"],
    "diario": ["descargar_mar.py", "descargar_indicadores.py", "descargar_zonas.py", "construir.py", "aviso_lluvia.py", "noticias.py", "metadatos.py"],
    "inundacion": ["exposicion.py", "reparar_poblacion.py", "ubigeo.py", "huellas.py", "impacto.py", "validar_radar.py", "panel.py", "metadatos.py", "auditoria.py"],
}
CRITICOS = {"construir.py", "impacto.py", "metadatos.py"}     # su fallo se marca como error, no solo advertencia


def correr(script: str, timeout_s: int) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-u", str(RAIZ / "src" / script)], cwd=RAIZ / "src", capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
                           env=os.environ | {"PYTHONIOENCODING": "utf-8"})
        codigo, salida, error = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        codigo, salida, error = -1, (e.stdout or "") if isinstance(e.stdout, str) else "", f"tiempo agotado ({timeout_s} s)"
    # los scripts heredados capturan sus errores e imprimen "ERROR": se cuentan como fallo parcial
    parcial = codigo == 0 and "ERROR" in salida
    return {"paso": script, "codigo": codigo, "ok": codigo == 0 and not parcial, "parcial": parcial,
            "segundos": round(time.time() - t0, 1), "salida_final": salida.strip().splitlines()[-8:],
            "error_final": error.strip().splitlines()[-8:]}


def main(perfil: str) -> int:
    pasos = PERFILES[perfil]
    timeout_s = int(os.getenv("IAPN_TIMEOUT_PASO_S", "3600"))
    inicio = ahora_lima()
    resultados = []
    for s in pasos:
        r = correr(s, timeout_s)
        resultados.append(r)
        marca = "OK " if r["ok"] else ("PARCIAL" if r["parcial"] else "FALLO")
        print(f"[{marca}] {s} ({r['segundos']} s)")
        if not r["ok"]:
            for linea in (r["error_final"] or r["salida_final"])[-3:]:
                print(f"        {linea}")
            if os.getenv("GITHUB_ACTIONS"):
                nivel = "error" if (s in CRITICOS and not r["parcial"]) else "warning"
                print(f"::{nivel} title=ETL {perfil}::{s} {'terminó con errores parciales' if r['parcial'] else 'falló'}; "
                      "se conserva el último resultado válido")
    registro = {"perfil": perfil, "inicio": inicio, "fin": ahora_lima(), "pasos": resultados,
                "ok": all(r["ok"] for r in resultados), "fallidos": [r["paso"] for r in resultados if not r["ok"]]}
    nombre = inicio[:16].replace(":", "")
    escribir_json(DATA / "registro" / f"{nombre}_{perfil}.json", registro)
    previo = DASH_DATA / "estado_actualizacion.json"
    hist = json.load(open(previo, encoding="utf-8")) if previo.exists() else {}
    hist[perfil] = {"ultima_corrida": registro["fin"], "ok": registro["ok"], "fallidos": registro["fallidos"],
                    "ultima_corrida_ok": registro["fin"] if registro["ok"] else hist.get(perfil, {}).get("ultima_corrida_ok")}
    escribir_json(previo, hist)
    criticos = [r for r in resultados if not r["ok"] and not r["parcial"] and r["paso"] in CRITICOS]
    return 1 if criticos else 0


if __name__ == "__main__":
    perfil = sys.argv[1] if len(sys.argv) > 1 else "local"
    if perfil not in PERFILES:
        sys.exit(f"Perfil desconocido: {perfil}. Use uno de {list(PERFILES)}")
    sys.exit(main(perfil))
