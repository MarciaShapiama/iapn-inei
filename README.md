# Inundaciones por El Niño en Tumbes y Piura

Sistema que estima, para cada uno de los 78 distritos de Tumbes y Piura, **la probabilidad de una emergencia por lluvia o inundación en las próximas una a cuatro semanas, y cuántas viviendas y personas viven en la zona inundable** según los Censos Nacionales 2025. Tiene tres partes:

1. **Exposición:** viviendas y personas del censo (por sexo, edad y material de la vivienda) dentro de la zona inundable de cada distrito.
2. **Probabilidad a 1-4 semanas:** un modelo de aprendizaje automático entrenado con las emergencias del SINPAD (INDECI) desde 2003, validado año por año y calibrado. Es el núcleo del trabajo.
3. **Aviso de 1 a 3 días:** reglas sobre el pronóstico de lluvia y el caudal de los ríos, como respaldo. El radar Sentinel-1 y las noticias solo se usan para comprobar; no entran al modelo.

Proyecto integrador del Programa de Extensión Universitaria: Ciencia del Dato (PEU-CD), INEI, 2026.
**Autores:** Christopher Calle, Luz Ángela Mendizábal, Maykol Ramírez y Marcia Shapiama De La Cruz. **Asesor:** Prof. Alexander Quispe.

- **Tablero 3D:** https://marciashapiama.github.io/iapn-inei/
- **Mapa 2D (sin aceleración gráfica), panel por distrito y metadatos:** https://marciashapiama.github.io/iapn-inei/mapa2d.html

> «Expuesto» significa que está dentro o cerca de una zona inundable o de agua detectada por satélite. **No equivale a afectados ni damnificados**: esas cifras las registra INDECI/COEN. Un escenario de 1 en 100 años **no anuncia una inundación este año**. Los avisos del tablero **no son oficiales**: los oficiales son de SENAMHI, ENFEN e INDECI.

## Qué tiene el tablero

