# 22 · Auditoría crítica: lo que el jurado va a preguntar

*6 de noviembre de 2026. Todo con el repositorio después de las partes 1 (mapa de 78 distritos) y 4 (modelo por plazo). Cada cifra sale de un archivo que se nombra al lado.*

## 1. ¿El modelo aprende o no?

El repositorio tiene tres modelos. Cada uno responde una pregunta distinta, y no aprenden lo mismo.

| Modelo | Pregunta | ¿Le gana a la climatología del distrito y su mes? | Evidencia |
|---|---|---|---|
| **Alerta** (`src/modelo_inundacion.py`) | ¿Habrá alguna emergencia en las próximas 4 semanas? | **No.** Logística 0,369 contra 0,394 de la climatología (PR-AUC, 2008-2025). LightGBM, 0,393: empata. La logística supera a la climatología solo con 14 % de probabilidad (bootstrap por años) | `data/modelo/resultados/metricas_resumen.csv`, `docs/evidencia/ml_evaluacion.json` |
| **Por plazo** (`src/prediccion_semanal.py`) | ¿Habrá emergencia exactamente en la semana t+h? | **Sí a 1 semana, poco a 2 y 3, no a 4.** Con todas las semanas juntas: 0,227 contra 0,161 a 1 semana. Año por año: 0,185 contra 0,168 (gana 12 de 18 años) a 1 semana y 0,164 contra 0,167 (8 de 18) a 4 semanas | `data/modelo/resultados_plazo/metricas_por_plazo.csv`, `metricas_por_anio.csv` |
| **Viviendas** (`src/modelo_afectados.py`, dos etapas) | ¿Cuántas viviendas afectadas habrá en la semana? | **En detectar la semana, sí:** PR-AUC 0,170 contra 0,117 de la climatología (promedio 2012-2025). **En la cantidad, no:** se queda corto en los años extremos (−41 % en 2017 y −74 % en 2023) | `data/modelo/resultados_afectados/metricas_resumen.csv`, `ranking_2017_2023.csv` |

**¿Le gana a una regla simple?** Sí. Para la semana siguiente (modelo por plazo, h = 1):

| Regla o modelo | PR-AUC |
|---|---|
| Logística con las variables del aviso | **0,227** |
| Climatología del distrito y su mes | 0,161 |
| «Mes del año» | 0,131 |
| «Hubo emergencia la semana pasada» | 0,103 |
| «Hubo un día de lluvia sobre p95 la semana pasada» | 0,096 |
| Tasa sin modelo | 0,031 |

**Excepción:** en 2023, con todo el norte inundado en marzo, «mes del año» (0,395) y la climatología (0,383) le ganan al modelo (0,371). En los años extremos la estación ya lo dice casi todo. Fuente: `metricas_por_plazo.csv`, columna `pr_auc_2023`.

**¿Hay fuga de información?**

| Modelo | Revisión | Resultado |
|---|---|---|
| Alerta | Variables de la semana t, etiqueta de t+1 a t+4. Se quitan las 4 últimas semanas del entrenamiento antes de cada año de prueba. La frecuencia histórica y la climatología salen solo del entrenamiento | Sin fuga. Anacronismo: la exposición (2026) se usa en semanas de 2003-2025 (la versión simple no la usa) |
| Por plazo | Tres pruebas automáticas (`tests/test_prediccion_semanal.py`): el objetivo es t+h; cambiar el futuro no cambia las variables de t; la historia no depende del año de prueba. El código comprueba que el entrenamiento termine antes que la prueba | Sin fuga. Anacronismo del censo y la zona inundable. «Emergencia en la semana t» no se conoce en tiempo real |
| Viviendas | Variables dinámicas de la semana anterior (`_l1`); historia solo con los años de entrenamiento; partición por años | Una fuga menor: `matriz()` rellena los datos faltantes con la mediana del **conjunto de prueba**, no del entrenamiento. No usa la etiqueta, pero conviene cambiarlo. Anacronismo del censo 2025 |

**¿Cuánto depende de 2017?** Se repitió el modelo por plazo sin entrenar nunca con 2017 (`python src/prediccion_semanal.py --sin-anio 2017`), comparando en los mismos años de prueba:

| Plazo | PR-AUC medio por año: con 2017 | sin 2017 | PR-AUC 2023: con 2017 | sin 2017 | Viviendas 2023: con 2017 | sin 2017 |
|---|---|---|---|---|---|---|
| 1 semana | 0,177 | 0,176 | 0,371 | 0,352 | −67 % | −81 % |
| 2 semanas | 0,166 | 0,166 | 0,412 | 0,398 | −74 % | −88 % |
| 3 semanas | 0,161 | 0,161 | 0,384 | 0,357 | −80 % | −92 % |
| 4 semanas | 0,156 | 0,157 | 0,370 | 0,354 | −84 % | −93 % |

