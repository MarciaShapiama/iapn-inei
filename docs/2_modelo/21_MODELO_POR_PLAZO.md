# 21 · El modelo de 1 a 4 semanas, medido por plazo

*6 de noviembre de 2026. Script: `src/prediccion_semanal.py`. Pruebas: `tests/test_prediccion_semanal.py`. Salidas: `data/modelo/resultados_plazo/` y `dashboard/data/prediccion_semanal.json`.*

## La pregunta

Con lo que se sabe al terminar la semana t (lunes a domingo), ¿cuál es la probabilidad de que el SINPAD registre una emergencia por inundación o lluvia intensa en el distrito **exactamente en la semana t+h**, para h = 1, 2, 3 y 4? Y si ocurre, ¿cuántas viviendas y personas podrían verse afectadas?

Es distinto del modelo de alerta de `src/modelo_inundacion.py`, que pregunta si habrá emergencia **en alguna** de las 4 semanas siguientes. Medir cada plazo por separado muestra dónde el modelo es fuerte y dónde se debilita.

## Datos y variables

- **Etiqueta:** SINPAD 2003-2025, 78 distritos (doc 19 y doc 20). Una semana-distrito vale 1 si hay al menos un registro de inundación o lluvia intensa. En promedio, 3,1 % de las semanas-distrito tiene emergencia.
- **Viviendas:** viviendas afectadas más destruidas del SINPAD en esa semana.
- **Variables sin aviso:** lluvia de 30 días, caudal frente a lo normal, Niño 1+2, época del año de la semana t+h (calendario) y frecuencia histórica de emergencias del distrito.
- **Variables del aviso**, que se suman a las anteriores:

| Variable | De dónde sale | Se conoce en la semana t porque… |
|---|---|---|
| ¿Hubo un día sobre el p95 de lluvia del distrito? | `data/modelo/lluvia_distritos.csv`; p95 y p99 de los días con 1 mm o más de 2001-2020, como en `prueba_aviso_pasado.py` | Usa la lluvia diaria de la semana t |
| ¿Hubo un día sobre el p99? | Igual | Igual |
| Lluvia de 7 días | Base distrito-semana | Es la lluvia de la semana t |
| ¿El río pasó su p95 de caudal diario? | `data/modelo/caudal_rios.csv`; p95 de 2001-2020; distritos de la lista `CUENCA` | Caudal diario de la semana t; 0 fuera de los valles |
| Niño 1+2 | Base | Valor de la semana t |
| % del distrito en zona inundable | JRC 1 en 100 años ÷ superficie del distrito | Fijo |
| Viviendas y personas del censo en esa zona | `dashboard/data/viviendas_censo.json` | Fijo (Censo 2025) |
| ¿Hubo emergencia en la semana t? | SINPAD | Es la semana t. Ojo: en tiempo real no se sabe, porque el SINPAD publica cada seis meses |

## Cómo se validó

Para cada año A de 2008 a 2025 se entrena con los ejemplos cuya semana objetivo t+h es anterior al 1 de enero de A, y se prueba con los de A. Nunca se mezclan semanas de un mismo año. La frecuencia histórica, la climatología y las viviendas típicas de cada distrito se calculan solo con el entrenamiento.

**Modelos y reglas comparados con las mismas reglas:**

- **Logística sin variables del aviso.**
- **Logística con variables del aviso** (L2, C = 0,3, sin pesos, para que las probabilidades se puedan leer como tales). Es el modelo que se publica en el tablero.
- **LightGBM con variables del aviso** (300 árboles de profundidad 3, mínimo 300 casos por hoja).
- **Reglas simples**, vueltas probabilidad con la frecuencia del entrenamiento:
  - «hubo emergencia en la semana t»;
  - «mes del año»;
  - «hubo un día de lluvia sobre el p95 en la semana t».
- **Climatología del distrito y su mes** (mitad distrito-mes y mitad mes general).

**Viviendas:** probabilidad × viviendas si ocurre. Para los modelos, las viviendas si ocurre salen de una regresión Gamma entrenada con las semanas con evento. Para las reglas, del promedio del distrito en el entrenamiento.

**Métricas:**

- **PR-AUC**, con todas las semanas de prueba juntas, al lado de la tasa sin modelo (proporción de semanas con emergencia) y el cociente entre los dos.
- **Brier skill score (BSS)** frente a predecir siempre la proporción del entrenamiento: 0 es no ganar nada y 1 es perfecto.
- **Aciertos en el top 10:** de los 10 distritos con más viviendas afectadas en el año, cuántos están entre los 10 que el modelo pone arriba.
- **Error en el total de viviendas del año:** se muestra la mediana del error absoluto y el error con signo en 2017 y 2023.

## Resultados

**Resumen por plazo** (todas las semanas de prueba 2008-2025 juntas):

