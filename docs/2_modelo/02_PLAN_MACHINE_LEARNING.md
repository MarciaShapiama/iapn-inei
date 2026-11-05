# 02 · Plan de machine learning

**Regla del documento:** solo se informa una métrica si salió de un experimento que se puede volver a correr con el repositorio. Donde no hay etiquetas independientes, se dice y no se entrena.

## 1. Inventario de datos y etiquetas

| Recurso | ¿Existe? | Sirve como etiqueta independiente? |
|---|---|---|
| Emergencias por distrito y fecha (DesInventar, fuente INDECI) | Sí, 2001–**2015** (`data/modelo/emergencias_desinventar.csv`) | Sí para el caso C (eventos reportados); sesgo de reporte |
| Totales INDECI 2003–2024 por provincia y distrito, sin fecha | Sí (`data/modelo/indeci/*.xlsx`) | Solo para validar órdenes de magnitud |
| Huellas Sentinel-1 2017 y 2023 | Sí (detección propia) | **No.** Salen de un algoritmo; no se pueden usar para validar otro algoritmo de radar |
| Peligro JRC 1/10 y 1/100 | Sí | **No.** Es un modelo, no una observación |
| Mapas de referencia independientes (óptico de alta resolución, mapeo de emergencia, campo) | **No en el repositorio** | Es lo que falta para los casos A y B |
| Lluvia NASA POWER semanal por distrito, caudal GloFAS, Niño 1+2/3.4 | Sí, 2001–2026 | Covariables (modeladas; celdas de ~50 km) |
| DEM, HAND, pendiente, distancia a ríos, uso del suelo | DEM Copernicus solo dentro de `huellas.py`; **HAND, uso del suelo y distancia a ríos no están** | — |

## 2. Comparación de casos

| | **A. Susceptibilidad espacial** | **B. Clasificación de inundación observada (SAR)** | **C. Probabilidad de emergencia distrito-semana** |
|---|---|---|---|
| Variable objetivo | Píxel/sector inundado en un evento (sí/no) | Píxel con agua de inundación en una pasada (sí/no) | `emergencia_1a4`: emergencia por inundación o lluvias en las 4 semanas siguientes |
| Unidad espacial | Píxel de 30–90 m o celda de 250 m | Píxel de 10–20 m | Distrito (75) |
| Horizonte | Estático (condicional a un evento) | Instantáneo (fecha de la pasada) | 1–4 semanas |
| Entradas | DEM, HAND, pendiente, distancia al río, geomorfología, uso del suelo, lluvia antecedente | VV, VH, cambio frente a la referencia, HAND, pendiente, agua permanente | Lluvia 7/30/90 d y anomalías, caudal, Niño, exposición, estacionalidad, historia del distrito |
| Etiquetas | **Faltan** (no hay huellas independientes) | **Faltan** (no hay referencia óptica ni de campo) | **Existen** hasta 2015 (311 semanas positivas) |
| Tamaño muestral | — | — | 31.008 distrito-semanas de prueba (2008–2015) |
| Riesgo de fuga | Píxeles vecinos en entrenamiento y prueba | Validar contra la misma detección | Historia del distrito con años futuros; ventana de la etiqueta que cruza el corte |
| Validación correcta | Por eventos y cuencas (Chira / Piura / Tumbes) | Por eventos y fechas; referencia independiente | Origen móvil por años |
| Línea base | Reglas HAND < x m y distancia < y m | Umbral fijo −17/−18 dB | Climatología del distrito por época |
| Costo | Medio (HAND y uso del suelo nuevos) | Alto (Sentinel-1 en varias fechas + digitalizar referencia) | Bajo (ya está) |
| **Decisión** | **No entrenar todavía**; preparar datos | **No entrenar todavía**; diseñar la validación | **Experimento reproducido y ampliado** |

## 3. Caso C: experimento reproducible

### 3.1 Diseño (ya implementado por el equipo en `src/modelo_inundacion.py`)

- **Validación con origen móvil por años:** para cada año *a* de 2008 a 2015 se entrena con los años < *a*. Se quitan las 4 últimas semanas, porque su etiqueta mira dentro del año *a*. La `frecuencia_historica` se calcula solo con los años de entrenamiento.
- **Modelos:** climatología (línea base sin modelo), logística simple (6 variables), logística completa (20 variables), LightGBM regularizado con restricciones monótonas.
- **Prueba final fuera de muestra:** se entrena con 2001–2015 y se ordenan los años 2016–2026 por riesgo medio de enero a abril. 2017 queda en el puesto **1** y 2023 en el **2** de 11.