Sin 2017, el modelo ordena casi igual las semanas y los distritos. Lo que pierde es la escala: 2017 es el único año extremo antes de 2023, y sin él la estimación de viviendas de 2023 empeora de −67 % a −81 %.

## 2. ¿De dónde sale cada dato y está bien?

| Fuente | Qué es | Quién la produce | Fecha o versión | Resolución | Cómo se descarga | Sesgos conocidos | Control hecho | Control que falta |
|---|---|---|---|---|---|---|---|---|
| **JRC** flood hazard v2 | Zona inundable y profundidad, crecidas de 1 en 10 y 1 en 100 años | Comisión Europea, JRC (CEMS-GloFAS) | v2; sin actualización periódica | ~90 m | Teselas GeoTIFF del FTP del JRC (`src/exposicion.py`) | Solo ríos grandes; no ve lluvia urbana, quebradas ni defensas; incluye la depresión de Sechura (laguna La Niña) | La zona de 1 en 100 años cubre el 84,5 % del área inundada que cartografió Copernicus EMSR199 en Piura en 2017 (`dashboard/data/validacion_2017.json`). Con 78 distritos, ρ = 0,41 entre edificaciones en la zona y afectados por inundación de INDECI 2003-2024; 10 de los 15 distritos con más afectados coinciden (`docs/evidencia/validacion_indeci.json`) | Comparar con CENEPRED/SIGRID |
| **WorldPop** 2026 R2025A | Población modelada | WorldPop (U. de Southampton) | R2025A v1, año 2026 | 100 m | GeoTIFF de data.worldpop.org | Modelo: reparte totales nacionales con covariables | Alineada con Open Buildings (r = 0,80 tras corregir 7,9 km de desplazamiento; doc 01). Zona de 1 en 100 años: 400 198 personas contra 407 877 del Censo 2025 (1,9 % de diferencia) | Comparación por distrito con 78 (Marcia) |
| **Open Buildings** v3 | Huella de cada edificación | Google Research | v3, imágenes hasta 2023 | Edificación | GeoParquet de VIDA (source.coop) | Cualquier uso; sin construcciones posteriores a 2023 | Coincide en posición con WorldPop | Muestra revisada en imágenes |
| **ESCALE** | Locales escolares y matrícula | MINEDU | Padrón 30/10/2026; Censo Educativo 2025 | Punto | CSV guardado a mano (ESCALE bloquea descargas automáticas) | Coordenadas declaradas; 4 % sin matrícula | Un local cuenta una vez (doc 07) | Revisar en campo los del borde de la zona |
| **RENIPRESS** | Establecimientos de salud | SUSALUD | Corte 30/09/2026 | Punto | CSV de datos abiertos | Coordenadas declaradas | Filtro por estado ACTIVO y categoría | Verificar los 146 dentro de la zona |
| **Sentinel-1** | Agua detectada por radar | ESA (Copernicus), vía Planetary Computer | RTC; pasa cada 6 a 12 días | ~55 m tal como se procesa | `src/huellas.py`, `src/satelite.py` | No ve agua entre edificios ni bajo vegetación; marca arena y salinas; llega días tarde | Contra EMSR199 (2017): detecta el 41,7 % del área inundada y el 63,4 % de lo que detecta es correcto. Contra 13 eventos con noticias: 4 de 13 (doc 09) | No entra a ningún modelo |
| **GloFAS** v4 | Caudal diario modelado (Piura, Chira, Tumbes) | Copernicus EMS (ECMWF), vía Open-Meteo | v4; 1984-hoy | ~5 km | `src/base_modelo.py`, `src/aviso_lluvia.py` | Simulado; Zarumilla sin celda con dato | p95 y p99 2001-2020. Caudal sobre p95: 65,7 % de las semanas con inundación de los distritos de río tuvieron aviso (`docs/evidencia/prueba_aviso_pasado.json`, 78 distritos) | Contrastar con estaciones de ANA y SENAMHI |
| **Open-Meteo y ERA5** | Pronóstico de lluvia a 7 días y normales 1991-2020 | Open-Meteo; ERA5 de ECMWF | API v1 | Punto (~11 km); ERA5 ~25 km | `src/aviso_lluvia.py` | Modelo, no pluviómetro; el umbral es por provincia | Con pronósticos reales, 9 de 10 eventos tuvieron aviso 1 a 3 días antes (doc 18) | Contrastar con estaciones SENAMHI |
| **NASA POWER** | Lluvia diaria por distrito, entra a los modelos | NASA Langley (PRECTOTCORR) | API diaria, 2001-hoy | ~50 km | `src/base_modelo.py` | Distritos vecinos comparten serie (Veintiséis de Octubre y Salitral de Sullana tienen la misma). El 2/11/2026 marcó 9 mm en Tumbes; el SENAMHI midió 110 mm en El Salto (doc 18) | Umbrales p95 y p99 del mismo dato | Estaciones SENAMHI: es lo que más mejoraría los modelos |
| **SINPAD** | Emergencias por distrito y fecha, con daños | INDECI | 2003-2025 y 2026-I; actualizado el 30/10/2026; semestral | Distrito, día | `src/etiqueta_sinpad.py` (SHA-256 y conteos en `data/modelo/sinpad/procedencia.json`) | Depende del reporte municipal; la fecha es la del registro; «lluvia intensa» mezcla daños por lluvia con desbordes; 2026-I con una columna mal llenada | 6 de 6 eventos verificados de 2017 y 2023 tienen registro a menos de 14 días (`docs/evidencia/auditoria_sinpad.json`); 2017: 85 960 viviendas afectadas contra 85 743 del informe OCHA/INDECI, 0,3 % de diferencia (doc 10) | Revisar a mano la muestra de 20 registros; preguntar al INDECI por el reparto Piura/Tumbes de 2017 |
| **Censo 2025** | Viviendas, materiales y personas por manzana y centro poblado | INEI | Entregas del 4 y 6/11/2026 | Manzana | Confidencial; `src/vivienda_inei.py` (Marcia) | Centros poblados solo como punto | Sumas de sexo y edad cuadran; manzanas iguales entre entregas (doc 17) | Volver a correr con el mapa de 78 (ver §3) |
| **Google Noticias** | Inundaciones reportadas en prensa | Medios, vía RSS | Diario | Lugar del titular | `src/noticias.py` | No oficial; ubicación por nombre | Catálogo verificado de 13 eventos con enlace | Solo cubre los días que el SINPAD aún no publica |
| **Límites distritales** | 78 distritos con UBIGEO | INEI, IDE (capa Distrito) | `fec_reg` 22/07/2022 | Polígono simplificado | WFS del INEI (`src/exposicion.py`) | El portal no declara licencia | 78/78 UBIGEO; totales casi iguales a los de GADM (doc 20) | Confirmar la licencia con el INEI |

