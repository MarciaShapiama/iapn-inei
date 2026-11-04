"""Utilidades comunes del flujo ETL: descargas con reintentos, registro de corridas, estado de vigencia y versiones.

Configuración por variables de entorno (todas opcionales):
    IAPN_REINTENTOS        número máximo de intentos por descarga (por defecto 4)
    IAPN_ESPERA_BASE_S     espera inicial entre intentos, se duplica en cada intento (por defecto 5)
    IAPN_TIMEOUT_S         tiempo máximo de una petición HTTP (por defecto 120)
    IAPN_USER_AGENT        identificador del cliente (por defecto genérico del proyecto)
    IAPN_HOY               fecha de referencia AAAA-MM-DD para calcular el estado (pruebas reproducibles)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")

REINTENTOS = int(os.getenv("IAPN_REINTENTOS", "4"))
ESPERA_BASE_S = float(os.getenv("IAPN_ESPERA_BASE_S", "5"))
TIMEOUT_S = float(os.getenv("IAPN_TIMEOUT_S", "120"))
USER_AGENT = os.getenv("IAPN_USER_AGENT", "Proyecto-integrador-PEU-CD-INEI (inundaciones Tumbes-Piura)")

ESTADOS = ("vigente", "rezagado", "no disponible", "estimado")


def hoy_lima() -> date:
    fijo = os.getenv("IAPN_HOY")
    return date.fromisoformat(fijo) if fijo else datetime.now(LIMA).date()


def ahora_lima() -> str:
    return datetime.now(LIMA).isoformat(timespec="minutes")


def descargar(url: str, *, metodo: str = "GET", intentos: int | None = None, espera: float | None = None,
              timeout: float | None = None, sesion=None, dormir=time.sleep, **kw):
    """Petición HTTP con reintentos y espera exponencial limitada. Lanza la última excepción si todos fallan.

    `sesion` y `dormir` se pueden inyectar en las pruebas.
    """
    import requests
    s = sesion or requests
    intentos = intentos or REINTENTOS
    espera = ESPERA_BASE_S if espera is None else espera
    kw.setdefault("headers", {"User-Agent": USER_AGENT})
    ultimo = None
    for i in range(intentos):
        try:
            r = s.request(metodo, url, timeout=timeout or TIMEOUT_S, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except Exception as error:  # noqa: BLE001 - se registra y se reintenta
            ultimo = error
            if i < intentos - 1:
                dormir(min(espera * 2 ** i, 300))
    raise RuntimeError(f"{url}: falló tras {intentos} intentos: {ultimo}")


def estado_por_fecha(ultima: str | date | None, tolerancia_dias: int | None, hoy: date | None = None,
                     estimado: bool = False) -> str:
    """'vigente' si el dato más reciente tiene a lo sumo `tolerancia_dias` de antigüedad, si no 'rezagado'.

    tolerancia_dias=None indica una línea base estática (versión fija de la fuente): es 'vigente' mientras exista.
    estimado=True marca productos modelados o escenarios (WorldPop, JRC, GloFAS): 'estimado' si existen.
    """
    if ultima is None:
        return "no disponible"
    if estimado:
        return "estimado"
    if tolerancia_dias is None:
        return "vigente"
    hoy = hoy or hoy_lima()
    if isinstance(ultima, str):
        ultima = date.fromisoformat(ultima[:10] if len(ultima) >= 10 else ultima + "-01")
    return "vigente" if (hoy - ultima).days <= tolerancia_dias else "rezagado"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def registrar_version(archivos: list[Path], manifiesto: Path, etiqueta: str) -> list[dict]:
    """Agrega al manifiesto (CSV, solo se añaden filas) la huella SHA-256 de cada archivo producido.

    Así ningún cambio de un archivo publicado pasa en silencio: queda la fecha, el tamaño y la huella anterior.
    """
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not manifiesto.exists()
    previas = {}
    if not nuevo:
        for linea in manifiesto.read_text(encoding="utf-8").splitlines()[1:]:
            partes = linea.split(",")
            if len(partes) >= 5:
                previas[partes[2]] = partes[4]
    filas = []
    with open(manifiesto, "a", encoding="utf-8") as f:
        if nuevo:
            f.write("fecha,etiqueta,archivo,bytes,sha256,cambio\n")
        for a in archivos:
            if not a.exists():
                continue
            h = sha256(a)
            rel = a.as_posix().split("/iapn-inei/")[-1] if "/iapn-inei/" in a.as_posix() else a.name
            cambio = "nuevo" if rel not in previas else ("igual" if previas[rel] == h else "modificado")
            fila = {"fecha": ahora_lima(), "etiqueta": etiqueta, "archivo": rel, "bytes": a.stat().st_size,
                    "sha256": h, "cambio": cambio}
            filas.append(fila)
            f.write(",".join(str(fila[k]) for k in ("fecha", "etiqueta", "archivo", "bytes", "sha256", "cambio")) + "\n")
    return filas


def escribir_json(ruta: Path, obj, **kw) -> None:
    """Escritura atómica: se escribe a un temporal y se renombra. Un fallo a mitad no deja un JSON roto."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, **({"indent": 1} | kw))
    os.replace(tmp, ruta)