| Pestaña | Qué muestra |
|---|---|
| Selector de distrito (arriba, en casi todas las pestañas) | Buscador por nombre y menús de departamento, provincia y distrito; enfoca todo el tablero y abre la ficha del distrito: censo por sexo, edad, material de la vivienda y zona urbana o rural; probabilidad a 1-4 semanas; emergencias del SINPAD 2003-2025 |
| Resumen | Cifras principales (personas, viviendas del Censo 2025, edificaciones, colegios con alumnos, salud, niños, adultos mayores, cultivos y carreteras en zona inundable), estado oficial del ENFEN y lo que pasa esta semana |
| Mapa de inundación | Vista 3D sobre el relieve: zona inundable por profundidad, agua vista por radar, edificaciones, colegios y salud |
| Antes y después | Fotos Sentinel-2 de 2017, 2023 y de estos días, con comparador deslizable |
| Alerta por distrito | Aviso de lluvia de los próximos 3 días y probabilidad de emergencia por distrito a 1-4 semanas (machine learning, doc 2.2), con su validación |
| ¿Dónde actuar primero? | Distritos ordenados por personas en riesgo esperado (probabilidad × personas expuestas), riesgo frente a vulnerabilidad, y colegios y salud en la zona inundable de los distritos en alerta |
| Lluvia y ríos | Las 11 provincias de Tumbes y Piura: lluvia de 20 días frente a lo normal, caudal y pronóstico de 7 días |
| El mar y El Niño | Anomalía diaria del mar, comparación de la temporada con 2017 y 2023, Niño 1+2 semanal e ICEN |
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
│   ├── 6_presentacion/       Informe final, guía de preguntas del jurado y avances anteriores
│   ├── evidencia/            Salidas de las pruebas (JSON) que respaldan las cifras de los documentos
│   └── figuras/              Figuras sueltas
├── herramientas/         Scripts que no son parte de la actualización diaria
│   ├── pruebas/              Pruebas con noticias, eventos pasados, Copernicus GFM e INDECI
│   ├── figuras/              Figuras de las presentaciones
│   ├── datos/                Nomenclátor de lugares para ubicar noticias
│   └── mapa/                 Propuesta de polígonos de agua más suaves
├── tests/                Pruebas automáticas (python -m pytest -q)
└── .github/workflows/    Actualización automática y publicación
```

El INEI entregó al proyecto los datos por manzana y centro poblado de los Censos Nacionales 2025 y autorizó su uso y la difusión de los resultados. El repositorio publica los totales por distrito (`dashboard/data/viviendas_censo.json`); los archivos por manzana no se incluyen y no se muestran cifras menores de 10.

## Documentos

Los documentos están numerados por carpeta: el primer número es el tema y el segundo, el orden de lectura. **Para empezar, lea 1.3, 2.2, 3.1 y 3.3.** Los marcados *(histórico)* documentan versiones anteriores y se conservan por trazabilidad.

| N.° | Documento | Contenido |
|---|---|---|
| **1 · Datos** | | |
| 1.1 | [Auditoría técnica y de datos](docs/1_datos/1.1_AUDITORIA_TECNICA_Y_DATOS.md) | Arquitectura, fuentes y licencias, errores corregidos |
| 1.2 | [Mapa con los 78 distritos del INEI](docs/1_datos/1.2_MAPA_78_DISTRITOS_INEI.md) | Límites oficiales del INEI en lugar de GADM (76): fuente, cambios y tabla antes y después |
| 1.3 | [Viviendas y personas del Censo 2025](docs/1_datos/1.3_VIVIENDAS_Y_PERSONAS_CENSO_2025.md) | Viviendas y personas (sexo y edad) en la zona inundable, materiales precarios, centros poblados y radar |
| 1.4 | [Cruce de habitantes](docs/1_datos/1.4_CRUCE_HABITANTES.md) | *(histórico)* Diseño del cruce antes de recibir los datos; reemplazado por 1.3 |
| 1.5 | [Colegios y pobreza](docs/1_datos/1.5_COLEGIOS_Y_POBREZA.md) | Padrón ESCALE de colegios y verificación de pobreza e IDH |
| **2 · Modelo** | | |
| 2.1 | [Variable dependiente del SINPAD](docs/2_modelo/2.1_VARIABLE_DEPENDIENTE_SINPAD.md) | La etiqueta sale del SINPAD (INDECI) 2003-2025: trazabilidad y auditoría |
| 2.2 | [Modelo por plazo (1 a 4 semanas)](docs/2_modelo/2.2_MODELO_POR_PLAZO.md) | **Modelo principal.** Probabilidad por semana y distrito, calibración, fases de aviso, margen de error y práctica con 2017 y 2023 |
| 2.3 | [Modelo de alerta](docs/2_modelo/2.3_MODELO_DE_ALERTA.md) | Modelo anterior: ¿emergencia en alguna de las próximas 4 semanas? |
| 2.4 | [Modelo de viviendas afectadas](docs/2_modelo/2.4_MODELO_VIVIENDAS_AFECTADAS.md) | Dos etapas (¿hay emergencia? → ¿cuántas viviendas?) |
| 2.5 | [Plan de machine learning](docs/2_modelo/2.5_PLAN_MACHINE_LEARNING.md) | *(histórico)* Plan inicial y su evaluación |
| 2.6 | [Diseño del modelo de viviendas](docs/2_modelo/2.6_DISENO_MODELO_VIVIENDAS.md) | *(histórico)* Primer diseño de la pregunta del profesor |
| **3 · Validación** | | |
| 3.1 | [¿El aviso habría anticipado el pasado?](docs/3_validacion/3.1_PRUEBA_AVISO_CON_EL_PASADO.md) | Pronósticos reales antes de 10 eventos (9 avisados), 24 años de INDECI y falsas alarmas |
| 3.2 | [El radar frente a las noticias](docs/3_validacion/3.2_RADAR_FRENTE_A_NOTICIAS.md) | Qué ve y qué no ve el satélite; capa de inundaciones reportadas |
| 3.3 | [Auditoría crítica](docs/3_validacion/3.3_AUDITORIA_CRITICA.md) | ¿El modelo aprende?, de dónde sale cada dato y qué falta: lo que preguntará el jurado |
| 3.4 | [Validación y viabilidad](docs/3_validacion/3.4_VALIDACION_Y_VIABILIDAD_EXPANSION.md) | Validación contra INDECI y costo de expandir a otras regiones |
| 3.5 | [Prueba del aviso de lluvia (noviembre)](docs/3_validacion/3.5_PRUEBA_AVISO_LLUVIA_NOVIEMBRE.md) | Aviso del 5/11 frente a lo que pasó |
| **4 · Tablero** | | |
| 4.1 | [Río normal frente a El Niño](docs/4_tablero/4.1_RIO_NORMAL_VS_NINO.md) | Capas, orden y vista propuesta |
| 4.2 | [Mejora visual](docs/4_tablero/4.2_MEJORA_VISUAL.md) | Por qué el mapa se veía tosco y cómo arreglarlo |
| **5 · Aporte y políticas** | | |
| 5.1 | [Aporte al INEI](docs/5_aporte_y_politicas/5.1_APORTE_AL_INEI.md) | Indicador principal y gobernanza |
| 5.2 | [Políticas públicas](docs/5_aporte_y_politicas/5.2_POLITICAS_PUBLICAS.md) | Opciones de política vinculadas a los resultados |
| 5.3 | [Estado del arte y bibliografía](docs/5_aporte_y_politicas/5.3_ESTADO_DEL_ARTE_Y_BIBLIOGRAFIA.md) | Detección de inundaciones y referencias con DOI verificados |
| 5.4 | [Estado del arte: avisos e impacto](docs/5_aporte_y_politicas/5.4_ESTADO_DEL_ARTE_AVISOS_E_IMPACTO.md) · [referencias](docs/5_aporte_y_politicas/5.4_REFERENCIAS.csv) | Avisos basados en impacto, daños y El Niño costero |
| 5.5 | [Trabajos parecidos en el mundo](docs/5_aporte_y_politicas/5.5_TRABAJOS_SIMILARES_Y_MEJORAS.md) | Qué tomamos de trabajos parecidos (Cataluña, Cruz Roja Perú, calibración) y mejoras pendientes |
| **6 · Presentación** | | |
| 6.1 | [Preguntas del jurado](docs/6_presentacion/6.1_PREGUNTAS_JURADO.md) | Preguntas con respuesta, cifra y fuente |
| — | [Informe final (PDF)](docs/6_presentacion/informe_final/Informe_final_proyecto_integrador.pdf) · [Word](docs/6_presentacion/informe_final/Informe_final_proyecto_integrador.docx) | Informe en formato APA 7, con las cifras del 9 de noviembre de 2026 |
| — | `docs/6_presentacion/presentacion/` y `avance_latex/` | *(histórico)* Presentaciones e informe de avance en LaTeX, anteriores al modelo por plazo |
| — | `docs/6_presentacion/Guia_didactica_modelo.pdf` | Guía didáctica del modelo de alerta, variable por variable |

Las salidas de las pruebas que respaldan cada cifra están en `docs/evidencia/` (JSON y CSV).

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
| `python src/etl.py inundacion` | Exposición (WorldPop, Open Buildings, RENIPRESS, OSM, límites del INEI, JRC) + Sentinel-1 + impacto + panel | Sí, varios GB | 30–120 min |

Pasos sueltos útiles:

| Comando | Qué hace |
|---|---|
| `python src/reparar_poblacion.py` | Verifica y corrige la alineación del ráster de población (idempotente) |
| `python src/ubigeo.py` | Descarga la tabla UBIGEO y la empata con los distritos |
| `python src/etiqueta_sinpad.py` | Arma la variable dependiente del modelo de alerta desde el SINPAD (INDECI), con huella SHA-256 y conteos por filtro (`--descargar` vuelve a bajar los CSV oficiales) |
| `python src/prediccion_semanal.py` | Modelo por plazo (1 a 4 semanas): validación año por año y `dashboard/data/prediccion_semanal.json` (`--sin-anio 2017` para la sensibilidad) |
| `python src/modelo_inundacion.py` | Reentrena y evalúa el modelo de emergencias (Y del SINPAD; `--fuente desinventar` para la versión anterior) |
| `python src/ml_evaluacion.py` | Bootstrap por años, calibración y falsos negativos |
| `python src/auditoria.py` | Regenera `docs/evidencia/auditoria_cifras.json` |
| `python src/aviso_lluvia.py` | Recalcula el aviso de lluvia por distrito |
| `python src/noticias.py` | Inundaciones reportadas en noticias (Google Noticias + catálogo verificado), con su verificación por radar; corre cada día |
| `python src/vivienda_inei.py` | Viviendas del Censo 2025 por distrito: zona inundable, materiales y radar → `viviendas_censo.json` (necesita los archivos del INEI en `datos_inei/manzana/`; no se suben) |
| `python src/validar_radar.py` | Compara el radar y la zona inundable con el mapa oficial de Copernicus 2017 |
| `python src/modelo_afectados.py` | Modelo de viviendas afectadas con el SINPAD (INDECI) |
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

NOAA OISST v2.1 y CPC (dominio público) · IGP ICEN · Open-Meteo y GloFAS v4 (CC BY 4.0) · JRC CEMS-GloFAS flood hazard v2 (CC BY 4.0) · Copernicus Sentinel-1 vía Microsoft Planetary Computer · WorldPop 2026 (CC BY 4.0) · Google Open Buildings v3 (CC BY 4.0 / ODbL) · RENIPRESS, SUSALUD (datos abiertos) · OpenStreetMap (ODbL, © colaboradores de OSM) · DesInventar/INDECI · tabla UBIGEO de `jmcastagnetto/ubigeo-peru-aumentado` (MIT; pobreza 2018 INEI e IDH 2019 PNUD según el compilador) · SINPAD del INDECI (datos abiertos, ODC-By) · límites distritales del INEI (Infraestructura de Datos Espaciales, capa Distrito: 78 distritos con UBIGEO; el portal no declara licencia, se cita la fuente). El detalle por capa está en `dashboard/data/metadatos.json`.

Equipo: Christopher, Maykol, Marcia y Luz Ángela.
