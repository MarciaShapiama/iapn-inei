# Inundaciones por El Niño en Tumbes y Piura

Tablero público que estima **cuántas viviendas y personas de Tumbes y Piura pueden verse afectadas por inundaciones durante El Niño costero, y dónde están**. Trabaja en tres tiempos:

1. **Anticipar:** cada mañana compara el pronóstico de lluvia de cada distrito con lo que es extremo en ese lugar, y sigue el caudal de los ríos.
2. **Confirmar:** el radar Sentinel-1 muestra dónde hubo agua abierta cuando pasa el satélite (más o menos cada 4 días; no ve calles ni cultivos inundados).
3. **Comprobar:** contra noticias, registros del INDECI y el mapa oficial de Copernicus de 2017.

Proyecto integrador del Programa de Extensión Universitaria: Ciencia del Dato (PEU-CD), INEI, 2026.
**Autores:** Marcia, Christopher, Maykol y Luz Ángela.

- **Tablero 3D:** https://marciashapiama.github.io/iapn-inei/
- **Mapa 2D (sin aceleración gráfica), panel por distrito y metadatos:** https://marciashapiama.github.io/iapn-inei/mapa2d.html

> «Expuesto» significa que está dentro o cerca de una zona inundable o de agua detectada por satélite. **No equivale a afectados ni damnificados**: esas cifras las registra INDECI/COEN. Un escenario de 1 en 100 años **no anuncia una inundación este año**. Los avisos del tablero **no son oficiales**: los oficiales son de SENAMHI, ENFEN e INDECI.

## Qué tiene el tablero

| Pestaña | Qué muestra |
|---|---|
| Resumen | Cifras principales (personas, viviendas del Censo 2025, edificaciones, colegios con alumnos, salud, niños, adultos mayores, cultivos y carreteras en zona inundable), estado oficial del ENFEN y lo que pasa esta semana |
| Mapa de inundación | Vista 3D sobre el relieve: zona inundable por profundidad, agua vista por radar, edificaciones, colegios y salud |
| Antes y después | Fotos Sentinel-2 de 2017, 2023 y de estos días, con comparador deslizable |
| Alerta por distrito | Aviso de lluvia de los próximos 3 días y riesgo de emergencia por distrito (machine learning), con su validación |
| Lluvia y ríos | Las 11 provincias de Tumbes y Piura: lluvia de 20 días frente a lo normal, caudal y pronóstico de 7 días |
| El mar y El Niño | Anomalía diaria del mar, Niño 1+2 semanal e ICEN |
| Método y fuentes | De dónde sale cada cifra, sus límites y la comparación con el mapa oficial de 2017 |

## Cómo está organizado el repositorio

```
iapn-inei/
├── dashboard/            El tablero publicado (index.html = 3D, mapa2d.html = 2D) y sus datos en dashboard/data/
├── src/                  Código que descarga, calcula y arma el tablero (lo corre GitHub Actions cada día)
├── data/                 Datos descargados y calculados (exposición, huellas de radar, normales, modelo, validación)
├── docs/                 Documentos del proyecto, ordenados por tema (ver tabla abajo)
│   ├── 1_datos/              Auditoría de datos, fuentes y cruces
│   ├── 2_modelo/             Modelos de machine learning
│   ├── 3_validacion/         Pruebas contra noticias, INDECI y Copernicus
│   ├── 4_tablero/            Mejoras del tablero (río normal frente a El Niño, calidad visual)
│   ├── 5_aporte_y_politicas/ Aporte al INEI, estado del arte y políticas públicas
│   ├── 6_presentacion/       Informe final, presentaciones LaTeX y guía de preguntas del jurado
│   ├── evidencia/            Salidas de las pruebas (JSON) que respaldan las cifras de los documentos
│   └── figuras/              Figuras sueltas
├── herramientas/         Scripts que no son parte de la actualización diaria
│   ├── pruebas/              Pruebas con noticias, eventos pasados, Copernicus GFM e INDECI
│   ├── figuras/              Figuras de las presentaciones
│   ├── documentos/           Conversión del informe a Word
│   └── mapa/                 Propuesta de polígonos de agua más suaves
├── tests/                Pruebas automáticas (python -m pytest -q)
└── .github/workflows/    Actualización automática y publicación
```

Los datos confidenciales del INEI (viviendas por manzana) **no están en este repositorio**: `.gitignore` los bloquea. Solo se publican totales por distrito (`dashboard/data/viviendas_censo.json`).

## Documentos

