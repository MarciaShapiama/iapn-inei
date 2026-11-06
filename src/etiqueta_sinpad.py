"""Variable dependiente desde el SINPAD del INDECI (fuente oficial, datos abiertos), con trazabilidad completa.

Reemplaza a DesInventar como fuente de las emergencias del modelo de alerta. DesInventar termina en 2015, mezcla
marejadas y en años antiguos recoge prensa; el SINPAD es el registro oficial de INDECI y cubre 2003-2026.

Fuente: INDECI, «Emergencias y daños a nivel nacional por departamento», Plataforma Nacional de Datos Abiertos
(https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento), licencia ODC-By.

Qué hace, paso a paso (cada paso deja su conteo en data/modelo/sinpad/procedencia.json):
    1. Descarga los dos CSV y el diccionario a data/modelo/sinpad/crudo/ (no se sube a GitHub: pesa ~29 MB) y guarda
       la huella SHA-256, el tamaño y la fecha de descarga de cada archivo.
    2. Se queda con Tumbes y Piura (UBIGEO 20xxxx y 24xxxx).
    3. Se queda con los peligros de agua: los que contienen «INUND» o «LLUVI» (INUNDACION, LLUVIA INTENSA y, en 2026,
       LLUVIAS INTENSAS e INUNDACIÓN POR DESBORDE DE RIO/CANALES). Quedan fuera marejadas, incendios, sismos, etc.
    4. Lee la fecha. El diccionario oficial dice «DD/MM/AAAA o MM/DD/AA»: la columna MES decide el orden.
       Se comprueba que la fecha leída coincida con las columnas AÑO y MES; las que no coinciden se descartan.
    5. Identifica el distrito por su UBIGEO. Desde el 6/11/2026 el mapa del INEI tiene los 78 distritos, así que ya no se
       unen Veintiséis de Octubre (200115) con Piura ni Canoas de Punta Sal (240203) con Zorritos (FUSION queda vacía).
    6. Agrupa por distrito y semana (lunes a domingo).

Salidas:
    data/modelo/sinpad/procedencia.json             de dónde salió cada número (URLs, SHA-256, conteos por paso)
    data/modelo/sinpad/eventos_agua_tumbes_piura.csv un registro por emergencia, con su código SINPAD (auditable)
    data/modelo/sinpad/sinpad_semanal.csv            distrito-semana con al menos una emergencia de agua

Uso: python src/etiqueta_sinpad.py            (usa los crudos si ya están; si no, descarga)
     python src/etiqueta_sinpad.py --descargar
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd

from config import DATA

CARPETA = DATA / "modelo" / "sinpad"
CRUDO = CARPETA / "crudo"
PROCEDENCIA = CARPETA / "procedencia.json"
EVENTOS = CARPETA / "eventos_agua_tumbes_piura.csv"
SEMANAL = CARPETA / "sinpad_semanal.csv"
UBIGEO = DATA / "exposicion" / "ubigeo_distritos.csv"

DATASET = "https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento"
ARCHIVOS = {
    "BD_2003-2025_EMERGENCIAS.csv": "https://www.datosabiertos.gob.pe/sites/default/files/BD_2003-2025_EMERGENCIAS.csv",
    "BD_2026_Semestre_I.csv": "https://www.datosabiertos.gob.pe/sites/default/files/BD_2026_Semestre_I.csv",
    "Diccionario_de_datos.xlsx": "https://www.datosabiertos.gob.pe/sites/default/files/Diccionario%20de%20datos_9.xlsx",
}
# Columnas por posición: los dos CSV nombran distinto las mismas columnas (diccionario oficial del dataset).
COLUMNAS = {0: "codigo", 1: "fecha_txt", 2: "anio", 3: "mes", 4: "ubigeo", 5: "dpto", 6: "prov", 7: "dist",
            8: "peligro", 14: "damnificados", 15: "afectados", 16: "viv_destruidas", 17: "viv_afectadas"}
PELIGRO_AGUA = r"INUND|LLUVI"
FUSION: dict[str, str] = {}     # antes (mapa GADM de 76): {"200115": "200101", "240203": "240201"}
MESES = {"ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
         "SETIEMBRE": 9, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12}
# Última semana con etiqueta confiable: el archivo 2026-I trae VIVIENDAS DESTRUIDAS = AFECTADOS (personas) en muchos
# registros y aún está incompleto (semestral). Para la Y del modelo se usa hasta el 29/12/2025.
FIN_ETIQUETA = "2025-12-29"


def normal(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().upper()
    return "".join(c for c in x if c.isalnum())


def fecha_sinpad(texto: str, mes: str) -> str | None:
    """Lee «DD/MM/AAAA» o «MM/DD/AA». La columna MES (texto) decide cuál número es el mes."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$", str(texto))
    mm = MESES.get(str(mes).strip().upper())
    if not m or mm is None:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y = 2000 + y if y < 100 else y
    if b == mm:
        dia, mes_n = a, b
    elif a == mm:
        dia, mes_n = b, a
    else:
        return None                                          # la fecha no coincide con la columna MES
    try:
        return datetime(y, mes_n, dia).strftime("%Y-%m-%d")
    except ValueError:
        return None