## 3. ¿Hay que volver a correr algo?

**Ya se volvió a correr con el mapa de 78 distritos** (partes 1 y 4):

- `exposicion.py` (distritos), `impacto.py`, `panel.py`, `aviso_lluvia.py`, `construir.py` y `metadatos.py`;
- `etiqueta_sinpad.py`, `base_modelo.py`, `modelo_inundacion.py`, `ml_evaluacion.py`, `modelo_afectados.py` y `prediccion_semanal.py`;
- `auditoria_sinpad.py`, `validacion_indeci.py`, `prueba_aviso_pasado.py` y `auditoria.py`.

**Queda desactualizado:**

| Qué | Por qué | Quién o qué necesita |
|---|---|---|
| `src/vivienda_inei.py` → `viviendas_censo.json` | Toma los nombres con tilde del mapa; con el mapa nuevo pueden cambiar algunos nombres (no las cifras, que van por UBIGEO) | Marcia (datos del INEI) |
| `src/cruce_habitantes.py` | Ya no une Veintiséis de Octubre ni Canoas de Punta Sal | Marcia (datos del INEI) |
| `herramientas/pruebas/prueba_aviso_temporada.py` (doc 18, prueba C) | Sus pronósticos guardados son de 76 puntos; se dejó con el mapa anterior a propósito | Red y miles de consultas a Open-Meteo |
| Doc 18, prueba B | `prueba_aviso_pasado.json` ya se recalculó con 78 distritos; el texto del doc aún tiene las cifras anteriores (detección con p95: 30 % → 30,2 %; caudal: 65 % → 65,7 %) | Editar el doc |
| Doc 06 | ρ con afectados por inundación: 0,38 → 0,41; top 15: 9 → 10 | Editar el doc |
| Doc 10 | Modelo de viviendas con 78: PR-AUC 0,175 → 0,170; top 10 en 2017: 5 → 4; en 2023: 7 → 6 | Editar el doc |
| Doc 02 y `modelo_inundacion.md` | Todavía citan las cifras de DesInventar (0,114 frente a 0,095) | Editar con las del SINPAD (doc 19) |
| Informe final, doc 15 y presentaciones | Cifras del mapa de 76 y de DesInventar | Editar al final, con las cifras ya cerradas |
| `data/modelo/sinpad_tumbes_piura_semanal.csv` (de `modelo_afectados.py`) y `data/modelo/sinpad/sinpad_semanal.csv` (de `etiqueta_sinpad.py`) | Son dos resúmenes del mismo SINPAD hechos por scripts distintos | Que `modelo_afectados.py` lea la salida de `etiqueta_sinpad.py` |

