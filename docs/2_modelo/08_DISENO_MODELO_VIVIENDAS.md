# 08 · Diseño del nuevo modelo: viviendas y personas afectadas por desborde

Pregunta definida por el profesor Alexander (reunión del 4 de noviembre de 2026):

> Predecir en serie de tiempo el número de viviendas (y personas) afectadas por el desborde de los ríos en Tumbes y Piura, y dónde van a estar.

Ejemplo: con cómo subió el río ayer, ¿cuántas viviendas se inundan mañana y en qué distritos?

Este documento propone la variable a predecir (Y), las variables explicativas (X), los modelos candidatos, cómo se valida y qué datos faltan. **Todavía no hay nada entrenado.**

## 1. Qué datos con fecha tenemos hoy

| Fuente | Qué trae | Periodo | ¿Sirve como Y? |
|---|---|---|---|
| DesInventar (fuente INDECI), `data/modelo/emergencias_desinventar.csv` | Un registro por emergencia, con fecha, distrito, afectados y viviendas afectadas | 1970–2015 | Poco: de 1 013 registros de lluvias e inundaciones en Tumbes y Piura, solo **77** tienen viviendas afectadas mayores que cero (38 832 en total, 13 282 de ellas en 1998) |
| INDECI, `data/modelo/indeci/*.xlsx` | Afectados, damnificados y viviendas por provincia y distrito, por tipo de peligro | 2003–2024, **sin fecha** | No para una serie de tiempo; sí para validar totales |
| Radar Sentinel-1 (`src/huellas.py`) | Agua nueva detectada en cada pasada | 2016–hoy, una pasada cada 4 a 6 días en cada lugar | Sí, como Y satelital (ver 2.2) |
| Censo 2025 del INEI (viviendas por manzana, **confidencial**) | Viviendas ocupadas y materiales | 2025 | Es el denominador: dice cuántas viviendas hay en cada lugar |

Conclusión: con lo que hay, no se puede entrenar un modelo diario de viviendas afectadas con etiquetas de INDECI. Hay que pedir los registros de SINPAD con fecha (sección 6) o usar una Y satelital.

## 2. Variable a predecir (Y)

**Unidad:** distrito por día. Hay 76 distritos en el mapa actual y 78 oficiales (sección 6). La manzana es posible para el "dónde" (sección 4), pero como unidad de entrenamiento casi todas tendrían cero.

### 2.1 Y observada (la ideal)

`viviendas_afectadas[d, t]`: viviendas afectadas por inundación o desborde registradas por INDECI en el distrito *d* el día *t*. Necesita los registros de SINPAD 2016–2026 con fecha. Hoy no los tenemos.

### 2.2 Y satelital (se puede calcular ya)

`viviendas_en_agua[d, p]`: viviendas del censo (o edificaciones de Google, si no se aprueba el uso del censo) cuyo centro cae dentro del agua detectada por Sentinel-1 en el distrito *d* y la pasada *p*. Se calcula para cada pasada desde 2016 con el mismo código de `huellas.py`.

Límite importante: los satélites casi no ven el agua entre casas. En el Bajo Piura en 2017, el radar del proyecto marcó agua en 9 de 195 065 edificaciones, y el mapa oficial de Copernicus EMS, en 27 (`docs/6_presentacion/presentacion/figuras/agua_resumen.json`). La Y satelital mide sobre todo agua en el campo y en los bordes de los pueblos. Se usa como **mínimo** y se calibra contra INDECI cuando haya datos con fecha.

Esto también aclara qué cuenta INDECI. En sus tablas 2003–2024 de Piura, los afectados por **lluvia intensa** suman 997 173 y los afectados por **inundación**, 130 482 (`data/modelo/indeci/7162837-piura_afect_prov_dist_peligro.xlsx`). La mayor parte del daño a viviendas viene de la lluvia sobre la ciudad (techos, calles anegadas, desagües), que no es desborde de ríos. Por eso la Y debe separar el tipo de peligro: el modelo de desborde se entrena solo con "inundación".

### 2.3 De viviendas a personas

`personas_afectadas = viviendas × personas por vivienda` de la manzana, con sexo y edad cuando el INEI los entregue. Así se obtienen niños de 0 a 4 años y adultos de 65 o más en riesgo.

## 3. Variables explicativas (X)