| Tema | Documento | Contenido |
|---|---|---|
| Datos | [01 Auditoría técnica y de datos](docs/1_datos/01_AUDITORIA_TECNICA_Y_DATOS.md) | Arquitectura, fuentes y licencias, errores corregidos y actualización del 4/11 |
| Datos | [07 Refuerzo](docs/1_datos/07_REFUERZO.md) | Padrón ESCALE de colegios y verificación de pobreza e IDH |
| Datos | [11 Cruce de habitantes](docs/1_datos/11_CRUCE_HABITANTES.md) | Cómo cruzar la data de habitantes del INEI (personas, sexo y edad) |
| Datos | [17 Viviendas y personas del Censo 2025](docs/1_datos/17_VIVIENDAS_INEI_MATERIALES.md) | Viviendas y personas (sexo y edad) en la zona inundable, materiales precarios, centros poblados rurales y radar |
| Modelo | [02 Plan de machine learning](docs/2_modelo/02_PLAN_MACHINE_LEARNING.md) | Modelo de alerta por distrito y su evaluación |
| Modelo | [08 Diseño del modelo de viviendas](docs/2_modelo/08_DISENO_MODELO_VIVIENDAS.md) | Primer diseño de la pregunta del profesor |
| Modelo | [10 Modelo de viviendas afectadas](docs/2_modelo/10_MODELO_VIVIENDAS_AFECTADAS.md) | Etiqueta real del SINPAD (INDECI), variables, 6 modelos y validación 2012-2025 |
| Modelo | [19 Variable dependiente desde el SINPAD](docs/2_modelo/19_VARIABLE_DEPENDIENTE_SINPAD.md) | El modelo de alerta usa el SINPAD 2003-2025 en lugar de DesInventar: trazabilidad, auditoría y resultados |
| Modelo | [Modelo de inundación](docs/2_modelo/modelo_inundacion.md) | Documento original del modelo de alerta |
| Validación | [06 Validación y viabilidad](docs/3_validacion/06_VALIDACION_Y_VIABILIDAD_EXPANSION.md) | Validación contra INDECI y costo de expandir |
| Validación | [09 El radar frente a las noticias](docs/3_validacion/09_PRUEBA_DETECTOR_NOTICIAS.md) | Tres pruebas (6 lugares recientes, 13 eventos verificados, cultivos inundados) y la capa de inundaciones reportadas del tablero |
| Validación | [18 ¿El aviso habría anticipado el pasado?](docs/3_validacion/18_PRUEBA_AVISO_CON_EL_PASADO.md) | Pronósticos reales antes de 10 eventos (9 avisados) y 24 años de emergencias de INDECI con lluvia y caudal |
| Validación | [14 Prueba del aviso de lluvia](docs/3_validacion/14_PRUEBA_AVISO_LLUVIA.md) | Aviso del 5/11 frente a lo que pasó |
| Tablero | [12 Río normal frente a El Niño](docs/4_tablero/12_RIO_NORMAL_VS_NINO.md) | Capas, orden y vista propuesta |
| Tablero | [13 Mejora visual](docs/4_tablero/13_MEJORA_VISUAL.md) | Por qué el mapa se veía tosco y cómo arreglarlo |
| Aporte | [03 Aporte al INEI](docs/5_aporte_y_politicas/03_APORTE_AL_INEI.md) | Indicador principal y gobernanza |
| Aporte | [04 Estado del arte](docs/5_aporte_y_politicas/04_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md) | Referencias con DOI verificados |
| Aporte | [05 Políticas públicas](docs/5_aporte_y_politicas/05_POLITICAS_PUBLICAS.md) | Opciones de política vinculadas a los resultados |
| Presentación | [15 Preguntas del jurado](docs/6_presentacion/15_PREGUNTAS_JURADO.md) | 20 preguntas con respuesta, cifra y fuente |
| Presentación | [Informe final](docs/6_presentacion/informe_final/INFORME_FINAL_PROYECTO_INTEGRADOR.md) · `.docx` | Informe para la evaluación del curso |
| Presentación | `docs/6_presentacion/presentacion/` | Presentaciones en LaTeX (avance, validación, de dónde sale el agua) |
| Presentación | `docs/6_presentacion/avance_latex/` | Informe de avance en LaTeX |
| Presentación | `docs/6_presentacion/Guia_didactica_modelo.pdf` | Guía didáctica del modelo de alerta, variable por variable (con la Y del SINPAD) |

## Instalación desde cero

Requisitos: Python 3.11 o superior (probado con 3.11 en Actions y 3.14 en Windows) y git.

```bash
git clone https://github.com/MarciaShapiama/iapn-inei.git
```

```bash
cd iapn-inei
```

```bash
python -m venv .venv
```

Activar el entorno: en Windows `.venv\Scripts\activate`; en Linux o macOS `source .venv/bin/activate`. Después:

```bash
pip install -r requirements.txt -r requirements-inundaciones.txt -r requirements-dev.txt
```

En Windows, si la consola muestra errores de acentos, defina `PYTHONIOENCODING=utf-8`.

## Ver el tablero en su computadora