### 3.2 Reproducción (4/11/2026, misma base del repositorio)

| Modelo | PR-AUC | ROC-AUC | Brier | Captura 5 % |
|---|---|---|---|---|
| Climatología | 0,095 | 0,829 | 0,010 | 37 % |
| Logística simple | 0,114 | 0,865 | 0,144 | 30 % |
| Logística completa | 0,122 | 0,846 | 0,147 | 36 % |
| LightGBM | 0,082 | 0,811 | 0,013 | 33 % |

Coinciden exactamente con `docs/2_modelo/modelo_inundacion.md`. Después de corregir la población (error E1 de la auditoría) actualicé las columnas de exposición de la base con `src/actualizar_exposicion_base.py` y volví a entrenar. La logística completa pasa a 0,124 y LightGBM a 0,078. La logística simple **no cambia (0,114)** porque no usa esas columnas.

### 3.3 Ampliación: incertidumbre, calibración y falsos negativos (`src/ml_evaluacion.py`)

Incertidumbre con *bootstrap* de 2.000 remuestreos **por años completos** (8 bloques). La tasa base es 1,0 %, así que un modelo al azar tendría PR-AUC ≈ 0,010. Los valores de esta tabla salen del archivo de predicciones, que se guarda redondeado a 5 decimales; esos empates explican la diferencia de ~0,003 con la tabla anterior.

| Modelo | PR-AUC [IC 90 %] | ROC-AUC [IC 90 %] | ΔPR-AUC vs climatología [IC 90 %] | P(supera a climatología) |
|---|---|---|---|---|
| Climatología | 0,095 [0,057–0,165] | 0,829 [0,779–0,871] | — | — |
| Logística simple | 0,111 [0,080–0,170] | 0,865 [0,842–0,900] | [−0,003; 0,039] | 0,92 |
| Logística completa | 0,121 [0,074–0,212] | 0,845 [0,801–0,895] | [0,000; 0,070] | 0,95 |
| LightGBM | 0,079 [0,054–0,148] | 0,811 [0,786–0,866] | [−0,048; 0,014] | 0,21 |

**Calibración** (recalibración isotónica dejando un año fuera):

| Modelo | Brier original | Brier recalibrado | Brier de la tasa base |
|---|---|---|---|
| Logística simple | 0,1438 | **0,0095** | 0,0099 |
| LightGBM | 0,0127 | 0,0098 | 0,0099 |
| Climatología | 0,0096 | 0,0097 | 0,0099 |

**Falsos negativos** (logística simple, 5 % de distrito-semanas con mayor riesgo):

- 217 de 311 emergencias (70 %) quedan fuera del 5 % de mayor riesgo.
- El **84 %** de esos falsos negativos ocurre **de enero a abril** (más en marzo, febrero y enero), es decir, en plena temporada de lluvias.
- **Diferencia grande entre departamentos:** en Tumbes se capturan el 46 % de las emergencias; en **Piura, solo el 5 %**. Los distritos con más falsos negativos son Pampas de Hospital, San Jacinto, San Juan de la Virgen, Zarumilla, Sullana y Corrales.

### 3.4 Lectura honesta

1. El modelo principal **supera a la climatología con probabilidad 0,92**, pero el intervalo de la diferencia **incluye el cero**. Con 8 años de prueba no se puede afirmar que gane. Es una mejora **posible, no demostrada**.
2. LightGBM **no mejora la línea base**: con 311 positivos se sobreajusta. No conviene usar modelos más complejos (LSTM/GRU) con esta muestra.
3. Las probabilidades sin calibrar **no deben mostrarse como probabilidades**. El tablero usa un percentil del riesgo (0–100), que está bien, pero no debe decir «X % de probabilidad».
4. Casi todo el poder viene de la **historia del distrito y la estacionalidad** (SHAP: `frecuencia_historica` 1,26 y `cos_semana` 0,47; la lluvia y el caudal valen menos de 0,21). La lluvia de NASA POWER en celdas de ~50 km diferencia poco a distritos vecinos.
5. **Fuga leve que hay que documentar:** las variables de exposición (personas y edificaciones en zona inundable) son de 2026 y se usan en semanas de 2001–2015. No son información del futuro sobre la etiqueta, pero sí un **anacronismo**. La versión simple no las usa.
6. No hay etiquetas fechadas después de 2015, así que **2017 y 2023 solo se revisan por ranking**, no con métricas. El ranking se mantiene (puestos 1 y 2 de 11), pero el índice de riesgo medio durante el evento es apenas **1,1 veces** (2017) y **1,0 veces** (2023) el de los mismos meses en años normales (`riesgo.json → revision`). **La señal es débil:** sirve para ordenar años, no para alertar semanas.