| Variable | Fuente | Resolución | ¿La tenemos? |
|---|---|---|---|
| X1 · Caudal del río el día anterior y máximo de los últimos 3 días | GloFAS v4 vía Open-Meteo | ~5 km, diario, 1984–hoy | Sí (`rios_caudal.csv`, `data/modelo/caudal_rios.csv`) |
| X2 · Caudal frente a su periodo de retorno (¿es una crecida de 1 en 2, 5 o 10 años?) | Calculado con el reanálisis GloFAS 1991–2020 que ya bajamos | diario | Se puede calcular |
| X3 · Lluvia acumulada de 1, 3, 7 y 30 días | NASA POWER (~50 km) y Open-Meteo | diario | Sí (`lluvia_distritos.csv`) |
| X4 · % del distrito en zona inundable JRC 1/10 y 1/100, y profundidad media | JRC CEMS-GloFAS v2 | 90 m, fijo | Sí |
| X5 · Viviendas del censo dentro de la zona JRC, y con paredes o piso precarios | INEI Censo 2025 | manzana, fijo | Sí, solo en local (confidencial) |
| X6 · Agua detectada en la pasada anterior | Sentinel-1 | 55 m, cada 4–6 días | Se puede calcular |
| X7 · Anomalía del mar Niño 1+2 | CPC / NOAA | semanal | Sí |
| X8 · Altura, pendiente y altura sobre el cauce más cercano (HAND) | Copernicus DEM 30 m | 30 m, fijo | Altura y pendiente sí; HAND falta calcular |
| X9 · Estación del año e historia del distrito | calendario, INDECI | — | Sí |
| X10 · Caudal medido en estaciones | SENAMHI / ANA | diario | **Falta** |
| X11 · Defensas ribereñas y su estado | ANA, Autoridad para la Reconstrucción con Cambios | tramos | **Falta** |

## 4. "Dónde": del distrito a la manzana

Proponemos un modelo físico simple como referencia para el "dónde":

1. Con el caudal pronosticado de GloFAS (X1) se estima a qué periodo de retorno corresponde (X2).
2. Se elige el mapa de JRC de ese escenario (1 en 10 o 1 en 100 años).
3. Las manzanas del censo dentro de esa mancha son las que podrían inundarse; su suma por distrito es la predicción.

No necesita entrenamiento y da un mapa por manzana. Los modelos de la sección 5 tienen que ganarle a esta referencia para justificarse.

## 5. Modelos candidatos

| Modelo | Por qué | Riesgo |
|---|---|---|
| R0 · Referencia sin modelo: persistencia (lo de la pasada anterior) y promedio del distrito en ese mes | Toda comparación necesita una base | — |
| R1 · Referencia física (sección 4) | Usa el conocimiento hidráulico de JRC | JRC marca un área mucho mayor que la real (precisión de 32 % en 2017) |
| M1 · Modelo de dos partes (*hurdle*): logística para "¿hay viviendas afectadas?" y binomial negativa para "¿cuántas?" | La mayoría de los días tienen cero; los coeficientes se pueden explicar | Necesita varios cientos de días con Y > 0 |
| M2 · Mixto con efecto aleatorio por distrito | Los distritos con pocos eventos toman fuerza de los demás | Más complejo de explicar |
| M3 · LightGBM con objetivo Poisson o Tweedie | Captura relaciones no lineales (umbral de desborde) | Con pocos eventos se sobreajusta, como en el caso C (doc 02) |
| Descartados: ARIMA por distrito (series cortas y casi todas en cero) y LSTM (necesita miles de cuencas; Nearing et al., 2024) | | |

## 6. Validación

- **Por año:** entrenar con los años anteriores y probar en el siguiente, como el modelo actual.
- **Por evento:** dejar fuera 2017 y 2023 completos.
- **Métricas:** error en el total de viviendas del evento; error absoluto medio por distrito; % de distritos con Y > 0 que el modelo pone entre los 10 primeros; correlación de Spearman con INDECI.
- Siempre frente a R0 y R1, con intervalos por *bootstrap* de años.

## 7. Datos que hay que pedir

| Dato | A quién | Para qué |
|---|---|---|
| Emergencias de SINPAD 2016–2026 por distrito y fecha, con viviendas afectadas, inhabitables y destruidas | INDECI | Y observada (2.1) |
| Personas por vivienda o manzana, con sexo y edad | INEI (Rodrigo Rivarola, vía Esther y Sheila) | Pasar de viviendas a personas (2.3) |
| Metodología de recolección del Censo 2025 | INEI | Explicarla ante el jurado |
| Límites distritales oficiales (faltan 200115 Veintiséis de Octubre y 240203 Canoas de Punta Sal) | INEI / IGN | Unidad correcta |
| Caudal diario de estaciones (El Tigre, Puente Sánchez Cerro, Ardilla, etc.) | SENAMHI / ANA | X10 y validar GloFAS |
| Defensas ribereñas | ANA / ARCC | X11 |

## 8. Próximos pasos antes del 15 de noviembre

1. Calcular la Y satelital (2.2) para todas las pasadas de 2016 a hoy en los distritos de la costa.
2. Calcular X2 (periodo de retorno del caudal) con el reanálisis GloFAS.
3. Armar la referencia física R1 y medirla contra INDECI 2017 (totales por distrito).
4. Entrenar M1 con la Y satelital y comparar con R0 y R1.
5. Cuando lleguen los datos de SINPAD, reentrenar con la Y observada.