**Orden para volver a correr todo:**

1. `python src/exposicion.py --forzar` (solo distritos si ya están los rásteres)
2. `python src/impacto.py`
3. `python src/panel.py`
4. `python src/aviso_lluvia.py`
5. `python src/construir.py`
6. `python src/metadatos.py`
7. `python src/etiqueta_sinpad.py`
8. `python src/base_modelo.py`
9. `python src/modelo_inundacion.py`
10. `python src/ml_evaluacion.py`
11. `python src/modelo_afectados.py`
12. `python src/prediccion_semanal.py`
13. `python herramientas/pruebas/auditoria_sinpad.py`, `herramientas/pruebas/validacion_indeci.py`, `herramientas/pruebas/prueba_aviso_pasado.py` y `python src/auditoria.py`
14. Marcia: `src/vivienda_inei.py` y `src/cruce_habitantes.py`
15. Con red: `herramientas/pruebas/prueba_aviso_temporada.py`
16. `python -m pytest -q`

## 4. ¿Qué mejorar primero?

Ordenado pensando en el 15 de noviembre.

| # | Mejora | Impacto | Esfuerzo | ¿Antes del 15? | Por qué (dato o trabajo) |
|---|---|---|---|---|---|
| 1 | Presentar el modelo por plazo como **índice para priorizar** distritos a 1-2 semanas, no como alerta | Alto | Bajo | **Sí** | Es donde le gana a la climatología (0,185 contra 0,168 año por año, 12 de 18 años). Merz et al. (2020) y Coughlan de Perez et al. (2016): un aviso basado en impacto debe decir para qué plazo sirve y con qué tasa de aciertos y falsas alarmas |
| 2 | Agregar la climatología como variable del modelo de alerta (logit de la climatología + lluvia + caudal + Niño 1+2) | Medio | Bajo | **Sí, como prueba** | En la prueba del 5/11 (mapa de 76) subió el PR-AUC de 0,397 a 0,425, pero ganó solo en 7 de 18 años (doc 19). No se repitió con 78. Hay que validarla igual que lo demás |
| 3 | Corregir la mediana de prueba en `modelo_afectados.matriz()` y unificar los dos archivos semanales del SINPAD | Bajo-medio (trazabilidad) | Bajo | **Sí** | Es la única fuga menor encontrada (§1) y evita dos versiones del mismo dato (§3) |
| 4 | Sensibilidad con Y solo de «inundación» (sin «lluvia intensa») | Medio | Bajo | **Sí** | De los 3 363 registros de agua del SINPAD en Tumbes y Piura, 3 135 son «lluvia intensa» o «lluvias intensas» y 228 son inundación (`procedencia.json`); el jurado puede preguntar si el modelo predice desbordes o techos dañados |
| 5 | Actualizar las cifras de los docs 02, 06, 10, 18, el informe y la presentación | Alto (coherencia ante el jurado) | Bajo | **Sí** | Hoy conviven cifras de DesInventar, del mapa de 76 y las nuevas (§3) |
| 6 | Volver a correr la prueba de falsas alarmas (prueba C) con 78 distritos y decidir la regla del río (p95 o p99) | Medio | Medio (red) | Si hay tiempo | El aviso de lluvia o caudal dio 597 avisos en 2025 para 252 distrito-semanas con daño (doc 18, con el mapa de 76). Bischiniotis et al. (2019): costo de actuar frente a calidad del aviso |
| 7 | Modelo de cantidad de viviendas que aprenda mejor los años extremos (por ejemplo, pesos por año o variables de El Niño en la etapa 2) | Medio | Medio | No | Subestima −67 % (2023) aun con el mejor modelo; Wagenaar et al. (2017) y Merz et al. (2013) muestran que con pocos datos los modelos multivariados de árboles mejoran a los de una sola variable |
| 8 | Lluvia de estaciones SENAMHI o pronósticos guardados como entrada | Alto | Alto | No | NASA POWER no vio la tormenta del 2/11/2026 en Tumbes (9 mm contra 110 mm medidos); la lluvia pesa poco en todos los modelos |