## 4. Caso A: susceptibilidad espacial (plan, sin entrenar)

**Por qué no se entrena ahora:** las únicas «etiquetas» espaciales son las huellas de radar propias (sesgadas hacia el desierto de Sechura y sin las ciudades) y el JRC (un modelo). Un clasificador entrenado con ellas aprendería a **reproducir el sesgo del algoritmo**, y validarlo contra la misma fuente daría una precisión engañosa.

**Datos que faltan:** (i) HAND (calculable con el DEM Copernicus GLO-30 y una red de drenaje, por ejemplo con `pysheds`/`whitebox`); (ii) uso del suelo (ESA WorldCover 10 m, CC BY 4.0); (iii) distancia a ríos (red hidrográfica ANA o derivada del DEM); (iv) **etiquetas independientes**: polígonos de inundación digitalizados sobre imágenes ópticas de alta resolución de marzo-abril de 2017 y de 2023, o mapas de activaciones de emergencia si existen.

**Diseño propuesto:**

- Muestreo estratificado por clase en celdas de 250 m, sin píxeles vecinos.
- Validación **por cuenca** (entrenar con Piura y Chira, probar con Tumbes, y rotar) y **por evento** (entrenar 2017, probar 2023) (Roberts et al., 2017).
- Línea base: reglas HAND < 5 m y distancia < 1 km. Modelos: logística, Random Forest, LightGBM.
- Métricas: PR-AUC, F1, IoU y recall de la clase inundada, con atención a los falsos negativos urbanos.
- Explicación con SHAP o importancia por permutación, leída con cautela.
- **Test final intocado:** la cuenca de Tumbes y el evento 2023.

## 5. Caso B: clasificación SAR (plan, sin entrenar)

**Comparación propuesta:** umbral fijo −17/−18 dB (actual) frente a Otsu global (ya implementado como diagnóstico en `huellas.py`), frente a Bmax/Otsu por teselas (Chini et al., 2017; Breña Aliaga et al., 2026), frente a Random Forest con VV, VH, ΔVV, ΔVH, HAND y pendiente.

- **Controles:** máscara de agua permanente (JRC Global Surface Water o la referencia seca), HAND para evitar falsos positivos en laderas, máscaras de sombra y *layover*, y estratificación por órbita (ascendente/descendente) y ángulo de incidencia.
- **Referencia independiente:** 300–500 puntos o polígonos interpretados sobre imágenes ópticas de fechas cercanas a cada pasada, estratificados en urbano, agrícola, desierto y humedal.
- **Métricas:** IoU, precisión, recall y F1 por estrato, y matriz de confusión. **Errores por zona:** urbano (falsos negativos por doble rebote), arrozales (falsos positivos por riego), Sechura (arena lisa).
- **Clase «ambigua» explícita:** riego, humedal, embalse, sombra radar.

## 6. Datos faltantes que bloquean A y B

| Falta | Para | Fuente candidata (verificar acceso y licencia) |
|---|---|---|
| Polígonos de inundación independientes 2017/2023 | A, B | Imágenes ópticas de alta resolución; mapas de emergencia; levantamientos municipales |
| HAND | A, B | Derivar del DEM Copernicus GLO-30 |
| Uso del suelo | A | ESA WorldCover |
| Emergencias fechadas 2016–2026 | C | SINPAD / INDECI (pedido formal) |
| Caudal **observado** | C | Estaciones hidrométricas SENAMHI / ANA (Puente Sánchez Cerro, El Tigre, Ardilla…) |

## 7. Comandos

```bash
python src/modelo_inundacion.py          # reproduce el caso C
python src/ml_evaluacion.py              # bootstrap por años, calibración y falsos negativos
python src/actualizar_exposicion_base.py # actualiza la exposición de la base tras corregir la población
```

Salidas: `data/modelo/resultados/*.csv`, `data/modelo/resultados/evaluacion_extra.json` y `docs/evidencia/ml_evaluacion.json`.
