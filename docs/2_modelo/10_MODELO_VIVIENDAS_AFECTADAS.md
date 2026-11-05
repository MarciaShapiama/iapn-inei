# 01 · Modelo de viviendas afectadas por inundación en Tumbes y Piura

Pregunta del profesor Alexander (reunión del 4 de noviembre de 2026): predecir en serie de tiempo cuántas viviendas y personas pueden verse afectadas por el desborde de los ríos en Tumbes y Piura, y dónde.

**Respuesta corta.** Sí se puede entrenar con datos reales. El INDECI publicó en datos abiertos sus registros del SINPAD por distrito y por fecha, de 2003 a junio de 2026, con viviendas afectadas y destruidas. Con esa etiqueta y las variables que ya tiene el repositorio, armamos un modelo por distrito y semana. Lo validamos año por año, de 2012 a 2025. El modelo de dos etapas detecta mejor que una referencia sin modelo en qué distritos y semanas habrá viviendas afectadas. Además, en 2017 y 2023 acierta 5 y 7 de los 10 distritos más afectados. En cambio, se queda corto en la cantidad en los años extremos: en 2023 estima la cuarta parte de lo que pasó. Hay que decirlo así.

---

## 1. La etiqueta real (Y): de dónde sale

### 1.1 Lo que encontramos