## 5. Diez preguntas difíciles del jurado

| # | Pregunta | Respuesta corta | Cifra | Fuente |
|---|---|---|---|---|
| 1 | ¿Su modelo predice o solo repite la historia? | A 1 y 2 semanas predice algo más que la historia; a 4 semanas, no | Año por año, PR-AUC 0,185 contra 0,168 (1 semana) y 0,164 contra 0,167 (4 semanas) | `metricas_por_anio.csv`; doc 21 |
| 2 | ¿Por qué el modelo de 4 semanas no le gana a la climatología? | Porque la época y la historia del distrito ya explican casi todo, y la lluvia de NASA POWER es demasiado gruesa | 0,369 contra 0,394 | `data/modelo/resultados/metricas_resumen.csv` |
| 3 | ¿De dónde sale la variable dependiente? | Del SINPAD del INDECI en datos abiertos, con huella SHA-256 de cada archivo | 3 363 registros de agua 2003-2025 (2 691 distrito-semanas con emergencia); 93 288 distrito-semanas | `data/modelo/sinpad/procedencia.json`; doc 19 |
| 4 | ¿Cómo saben que no hay fuga de información? | Partición por años, historia solo con el entrenamiento y pruebas automáticas que cambian el futuro y comprueban que nada cambia | 7 pruebas aprobadas | `tests/test_prediccion_semanal.py` |
| 5 | ¿Qué pasa si quitan 2017? | El orden casi no cambia; empeora la cantidad estimada en 2023 | PR-AUC 0,177 → 0,176; viviendas 2023 −67 % → −81 % | `metricas_por_anio_sin_2017.csv` |
| 6 | ¿Cuántas viviendas se van a afectar en 2026? | No damos una cifra: el modelo subestima los años extremos; sí ordena los distritos | 2023: −67 % a una semana; top 10 con 2,8 aciertos de 10 en promedio | doc 21 |
| 7 | ¿Por qué no usan el satélite para predecir? | Llega días tarde y no ve las ciudades; solo confirma | Detecta el 41,7 % del área de Copernicus 2017; 4 de 13 eventos con noticias | `validacion_2017.json`; doc 09 |
| 8 | ¿Cuántas personas están expuestas? | En la zona de 1 en 100 años, unas 400 mil; no son afectados | 407 877 (Censo 2025) y 400 198 (WorldPop) | doc 17; doc 20 |
| 9 | ¿El mapa tiene los 78 distritos? | Sí, desde el 6/11, con los límites oficiales del INEI | Totales +0,2 % frente al mapa anterior | doc 20 |
| 10 | ¿El aviso de 1 a 3 días sirve? | Sí, pero con muchas falsas alarmas: dice «prepárate», no «se va a inundar» | 9 de 10 eventos con aviso; 43 de cada 100 semanas con aviso tuvieron daño en 2025 | doc 18 |

## Referencias citadas en el §4

- Merz, B., et al. (2020). Impact forecasting to support emergency management of natural hazards. *Reviews of Geophysics, 58*(4). https://doi.org/10.1029/2020RG000704
- Coughlan de Perez, E., et al. (2016). Action-based flood forecasting for triggering humanitarian action. *Hydrology and Earth System Sciences, 20*(9), 3549-3560. https://doi.org/10.5194/hess-20-3549-2016
- Bischiniotis, K., et al. (2019). Assessing time, cost and quality trade-offs in forecast-based action for floods. *International Journal of Disaster Risk Reduction, 40*, 101252. https://doi.org/10.1016/j.ijdrr.2019.101252
- Wagenaar, D., de Jong, J., & Bouwer, L. M. (2017). Multi-variable flood damage modelling with limited data using supervised learning approaches. *Natural Hazards and Earth System Sciences, 17*(9), 1683-1696. https://doi.org/10.5194/nhess-17-1683-2017
- Merz, B., Kreibich, H., & Lall, U. (2013). Multi-variate flood damage assessment: a tree-based data-mining approach. *Natural Hazards and Earth System Sciences, 13*(1), 53-64. https://doi.org/10.5194/nhess-13-53-2013

Los DOI se verificaron en la API de Crossref el 6/11/2026; de estos trabajos solo se leyó el resumen (ver la Parte 2).
