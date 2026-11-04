# Inundaciones por El Niño en Tumbes y Piura

Tablero público sobre la **exposición potencial** a inundaciones en **Tumbes y Piura**. Incluye:

- la zona inundable (escenarios JRC de 1 en 10 y 1 en 100 años) y lo que detectó el radar Sentinel-1 en 2017, 2023 y en los últimos días;
- población, edificaciones, colegios y establecimientos de salud potencialmente expuestos, por distrito (UBIGEO);
- un panel de decisiones con peligro, exposición, vulnerabilidad y riesgo estimado;
- un modelo experimental de emergencias por distrito y semana;
- el monitoreo diario del mar frente al Perú.

Proyecto integrador del Programa de Extensión Universitaria en Ciencia de Datos (PEU-CD) del INEI.

- **Tablero 3D:** `dashboard/index.html` · **Mapa 2D sin GPU, panel y metadatos:** `dashboard/mapa2d.html`
- **Sitio publicado:** https://marciashapiama.github.io/iapn-inei/ · mapa 2D: https://marciashapiama.github.io/iapn-inei/mapa2d.html
- **Repositorio:** https://github.com/MarciaShapiama/iapn-inei

### Qué tiene el tablero

| Pestaña | Qué muestra |
|---|---|
| Resumen | Las cifras principales en una frase (personas, edificaciones, colegios, salud, niños de 0 a 4 años, adultos de 65 o más, cultivos y carreteras), el estado oficial del ENFEN, lo que pasa esta semana y lo que pasó en 2017 y 2023 |
| Mapa de inundación | Vista 3D sobre el relieve: zona inundable por profundidad, edificaciones, colegios y salud |
| Antes y después | Fotos Sentinel-2 de 2017, 2023 y de estos días en Piura, Tumbes y Sechura, con comparador deslizable |
| Alerta por distrito | Riesgo de emergencia en las próximas 4 semanas (modelo de machine learning), su validación y los modelos comparados |
| Lluvia y ríos | Las 8 provincias de Tumbes y Piura: lluvia de 20 días frente a lo normal, caudal y pronóstico de 7 días |
| El mar y El Niño | Anomalía diaria del mar (últimos 20 días), Niño 1+2 semanal e ICEN |
| Método y fuentes | De dónde sale cada cifra, sus límites y los autores |

### Autores

Marcia, Christopher, Maykol y Luz Ángela.

> «Expuesto» significa que está dentro o cerca de una zona inundable o de agua detectada por satélite. **No equivale a afectados ni damnificados**: esas cifras las registra INDECI/COEN. Un escenario de 1 en 100 años **no anuncia una inundación este año**. Este tablero **no emite alertas**: las alertas oficiales son de SENAMHI, ENFEN e INDECI.

## Documentos

| Documento | Contenido |
|---|---|
| [docs/01_AUDITORIA_TECNICA_Y_DATOS.md](docs/01_AUDITORIA_TECNICA_Y_DATOS.md) | Arquitectura, fuentes y licencias, errores encontrados y corregidos, evidencia |
| [docs/02_PLAN_MACHINE_LEARNING.md](docs/02_PLAN_MACHINE_LEARNING.md) | Casos A/B/C, experimento reproducido, incertidumbre, calibración y falsos negativos |
| [docs/03_APORTE_AL_INEI.md](docs/03_APORTE_AL_INEI.md) | Opciones de aporte estadístico, indicador principal y gobernanza |
| [docs/04_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md](docs/04_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md) | 21 referencias con DOI verificados (APA 7) |
| [docs/05_POLITICAS_PUBLICAS.md](docs/05_POLITICAS_PUBLICAS.md) | 7 opciones de política vinculadas a los resultados |
| [INFORME_FINAL_PROYECTO_INTEGRADOR.md](INFORME_FINAL_PROYECTO_INTEGRADOR.md) · `.docx` | Informe para la evaluación del curso (Markdown y Word), con resumen ejecutivo y preguntas del jurado |
| `docs/avance_latex/avance_proyecto.tex` · `.pdf` | Informe de avance para el docente (LaTeX); se compila con `pdflatex` (dos pasadas) |
| [docs/06_VALIDACION_Y_VIABILIDAD_EXPANSION.md](docs/06_VALIDACION_Y_VIABILIDAD_EXPANSION.md) | Validación del piloto contra INDECI y viabilidad de expandir al norte y a todo el Perú |
| `docs/presentacion/presentacion_avance.tex` · `.pdf` | Presentación del avance (Beamer 16:9, 17 diapositivas) |
| `docs/presentacion/presentacion_validacion_expansion.tex` · `.pdf` | Presentación de la validación con INDECI y la viabilidad de expansión (Beamer 16:9, 13 diapositivas) |
| [docs/07_REFUERZO.md](docs/07_REFUERZO.md) | Padrón oficial de colegios (ESCALE) y verificación de pobreza e IDH contra el INEI y el PNUD |
| [docs/modelo_inundacion.md](docs/modelo_inundacion.md) | Modelo de alerta (documento original del equipo) |
| `docs/evidencia/` | Salidas de pruebas, auditoría de cifras, ML y verificación de DOI |

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
| `python src/etl.py diario` | Mar (NOAA), índices (CPC, IGP), BCRP, COES, lluvia y caudal (Open-Meteo) + tablero + metadatos | Sí | 5–45 min |
| `python src/etl.py inundacion` | Exposición (WorldPop, Open Buildings, RENIPRESS, OSM, GADM, JRC) + Sentinel-1 + impacto + panel | Sí, varios GB | 30–120 min |

Pasos sueltos útiles:

| Comando | Qué hace |
|---|---|
| `python src/reparar_poblacion.py` | Verifica y corrige la alineación del ráster de población (idempotente) |
| `python src/ubigeo.py` | Descarga la tabla UBIGEO y la empata con los distritos |
| `python src/modelo_inundacion.py` | Reentrena y evalúa el modelo de emergencias |
| `python src/ml_evaluacion.py` | Bootstrap por años, calibración y falsos negativos |
| `python src/auditoria.py` | Regenera `docs/evidencia/auditoria_cifras.json` |
| `python herramientas/md_a_docx.py` | Genera el informe en Word desde el Markdown |
| `python herramientas/figuras_avance.py` | Regenera las figuras del informe LaTeX |
| `python herramientas/validacion_indeci.py` | Validación externa con registros INDECI 2003-2024 |
| `python herramientas/viabilidad_expansion.py` | Estima el costo de expandir a otros departamentos |
| `python herramientas/figuras_presentacion.py` | Figuras de la presentación |

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

NOAA OISST v2.1 y CPC (dominio público) · IGP ICEN · BCRP · COES · Open-Meteo y GloFAS v4 (CC BY 4.0) · JRC CEMS-GloFAS flood hazard v2 (CC BY 4.0) · Copernicus Sentinel-1 vía Microsoft Planetary Computer · WorldPop 2026 (CC BY 4.0) · Google Open Buildings v3 (CC BY 4.0 / ODbL) · RENIPRESS, SUSALUD (datos abiertos) · OpenStreetMap (ODbL, © colaboradores de OSM) · DesInventar/INDECI · tabla UBIGEO de `jmcastagnetto/ubigeo-peru-aumentado` (MIT; pobreza 2018 INEI e IDH 2019 PNUD según el compilador) · límites GADM 4.1 (**uso académico y no comercial; no se ofrecen para descargar**). El detalle por capa está en `dashboard/data/metadatos.json`.

Equipo: Christopher, Maykol, Marcia y Luz Ángela.
