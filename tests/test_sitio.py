"""Smoke test del sitio estático: levanta un servidor local y comprueba que las páginas y los datos responden.

Con la variable IAPN_URL_SITIO apunta a un sitio desplegado (p. ej. GitHub Pages) en lugar del local.
"""
import json
import os
import threading
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import RAIZ


@pytest.fixture(scope="module")
def base():
    url = os.getenv("IAPN_URL_SITIO")
    if url:
        yield url.rstrip("/")
        return
    h = partial(SimpleHTTPRequestHandler, directory=str(RAIZ / "dashboard"))
    h.log_message = lambda *a: None
    srv = ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def leer(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, r.read()


@pytest.mark.parametrize("pagina,marca", [("index.html", "mapa2d.html"), ("mapa2d.html", "leaflet")])
def test_paginas(base, pagina, marca):
    st, b = leer(f"{base}/{pagina}")
    assert st == 200 and marca in b.decode("utf-8")


def test_respaldo_sin_webgl_presente(base):
    _, b = leer(f"{base}/index.html")
    t = b.decode("utf-8")
    assert "hayWebGL" in t and "SIN_GPU" in t and "sin3d=1" in t


@pytest.mark.parametrize("archivo", ["inundacion.json", "metadatos.json", "panel_distritos.json", "distritos_tumbes_piura.geojson",
                                     "capa_rp100.geojson", "resumen.json"])
def test_datos_json(base, archivo):
    st, b = leer(f"{base}/data/{archivo}")
    assert st == 200 and json.loads(b)


def test_descargas_csv(base):
    st, b = leer(f"{base}/data/descargas/panel_distritos.csv")
    assert st == 200 and b.decode("utf-8-sig").startswith("ubigeo,")


def test_tamanos_razonables():
    """GitHub Pages: archivos individuales pequeños para que el tablero cargue en conexiones móviles."""
    for f in (RAIZ / "dashboard" / "data").rglob("*"):
        if f.is_file():
            assert f.stat().st_size < 8_000_000, f.name
