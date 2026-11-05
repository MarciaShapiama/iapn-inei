# Informe final · Proyecto integrador PEU Ciencia de Datos (INEI)

## Exposición potencial a inundaciones asociadas a El Niño en Tumbes y Piura: un tablero estadístico reproducible por UBIGEO

**Equipo:** Christopher, Maykol, Marcia y Luz Ángela · **Fecha:** 4 de noviembre de 2026
**Repositorio:** `MarciaShapiama/iapn-inei` · **Tablero:** https://marciashapiama.github.io/iapn-inei/ · **Documentos de soporte:** `docs/01` a `docs/05` y `docs/evidencia/`

---

## Resumen ejecutivo (dos páginas)

**Problema.** Piura y Tumbes sufren inundaciones recurrentes con El Niño (1983, 1998, 2017) y con eventos como el ciclón Yaku (2023). Las autoridades necesitan saber **dónde** y **cuánta** población, edificaciones, colegios y establecimientos de salud quedarían expuestos, con cifras cuyo origen se pueda revisar.

**Qué hicimos.** Partimos del tablero del equipo, que ya integraba el peligro JRC, el radar Sentinel-1, WorldPop, Open Buildings, colegios, salud, el mar y la lluvia. Lo **auditamos** (doc 01) y construimos un **MVP reproducible**:

1. ETL con reintentos, registro de fallos y conservación del último resultado válido.
2. Metadatos y estado por capa: `vigente`, `rezagado`, `no disponible` o `estimado`.
3. Cifras por **UBIGEO** que concilian con el total.
4. **Mapa 2D sin GPU** con selectores (departamento, provincia, distrito, ámbito de cuenca), comparador temporal del radar y descargas CSV/GeoJSON.
5. **Panel de decisiones** con peligro, exposición, vulnerabilidad y riesgo estimado separados.
6. **38 pruebas automáticas** y un flujo de GitHub Actions que corre las pruebas antes de guardar.

**Hallazgos de la auditoría que cambian cifras publicadas.**

- **Población desplazada unos 7,9 km al oeste** por un error de recorte del ráster WorldPop. Esto alteraba todas las cifras de población por distrito y por evento. Corregido y verificado contra la densidad de edificaciones (fuente independiente): correlación 0,00 antes y 0,80 después. Consecuencias: la población dentro de la mancha de 2023 pasó de 4.756 a **62**; la zona 1/100 pasó de 416.612 a **408.970**.
- **Conteos de colegios y salud:** eran anillos que no se superponen, pero se rotulaban como acumulados. Hasta 1 km hay **2.636 colegios**, no 684.
- **Suma de Piura + Tumbes:** faltaban **4.138 edificaciones** fuera de los polígonos distritales. Ahora se informan como «sin distrito asignado».
- **Capa de radar «últimos 24 días»:** su periodo de referencia se solapaba con el evento. Se corrigió el código y se **recalculó la capa** con Sentinel-1 (27,2 km² de agua nueva en tierra, sobre todo en Sechura; estado vigente).
- **«Viviendas»** eran huellas de edificación de cualquier uso. Ahora se rotulan **edificaciones**.

**Cifras principales (zona inundable de 1 en 100 años, JRC; exposición potencial, no afectados).** 5.594 km²; **408.970 personas** (WorldPop, modelada); **152.486 edificaciones**; **684 colegios** y **146 establecimientos de salud** dentro de la mancha (2.636 y 577 hasta 1 km). Distritos con prioridad alta de revisión según el índice relativo: La Arena, Bernal, La Unión, El Tallán, Colán, Cura Mori, Cristo Nos Valga, Tambo Grande, Catacaos, entre otros (15 de 76).

**Machine learning.** Reproducimos el modelo de alerta del equipo (emergencia en las próximas 4 semanas, 75 distritos, validación por años 2008–2015) con métricas idénticas. La logística simple (PR-AUC 0,114) **probablemente** supera a la climatología (0,095), pero el intervalo de confianza de la diferencia incluye el cero (**[−0,003; 0,039]**). LightGBM no supera la línea base. Las probabilidades sin calibrar no deben leerse como probabilidades. El modelo captura el 46 % de las emergencias de Tumbes y **solo el 5 % de las de Piura**. Para susceptibilidad espacial y clasificación SAR **no entrenamos**: no hay etiquetas independientes.

**Aporte al INEI.** Una estadística territorial de **población y edificaciones potencialmente expuestas por UBIGEO**, con metadatos, diccionario y periodicidad, que puede integrarse al Sistema Estadístico Nacional. El INEI produce estadística; las alertas y las obras corresponden a otras entidades.

