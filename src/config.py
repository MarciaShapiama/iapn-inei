"""Configuración del Monitor de El Niño Costero."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
HIST_MAR = DATA / "historico" / "mar"          # un archivo por día: nunca se borra
HIST_ECON = DATA / "historico" / "economia"    # copias fechadas de cada descarga económica
DASH = RAIZ / "dashboard"
DASH_DATA = DASH / "data"

# Ventana operativa que pidió el asesor: los últimos 20 días.
DIAS_VENTANA = 20

# Mar frente al Perú (grados). Rejilla OISST 0.25°, se toma 1 de cada 2 celdas (0.5°).
LAT_MIN, LAT_MAX = -19.0, 1.0
LON_MIN, LON_MAX = -86.0, -70.0
PASO = 2

ERDDAPS = ["https://coastwatch.pfeg.noaa.gov/erddap/griddap", "https://upwell.pfeg.noaa.gov/erddap/griddap"]  # principal y espejo
DATASETS_SST = ["ncdcOisst21NrtAgg_LonPM180", "ncdcOisst21Agg_LonPM180"]   # tiempo casi real; definitivo
DATASETS_HIST = ["ncdcOisst21Agg_LonPM180", "ncdcOisst2Agg_LonPM180"]      # para los picos históricos

# Departamentos con litoral (nombres como en data/departamentos.geojson).
COSTEROS = ["TUMBES", "PIURA", "LAMBAYEQUE", "LA LIBERTAD", "ANCASH", "LIMA", "CALLAO",
            "ICA", "AREQUIPA", "MOQUEGUA", "TACNA"]
DIST_MAX_KM = 150      # mar asignado a cada región: celdas a menos de 150 km de su litoral

# Magnitud según la anomalía (umbrales del ICEN, ENFEN): °C
MAGNITUDES = [(-99, 0.4, "Normal"), (0.4, 1.0, "Cálido débil"), (1.0, 1.7, "Cálido moderado"),
              (1.7, 3.0, "Cálido fuerte"), (3.0, 99, "Cálido extraordinario")]

# Episodios para comparar (pico aproximado de la anomalía frente a la costa norte).
PICOS = {"1983": "1983-05-15", "1998": "1998-01-15", "2017": "2017-03-15", "2023": "2023-06-15"}

SERIES_BCRP = {
    "PN01728AM": "Producción nacional (PBI)", "PN01713AM": "Agropecuario", "PN01716AM": "Pesca",
    "PN01717AM": "Minería e Hidrocarburos", "PN01720AM": "Manufactura", "PN01723AM": "Electricidad y Agua",
    "PN01724AM": "Construcción", "PN01725AM": "Comercio", "PN01726AM": "Otros Servicios",
    "PN01727AM": "Derechos de Importación y Otros Impuestos",
}


def magnitud(anom: float) -> str:
    for lo, hi, nombre in MAGNITUDES:
        if lo <= anom < hi:
            return nombre
    return "Sin dato"