| Fuente | Qué trae | Periodo | Formato y descarga | ¿Sirve como Y? |
|---|---|---|---|---|
| **INDECI, «Emergencias y daños a nivel nacional por departamento»** ([página](https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento)) | Un registro por emergencia: código SINPAD, fecha, ubigeo del distrito, peligro, fallecidos, damnificados, afectados, viviendas destruidas y afectadas, colegios, salud, cultivos, vías | 2003 a 2025 y primer semestre de 2026 | Dos CSV con `;` y codificación latin-1: [2003-2025](https://www.datosabiertos.gob.pe/sites/default/files/BD_2003-2025_EMERGENCIAS.csv) (27 MB, 142 139 registros) y [2026-I](https://www.datosabiertos.gob.pe/sites/default/files/BD_2026_Semestre_I.csv) (9 352). Publicado el 26/08/2026, actualizado el 30/10/2026, frecuencia semestral, licencia Open Data Commons Attribution | **Sí. Es la etiqueta principal** |
| INDECI, «Emergencias Históricas registradas con SINPAD» ([página](https://datosabiertos.gob.pe/dataset/emergencias-hist%C3%B3ricas-registradas-con-sinpad)) | Archivos por año | — | Al 5/11/2026 la página pide iniciar sesión («Acceso denegado») | No se pudo revisar |
| DesInventar (UNDRR, con datos del INDECI) ([descarga](https://desinventar-api.undrr.org/download.html)) | Un registro por evento, con fecha y distrito | En Tumbes y Piura llega solo a **2015** (`data/modelo/emergencias_desinventar.csv`) | XML dentro de un ZIP | Solo para años antiguos. De 1 013 registros de lluvias e inundaciones, solo 77 tienen viviendas afectadas (doc 08) |
| Compendios estadísticos del INDECI ([2023](https://cdn.www.gob.pe/uploads/document/file/5591372/4965310-compendio-final-af-2023-indeci.pdf), [2024](https://cdn.www.gob.pe/uploads/document/file/7175987/6151912-compendio-estadistico-2024.pdf)) | Totales anuales por departamento y peligro | Un año por documento | PDF | No como serie; sí para comprobar totales |
| Tablas del INDECI ya guardadas en el repositorio (`data/modelo/indeci/*.xlsx`) | Totales por provincia y distrito | 2003-2024, sin fecha | Excel | No como serie; sí para validar |
| Reportes del COEN e informes de emergencia del INDECI ([emergencias](https://portal.indeci.gob.pe/emergencias/), [informes](https://portal.indeci.gob.pe/informe/informe-de-emergencia/)) | Cada evento, con daños por distrito | Al día | Web y PDF, uno por evento | Para **estos días** (noviembre de 2026), que aún no están en el archivo semestral. Se cargan a mano |

### 1.2 Qué hay para Tumbes y Piura

Filtramos los 78 distritos (ubigeos que empiezan con 20 y 24) y los peligros de agua:

- «Lluvia intensa» y «lluvias intensas»: 3 135 registros.
- «Inundación», «inundación por desborde de río» y «de canales»: 228 registros.

En total quedan **3 363 emergencias en 2 691 distrito-semanas**, de enero de 2003 a junio de 2026. En 2 329 de esas semanas hubo viviendas afectadas o destruidas. Entre 2003 y 2025 suman 463 670 viviendas. El archivo `sinpad_tumbes_piura_semanal.csv`, que acompaña a este documento, tiene ese resumen semanal.

| Año | Viviendas afectadas | Viviendas destruidas |
|---|---|---|
| 2017 | 85 960 | 13 219 |
| 2023 | 118 241 | 11 279 |
| 2025 | 27 892 | 5 096 |

(Suma por semanas que empiezan ese año; el corte por fecha exacta cambia unas pocas decenas.)

**Comprobación con una cifra oficial publicada.** Para 2017, el informe n.º 10 de OCHA (mayo de 2017, cifras del INDECI, ya citado en `src/impacto.py`) da 74 348 viviendas afectadas en Piura y 11 395 en Tumbes: 85 743 en total. El SINPAD abierto da 85 960 en total, una diferencia de 0,3 %. El reparto por departamento no coincide: el SINPAD da 65 467 en Piura y 20 493 en Tumbes. Conviene preguntarle al INDECI por qué.

### 1.3 Problemas del archivo que el código ya resuelve

1. **Fechas con dos formatos.** Hasta 2024 vienen como día/mes/año (11/02/2003). En 2025 y 2026 vienen como mes/día/año corto (03/26/25). Sin corregirlo, 330 registros de 2025 se pierden o quedan en el mes equivocado. El código usa la columna MES para decidir el orden.
2. **El archivo de 2026 tiene una columna mal llenada.** En 132 de sus 302 registros de lluvias, inundaciones y deslizamientos, «viviendas destruidas» repite el número de «afectados», que son personas. Por eso, para 2026 solo se usan las viviendas afectadas, y el modelo se entrena y valida hasta diciembre de 2025.
3. **Dos distritos nuevos.** El mapa de distritos del repositorio (GADM) no tiene Veintiséis de Octubre (200115) ni Canoas de Punta Sal (240203). Sus registros se suman a Piura y a Zorritos, que son los polígonos que los contienen; lo comprobamos con puntos de su territorio. Cuando el repositorio tenga los límites oficiales del INEI, se quita esa fusión (`FUSION` en el código).
4. **«Inundación» y «lluvia intensa» se mezclan.** En Tumbes y Piura el SINPAD registra casi todo como lluvia intensa (3 135 contra 228). Una misma crecida puede quedar en cualquiera de los dos. Por eso la Y suma ambos, y la variable `eventos_inundacion` permite separar solo los desbordes si el profesor lo pide.

---

## 2. Qué se predice (Y) y por qué

**Y = viviendas afectadas + viviendas destruidas por inundación o lluvia intensa, en un distrito y una semana** (lunes a domingo).

- **Por qué distrito:** el SINPAD registra por distrito, la exposición del censo está por distrito y las decisiones (municipalidad, INDECI) se toman a ese nivel.
- **Por qué semana y no día:**
  - La fecha del SINPAD es la del registro de la emergencia, que puede ser días después del desborde.
  - Por día, menos del 0,5 % de las filas tendría un evento; por semana, el 2,3 %.
  - La base del repositorio ya está por semana.
  - Igual se puede leer como serie de tiempo: cada lunes se estima la semana que empieza.
- **Personas:** el SINPAD trae «afectados» y «damnificados». Cuando el código baja el archivo completo (`--descargar`), guarda también esas dos columnas. Así se puede repetir todo con Y = personas. Con la data de habitantes del INEI (tarea 2), las viviendas se pueden pasar a personas por sexo y edad.

---

## 3. Variables explicativas (X)

Todas las variables que cambian en el tiempo se toman **de la semana anterior**, porque son las que se conocen el lunes. Una versión aparte usa la lluvia de la misma semana; equivale a tener un pronóstico perfecto y sirve como techo de lo que se puede lograr.

| Variable | Fuente | Resolución | Periodo | ¿Está en el repositorio? |
|---|---|---|---|---|
| Lluvia de 7, 30 y 90 días y su anomalía | NASA POWER | ~50 km, diaria | 2001-hoy | Sí (`base_distrito_semana.csv`) |
| Lluvia pronosticada de los próximos 7 días | Open-Meteo | punto del distrito, diaria | 7 días | Sí, solo el pronóstico de hoy (`aviso_lluvia.json`). **Falta guardar el histórico de pronósticos** para entrenar con él |
| Caudal del río la semana anterior, frente a lo normal y máximo de 4 semanas | GloFAS v4 | ~5 km, diaria | 1984-hoy | Sí |
| Caudal frente a su periodo de retorno (¿crecida de 1 en 2, 5 o 10 años?) | GloFAS, reanálisis | diaria | — | **Falta calcularla** |
| Niño 1+2 | NOAA CPC | semanal | 1981-hoy | Sí |
| % del distrito en zona inundable (km² y personas en la zona de 1 en 100 años) | JRC CEMS-GloFAS v2 | 90 m, fija | — | Sí |
| Viviendas del Censo 2025 en zona inundable y % con paredes frágiles | INEI, Censos Nacionales 2025 | manzana, sumada por distrito | 2025 | Sí, en totales por distrito (`dashboard/data/viviendas_censo.json`). El código lee también `datos_inei/viviendas_distrito.csv` si existe en la laptop |
| Personas por sexo y edad en zona inundable | INEI (llega ahora) | manzana | 2025 | **Falta** (tarea 2) |
| Altura y pendiente | Copernicus DEM | 30 m | — | Altura y pendiente sí; la altura sobre el cauce (HAND) falta |
| Historia del distrito (promedio de viviendas afectadas y frecuencia de eventos) | SINPAD | — | — | Se calcula **solo con los años de entrenamiento** |
| Época del año | calendario | semana | — | Sí |

---

## 4. Modelos comparados

| Modelo | Qué hace | A favor | Riesgo con pocos eventos |
|---|---|---|---|
| R00 · Siempre cero | Predice que no pasa nada | Muestra qué métrica engaña | — |
| R0 · Climatología (referencia sin modelo) | Promedio del distrito en ese mes, con los años anteriores | Toda comparación necesita una base | No reacciona a la lluvia ni al río |
| M1 · Poisson | Regresión para conteos | Simple y fácil de explicar | Supone que la media y la varianza son iguales, y aquí la varianza es enorme |
| **M2 · Dos etapas** | 1) ¿Hay viviendas afectadas? (logística). 2) Si las hay, ¿cuántas? (Gamma) | Separa el «si» del «cuánto», que es como se comporta el dato: 97,7 % de ceros y unos pocos miles | La segunda etapa aprende de solo ~2 000 semanas positivas |
| M3 · Binomial negativa | Conteos con más dispersión que Poisson | Pensada para datos así | En la práctica se dispara: algunos años sobreestima el total varias veces |
| M4 · Gradient boosting con objetivo Poisson | Árboles que aprenden umbrales (por ejemplo, desde cuánta lluvia empieza el daño). Usa LightGBM si está instalado; si no, el equivalente de scikit-learn | Capta relaciones no lineales | Con pocos eventos se aprende los casos de memoria |
| M5 · Binomial negativa con ceros inflados | Una parte para los «ceros de verdad» y otra para los conteos | Diseñada para exceso de ceros | Necesita statsmodels; en el repositorio sí corre (tabla 5.1) |

---

## 5. Cómo se validó

- **Por años, sin mirar el futuro.** Para cada año de 2012 a 2025 se entrena con todos los años anteriores (desde 2003) y se prueba en ese año. La historia del distrito también se calcula solo con los años anteriores.
- **Métricas:**
  - **PR-AUC de «¿hay evento?»:** mide qué tan bien ordena las semanas con viviendas afectadas. Es la métrica principal.
  - **Spearman entre distritos:** si el orden de distritos por viviendas estimadas coincide con el real.
  - **Acierto en el top 10:** cuántos de los 10 distritos más afectados están en los 10 que el modelo pone arriba.
  - **Error en el total del año.**
  - **Error absoluto medio por distrito-semana.** Lo reportamos, pero engaña: «siempre cero» saca el mejor valor (6,96), porque casi todas las semanas son cero. No sirve para elegir el modelo.

### 5.1 Resultados promedio, 2012-2025 (anticipación: datos de la semana anterior)

| Modelo | PR-AUC «¿hay evento?» | Spearman distritos | Acierto top 10 | Error del total anual (mediana) |
|---|---|---|---|---|
| R0 Climatología | 0,122 | 0,27 | 25 % | 89 % |
| M1 Poisson | 0,152 | 0,32 | 26 % | 43 % |
| **M2 Dos etapas** | **0,175** | **0,38** | **30 %** | **53 %** |
| M3 Binomial negativa | 0,182 | 0,41 | 31 % | 180 % |
| M4 Boosting Poisson | 0,162 | 0,37 | 31 % | 77 % |
| M5 Binomial negativa con ceros inflados | 0,159 | 0,37 | 29 % | 67 % |

Nota de integración (5/11/2026): al correr el código en el repositorio, con LightGBM y statsmodels instalados, se reproducen las cifras de R0, M1, M2 y M3. M4 sale con 0,166 de PR-AUC (con LightGBM, en lugar del equivalente de scikit-learn) y M5 queda por debajo del modelo de dos etapas, que se mantiene como el recomendado.

La proporción de semanas con viviendas afectadas va de 0,5 % a 9,6 % según el año. En cada año, el PR-AUC del modelo de dos etapas es entre 3,5 y 19 veces esa proporción, que es lo que sacaría un modelo al azar.

Con la lluvia de la misma semana (techo, como si el pronóstico fuera perfecto), el PR-AUC del modelo de dos etapas sube a 0,227 y el del Poisson a 0,204. La diferencia muestra cuánto se ganaría con un buen pronóstico de lluvia.

### 5.2 Los dos años que importan

| Año | Viviendas reales | Dos etapas: total estimado | Error | Acierto top 10 | Spearman | PR-AUC |
|---|---|---|---|---|---|---|
| 2017 | 100 621 | 60 137 | −40 % | 5 de 10 | 0,38 | 0,264 |
| 2023 | 131 594 | 33 670 | −74 % | 7 de 10 | 0,47 | 0,352 |

La climatología, en cambio, estima 11 263 en 2017 y 13 984 en 2023 (−89 % en ambos). El modelo capta que esos años son distintos, pero no en toda su magnitud.

**Dónde falla.** En 2017, los cinco distritos con más viviendas afectadas fueron Catacaos (15 115), Piura (8 621), Tambogrande (6 846), Colán (4 293) y Pampas de Hospital (3 435). El modelo puso arriba a Tumbes (12 347 estimadas), Tambogrande, Zarumilla, Salitral y Chulucanas. Le da demasiado peso al distrito Tumbes, que es el que más emergencias registra en la historia. En 2023 acertó tres de los cinco primeros: Tambogrande, Catacaos y Chulucanas.

### 5.3 Por qué recomendamos el modelo de dos etapas

- Es el más equilibrado: mejora a la climatología en las tres métricas de orden (PR-AUC, Spearman y top 10) y su error en el total es estable.
- La binomial negativa ordena algo mejor en promedio, pero su total se dispara: 180 % de error típico. Un total así no se puede mostrar en el tablero.
- Se explica en una frase: «primero estima la probabilidad de que haya viviendas afectadas; después, cuántas, si las hay».

**Cómo decirlo ante el jurado:** «El modelo ordena bien dónde y cuándo puede haber viviendas afectadas: es mejor que mirar solo la historia del distrito. Pero en años extremos como 2023 subestima la cantidad. Por eso lo usamos para ordenar distritos y no como cifra exacta».

---

## 6. Limitaciones

- **La etiqueta es lo que se registró.** El SINPAD cuenta las emergencias que los gobiernos locales reportaron. Si una municipalidad no registra, el modelo ve cero.
- **Lluvia gruesa.** La lluvia de NASA POWER viene en cuadros de unos 50 km, y distritos vecinos comparten valores. Con PISCO del SENAMHI (~10 km) debería mejorar.
- **Falta el pronóstico histórico.** El modelo usa la lluvia observada de la semana anterior. En operación usaría el pronóstico de Open-Meteo. Para entrenar con él hay que guardar cada día el pronóstico; el repositorio hoy guarda solo el del día.
- **Inundación y lluvia mezcladas** (sección 1.3). El modelo predice daño por agua, no solo por desborde de ríos.
- **2026 no se usa para entrenar** por el problema de la columna de viviendas destruidas. Hay que preguntarle al INDECI.

## 7. Siguientes pasos (en orden)

1. Agregar el caudal frente a su periodo de retorno (GloFAS), que es la variable física del desborde.
2. Guardar cada día el pronóstico de lluvia de Open-Meteo por distrito, para tener el histórico.
3. Probar con lluvia PISCO.
4. Repetir con Y = personas (afectados + damnificados) y, con la data del INEI, por sexo y edad.
5. Escribir al INDECI por la columna de 2026 y por el reparto Piura/Tumbes de 2017.

## 8. Cómo correrlo

```bash
# desde la raíz del repositorio, con modelo_afectados.py en src/
# y sinpad_tumbes_piura_semanal.csv en data/modelo/
python src/modelo_afectados.py                  # anticipación (unos 2 minutos)
python src/modelo_afectados.py --lluvia-semana  # techo con la lluvia de la misma semana
python src/modelo_afectados.py --descargar      # vuelve a bajar el SINPAD del INDECI
```

Los resultados quedan en `data/modelo/resultados_afectados/`. Las tablas de este documento salen de esos archivos; copias en `resultados_modelo/` del paquete.