**Políticas.** Siete opciones para evaluar (doc 05): continuidad educativa y de salud, ordenamiento territorial, mantenimiento focalizado de drenes, rutas y refugios, comunicación de riesgo y levantamiento de datos.

**Limitaciones principales.** El JRC es un escenario (90 m, sin defensas ni inundación pluvial). El radar subdetecta en ciudades (Catacaos 2017: 1,1 km²). La población es modelada. Faltan 2 distritos en los límites usados. Los colegios no vienen del padrón oficial. El umbral adaptativo del radar está implementado, pero aún no se eligió con una referencia independiente.

---

## 1. Planteamiento

**1.1 Problema de investigación.** No existe en un solo lugar una cuantificación territorial, reproducible y desagregada por distrito de cuánta población, cuántas edificaciones y qué servicios esenciales quedan en zonas inundables o en áreas inundadas en eventos recientes en Tumbes y Piura, con la incertidumbre y la procedencia de cada cifra.

**1.2 Pregunta.** ¿Cuánta población, cuántas edificaciones, colegios y establecimientos de salud de Tumbes y Piura están potencialmente expuestos a inundación fluvial (escenarios de 10 y 100 años) y a las inundaciones detectadas por radar en 2017 y 2023? ¿Qué distritos deberían revisarse primero considerando a la vez peligro, exposición y vulnerabilidad?

**1.3 Objetivo general.** Construir y validar un sistema reproducible de indicadores de exposición a inundaciones por UBIGEO para Tumbes y Piura, publicado como tablero estático con metadatos y pruebas.

**1.4 Objetivos específicos.**
1. Auditar el tablero existente y corregir errores de cálculo y rotulado.
2. Calcular la exposición por distrito, dentro de la mancha y en acumulados hasta 500 m y 1 km, conciliada con el total.
3. Documentar la fuente, la definición, la vigencia y el estado de cada capa.
4. Ofrecer un mapa usable sin aceleración gráfica y descargas abiertas.
5. Evaluar con rigor si el machine learning mejora una línea base simple.
6. Proponer un aporte estadístico al INEI y opciones de política pública.

**1.5 Preguntas analíticas (en lugar de hipótesis causales).**
- H1: la exposición se concentra en el Bajo Piura y en la cuenca baja del Tumbes. → **Se confirma** (doc 05, P3).
- H2: el radar con umbral fijo subestima la inundación urbana. → **Se confirma** (Catacaos 2017).
- H3: un modelo con lluvia, caudal y mar supera a la climatología para anticipar emergencias. → **No se demuestra** con 8 años de prueba.

**1.6 Alcance y delimitación.** Tumbes y Piura (76 distritos GADM; 78 según el INEI). Inundación fluvial (JRC) y agua detectada por radar. Exposición actual (población 2026, edificaciones v3). **Fuera del alcance:** inundación pluvial urbana, huaicos, daños y pérdidas, alertas oficiales y el resto del Perú (fase P3).

## 2. Qué existe y qué aporta este trabajo

| Recurso | Qué ofrece | Qué agrega este proyecto |
|---|---|---|
| SIGRID / CENEPRED | Escenarios y estudios oficiales de riesgo | No los reemplaza. Agrega cifras por UBIGEO con método abierto y comparable entre distritos (no integramos SIGRID en esta entrega) |
| SENAMHI | Avisos y datos observados | El tablero enlaza y diferencia «modelado» de «observado» |
| INDECI / COEN | Registro de daños | Exposición **antes** del evento; no estima daños |
| Tablero del equipo (inicio) | Mapa 3D atractivo con muchas capas | Cifras corregidas, trazabilidad, pruebas, mapa 2D y panel de decisiones |
| Monitor complementario (Maykol) | Lluvia, Sentinel-2 antes/después, agua SAR a −18 dB | Comparación metodológica del umbral SAR (doc 01 §4.5); no se modificó |

**Beneficiarios:** gobiernos regionales y municipalidades, DRE/UGEL, DIRESA, el INEI y la academia. **Sostenibilidad:** costo cero (GitHub Pages + Actions y fuentes abiertas), código documentado y pruebas automáticas.

## 3. Método

### 3.1 Arquitectura y flujo de datos