def descargar(forzar: bool) -> dict:
    import requests
    CRUDO.mkdir(parents=True, exist_ok=True)
    info = {}
    for nombre, url in ARCHIVOS.items():
        ruta = CRUDO / nombre
        cab = {}
        if forzar or not ruta.exists():
            r = requests.get(url, timeout=900, headers={"User-Agent": "proyecto-integrador-peu-cd"})
            r.raise_for_status()
            ruta.write_bytes(r.content)
            cab = {"last_modified_servidor": r.headers.get("last-modified")}
        datos = ruta.read_bytes()
        info[nombre] = {"url": url, "bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest(),
                        "descargado": datetime.fromtimestamp(ruta.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                        **cab}
    return info


def leer() -> pd.DataFrame:
    partes = []
    for nombre in ["BD_2003-2025_EMERGENCIAS.csv", "BD_2026_Semestre_I.csv"]:
        t = pd.read_csv(io.StringIO((CRUDO / nombre).read_bytes().decode("latin-1")), sep=";", dtype=str)
        t.columns = range(t.shape[1])
        t = t.rename(columns=COLUMNAS)[list(COLUMNAS.values())]
        t["archivo"] = nombre
        partes.append(t)
    return pd.concat(partes, ignore_index=True)


def main(forzar: bool = False) -> dict:
    archivos = descargar(forzar)
    t = leer()
    pasos = [{"paso": "1. Registros en los archivos oficiales", "registros": len(t)}]

    t = t[t["ubigeo"].str.strip().str.match(r"^(20|24)\d{4}$", na=False)].copy()
    t["ubigeo"] = t["ubigeo"].str.strip()
    pasos.append({"paso": "2. Tumbes y Piura (UBIGEO 20xxxx, 24xxxx)", "registros": len(t)})
    peligros_todos = t["peligro"].str.strip().value_counts().to_dict()

    t = t[t["peligro"].str.contains(PELIGRO_AGUA, case=False, na=False)].copy()
    pasos.append({"paso": "3. Peligros de agua (contienen INUND o LLUVI)", "registros": len(t),
                  "peligros_incluidos": t["peligro"].str.strip().value_counts().to_dict()})

    t["fecha"] = [fecha_sinpad(f, m) for f, m in zip(t["fecha_txt"], t["mes"])]
    t["fecha"] = pd.to_datetime(t["fecha"])
    malas = t[t["fecha"].isna() | (t["fecha"].dt.year.astype("Int64").astype(str) != t["anio"].str.strip())]
    t = t.drop(malas.index)
    pasos.append({"paso": "4. Fecha válida y coherente con las columnas AÑO y MES", "registros": len(t),
                  "descartados": len(malas), "codigos_descartados": malas["codigo"].tolist()[:50]})

    t["ubigeo_modelo"] = t["ubigeo"].replace(FUSION)
    from ubigeo import clave_distrito
    ub = pd.read_csv(UBIGEO, dtype={"inei": str})
    # La clave es la misma de la base del modelo; los dos Salitral (Morropón y Sullana) llevan la provincia.
    ub["clave"] = [clave_distrito(a, b, c) for a, b, c in zip(ub["departamento"], ub["provincia"], ub["distrito"])]
    ub["prov_n"] = ub["provincia"].map(normal)
    t = t.merge(ub[["inei", "clave", "prov_n"]].rename(columns={"inei": "ubigeo_modelo"}), on="ubigeo_modelo", how="left")
    sin = t[t["clave"].isna()]
    pasos.append({"paso": "5. Distrito identificado por UBIGEO (78 distritos)", "registros": int(t["clave"].notna().sum()),
                  "sin_distrito": len(sin), "ubigeos_sin_distrito": sorted(sin["ubigeo"].unique().tolist()),
                  "fusionados": {k: int((t["ubigeo"] == k).sum()) for k in FUSION}})
    t = t[t["clave"].notna()].copy()

    for c in ["damnificados", "afectados", "viv_destruidas", "viv_afectadas"]:
        t[c] = pd.to_numeric(t[c].str.replace(",", ".", regex=False), errors="coerce").fillna(0)
    t["inundacion"] = t["peligro"].str.contains("INUND", case=False).astype(int)
    t["semana"] = t["fecha"].dt.to_period("W-SUN").dt.start_time
    t = t.sort_values(["fecha", "codigo"])
    CARPETA.mkdir(parents=True, exist_ok=True)
    t[["codigo", "fecha", "semana", "ubigeo", "ubigeo_modelo", "clave", "prov_n", "dpto", "prov", "dist", "peligro", "inundacion",
       "afectados", "damnificados", "viv_afectadas", "viv_destruidas", "archivo"]].to_csv(EVENTOS, index=False,
                                                                                         date_format="%Y-%m-%d")
    s = (t.groupby(["clave", "prov_n", "semana"])
         .agg(eventos=("codigo", "size"), eventos_inundacion=("inundacion", "sum"),
              viv_afectadas=("viv_afectadas", "sum"), viv_destruidas=("viv_destruidas", "sum"))
         .reset_index())
    s.to_csv(SEMANAL, index=False, date_format="%Y-%m-%d")
    pasos.append({"paso": "6. Distrito-semanas con al menos una emergencia de agua", "registros": len(s),
                  "distritos": int(s["clave"].nunique()), "desde": str(s["semana"].min().date()),
                  "hasta": str(s["semana"].max().date()),
                  "hasta_fin_etiqueta": int((s["semana"] <= FIN_ETIQUETA).sum())})

    proc = {"fuente": "INDECI - SINPAD, «Emergencias y daños a nivel nacional por departamento»",
            "dataset": DATASET, "licencia": "Open Data Commons Attribution License (ODC-By)",
            "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fin_etiqueta": FIN_ETIQUETA, "archivos": archivos, "pasos": pasos,
            "peligros_tumbes_piura_todos": peligros_todos,
            "registros_por_anio": t.groupby(t["fecha"].dt.year).size().to_dict(),
            "semanas_por_anio": s.groupby(s["semana"].dt.year).size().to_dict()}
    PROCEDENCIA.write_text(json.dumps(proc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for p in pasos:
        print(f"  {p['paso']}: {p['registros']:,}")
    print(f"Salidas: {EVENTOS.name}, {SEMANAL.name}, {PROCEDENCIA.name}")
    return proc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--descargar", action="store_true", help="vuelve a bajar los archivos oficiales")
    main(ap.parse_args().descargar)