Los datos ya calculados están en `dashboard/data/`. Hay que servirlos con un servidor HTTP: abrir el archivo con doble clic no funciona, porque el navegador bloquea `fetch`.

```bash
python -m http.server 8765 --directory dashboard
```

Abra http://localhost:8765/ (3D) o http://localhost:8765/mapa2d.html (2D). Para probar el respaldo sin aceleración gráfica abra `index.html?sin3d=1`.

## Actualizar los datos

El orquestador `src/etl.py` corre los pasos en orden. Si un paso falla, lo registra en `data/registro/`, **conserva la última salida válida** y sigue con los demás. El estado de cada capa (`vigente`, `rezagado`, `no disponible`, `estimado`) se recalcula a partir de las fechas reales de los archivos.

| Perfil | Qué hace | Red | Tiempo aproximado |
|---|---|---|---|
| `python src/etl.py local` | Recalcula impacto, panel, metadatos y auditoría con los datos ya descargados | No | ~30 s |
| `python src/etl.py diario` | Mar (NOAA), índices (CPC, IGP), lluvia y caudal (Open-Meteo), aviso de lluvia + tablero + metadatos | Sí | 5–15 min |
| `python src/etl.py inundacion` | Exposición (WorldPop, Open Buildings, RENIPRESS, OSM, GADM, JRC) + Sentinel-1 + impacto + panel | Sí, varios GB | 30–120 min |

Pasos sueltos útiles:

| Comando | Qué hace |
|---|---|
| `python src/reparar_poblacion.py` | Verifica y corrige la alineación del ráster de población (idempotente) |
| `python src/ubigeo.py` | Descarga la tabla UBIGEO y la empata con los distritos |
| `python src/etiqueta_sinpad.py` | Arma la variable dependiente del modelo de alerta desde el SINPAD (INDECI), con huella SHA-256 y conteos por filtro (`--descargar` vuelve a bajar los CSV oficiales) |
| `python src/modelo_inundacion.py` | Reentrena y evalúa el modelo de emergencias (Y del SINPAD; `--fuente desinventar` para la versión anterior) |
| `python src/ml_evaluacion.py` | Bootstrap por años, calibración y falsos negativos |
| `python src/auditoria.py` | Regenera `docs/evidencia/auditoria_cifras.json` |
| `python src/aviso_lluvia.py` | Recalcula el aviso de lluvia por distrito |
| `python src/noticias.py` | Inundaciones reportadas en noticias (Google Noticias + catálogo verificado), con su verificación por radar; corre cada día |
| `python src/vivienda_inei.py` | Viviendas del Censo 2025 por distrito: zona inundable, materiales y radar → `viviendas_censo.json` (necesita los archivos del INEI en `datos_inei/manzana/`; no se suben) |
| `python src/validar_radar.py` | Compara el radar y la zona inundable con el mapa oficial de Copernicus 2017 |
| `python src/modelo_afectados.py` | Modelo de viviendas afectadas con el SINPAD (INDECI) |
| `python herramientas/documentos/md_a_docx.py` | Genera el informe en Word desde el Markdown |
| `python herramientas/figuras/figuras_avance.py` | Regenera las figuras del informe LaTeX |
| `python herramientas/pruebas/prueba_noticias_verificadas.py` | Prueba del radar con cada evento de `data/eventos/catalogo_verificado.csv` |
| `python herramientas/pruebas/prueba_aviso_pasado.py` | Aviso de lluvia y caudal frente a eventos con noticias y emergencias de SINPAD 2003-2026 |
| `python herramientas/pruebas/prueba_aviso_pronostico_real.py` | Aviso con los pronósticos reales hechos 1-3 días antes de cada evento (necesita red) |
| `python herramientas/pruebas/validacion_indeci.py` | Validación externa con registros INDECI 2003-2024 |
| `python herramientas/pruebas/auditoria_sinpad.py` | Auditoría de la variable dependiente del SINPAD: eventos verificados, comparación con DesInventar y distribución de Y |
| `python herramientas/pruebas/viabilidad_expansion.py` | Estima el costo de expandir a otros departamentos |
| `python herramientas/figuras/figuras_presentacion.py` | Figuras de la presentación |

### Variables de entorno (opcionales)