```
Fuentes abiertas ──► src/etl.py (perfiles diario / inundacion / local)
  NOAA OISST, CPC, IGP        descargar_*.py ──┐
  Open-Meteo, GloFAS                           ├─► construir.py ─► dashboard/data/{mar,zonas,…}.json
  WorldPop, Open Buildings     exposicion.py ─► reparar_poblacion.py ─► ubigeo.py
  RENIPRESS, OSM, GADM, JRC                                            │
  Sentinel-1 (Planetary C.)    huellas.py ─────────────────────────────┤
                                                                       ▼
                               impacto.py ─► inundacion.json, capa_*.geojson, descargas/exposicion_distritos.csv
                               panel.py   ─► panel_distritos.json, descargas/panel_distritos.csv
                               metadatos.py ─► metadatos.json (estado por capa)
                               auditoria.py ─► docs/evidencia/auditoria_cifras.json
  registro: data/registro/*.json · versiones: data/versiones/manifiesto.csv (SHA-256)
  pruebas: tests/ (pytest) ─► GitHub Actions «Pruebas» ─► Pages (index.html 3D + mapa2d.html 2D)
```

### 3.2 Unidad de análisis y variables

- **Unidad:** distrito (UBIGEO INEI), píxel (ráster) y local (punto).
- **Exposición:** población WorldPop × fracción de la celda dentro de la mancha; edificaciones cuyo centro cae dentro.
- **Distancia:** transformada euclidiana en metros desde el borde de la mancha; clases dentro, 0–500 m y 500 m–1 km, y acumulados.
- **Peligro:** porcentaje del área distrital en la zona 1/100.
- **Vulnerabilidad:** porcentaje de pobreza monetaria 2018.
- **Riesgo estimado:** promedio de los percentiles de las tres dimensiones.
- **Radar:** VV con detección de cambios frente a la temporada seca, con máscaras DEM y de agua permanente (doc 01 §4.5).

### 3.3 Validación estadística

- Conciliación de sumas (prueba automática).
- Monotonía de los acumulados.
- Alineación de la población con las edificaciones (correlación espacial).
- Población WorldPop por distrito frente a la estimación 2020: razón entre 0,85 y 1,10 en los distritos de más de 40 mil habitantes, salvo Piura (1,75), que absorbe a Veintiséis de Octubre.
- **Las estimaciones modeladas se distinguen siempre de las oficiales.** No hubo acceso a las proyecciones distritales oficiales del INEI en esta entrega.

### 3.4 Limitaciones

Ver doc 01 §5 y §6. Las principales: el JRC no es un pronóstico; el radar no es verdad-terreno; la población es modelada; los límites son GADM (licencia y distritos faltantes); los colegios vienen de OSM.

## 4. Machine learning (síntesis del doc 02)

| Caso | Decisión | Por qué |
|---|---|---|
| A. Susceptibilidad espacial | No entrenar todavía | Sin etiquetas independientes; entrenar con el JRC o con el radar propio reproduce su sesgo |
| B. Clasificación SAR | No entrenar todavía; Otsu implementado como diagnóstico | Falta una referencia óptica o de campo; diseño de validación listo |
| C. Emergencia distrito-semana | Reproducido y ampliado | Hay etiquetas 2001–2015. Logística simple 0,114 frente a climatología 0,095 (IC de la diferencia [−0,003; 0,039]); LightGBM 0,082 |

## 5. Aporte, políticas, bibliografía, riesgos y ética

- **Aporte al INEI:** doc 03. Indicador principal: población potencialmente expuesta a la zona 1/100 por UBIGEO (408.970 en total; Catacaos 85 % de su población modelada).
- **Políticas:** doc 05 (P1–P7).
- **Bibliografía:** doc 04 (21 referencias: 19 artículos arbitrados, incluido Otsu (1979); 1 en actas de congreso y 1 preprint; 20 DOI verificados en Crossref y el preprint en arXiv).
- **Ética de datos:**
  - no usar «damnificados» ni «afectados» para la exposición;
  - no publicar datos personales;
  - la vulnerabilidad fina solo se publicaría agregada y respetando el secreto estadístico;
  - el índice de riesgo es relativo y **no autoriza reubicaciones**;
  - la licencia GADM impide redistribuir los polígonos: el mapa 2D no los ofrece para descargar y se recomienda cambiar a límites oficiales.

## 6. Evidencia técnica

