# Modelo de alerta de inundaciones · Tumbes y Piura

**Pregunta:** ¿habrá una emergencia por inundación o lluvias en el distrito en las próximas 4 semanas?

## Datos
- `data/modelo/base_distrito_semana.csv`: 78 distritos × semanas desde 2001 (75 antes del 6/11/2026, con el mapa GADM) (se actualiza los lunes).
- Etiqueta: `emergencia_1a4` (DesInventar, fuente INDECI). Solo tiene fechas hasta **2015**.
- Variables: lluvia de 7, 30 y 90 días y sus anomalías (NASA POWER); caudal del río más cercano (GloFAS); Niño 1+2 y 3.4; exposición (zona inundable 1 en 10 y 1 en 100 años, viviendas, personas); época del año.
- Totales del INDECI 2003-2024 por provincia, sin fechas: `data/modelo/indeci/`.

## Cómo se evalúa (las mismas reglas para todos los modelos)
- **Origen móvil por años:** para cada año de 2008 a 2015 se entrena con los años anteriores y se evalúa ese año. Se quitan las 4 últimas semanas del entrenamiento, porque su etiqueta mira dentro del año de prueba.
- `frecuencia_historica` (emergencias del distrito) se calcula **solo con los años de entrenamiento**.
- **Métrica principal: PR-AUC.** Solo el 0,3 % de las semanas tiene emergencia; con clases tan raras la exactitud engaña.
- Métricas complementarias: ROC-AUC, Brier y **captura** (% de emergencias en el 5 % de distrito-semanas con más riesgo).
- **Prueba fuera de muestra:** se entrena con 2001-2015 y se mira si 2017 y 2023 salen como los años más riesgosos entre enero y abril (2016-2026).

## Resultados (`python src/modelo_inundacion.py`)

| Modelo | PR-AUC | ROC-AUC | Captura 5 % |
|---|---|---|---|
| Climatología (referencia sin modelo) | 0,095 | 0,829 | 37 % |
| **Logística simple (principal)** | **0,114** | **0,865** | 30 % |
| Logística completa (20 variables) | 0,122 | 0,846 | 36 % |
| LightGBM regularizado | 0,082 | 0,811 | 33 % |

- **La logística simple es el modelo principal.** Rinde casi igual que la completa, todos sus signos tienen sentido (más lluvia, más caudal y mar más caliente dan más riesgo) y, fuera de muestra, **ubica 2017 en el puesto 1 y 2023 en el puesto 2** de 11 años.
- La logística completa no reconoce 2017: tiene variables de lluvia superpuestas con signos negativos.
- **LightGBM no le gana a la referencia.** Con 311 semanas positivas se sobreajusta, incluso muy regularizado.
- **Lo que más pesa** es la historia del distrito y la época del año. La lluvia, el caudal y el mar suben el riesgo, pero su efecto es moderado.

## Cómo comparar el modelo de Maykol
1. Usar la misma base, los mismos años de prueba (2008-2015) y la misma etiqueta `emergencia_1a4`.
2. Guardar sus predicciones con las columnas `clave, semana, prediccion` y unirlas a `data/modelo/resultados/predicciones_validacion.csv` por `clave` y `semana`.
3. Comparar PR-AUC, ROC-AUC y captura. Ver también si su modelo pone a 2017 y 2023 arriba del ranking de enero a abril.
4. **Para fusionar:** si los dos aportan, promediar sus **rangos** (percentiles) y evaluar la mezcla con las mismas reglas.

## Archivos de salida (`data/modelo/resultados/`)
- `metricas_resumen.csv`, `metricas_por_anio.csv`
- `predicciones_validacion.csv`: predicción de cada modelo para cada distrito-semana de 2008-2015
- `riesgo_2016_hoy.csv`: índice de riesgo 0-100 y alerta (≥ 95, el 5 % más alto de la historia) desde 2016
- `importancia_shap.csv`: contribuciones SHAP de LightGBM
- `dashboard/data/riesgo.json`: para el tablero

## Limitaciones
- Las fechas de emergencias llegan solo a 2015; 2017 y 2023 se revisan con el ranking, no con etiquetas.
- La lluvia de NASA POWER viene en celdas de ~50 km: distritos vecinos comparten valores.
- DesInventar registra emergencias reportadas; puede haber inundaciones sin registro.
