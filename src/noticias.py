"""Inundaciones reportadas en Tumbes y Piura: noticias del día + catálogo verificado, con su verificación por radar.

Por qué: el radar solo ve agua abierta en el llano. Una inundación de calles, un desborde dentro de un poblado o una
crecida en la sierra no aparecen en la capa azul. Para que NINGÚN evento reportado quede fuera del tablero, cada
noticia se ubica en el mapa con su enlace, y al lado se dice si el radar la vio y, si no, por qué.

Fuentes:
    Google Noticias (RSS, sin clave): titulares en español de los últimos días con palabras de inundación y
        «Piura» o «Tumbes». Cada titular se ubica con data/eventos/lugares.csv (392 centros poblados y lugares
        de Tumbes y Piura); si no nombra un lugar de la zona, se descarta. Son REPORTES DE PRENSA, no verificados.
    data/eventos/catalogo_verificado.csv: eventos revisados a mano por el equipo, con su prueba de radar en
        docs/evidencia/prueba_noticias_verificadas.json (herramientas/pruebas/prueba_noticias_verificadas.py).

Registro: cada titular nuevo se agrega a data/eventos/noticias_registro.csv (nunca se borra): así un evento sigue en
el tablero aunque la noticia salga del RSS.

Salida: dashboard/data/eventos_reportados.json
Uso: python src/noticias.py   (IAPN_NOTICIAS_SIN_RED=1 rehace la salida solo con el registro, sin descargar)
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from comun import ahora_lima, descargar, escribir_json, hoy_lima
from config import DASH_DATA, DATA

EVENTOS = DATA / "eventos"
LUGARES = EVENTOS / "lugares.csv"
CATALOGO = EVENTOS / "catalogo_verificado.csv"
REGISTRO = EVENTOS / "noticias_registro.csv"
PRUEBA = DATA.parent / "docs" / "evidencia" / "prueba_noticias_verificadas.json"
HUELLAS = DATA / "huellas"
SALIDA = DASH_DATA / "eventos_reportados.json"
LIMA = ZoneInfo("America/Lima")

RSS = "https://news.google.com/rss/search"
DIAS = 14
PALABRAS = "(inundación OR inundaciones OR inundadas OR inundado OR desborde OR desborda OR aniegos OR anegadas OR huaico)"
CONSULTAS = [f"{PALABRAS} {r} when:{DIAS}d" for r in ("Piura", "Tumbes")]
REDES = {"facebook", "youtube", "tiktok", "instagram", "x", "twitter"}
# Un titular cuenta como HECHO si dice que algo pasó. Si además trae palabras de aviso («alerta», «riesgo»,
# «podría»...), tiene que tener un verbo fuerte: «riesgo de inundación» no es una inundación.
HECHO = re.compile(r"INUNDA|DESBORD|ANIEG|ANEGAD|BAJO EL AGUA|DAMNIFICAD|AFECTAD|AISLAD|HUAICO|COLAPS|ACTIVA")
FUERTE = re.compile(r"\b(INUNDAN|INUNDARON|INUNDO|INUNDA|INUNDADAS?|INUNDADOS?|DESBORDO|DESBORDA|SE DESBORDA|DESBORDARON|"
                    r"ANIEGOS?|ANEGADAS?|ANEGADOS?|BAJO EL AGUA|DAMNIFICADOS?|AFECTADAS?|AFECTADOS?|AISLADOS?|AISLO|"
                    r"ACTIVAN|ACTIVARON|ACTIVA|HUAICO|COLAPSA|COLAPSO)\b")
AVISO = re.compile(r"\b(ALERTA|ADVIERTE|ADVIERTEN|RIESGO|RIESGOS|PODRIA|PODRIAN|PRONOSTICO|PREVIENE|PREVENIR|PREVENCION|"
                   r"SIMULACRO|PREVE|POSIBLE|TEMEN|EXIGE|PIDE|PLAN|REDUCIR|OBRAS)\b")
# Titulares que hablan de la inundación pero no informan un hecho: prevención, pronóstico, gestión, opinión.
NO_HECHO = re.compile(r"\b(EVITAN|EVITARON|EVITA|PREVE|PREPARA|PREPARAN|PRESUPUESTO|FISCALIZA|CONOCE|VULNERABLES|SERAN|"
                      r"VERAN|COMENZARAN|CONTINUARIAN|EXPLICA|ANTE LLUVIAS|ANTE INUNDACIONES|RIESGO DE DESBORDES?|"
                      r"RIESGO DE ACTIVACION|SE PREVE|QUE RIESGO|BAJO ALERTA|SE ACTIVA EL RIESGO)\b")
VERIFICACION = re.compile(r"\b(FALSO|ENGANOSO|NO SON DE|VERIFICACION|FACTUAL)\b")
# nombres de centros poblados que también son palabras comunes, apellidos o lugares de otras regiones
NO_LUGAR = {"EL ALTO", "LA ARENA", "SALITRAL", "SANTA ROSA", "LAS LOMAS", "SAN MARTIN", "GRAU", "LA QUEBRADA",
            "LA LAGUNA", "LA LIBERTAD", "LA CURVA", "LA PIEDRA", "LA PALMA", "LA PENA", "LA HORCA", "LAS VEGAS",
            "MIRAFLORES", "LOS OLIVOS", "SAN ISIDRO", "SAN MIGUEL", "SANTA CRUZ", "SAN JOSE", "SANTA ANA", "SANTA CLARA",
            "FATIMA", "BELEN", "EL PORVENIR", "LA ESMERALDA", "NUEVA ESPERANZA", "NUEVO PROGRESO", "NUEVO PARAISO",
            "CONSTANTE", "CORONADO", "MONTERO", "NEGREIROS", "BERNAL", "CHIRINOS", "SOJO", "LAS MERCEDES",
            "LAS PALMERAS", "LAS PAMPAS", "ARENAL", "TUNAL", "SAUSAL", "CANAVERAL", "GARBANZAL", "CRUCETA", "SAN PEDRO",
            "SAN FRANCISCO", "SAN RAFAEL", "SAN JORGE", "SANTA ELENA", "SANTA SOFIA", "SANTA PAULA", "SANTA VICTORIA",
            "LA CAPILLA", "LA QUINTA", "LA NORIA", "LA VINA", "LA TINA", "LA RITA", "LA CAMPINA", "MIRAMAR",
            "LAS MALVINAS", "LOS RANCHOS", "EL TAMBO", "EL CUCHO", "LA ENCANTADA", "LA MARGARITA", "VERANDA"}
RIOS = re.compile(r"\bRIOS? (TUMBES|ZARUMILLA|PIURA|CHIRA)( Y (TUMBES|ZARUMILLA|PIURA|CHIRA))?\b")
ANIO = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
ALIAS = {"TAMBOGRANDE": "TAMBO GRANDE", "PUERTO PIZARRO": "PUERTO PIZARRO", "CURA MORI": "CUCUNGARA"}
RADIO_KM = 3.0
DETECTADO_KM2 = 0.05



# Nombres para mostrar: el nomenclátor viene en mayúsculas y sin tildes.
_MINUSC = {"De", "Del", "La", "Las", "Los", "Y", "El"}
_TILDES = {"Peru": "Perú", "Mancora": "Máncora", "Vaqueria": "Vaquería", "Morropon": "Morropón", "Organos": "Órganos",
           "Colan": "Colán", "Union": "Unión", "Tallan": "Tallán", "Rio": "Río", "Jose": "José", "Maria": "María",
           "Veintiseis": "Veintiséis", "Frias": "Frías", "Jilili": "Jililí", "Belen": "Belén", "Simon": "Simón",
           "Lucia": "Lucía", "Martin": "Martín", "Ramon": "Ramón", "Andres": "Andrés", "Jesus": "Jesús", "Angel": "Ángel",
           "Bolivar": "Bolívar", "Huarmaca": "Huarmaca", "Paijan": "Paiján", "Sullana": "Sullana", "Pariñas": "Pariñas"}


def bonito(nombre: str) -> str:
    """'PAMPAS DE HOSPITAL' -> 'Pampas de Hospital'; 'PUERTO PERU' -> 'Puerto Perú'."""
    palabras = str(nombre).title().split()
    out = []
    for i, w in enumerate(palabras):
        w = _TILDES.get(w, w)
        out.append(w.lower() if i > 0 and w in _MINUSC else w)
    return " ".join(out)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", s).upper().split())


# ---------------------------------------------------------------- noticias
def leer_rss() -> list[dict]:
    filas = []
    for q in CONSULTAS:
        xml = descargar(RSS, params={"q": q, "hl": "es-419", "gl": "PE", "ceid": "PE:es-419"}).content
        for it in ET.fromstring(xml).findall("./channel/item"):
            fuente = it.find("source")
            medio = (fuente.text if fuente is not None else "") or ""
            titulo = (it.findtext("title") or "").strip()
            if medio and titulo.endswith(" - " + medio):
                titulo = titulo[: -len(medio) - 3].strip()
            pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(LIMA)
            filas.append({"fecha": pub.date().isoformat(), "titulo": titulo, "medio": medio,
                          "sitio": fuente.get("url", "") if fuente is not None else "", "url": it.findtext("link") or "",
                          "visto": ahora_lima()})
    return filas


def es_hecho(titulo: str, medio: str, fecha: str) -> bool:
    t = norm(titulo)
    if norm(medio).lower() in REDES or VERIFICACION.search(t) or NO_HECHO.search(t):
        return False
    if any(a != fecha[:4] for a in ANIO.findall(t)):      # recuerda otro año («las inundaciones de 2017»)
        return False
    if AVISO.search(t):
        return bool(FUERTE.search(t))
    return bool(HECHO.search(t))


def actualizar_registro(nuevas: list[dict]) -> pd.DataFrame:
    cols = ["fecha", "titulo", "medio", "sitio", "url", "visto"]
    viejo = pd.read_csv(REGISTRO, dtype=str) if REGISTRO.exists() else pd.DataFrame(columns=cols)
    todo = pd.concat([viejo, pd.DataFrame(nuevas, columns=cols)], ignore_index=True)
    todo["_k"] = todo["titulo"].map(norm) + "|" + todo["medio"].fillna("")
    todo = todo.drop_duplicates("_k", keep="first").drop(columns="_k").sort_values(["fecha", "titulo"])
    EVENTOS.mkdir(parents=True, exist_ok=True)
    todo.to_csv(REGISTRO, index=False, encoding="utf-8")
    return todo


# ---------------------------------------------------------------- ubicar y clasificar
class Nomenclator:
    def __init__(self, lug: pd.DataFrame):
        self.lug = lug
        nombres = sorted({n for n in lug["nombre"] if n not in NO_LUGAR}, key=len, reverse=True)
        self.patrones = [(n, re.compile(rf"\b{re.escape(n)}\b")) for n in nombres]

    def ubicar(self, titulo: str) -> list[tuple[pd.Series, str]]:
        """Todos los lugares de Tumbes y Piura que nombra el titular (máximo 3). Si solo dice «Piura» o «Tumbes», la
        ciudad, marcada como ubicación aproximada."""
        t = norm(titulo)
        for a, b in ALIAS.items():
            t = re.sub(rf"\b{a}\b", b, t)
        # «río Zarumilla», «río Tumbes», «ríos Tumbes y Zarumilla» nombran el río, no la ciudad del mismo nombre
        t = RIOS.sub(" ", t)
        deps = [d for d in ("PIURA", "TUMBES") if re.search(rf"\b{d}\b", t)]
        hallados = []
        for n, p in self.patrones:
            if p.search(t) and not any(n in h for h in hallados):
                hallados.append(n)
        out = []
        for n in [h for h in hallados if h not in ("PIURA", "TUMBES")]:
            c = self.lug[self.lug["nombre"] == n]
            if deps:                              # «… en Tumbes»: no ubicar en un homónimo de Piura
                c = c[c["departamento"].isin(deps)]
            if len(c):
                out.append((c.sort_values("tipo").iloc[0], "lugar nombrado en la noticia"))
        if not out:
            for d in deps:
                c = self.lug[(self.lug["nombre"] == d) & (self.lug["tipo"] == "capital de distrito")]
                out.append((c.iloc[0], f"solo dice «{d.title()}»: se ubica en la ciudad (aproximado)"))
        return out[:3]


def clasificar(titulo: str) -> str:
    """Tipo según lo que DICE el titular. «Desborde» solo si lo dice explícitamente: mencionar un río, su caudal o
    una alerta no es un desborde."""
    t = norm(titulo)
    if re.search(r"HUAICO|DESLIZAMIENTO|DERRUMBE", t):
        return "huaico o deslizamiento"
    if re.search(r"DESBORD|CRECIDA|SE SALE|SE SALIO", t):
        return "desborde de río o quebrada"
    if re.search(r"QUEBRADA", t):
        return "activación de quebrada"
    if re.search(r"CALLES|ANIEG|ANEGAD|LLUVIA|AVENIDA|COLEGIO|MERCADO|LAGUNA", t):
        return "lluvia urbana"
    return "inundación"


# ---------------------------------------------------------------- radar
def capas_radar() -> list[dict]:
    """Capas de radar PUBLICADAS (dashboard/data/capa_*.geojson): lo mismo que se ve en el mapa, ya sin mar, orilla
    ni manchas sueltas (src/impacto.py)."""
    from shapely import STRtree
    from shapely.geometry import shape
    capas = []
    for clave in ("2017", "2023", "vivo"):
        ruta, meta_ruta = DASH_DATA / f"capa_{clave}.geojson", HUELLAS / f"{clave}.json"
        if ruta.exists() and meta_ruta.exists():
            meta = json.load(open(meta_ruta, encoding="utf-8"))
            geoms = [shape(f["geometry"]) for f in json.load(open(ruta, encoding="utf-8"))["features"]]
            capas.append({"clave": clave, "nombre": meta.get("nombre", clave), "periodo": meta["periodo"],
                          "pasadas": meta.get("imagenes_evento", []), "geoms": geoms, "arbol": STRtree(geoms)})
    return capas


def radar_en(capa: dict, lon: float, lat: float) -> float:
    """km² de agua de la capa publicada a menos de RADIO_KM del punto."""
    import shapely
    from shapely.geometry import Point
    k = np.cos(np.radians(lat))
    a_grados = lambda c: np.c_[lon + c[:, 0] / (111.32 * k), lat + c[:, 1] / 110.6]  # noqa: E731
    a_km = lambda c: np.c_[(c[:, 0] - lon) * 111.32 * k, (c[:, 1] - lat) * 110.6]     # noqa: E731
    circulo = shapely.transform(Point(0, 0).buffer(RADIO_KM, 32), a_grados)
    total = 0.0
    for i in capa["arbol"].query(circulo):
        inter = capa["geoms"][i].intersection(circulo)
        if not inter.is_empty:
            total += shapely.transform(inter, a_km).area
    return total


def verificar_radar(ev: dict, capas: list[dict], prueba: dict) -> dict:
    p = prueba.get(ev["id"])
    capa = next((c for c in capas if c["periodo"][0] <= ev["fecha"] <= c["periodo"][1]), None)
    r = {"capa": capa["nombre"] if capa else None}
    if capa:
        r["km2_a_3km"] = round(radar_en(capa, ev["lon"], ev["lat"]), 2)
        r["pasadas_desde_la_noticia"] = [f for f in capa["pasadas"] if f >= ev["fecha"]]
    if p and "V0_reglas_actuales" in p:          # prueba dedicada del catálogo verificado
        r.update({"prueba_km2_reglas_actuales": p["V0_reglas_actuales"],
                  "prueba_km2_sin_limite_altura": p["V1_sin_limite_altura"],
                  "prueba_km2_sin_altura_ni_pendiente": p["V2_sin_altura_ni_pendiente"],
                  "prueba_pasadas": p.get("pasadas_desde_la_noticia", [])})
    km2 = r.get("prueba_km2_reglas_actuales", r.get("km2_a_3km"))
    alto = ev["altura_m"] > 250
    if km2 is not None and km2 >= DETECTADO_KM2:
        r["veredicto"] = "detectado"
        r["explicacion"] = (f"El radar marcó {km2:.2f} km² de agua nueva a menos de {RADIO_KM:.0f} km (puede no ser "
                            "exactamente el punto de la noticia).")
    elif capa is None and not p:
        r["veredicto"] = "sin radar"
        r["explicacion"] = "No hay una capa de radar calculada para esa fecha."
    elif alto:
        r["veredicto"] = "fuera de alcance"
        r["explicacion"] = (f"Está a {ev['altura_m']} m de altura. El detector solo trabaja debajo de 250 m: en la sierra "
                            "la sombra del relieve se confunde con agua y los ríos son más angostos que un píxel.")
    elif ev["tipo"] == "lluvia urbana":
        r["veredicto"] = "fuera de alcance"
        r["explicacion"] = "Calles inundadas por lluvia: el radar no ve el agua entre casas y edificios."
    elif ev["tipo"] == "activación de quebrada":
        r["veredicto"] = "fuera de alcance"
        r["explicacion"] = ("Quebrada activada: el agua corre por un cauce de pocos metros y dura horas; el radar (píxel de "
                            "~55 m, una pasada cada pocos días) no alcanza a verla.")
    elif capa and not r.get("pasadas_desde_la_noticia") and not (p and p.get("pasadas_desde_la_noticia")):
        r["veredicto"] = "sin pasada"
        r["explicacion"] = "El satélite Sentinel-1 todavía no pasó por aquí después de la fecha de la noticia."
    else:
        r["veredicto"] = "no detectado"
        r["explicacion"] = ("El radar no encontró agua abierta nueva cerca: la inundación pudo ser breve, angosta o "
                            "dentro del poblado.")
    return r


# ---------------------------------------------------------------- armar eventos
def eventos_de_noticias(reg: pd.DataFrame, nom: Nomenclator) -> list[dict]:
    grupos: dict[tuple, dict] = {}
    for _, n in reg.fillna("").sort_values("fecha").iterrows():
        if not es_hecho(n["titulo"], n["medio"], n["fecha"]):
            continue
        for l, precision in nom.ubicar(n["titulo"]):
            agregar(grupos, n, l, precision)
    for g in grupos.values():                      # el tipo más específico entre todos los titulares del grupo
        # Un desborde o un huaico dicho explícitamente manda; si no, el tipo que más titulares describen.
        tipos = [clasificar(a["titulo"]) for a in g["articulos"]]
        fuertes = [t for t in ("desborde de río o quebrada", "huaico o deslizamiento") if t in tipos]
        resto = [t for t in tipos if t in ("activación de quebrada", "lluvia urbana")]
        if fuertes:
            g["tipo"] = fuertes[0]
        elif resto:
            g["tipo"] = max(("lluvia urbana", "activación de quebrada"), key=resto.count)
        # el título del evento: el primer titular que informa un hecho sin palabras de aviso
        g["titulo"] = next((a["titulo"] for a in g["articulos"]
                            if FUERTE.search(norm(a["titulo"])) and not AVISO.search(norm(a["titulo"]))), g["titulo"])
    return list(grupos.values())


def agregar(grupos: dict, n, l, precision: str) -> None:
    """Junta en un evento los titulares del mismo lugar con menos de 3 días entre sí."""
    f = date.fromisoformat(n["fecha"])
    clave = next((k for k in grupos if k[0] == l["nombre"] and k[1] == l["ubigeo"]
                  and abs((f - date.fromisoformat(grupos[k]["fecha_fin"])).days) <= 3), None)
    art = {"titulo": n["titulo"], "medio": n["medio"], "fecha": n["fecha"], "url": n["url"]}
    if clave:
        g = grupos[clave]
        if norm(art["titulo"]) not in {norm(a["titulo"]) for a in g["articulos"]}:
            g["articulos"].append(art)
        g["fecha_fin"] = max(g["fecha_fin"], n["fecha"])
        return
    grupos[(l["nombre"], l["ubigeo"], f)] = {
        "id": f"n-{n['fecha']}-{norm(l['nombre']).lower().replace(' ', '-')}", "origen": "noticias (automático)",
        "fecha": n["fecha"], "fecha_fin": n["fecha"], "lugar": bonito(l["nombre"]), "ubigeo": l["ubigeo"],
        "distrito": bonito(l["distrito"]), "provincia": bonito(l["provincia"]),
        "departamento": bonito(l["departamento"]), "lat": float(l["lat"]), "lon": float(l["lon"]),
        "altura_m": int(l["altura_m"]), "precision": precision, "tipo": clasificar(n["titulo"]),
        "titulo": n["titulo"], "articulos": [art]}


def eventos_verificados(lug: pd.DataFrame) -> list[dict]:
    out = []
    for _, e in pd.read_csv(CATALOGO, dtype=str).fillna("").iterrows():
        l = lug[(lug["nombre"] == e["lugar"]) & (lug["ubigeo"] == e["ubigeo"])].iloc[0]
        arts = [{"titulo": e["descripcion"], "medio": e["medio"], "fecha": e["fecha"], "url": e["fuente"]}]
        if e["fuente2"]:
            arts.append({"titulo": e["descripcion"], "medio": e["medio2"], "fecha": e["fecha"], "url": e["fuente2"]})
        out.append({"id": e["id"], "origen": "verificado por el equipo", "fecha": e["fecha"], "fecha_fin": e["fecha"],
                    "lugar": bonito(l["nombre"]), "ubigeo": e["ubigeo"], "distrito": bonito(l["distrito"]),
                    "provincia": bonito(l["provincia"]), "departamento": bonito(l["departamento"]),
                    "lat": float(l["lat"]), "lon": float(l["lon"]), "altura_m": int(l["altura_m"]),
                    "precision": "centro del poblado", "tipo": "desborde de río o quebrada" if e["tipo"] == "desborde de río"
                    else e["tipo"], "titulo": e["descripcion"], "articulos": arts})
    return out


def unir(verificados: list[dict], de_noticias: list[dict]) -> list[dict]:
    """Una noticia del mismo distrito y con menos de 3 días de diferencia que un evento verificado se suma a ese
    evento (como fuente adicional) en lugar de aparecer dos veces en el mapa."""
    out = list(verificados)
    for n in de_noticias:
        v = next((v for v in verificados if v["ubigeo"] == n["ubigeo"]
                  and abs((date.fromisoformat(v["fecha"]) - date.fromisoformat(n["fecha"])).days) <= 3), None)
        if v is None:
            out.append(n)
            continue
        vistos = {norm(a["titulo"]) for a in v["articulos"]} | {a["url"] for a in v["articulos"]}
        v["articulos"] += [a for a in n["articulos"] if norm(a["titulo"]) not in vistos and a["url"] not in vistos]
    return out


def main() -> None:
    lug = pd.read_csv(LUGARES, dtype={"ubigeo": str})
    if os.getenv("IAPN_NOTICIAS_SIN_RED") != "1":
        try:
            nuevas = leer_rss()
            print(f"RSS: {len(nuevas)} titulares")
        except Exception as error:  # noqa: BLE001
            print(f"ERROR: Google Noticias no disponible ({error}); se usa el registro")
            nuevas = []
    else:
        nuevas = []
    reg = actualizar_registro(nuevas)
    prueba = {}
    if PRUEBA.exists():
        prueba = {e["id"]: e for e in json.load(open(PRUEBA, encoding="utf-8"))["eventos"]}
    capas = capas_radar()
    evs = unir(eventos_verificados(lug), eventos_de_noticias(reg, Nomenclator(lug)))
    for ev in evs:
        ev["radar"] = verificar_radar(ev, capas, prueba)
    evs.sort(key=lambda e: (e["fecha"], e["lugar"]), reverse=True)
    resumen = {v: sum(1 for e in evs if e["radar"]["veredicto"] == v)
               for v in ("detectado", "no detectado", "fuera de alcance", "sin pasada", "sin radar")}
    escribir_json(SALIDA, {
        "generado": ahora_lima(), "hoy": hoy_lima().isoformat(),
        "fuentes": {"noticias": f"Google Noticias (RSS), últimos {DIAS} días, titulares con palabras de inundación y "
                                "«Piura» o «Tumbes»; acumulados en data/eventos/noticias_registro.csv",
                    "verificados": "data/eventos/catalogo_verificado.csv (revisión manual del equipo)",
                    "radar": "capas data/huellas/*.tif y prueba dedicada docs/evidencia/prueba_noticias_verificadas.json"},
        "aviso": "Los eventos de noticias son reportes de prensa ubicados automáticamente por el nombre del lugar: no "
                 "están verificados ni equivalen a cifras oficiales (INDECI/COEN).",
        "resumen_radar": resumen, "n": len(evs), "eventos": evs})
    print(f"{len(evs)} eventos ({sum(e['origen'].startswith('verificado') for e in evs)} verificados); radar: {resumen}")


if __name__ == "__main__":
    main()