| Plazo | Tasa sin modelo | Logística con aviso | LightGBM con aviso | Logística sin aviso | Climatología distrito-mes | Mejor regla simple (mes del año) |
|---|---|---|---|---|---|---|
| 1 semana | 0,031 | **0,227** (7,3 veces la tasa) | 0,239 | 0,206 | 0,161 | 0,131 |
| 2 semanas | 0,031 | **0,207** (6,6) | 0,210 | 0,188 | 0,161 | 0,131 |
| 3 semanas | 0,031 | **0,191** (6,1) | 0,197 | 0,170 | 0,161 | 0,131 |
| 4 semanas | 0,031 | **0,176** (5,6) | 0,175 | 0,163 | 0,161 | 0,131 |

**Promedio de los 18 años, cada año por separado** (no se mezclan años con muchas y pocas emergencias):

| Plazo | Logística con aviso | LightGBM con aviso | Climatología distrito-mes | Años en que la logística gana a la climatología |
|---|---|---|---|---|
| 1 semana | 0,185 | 0,193 | 0,168 | 12 de 18 |
| 2 semanas | 0,174 | 0,178 | 0,168 | 9 de 18 |
| 3 semanas | 0,170 | 0,175 | 0,168 | 11 de 18 |
| 4 semanas | 0,164 | 0,160 | 0,167 | 8 de 18 |

### Tablas completas por plazo

**Plazo 1 semana** (tasa sin modelo: 0,031)

| Modelo o regla | PR-AUC | Veces sobre la tasa | BSS | Top 10 (promedio) | Error total de viviendas (mediana) | PR-AUC 2017 | PR-AUC 2023 | Viviendas 2017 | Viviendas 2023 |
|---|---|---|---|---|---|---|---|---|---|
| logística con variables del aviso | 0,227 | 7,3 | 0,111 | 2,8 de 10 | 82 % | 0,321 | 0,371 | −43 % | −67 % |
| LightGBM con variables del aviso | 0,239 | 7,7 | 0,122 | 2,9 de 10 | 86 % | 0,346 | 0,378 | −52 % | −66 % |
| logística sin variables del aviso | 0,206 | 6,6 | 0,096 | 2,8 de 10 | 83 % | 0,307 | 0,368 | −52 % | −72 % |
| climatología distrito y mes | 0,161 | 5,2 | 0,064 | 1,7 de 10 | 154 % | 0,313 | 0,383 | −87 % | −88 % |
| regla: mes del año | 0,131 | 4,2 | 0,049 | 1,1 de 10 | 163 % | 0,282 | 0,395 | −86 % | −87 % |
| regla: emergencia en la semana t | 0,103 | 3,3 | 0,043 | 1,7 de 10 | 160 % | 0,126 | 0,172 | −77 % | −79 % |
| regla: lluvia sobre p95 en la semana t | 0,096 | 3,1 | 0,029 | 1,3 de 10 | 136 % | 0,188 | 0,234 | −76 % | −81 % |

**Plazo 2 semanas**

| Modelo o regla | PR-AUC | Veces sobre la tasa | BSS | Top 10 (promedio) | Error total de viviendas (mediana) | PR-AUC 2017 | PR-AUC 2023 | Viviendas 2017 | Viviendas 2023 |
|---|---|---|---|---|---|---|---|---|---|
| logística con variables del aviso | 0,207 | 6,6 | 0,094 | 3,1 de 10 | 85 % | 0,308 | 0,412 | −68 % | −74 % |
| LightGBM con variables del aviso | 0,210 | 6,7 | 0,100 | 2,8 de 10 | 88 % | 0,359 | 0,418 | −74 % | −75 % |
| logística sin variables del aviso | 0,188 | 6,0 | 0,082 | 2,9 de 10 | 85 % | 0,323 | 0,381 | −72 % | −77 % |
| climatología distrito y mes | 0,161 | 5,2 | 0,064 | 1,7 de 10 | 154 % | 0,313 | 0,382 | −87 % | −88 % |
| regla: mes del año | 0,131 | 4,2 | 0,049 | 1,1 de 10 | 164 % | 0,282 | 0,395 | −86 % | −87 % |
| regla: emergencia en la semana t | 0,099 | 3,2 | 0,037 | 1,6 de 10 | 162 % | 0,120 | 0,197 | −79 % | −80 % |
| regla: lluvia sobre p95 en la semana t | 0,085 | 2,7 | 0,020 | 1,2 de 10 | 145 % | 0,149 | 0,209 | −80 % | −83 % |

**Plazo 3 semanas**