| Comando | Resultado |
|---|---|
| `python src/etl.py local` | 4/4 pasos OK (impacto 22,4 s) |
| `python src/reparar_poblacion.py` | 86 columnas, r = 0,798; segunda corrida «ya alineado» |
| `python -m pytest -q` | **38 passed** (`docs/evidencia/pytest_salida.txt`, `pytest_detalle.txt`) |
| `python src/modelo_inundacion.py` | Métricas idénticas a las documentadas por el equipo |
| `python src/ml_evaluacion.py` | Bootstrap, calibración y falsos negativos (`docs/evidencia/ml_evaluacion.json`) |
| Crossref API | 20/20 DOI con HTTP 200 (`docs/evidencia/crossref_verificacion.txt`) |
| Recorrido en el navegador | Piura → Catacaos → Radar 2017 → metadatos → CSV/GeoJSON; móvil 375 px; `?sin3d=1` (doc 01 §9) |

No hay capturas de pantalla en el repositorio: no se pidió autorización para guardarlas.

## 7. Hoja de ruta

| Prioridad | Tarea | Esfuerzo | Depende de | Responsable sugerido | Criterio de aceptación |
|---|---|---|---|---|---|
| **P0** | Proponer los cambios del fork al repositorio del equipo (pull request) | 0,5 d | revisión del equipo | Marcia | PR fusionado; el sitio del equipo muestra `mapa2d.html` |
| P0 | Volver a correr `base_modelo.py` completo (con red) | 0,5 d | — | Luz Ángela | Pruebas pasan; métricas registradas |
| P0 | Quitar `__pycache__` versionado; dibujar gráficos D3 al mostrar la pestaña (E14) | 0,5 d | — | Maykol | Sin errores en la consola |
| **P1** | Límites distritales oficiales INEI/IGN (78 distritos) | 2 d | pedido al INEI | equipo + INEI | 78 UBIGEO; prueba de cobertura |
| P1 | Padrón ESCALE georreferenciado | 1 d | descarga MINEDU | Luz Ángela | Colegios con código modular; sin locales de Ecuador |
| P1 | Validación con Censo 2017 / proyecciones INEI por distrito | 2 d | datos INEI | Marcia | Tabla de razones WorldPop/oficial publicada |
| P1 | Integrar avisos SENAMHI, estaciones ANA y escenarios SIGRID | 3 d | acceso y licencias | Maykol | Capas con metadatos y estado |
| **P2** | Caso B: referencia independiente 2017/2023 y comparación de umbrales | 5 d | imágenes ópticas | Christopher | IoU/F1 por estrato frente a la línea base |
| P2 | Caso A: HAND, WorldCover y validación por cuenca | 5 d | P2-B | equipo | PR-AUC y recall de la clase inundada con test final intocado |
| P2 | Caso C: emergencias fechadas 2016–2026 y caudal observado | 3 d | SINPAD, ANA | Luz Ángela | Validación en 2017/2023 con etiquetas |
| **P3** | Extender a la costa norte y luego a todo el Perú | 10 d o más | P1 | equipo | Mismas pruebas por departamento |

## 8. Preguntas probables del jurado

1. **¿Cómo sé que las cifras no son inventadas?** Cada cifra sale de un script versionado. `python src/etl.py local` las vuelve a calcular; `pytest` comprueba sumas, acumulados y alineación; `metadatos.json` dice de dónde viene cada capa.
2. **¿Por qué cambió la población respecto de la versión anterior?** Por un error de recorte del ráster WorldPop (~7,9 km al oeste). Lo demostramos con una fuente independiente: la correlación con la densidad de edificaciones pasa de 0,00 a 0,80 (`reparar_poblacion.py`, `docs/evidencia/cifras_antes_despues.csv`).
3. **¿408.970 personas se inundarán?** No. Es población **potencialmente expuesta** a un escenario con 1 % de probabilidad anual. No es un pronóstico ni un conteo de afectados.
4. **¿Por qué 2023 tiene 728 km² y casi nadie expuesto?** El 86 % de la mancha está en el desierto de Sechura. El radar además subdetecta en ciudades.
5. **¿Por qué no usaron deep learning?** Con 311 casos positivos, LightGBM ya se sobreajusta. Las LSTM se justifican con miles de cuencas (Nearing et al., 2024).
6. **¿El modelo de alerta funciona?** Ordena bien los años (2017 primero y 2023 segundo), pero no demuestra mejora significativa sobre la climatología y casi no captura las emergencias de Piura (5 %). No debe usarse como alerta.
7. **¿Qué gana el INEI?** Un indicador territorial reproducible por UBIGEO, con metadatos y periodicidad, listo para interoperar con CENEPRED, MINEDU y MINSA.
8. **¿Y si falla una fuente?** `etl.py` registra el fallo, conserva el último resultado válido y lo rotula `rezagado`. Las pruebas impiden guardar cifras incoherentes.
9. **¿El índice de riesgo reemplaza a CENEPRED?** No. Es un orden relativo entre 76 distritos para priorizar revisiones.

