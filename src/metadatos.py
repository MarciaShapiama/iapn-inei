"""Catálogo de metadatos y estado de cada capa/indicador del tablero (trazabilidad).

Para cada capa: fuente, URL, licencia, definición, unidades, cobertura, resolución, versión, periodo real cubierto,
fecha del dato más reciente, fecha de cálculo, frecuencia esperada, método, advertencias y ESTADO:
    vigente        dato observado dentro de su tolerancia de actualización (o línea base de versión fija)
    rezagado       el dato más reciente es más antiguo que la tolerancia: se muestra el último válido, rotulado
    no disponible  el archivo no existe o no pasó el control de calidad
    estimado       producto modelado o escenario (WorldPop, JRC, GloFAS, pronósticos): no es una observación

Las fechas se leen de los ARCHIVOS (no se escriben a mano), así el estado no miente si una actualización falla.
Salida: dashboard/data/metadatos.json
Uso: python src/metadatos.py
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from comun import ahora_lima, escribir_json, estado_por_fecha, hoy_lima
from config import DASH_DATA, DATA, HIST_MAR

HUELLAS = DATA / "huellas"
EXPO = DATA / "exposicion"


def _max_csv(ruta, col, filtro=None):
    if not ruta.exists():
        return None
    d = pd.read_csv(ruta)
    if filtro is not None:
        d = d[filtro(d)]
    return None if d.empty else str(d[col].max())


def _huella(clave):
    r = HUELLAS / f"{clave}.json"
    return json.load(open(r, encoding="utf-8")) if r.exists() else None


def capas(hoy: date | None = None) -> list[dict]:
    hoy = hoy or hoy_lima()
    hoy_s = hoy.isoformat()
    ultimo_mar = max((p.name[:10] for p in HIST_MAR.glob("*.csv.gz")), default=None)
    lluvia_obs = _max_csv(DATA / "zonas_lluvia.csv", "fecha", lambda d: d["fecha"] < hoy_s)
    lluvia_pron = _max_csv(DATA / "zonas_lluvia.csv", "fecha")
    caudal = _max_csv(DATA / "rios_caudal.csv", "fecha", lambda d: d["fecha"] < hoy_s)
    nino = _max_csv(DATA / "noaa_semanal.csv", "semana")
    icen = _max_csv(DATA / "icen.csv", "fecha")
    L = []

    def capa(id_, nombre, *, fuente, url, licencia, definicion, unidades, cobertura, resolucion, version, naturaleza,
             periodo, ultima, tolerancia, frecuencia, metodo, advertencias, archivo=None, estado=None):
        existe = archivo is None or (DASH_DATA / archivo).exists() or (DATA / archivo).exists()
        e = estado or ("no disponible" if not existe else estado_por_fecha(ultima, tolerancia, hoy))
        if e == "vigente" and naturaleza in ("modelado", "escenario", "pronóstico"):
            e = "estimado"          # fresco, pero es un producto modelado: no se presenta como observación
        L.append({"id": id_, "nombre": nombre, "fuente": fuente, "url": url, "licencia": licencia, "definicion": definicion,
                  "unidades": unidades, "cobertura": cobertura, "resolucion": resolucion, "version": version,
                  "naturaleza": naturaleza, "periodo": periodo, "dato_mas_reciente": ultima,
                  "tolerancia_dias": tolerancia, "frecuencia": frecuencia, "metodo": metodo,
                  "advertencias": advertencias, "estado": e, "archivo": archivo})

    capa("peligro_rp10", "Zona inundable, crecida de 1 en 10 años", fuente="JRC CEMS-GloFAS flood hazard maps v2",
         url="https://data.jrc.ec.europa.eu/collection/id-0054", licencia="CC BY 4.0 (Comisión Europea, JRC)",
         definicion="Extensión y profundidad de inundación fluvial para un caudal con periodo de retorno de 10 años.",
         unidades="m (profundidad); km² (área)", cobertura="Tumbes y Piura (caja -81,40/-6,40/-79,15/-3,35)",
         resolucion="3 segundos de arco (~90 m)", version="v2 (verificar fecha de publicación en el catálogo JRC)", naturaleza="escenario", periodo=None,
         ultima="2024-01-01", tolerancia=None, frecuencia="sin actualización periódica",
         metodo="Modelo hidrodinámico (LISFLOOD-FP) forzado con caudales extremos GloFAS; solo ríos por encima del área de drenaje mínima documentada por el JRC.",
         advertencias=["Escenario probabilístico: no indica que habrá inundación este año.",
                       "No representa inundación pluvial urbana, drenaje ni quebradas pequeñas.",
                       "No considera defensas ribereñas locales; no sustituye estudios EVAR/CENEPRED."],
         archivo="capa_rp10.geojson")
    capa("peligro_rp100", "Zona inundable, crecida de 1 en 100 años", fuente="JRC CEMS-GloFAS flood hazard maps v2",
         url="https://data.jrc.ec.europa.eu/collection/id-0054", licencia="CC BY 4.0 (Comisión Europea, JRC)",
         definicion="Extensión y profundidad de inundación fluvial para un caudal con periodo de retorno de 100 años "
                    "(probabilidad anual de excedencia de 1 %).",
         unidades="m; km²", cobertura="Tumbes y Piura", resolucion="~90 m", version="v2", naturaleza="escenario",
         periodo=None, ultima="2024-01-01", tolerancia=None, frecuencia="sin actualización periódica",
         metodo="Igual que 1 en 10 años.", advertencias=["Un periodo de retorno de 100 años NO significa 'una vez cada 100 años exactos' ni 'este año'.",
                                                          "Incluye la depresión del desierto de Sechura (laguna La Niña), poco poblada."],
         archivo="capa_rp100.geojson")
    for clave, nombre in (("2017", "Agua detectada por radar, El Niño costero 2017"), ("2023", "Agua detectada por radar, ciclón Yaku 2023"),
                          ("vivo", "Agua nueva detectada por radar, últimos 24 días")):
        h = _huella(clave)
        solapa = bool(h and h["referencia"][1] >= h["periodo"][0])
        adv = ["Detección automática sin validación de campo: no es verdad-terreno.",
               "El radar no detecta agua bajo vegetación densa ni entre edificios: subestima en ciudades.",
               "Umbral fijo VV −17 dB y caída ≥ 3 dB, compuesto mínimo del periodo: tiende a sobredetectar en arena lisa y salinas.",
               "Puede confundir riego por inundación (arrozales), humedales y lagunas temporales con inundación."]
        if solapa:
            adv.insert(0, "CONTROL DE CALIDAD FALLIDO: la referencia seca se solapa con el periodo del evento "
                          f"({h['referencia'][0]}–{h['referencia'][1]} vs {h['periodo'][0]}–{h['periodo'][1]}). Recalcular con src/huellas.py.")
        if clave == "vivo":
            adv.append("Parte del agua nueva puede ser riego por inundación (arrozales) y humedales, sobre todo cuando no llueve; "
                       "el radar no ve las calles inundadas ni las quebradas.")
        capa(f"radar_{clave}", nombre, fuente="Copernicus Sentinel-1 RTC (ESA), vía Microsoft Planetary Computer",
             url="https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc", licencia="Datos Copernicus: libre y abierto (atribución)",
             definicion="Píxeles con retrodispersión VV baja en el evento y caída frente a una referencia de temporada seca.",
             unidades="km²", cobertura="Tierra de Tumbes y Piura (polígonos distritales erosionados)", resolucion="~55 m (0,0005°)",
             version="RTC (Planetary Computer)", naturaleza="observado (derivado)",
             periodo=h["periodo"] if h else None, ultima=(h["imagenes_evento"][-1] if h and h["imagenes_evento"] else None),
             tolerancia=(12 if clave == "vivo" else None), frecuencia=("lunes y jueves" if clave == "vivo" else "una vez"),
             metodo="Detección de cambios VV; máscaras de agua permanente, altura > 250 m, pendiente > 5°, manchas < 5 px.",
             advertencias=adv, archivo=f"capa_{clave}.geojson",
             estado=("no disponible" if solapa else None))
        if h:
            L[-1]["imagenes"] = h["imagenes_evento"]; L[-1]["imagenes_referencia"] = len(h["imagenes_referencia"])
            L[-1]["calculado"] = h.get("calculado")
    capa("poblacion", "Población potencialmente expuesta", fuente="WorldPop Global2 R2025A, 2026, constrained, 100 m",
         url="https://hub.worldpop.org/", licencia="CC BY 4.0", definicion="Población modelada por celda de 100 m, restringida a zonas con edificaciones.",
         unidades="personas", cobertura="Caja Tumbes-Piura", resolucion="100 m", version="R2025A v1, año 2026", naturaleza="modelado",
         periodo=["2026", "2026"], ultima="2026-01-01", tolerancia=None, frecuencia="anual (WorldPop)",
         metodo="Desagregación dasimétrica de totales nacionales con covariables geoespaciales (WorldPop).",
         advertencias=["Estimación modelada, no cifra oficial del INEI.", "No equivale a personas afectadas ni damnificadas."],
         archivo="inundacion.json")
    capa("edificaciones", "Edificaciones potencialmente expuestas", fuente="Google Open Buildings v3 (vía VIDA, source.coop)",
         url="https://sites.research.google/open-buildings/", licencia="CC BY 4.0 / ODbL (según fuente de la huella)",
         definicion="Huellas de edificación detectadas en imágenes satelitales (confianza ≥ 0,75); se usa su centro.",
         unidades="edificaciones", cobertura="Caja Tumbes-Piura", resolucion="huella individual", version="v3 (imágenes hasta 2023)",
         naturaleza="observado (derivado, ML)", periodo=None, ultima="2023-05-01", tolerancia=None, frecuencia="sin actualización periódica",
         metodo="Segmentación de imágenes de alta resolución (Google Research).",
         advertencias=["Son edificaciones de cualquier uso (vivienda, comercio, depósitos, corrales), no viviendas censales.",
                       "No reflejan construcciones posteriores a las imágenes de la versión v3."], archivo="inundacion.json")
    capa("colegios", "Locales educativos", fuente="ESCALE (MINEDU): padrón de servicios educativos y Censo Educativo 2025 (matrícula)",
         url="https://escale.minedu.gob.pe/", licencia="Datos públicos del Estado peruano",
         definicion="Un local escolar por código de local (CODLOCAL); alumnos = matrícula del Censo Educativo 2025 (campo TALUM) sumada por local.",
         unidades="locales y alumnos", cobertura="Tumbes y Piura", resolucion="punto", version="padrón 30-10-2026; matrícula 2025",
         naturaleza="registro administrativo", periodo=None, ultima="2026-10-30", tolerancia=None, frecuencia="una vez",
         metodo="Locales del padrón con coordenadas, cruzados con la zona inundable y con anillos de 500 m y 1 km.",
         advertencias=["Un local con inicial, primaria y secundaria cuenta una vez.",
                       "El 4 % de los locales no tiene matrícula y en el 8,5 % de los servicios MINEDU la estimó porque no respondieron: el total de alumnos es un mínimo.",
                       "Las coordenadas del padrón son declaradas por el colegio; los locales cerca del borde de la zona deben verificarse en campo."],
         archivo="inundacion.json")
    capa("salud", "Establecimientos de salud", fuente="RENIPRESS (SUSALUD), datos abiertos", url="https://www.datosabiertos.gob.pe/",
         licencia="Datos abiertos del Perú (atribución)", definicion="Establecimientos activos de categoría I-1 a III.",
         unidades="establecimientos", cobertura="Departamentos de Tumbes y Piura", resolucion="punto", version="corte 30-09-2026",
         naturaleza="registro administrativo", periodo=None, ultima="2026-09-30", tolerancia=None, frecuencia="mensual (fuente)",
         metodo="Filtro por departamento, estado ACTIVO y categoría.", advertencias=["Coordenadas declaradas; algunas pueden estar desplazadas."],
         archivo="inundacion.json")
    capa("mar", "Anomalía diaria de la temperatura del mar", fuente="NOAA OISST v2.1 (ERDDAP CoastWatch)",
         url="https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21NrtAgg_LonPM180.html", licencia="Dominio público (NOAA)",
         definicion="Diferencia frente a la climatología 1991-2020 de OISST.", unidades="°C", cobertura="1°N–19°S, 70°–86°O",
         resolucion="0,25° (se usa 0,5°)", version="v2.1 NRT", naturaleza="observado (satélite + boyas, interpolado)",
         periodo=None, ultima=ultimo_mar, tolerancia=3, frecuencia="diaria (rezago ~1-2 días)",
         metodo="Interpolación óptima (OI) de satélite AVHRR, boyas y barcos.",
         advertencias=["Una anomalía cálida del mar no determina por sí sola una inundación local.",
                       "Las magnitudes ENFEN (débil…extraordinario) se definen para el ICEN trimestral, no para la anomalía diaria: en el tablero son referencia."],
         archivo="mar.json")
    capa("nino12", "Índice Niño 1+2 semanal", fuente="NOAA CPC", url="https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for",
         licencia="Dominio público (NOAA)", definicion="Anomalía semanal de TSM en 0–10°S, 90–80°O (base 1991-2020).", unidades="°C",
         cobertura="Región Niño 1+2", resolucion="semanal", version="OISST v2.1", naturaleza="observado", periodo=None, ultima=nino,
         tolerancia=10, frecuencia="semanal (miércoles)", metodo="Promedio areal de OISST.", advertencias=[], archivo="indices.json")
    capa("icen", "ICEN (Índice Costero El Niño)", fuente="IGP / ENFEN", url="http://met.igp.gob.pe/datos/ICEN.txt",
         licencia="Información pública (IGP)", definicion="Media corrida de 3 meses de la anomalía de TSM en Niño 1+2 (ERSST, versión según IGP).",
         unidades="°C", cobertura="Región Niño 1+2", resolucion="mensual", version="ERSST (según IGP)", naturaleza="observado (índice oficial)",
         periodo=None, ultima=icen, tolerancia=75, frecuencia="mensual (rezago de ~2 meses por la media corrida)",
         metodo="Definición operacional del ENFEN para la costa peruana (nota técnica ENFEN, 2012); verificar la versión vigente en 2026.",
         advertencias=["El estado oficial (vigilancia/alerta) lo emite la Comisión Multisectorial ENFEN en sus comunicados, no este tablero."],
         archivo="indices.json")
    capa("lluvia", "Lluvia diaria por provincia (observada modelada + pronóstico)", fuente="Open-Meteo (modelos meteorológicos); normal ERA5 1991-2020",
         url="https://open-meteo.com/", licencia="CC BY 4.0 (Open-Meteo)", definicion="Precipitación diaria en el punto de la capital provincial.",
         unidades="mm/día", cobertura="34 provincias costeras", resolucion="punto (~11 km de modelo)", version="API v1", naturaleza="modelado",
         periodo=None, ultima=lluvia_obs, tolerancia=2, frecuencia="diaria",
         metodo="Mejor combinación de modelos numéricos para días pasados; pronóstico de 7 días.",
         advertencias=["No son lecturas de pluviómetros del SENAMHI.", f"Incluye pronóstico hasta {lluvia_pron}: el pronóstico no es observación.",
                       "Los avisos oficiales los emite SENAMHI."], archivo="zonas.json")
    capa("caudal", "Caudal del río principal (modelado)", fuente="GloFAS v4 (Copernicus EMS) vía Open-Meteo Flood API",
         url="https://open-meteo.com/en/docs/flood-api", licencia="CC BY 4.0", definicion="Caudal diario simulado en la celda del río.",
         unidades="m³/s", cobertura="Ríos principales de la costa", resolucion="0,05° (~5 km)", version="GloFAS v4", naturaleza="modelado",
         periodo=None, ultima=caudal, tolerancia=3, frecuencia="diaria", metodo="Modelo hidrológico LISFLOOD forzado con meteorología.",
         advertencias=["Caudal simulado, no medido: contrastar con estaciones hidrométricas ANA/SENAMHI."], archivo="zonas.json")
    capa("indice_provincial", "Indicador de condiciones por provincia (propio, 0-100; no es una alerta)", fuente="Cálculo del proyecto (src/construir.py)",
         url="", licencia="—", definicion="mar (hasta 50) + lluvia 20 d + pronóstico 7 d frente a la normal (hasta 25) + caudal frente al p90 (hasta 25).",
         unidades="puntos", cobertura="34 provincias costeras", resolucion="provincia", version="2026-11", naturaleza="modelado",
         periodo=None, ultima=lluvia_obs, tolerancia=2, frecuencia="diaria", metodo="Suma ponderada con topes; pesos fijados por el equipo, sin calibrar.",
         advertencias=["Pesos no calibrados contra eventos observados.", "La mitad del puntaje es la anomalía del mar: con mar cálido y sin lluvia el índice puede marcar 'Alerta'.",
                       "No es una alerta oficial."], archivo="zonas.json")
    capa("vulnerabilidad", "Pobreza monetaria y IDH distrital (contexto de vulnerabilidad)",
         fuente="Pobreza: INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2018, anexos 03 (punto medio del intervalo de confianza al 95 %). IDH: PNUD, Índice de Desarrollo Humano Perú 2019, hoja Distrital. Se leen de la tabla UBIGEO compilada (jmcastagnetto/ubigeo-peru-aumentado).",
         url="https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1718/Libro.pdf", licencia="Fuentes oficiales INEI y PNUD; compilación MIT",
         definicion="% de población en pobreza monetaria total; IDH.", unidades="%; índice 0-1", cobertura="78 distritos de Tumbes y Piura",
         resolucion="distrito", version="pobreza 2018, IDH 2019", naturaleza="estimación oficial de área pequeña",
         periodo=["2018", "2019"], ultima="2019-12-31", tolerancia=None, frecuencia="sin actualización en la compilación",
         metodo="Empate por UBIGEO con los 78 distritos del mapa oficial del INEI (78/78).",
         advertencias=["Verificado el 4/11/2026 en 5 distritos contra los documentos originales: el IDH coincide con el PNUD hasta la sexta cifra decimal y la pobreza con el punto medio del intervalo del INEI (anexo 03.21, pág. 193). PNUD: https://www.undp.org/sites/g/files/zskgke326/files/migration/pe/IDH-2019.xlsx",
                       "No incluye discapacidad, edad, material de vivienda ni saneamiento (requiere Censo 2017 / REDATAM)."],
         archivo="panel_distritos.json")
    return L


def main() -> None:
    L = capas()
    resumen = {e: sum(1 for c in L if c["estado"] == e) for e in ("vigente", "rezagado", "no disponible", "estimado")}
    escribir_json(DASH_DATA / "metadatos.json", {"generado": ahora_lima(), "hoy": hoy_lima().isoformat(), "resumen_estado": resumen, "capas": L})
    for c in L:
        print(f"  {c['estado']:<14} {c['id']:<18} último dato {c['dato_mas_reciente']}")
    print("Resumen:", resumen)


if __name__ == "__main__":
    main()