| Modelo o regla | PR-AUC | Veces sobre la tasa | BSS | Top 10 (promedio) | Error total de viviendas (mediana) | PR-AUC 2017 | PR-AUC 2023 | Viviendas 2017 | Viviendas 2023 |
|---|---|---|---|---|---|---|---|---|---|
| logística con variables del aviso | 0,191 | 6,1 | 0,083 | 3,1 de 10 | 97 % | 0,318 | 0,384 | −84 % | −80 % |
| LightGBM con variables del aviso | 0,197 | 6,3 | 0,092 | 2,8 de 10 | 111 % | 0,343 | 0,415 | −84 % | −81 % |
| logística sin variables del aviso | 0,170 | 5,5 | 0,070 | 2,8 de 10 | 92 % | 0,306 | 0,360 | −84 % | −82 % |
| climatología distrito y mes | 0,161 | 5,1 | 0,064 | 1,7 de 10 | 154 % | 0,313 | 0,381 | −87 % | −88 % |
| regla: mes del año | 0,131 | 4,2 | 0,049 | 1,1 de 10 | 164 % | 0,282 | 0,395 | −86 % | −87 % |
| regla: emergencia en la semana t | 0,101 | 3,2 | 0,037 | 1,6 de 10 | 162 % | 0,142 | 0,178 | −79 % | −80 % |
| regla: lluvia sobre p95 en la semana t | 0,070 | 2,2 | 0,012 | 1,2 de 10 | 148 % | 0,128 | 0,161 | −80 % | −83 % |

**Plazo 4 semanas**

| Modelo o regla | PR-AUC | Veces sobre la tasa | BSS | Top 10 (promedio) | Error total de viviendas (mediana) | PR-AUC 2017 | PR-AUC 2023 | Viviendas 2017 | Viviendas 2023 |
|---|---|---|---|---|---|---|---|---|---|
| logística con variables del aviso | 0,176 | 5,6 | 0,074 | 2,7 de 10 | 100 % | 0,290 | 0,370 | −86 % | −84 % |
| LightGBM con variables del aviso | 0,175 | 5,6 | 0,078 | 2,7 de 10 | 113 % | 0,308 | 0,366 | −84 % | −86 % |
| logística sin variables del aviso | 0,163 | 5,2 | 0,065 | 2,6 de 10 | 98 % | 0,279 | 0,365 | −86 % | −85 % |
| climatología distrito y mes | 0,161 | 5,1 | 0,064 | 1,7 de 10 | 155 % | 0,313 | 0,381 | −87 % | −88 % |
| regla: mes del año | 0,131 | 4,2 | 0,049 | 1,2 de 10 | 164 % | 0,282 | 0,395 | −86 % | −87 % |
| regla: emergencia en la semana t | 0,085 | 2,7 | 0,026 | 1,6 de 10 | 162 % | 0,128 | 0,141 | −79 % | −81 % |
| regla: lluvia sobre p95 en la semana t | 0,061 | 2,0 | 0,007 | 1,2 de 10 | 152 % | 0,110 | 0,127 | −81 % | −84 % |

### ¿Cuánto depende de 2017?

Se repitió todo sin entrenar nunca con 2017 (`python src/prediccion_semanal.py --sin-anio 2017`). Las dos columnas se comparan en los mismos años de prueba (2008-2016 y 2018-2025).

| Plazo | Modelo | PR-AUC medio por año: con 2017 | sin 2017 | PR-AUC 2023: con 2017 | sin 2017 | Viviendas 2023: con 2017 | sin 2017 |
|---|---|---|---|---|---|---|---|
| 1 | Logística con aviso | 0,177 | 0,176 | 0,371 | 0,352 | −67 % | −81 % |
| 1 | Climatología | 0,160 | 0,161 | 0,383 | 0,380 | −88 % | −92 % |
| 2 | Logística con aviso | 0,166 | 0,166 | 0,412 | 0,398 | −74 % | −88 % |
| 3 | Logística con aviso | 0,161 | 0,161 | 0,383 | 0,357 | −80 % | −92 % |
| 4 | Logística con aviso | 0,156 | 0,157 | 0,370 | 0,354 | −84 % | −93 % |
| 4 | Climatología | 0,159 | 0,160 | 0,381 | 0,379 | −88 % | −92 % |

Sin 2017, el orden de las semanas casi no cambia. Lo que se pierde es la escala: el modelo aprende de 2017 cuántas viviendas puede afectar un año extremo, y sin él subestima más 2023 (−81 % en vez de −67 % a una semana).

## Lectura honesta