## 9. Estado por requisito

| Requisito | Estado | Evidencia | Notas |
|---|---|---|---|
| Inspección y síntesis | Hecho | doc 01 §2 | — |
| Auditoría técnica (`docs/01`) | Hecho | archivo + `auditoria.py` | — |
| Coherencia dentro ≤ 500 m ≤ 1 km | Hecho | `test_acumulados_monotonos` | — |
| Suma subregiones = total | Hecho | `test_suma_de_departamentos_igual_al_total` | — |
| Caso 2023 verificado | Hecho | doc 01 §4.3 | Además se encontró y corrigió E1 |
| Rótulo edificaciones / exposición | Hecho | `test_sin_rotulos_engañosos` | — |
| Unidades, ICEN, fechas Lima/UTC | Parcial | doc 01 §4.6 | No verifiqué el comunicado ENFEN vigente |
| Mapa 2D sin WebGL | Hecho | recorrido; `test_respaldo_sin_webgl_presente` | Simulado con `?sin3d=1`; sin probar en una máquina real sin GPU |
| ETL reproducible con reintentos, registro y degradación | Hecho (local) / Parcial (en línea) | `etl.py`, `test_descargar_*` | Perfiles `diario` e `inundacion` no ejecutados aquí (necesitan red y varios GB) |
| Metadatos y estado por capa | Hecho | `metadatos.json`, `test_metadatos_completos` | — |
| Mapa usable: selectores, escenarios, capas, leyenda, escala, filtros, descargas, móvil | Hecho | recorrido doc 01 §9 | «Cuenca» = agrupación aproximada de distritos, no límites ANA |
| Cifras por UBIGEO, anillos y acumulados | Hecho | `exposicion_distritos.csv`, `test_csv_por_distrito_concilia` | — |
| Validación contra totales INEI | Parcial | `test_poblacion_distrital_plausible` | Se usó una estimación 2020 de terceros, no la proyección oficial |
| Comparador temporal del radar | Hecho | `mapa2d.html` | — |
| Umbral adaptativo | Parcial | `huellas.otsu`, `test_otsu_*` | Implementado; no se volvió a procesar Sentinel-1 |
| Panel de decisiones | Hecho | `panel_distritos.json`, `test_panel_dimensiones_separadas` | — |
| Pruebas y CI | Hecho (local) | 38 passed; `pruebas.yml` | Workflows sin ejecutar en GitHub (sin push) |
| Smoke test del sitio desplegado | Parcial | `test_sitio.py` con `IAPN_URL_SITIO` | Solo contra el servidor local |
| Plan de ML (`docs/02`) y experimento | Hecho | `ml_evaluacion.json` | Casos A y B no entrenados (justificado) |
| Aporte al INEI (`docs/03`) | Hecho | archivo | — |
| Bibliografía (`docs/04`) | Hecho | `crossref_verificacion.txt` | Detalles de 4 trabajos recientes solo desde el resumen |
| Políticas públicas (`docs/05`) | Hecho | archivo | — |
| Informe final (Markdown) | Hecho | este archivo | — |
| Informe en Word | Hecho | `INFORME_FINAL_PROYECTO_INTEGRADOR.docx` | Generado con `herramientas/documentos/md_a_docx.py`; índice actualizado en Word |
| Informe de avance para el docente (LaTeX) | Hecho | `docs/6_presentacion/avance_latex/avance_proyecto.tex` y `.pdf` | 10 páginas; figuras en `docs/6_presentacion/avance_latex/figuras/` |
| README actualizado | Hecho | `README.md` | — |
| Recálculo del radar «vivo» | Hecho | `data/huellas/vivo.json`, `metadatos.json` | 27,2 km²; estado vigente |
| Commit y push de la rama | Hecho | rama `auditoria-mvp-piloto` en GitHub; workflow «Pruebas» en verde | — |
| Publicación en GitHub Pages | Hecho | https://marciashapiama.github.io/iapn-inei/ | Fork del repositorio del equipo; falta proponer los cambios al original con un pull request |

**Problemas abiertos:** llevar los cambios al repositorio del equipo; límites oficiales; padrón ESCALE; licencia GADM; validación independiente del radar; emergencias después de 2015.

**Tres próximos pasos:**
1. Proponer los cambios al repositorio del equipo con un pull request desde el fork.
2. Conseguir los límites oficiales del INEI y el padrón ESCALE.
3. Construir la referencia independiente 2017/2023 para los casos A y B.
