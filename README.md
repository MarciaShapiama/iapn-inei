# Monitor de El Niño Costero · Perú

Tablero público que sigue, **día a día**, la temperatura del mar frente al Perú y su relación con la producción.
Proyecto integrador del Programa de Especialización en Ciencia de Datos (PEU-CD) del INEI.

**Tablero:** https://marciashapiama.github.io/iapn-inei/

## Qué muestra

| Pestaña | Contenido |
|---|---|
| Situación | Titular del día, costa norte, región más cálida, Niño 1+2 y el ICEN oficial. **Franja costera**: anomalía de cada región costera en cada uno de los últimos 20 días |
| El mar · 20 días | Mapa de la anomalía (rejilla de 0,5°) con botón para reproducir los últimos 20 días |
| Regiones costeras | Las 11 regiones: anomalía de hoy, magnitud (umbrales ENFEN), tendencia en °C por semana y días seguidos en condición cálida |
| ¿Cómo en 1998? | El mar de hoy frente al día pico de 1983, 1998, 2017 o 2023, y qué porcentaje de ese pico tiene hoy cada región |
| Economía | Producción por sector (INEI vía BCRP) con los meses de El Niño sombreados; electricidad diaria (últimos 20 días) y mensual del COES |
| Índices oficiales | Niño 1+2, 3, 3.4 y 4 (semanal) e ICEN mensual desde 1980 |

## Cómo se guarda el histórico

Todos los días a las 8:20 a. m. (Lima), GitHub Actions (`.github/workflows/actualizar.yml`):

1. revisa los **últimos 20 días** del mar y descarga los que falten;
2. guarda **cada día en su propio archivo con su fecha**: `data/historico/mar/AAAA-MM-DD.csv.gz` (lat, lon, anomalía). Nada se borra, así el histórico crece un día cada día;
3. descarga índices, producción y electricidad y guarda una copia fechada en `data/historico/economia/`;
4. arma los archivos del tablero (`dashboard/data/`) y lo publica (`.github/workflows/pages.yml`).

Si una fuente no responde un día, se vuelve a intentar al día siguiente: los días que faltan dentro de la ventana de 20 se completan solos.

## Programas

| Archivo | Qué hace |
|---|---|
| `src/config.py` | Parámetros: ventana de 20 días, zona del mar, regiones costeras, umbrales de magnitud |
| `src/descargar_mar.py` | Anomalía diaria del mar (NOAA OISST v2.1, ERDDAP) y días pico de episodios pasados |
| `src/descargar_indicadores.py` | Niño 1+2/3/3.4/4 (NOAA CPC), ICEN (IGP), sectores (BCRP), electricidad (COES) |
| `src/construir.py` | Asigna el mar a cada región costera (celdas a menos de 150 km) y prepara los datos del tablero |
| `dashboard/index.html` | El tablero (D3) |

Para correrlo en una computadora: `pip install -r requirements.txt`, luego los tres programas de `src/` en ese orden.

## Fuentes

NOAA NCEI (OISST v2.1) vía ERDDAP de NOAA CoastWatch · NOAA CPC (índices semanales, base 1991-2020) ·
IGP (ICEN) · INEI vía BCRPData · COES-SINAC · límites departamentales del INEI.

Equipo: Christopher, Maykol, Marcia y Luz Ángela.
