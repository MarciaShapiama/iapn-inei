"""Prueba del radar con inundaciones pasadas que duraron varios días (desborde del río Tumbes sobre cultivos).

Si el agua se queda varios días en el campo, el radar debería verla aunque pase cada ~4 días. Se repite el cálculo
de src/huellas.py (mismas reglas, vía herramientas/prueba_noticias.probar) en un cuadrado de ~13 km sobre el valle
bajo del río Tumbes, con una ventana desde un día antes hasta 7 días después de la noticia, frente a la temporada seca
anterior. Salida: docs/evidencia/prueba_eventos_pasados.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(R / "herramientas" / "pruebas"))
import prueba_noticias as pn  # noqa: E402

pn.MEDIO = 0.06
SALIDA = R / "docs" / "evidencia" / "prueba_eventos_pasados.json"
EVENTOS = [
    {"lugar": "Valle bajo del río Tumbes (San Jacinto, Corrales, Pampas de Hospital, San Juan de la Virgen)",
     "lat": -3.64, "lon": -80.45, "fecha": "2025-02-12",
     "noticia": "Desborde del río Tumbes (1 100 m³/s): 1 284 ha de cultivo inundadas según la Agencia Agraria de Tumbes",
     "fuente": "https://andina.pe/agencia/noticia-tumbes-alerta-desborde-del-rio-tumbes-deja-mas-1200-hectareas-cultivo-inundadas-1018652.aspx",
     "ventana": {"evento": ("2025-02-11", "2025-02-19"), "ref": ("2024-08-01", "2024-11-30")}},
    {"lugar": "Valle bajo del río Tumbes (San Jacinto, Malval, Plateros, Cerro Blanco)",
     "lat": -3.64, "lon": -80.45, "fecha": "2023-04-29",
     "noticia": "Desborde del río Tumbes (1 833 m³/s): unas 1 600 ha de banano, limón y arroz afectadas o perdidas",
     "fuente": "https://andina.pe/agencia/noticia-desborde-del-rio-tumbes-inunda-mas-500-hectareas-cultivo-y-cientos-viviendas-938318.aspx",
     "ventana": {"evento": ("2023-04-28", "2023-05-06"), "ref": ("2022-08-01", "2022-11-30")}},
]


def main() -> None:
    from huellas import catalogo
    cat = catalogo()
    res = []
    for e in EVENTOS:
        print(e["lugar"], e["fecha"], flush=True)
        try:
            o = pn.probar(cat, e, e["ventana"])
            o["ventana"] = e["ventana"]
        except Exception as error:  # noqa: BLE001
            o = {"lugar": e["lugar"], "fecha": e["fecha"], "error": str(error)}
        res.append(o)
        print(json.dumps(o, ensure_ascii=False), flush=True)
    SALIDA.write_text(json.dumps({"lado_cuadrado_km": round(2 * pn.MEDIO * 111, 1), "eventos": res}, ensure_ascii=False, indent=1),
                      encoding="utf-8")


if __name__ == "__main__":
    main()