1. **Sí aprende algo más que la estación, sobre todo a 1 y 2 semanas.** Con las variables del aviso, la logística supera a la climatología del distrito y su mes en los cuatro plazos si se miran todas las semanas juntas (0,227 contra 0,161 a una semana). Año por año la ventaja es menor: gana en 12 de 18 años a una semana y en 8 de 18 a cuatro semanas.
2. **La ventaja se pierde con el plazo.** A 4 semanas, el promedio por año queda igual o por debajo de la climatología (0,164 contra 0,167). Para un mes vista, la historia del distrito y la época dicen casi lo mismo que el modelo.
3. **Las variables del aviso suman.** La misma logística sin ellas baja de 0,227 a 0,206 a una semana. LightGBM gana un poco más a 1-3 semanas, pero es más difícil de explicar y no mejora la cantidad de viviendas.
4. **Las reglas simples pierden.** «Hubo emergencia en la semana t» (0,103) y «lluvia sobre p95 en la semana t» (0,096) quedan muy por debajo; «mes del año» (0,131), también. **Excepción importante:** en 2023, la regla «mes del año» (0,395) y la climatología (0,383) le ganan al modelo (0,371) a una semana. En los años extremos todo el norte se inunda en marzo y la estación ya lo dice.
5. **La cantidad de viviendas sigue siendo el punto débil.** El error del total anual es grande (mediana de 82 % a una semana). En los años extremos el modelo se queda corto (−43 % en 2017 y −67 % en 2023) y en los años tranquilos se pasa. Sirve para ordenar distritos (top 10: 2,8 de 10, contra 1,7 de la climatología), no para dar una cifra de viviendas.

## Fuga de información: cómo se comprobó

- **El objetivo es la semana t+h y nada más.** `test_objetivo_es_la_semana_t_mas_h` comprueba que `semana_obj − semana = h` en todas las filas y que el objetivo coincide con la emergencia del panel en t+h.
- **Las variables no cambian si se cambia el futuro.** `test_variables_son_de_la_semana_t` pone −999 en todas las variables de las semanas posteriores al 6/3/2017 y comprueba que las variables de esa semana quedan iguales.
- **La historia del distrito sale solo del entrenamiento.** `test_historia_solo_con_entrenamiento` invierte la etiqueta del año de prueba y comprueba que la historia no cambia.
- **No se mezclan años.** En cada año de prueba, el código verifica que la última semana objetivo del entrenamiento sea anterior a la primera de la prueba (`assert` en `correr()`).
- **Lo que no es fuga pero hay que decir:**
  - el censo 2025 y la zona inundable se usan también en 2003-2024 (anacronismo de exposición);
  - «emergencia en la semana t» no se conoce en tiempo real, porque el SINPAD publica cada seis meses;
  - los umbrales p95 y p99 se calculan con 2001-2020, que incluye años de prueba. Es un umbral de clima fijo, no usa la etiqueta.

## Llevarlo al tablero

- **`src/prediccion_semanal.py`** entrena con toda la etiqueta (semanas objetivo hasta el 29/12/2025) y predice desde la última semana con lluvia para al menos el 90 % de los distritos (hoy: semana del 2/11/2026). Escribe **`dashboard/data/prediccion_semanal.json`** con, por distrito:
  - la probabilidad a 1, 2, 3 y 4 semanas;
  - las viviendas estimadas si ocurre, con el rango del 10 % al 90 % de sus emergencias pasadas;
  - las personas estimadas (viviendas × personas por vivienda del censo en la zona inundable del distrito);
  - la calidad de cada plazo.
- **`prediccionVista`**, en `dashboard/index.html`, agrega a la pestaña «Alerta por distrito» un panel con:
  - la tabla de calidad por plazo (PR-AUC del modelo, tasa, climatología, BSS y top 10);
  - los 15 distritos con más probabilidad, con una barra por plazo, las viviendas y las personas si ocurre.
  Si el JSON no existe, el panel no aparece.
- **Flujo semanal:** en `.github/workflows/base_modelo.yml` (lunes) va después de `python -u src/modelo_inundacion.py`:
  ```yaml
      - run: python -u src/prediccion_semanal.py
  ```
  En el paso «Guardar» hay que agregar `dashboard/data/prediccion_semanal.json` al `git add` (`data/modelo` ya incluye `resultados_plazo/`). Lo agrega Marcia; no se tocó `.github/workflows/`.

## Cómo se probó

- Se corrió dos veces, y `metricas_por_plazo.csv`, `metricas_por_anio.csv` y `prediccion_semanal.json` dan la misma huella SHA-256, sin contar la fecha.
- `tests/test_prediccion_semanal.py`: 7 pruebas aprobadas.
- El panel se revisó en el tablero local: aparece con las cifras del JSON y sin errores en la consola.

## Límites

- La etiqueta es la semana de **registro** en el SINPAD, que puede ser posterior al daño.
- La lluvia es de NASA POWER (celdas de ~50 km). Es la principal razón de que el clima aporte poco.
- La probabilidad publicada usa la última semana con lluvia de NASA POWER, que llega con unos días de retraso.
- Las personas son una estimación (viviendas × personas por vivienda del censo), no un dato del SINPAD.
- No se probó con pronósticos de lluvia (Open-Meteo): no hay un archivo largo de pronósticos para entrenar. Es la mejora natural para los plazos de 1 y 2 semanas.