| Variable | Por defecto | Uso |
|---|---|---|
| `IAPN_REINTENTOS` | 4 | Intentos por descarga |
| `IAPN_ESPERA_BASE_S` | 5 | Espera inicial entre intentos (se duplica en cada intento, máximo 300 s) |
| `IAPN_TIMEOUT_S` | 120 | Tiempo máximo por petición HTTP |
| `IAPN_TIMEOUT_PASO_S` | 3600 | Tiempo máximo por paso del ETL |
| `IAPN_USER_AGENT` | genérico del proyecto | Identificador del cliente HTTP |
| `IAPN_HOY` | fecha de Lima | Fija «hoy» (AAAA-MM-DD) para que el cálculo de estados sea reproducible |
| `IAPN_S1_UMBRAL_DB` | −17 | Umbral VV para agua (dB) |
| `IAPN_S1_CAIDA_DB` | 3 | Caída mínima frente a la referencia seca (dB) |
| `IAPN_S1_UMBRAL_MODO` | `fijo` | `otsu` = umbral adaptativo acotado a [−24, −14] dB |
| `IAPN_S1_COMPUESTO` | `minimo` | `p10` = percentil 10 de las pasadas (menos sensible al moteado) |
| `IAPN_URL_SITIO` | — | Hace que `tests/test_sitio.py` pruebe un sitio desplegado en lugar del local |

## Pruebas

```bash
python -m pytest -q
```

Son 38 pruebas: unitarias (anillos, Otsu, referencia del radar, reintentos, estados); de integración de datos (sumas que concilian, acumulados que crecen, UBIGEO únicos, geometrías dentro de la caja, población alineada con las edificaciones, metadatos completos); y un smoke test del sitio con un servidor local. En GitHub Actions, el workflow **Pruebas** corre en cada push y después de cada actualización. Además, los workflows de actualización **no guardan** si las pruebas de datos fallan.

## Automatización (GitHub Actions)

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `actualizar.yml` | Diario 13:20 UTC (8:20 Lima) | `etl.py diario` → pruebas → commit |
| `inundaciones.yml` | Lunes y jueves | `etl.py inundacion` → pruebas → commit |
| `base_modelo.yml` | Lunes | Base distrito-semana y modelo |
| `pruebas.yml` | Push, PR y tras las actualizaciones | Estado de las capas (`::warning::` si hay datos rezagados) + pytest + smoke test del sitio publicado |
| `pages.yml` | Push a `dashboard/` o tras cualquiera de las actualizaciones | Publica `dashboard/` en GitHub Pages |

## Despliegue manual

1. Ejecute `python src/etl.py local` y `python -m pytest -q`. Las pruebas deben pasar.
2. Haga commit de `src/`, `dashboard/`, `data/`, `docs/` y `tests/`.
3. Haga `git push` a `main`. `pages.yml` publica automáticamente. También puede lanzarlo a mano en *Actions → Publicar tablero → Run workflow*.
4. Compruebe el sitio con `IAPN_URL_SITIO=https://marciashapiama.github.io/iapn-inei python -m pytest tests/test_sitio.py` (el workflow «Pruebas» usa automáticamente la cuenta dueña del repositorio).

## Solución de fallos

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El mapa 3D sale en negro o muestra «no puede crear un contexto WebGL» | Navegador o máquina sin aceleración gráfica | Use `mapa2d.html`. No es un fallo del servidor |
| «No se pudieron cargar los archivos del mapa» | El HTML se abrió sin servidor | `python -m http.server 8765 --directory dashboard` |
| Una capa aparece `rezagado` | Falló la descarga de esa fuente o la fuente se retrasó | Revise `data/registro/*.json` y vuelva a correr el perfil; el tablero sigue mostrando el último dato válido |
| `radar_vivo` aparece `no disponible` | Control de calidad fallido (por ejemplo, referencia seca solapada con el evento) | `python src/huellas.py vivo` y después `python src/etl.py local` |
| `UnicodeEncodeError` en Windows | Consola en cp1252 | `set PYTHONIOENCODING=utf-8` |
| Falla `test_poblacion_alineada_con_edificaciones` | Se volvió a descargar WorldPop con un recorte desalineado | `python src/reparar_poblacion.py` |
| Overpass, ERDDAP u Open-Meteo devuelven 429 o 5xx | Límite de uso | Los reintentos son automáticos; espere y vuelva a correr |

## Fuentes y licencias

NOAA OISST v2.1 y CPC (dominio público) · IGP ICEN · Open-Meteo y GloFAS v4 (CC BY 4.0) · JRC CEMS-GloFAS flood hazard v2 (CC BY 4.0) · Copernicus Sentinel-1 vía Microsoft Planetary Computer · WorldPop 2026 (CC BY 4.0) · Google Open Buildings v3 (CC BY 4.0 / ODbL) · RENIPRESS, SUSALUD (datos abiertos) · OpenStreetMap (ODbL, © colaboradores de OSM) · DesInventar/INDECI · tabla UBIGEO de `jmcastagnetto/ubigeo-peru-aumentado` (MIT; pobreza 2018 INEI e IDH 2019 PNUD según el compilador) · límites GADM 4.1 (**uso académico y no comercial; no se ofrecen para descargar**). El detalle por capa está en `dashboard/data/metadatos.json`.

Equipo: Christopher, Maykol, Marcia y Luz Ángela.
