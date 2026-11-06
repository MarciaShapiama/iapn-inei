# 06 · Guía de preguntas del jurado

Veinte preguntas difíciles que puede hacer un jurado del INEI que conoce la metodología. Cada una tiene una respuesta corta para decir en voz alta, la cifra que la respalda y de dónde sale.

Las cifras con ruta (por ejemplo, `dashboard/data/inundacion.json`) están en el repositorio y se pueden abrir en la sustentación. Las del modelo nuevo salen de la tarea 1 (`resultados_modelo/`).

---

## A. Datos y fuentes

**1. ¿Por qué usan WorldPop y no el censo para contar personas?**
Porque cuando armamos el tablero no teníamos la población del censo por manzana; ya la pedimos al INEI. Comprobamos que WorldPop no se aleja del censo en el total de Piura.
- Cifra: WorldPop da 2 120 104 habitantes en Piura; los Censos Nacionales 2025, unos 2 115 000. La diferencia es 0,2 %.
- Fuente: `docs/1_datos/01_AUDITORIA_TECNICA_Y_DATOS.md`, sección 10.5; [Panamericana, cifras del INEI](https://panamericana.pe/nacionales/471688-inei-entrega-informacion-actualizada-situacion-poblacion-viviendas-piura-llegada-fenomeno-nino).

**2. ¿«Expuesto» es lo mismo que «afectado» o «damnificado»?**
No. Expuesto es quien vive donde una crecida grande podría llegar. Afectado es quien registró daño en una emergencia. Esa cifra la da el INDECI.
- Cifra: 399 506 personas viven en la zona de la crecida de 1 en 100 años. En 2017, el SINPAD registró 85 960 viviendas afectadas en Tumbes y Piura.
- Fuente: `dashboard/data/inundacion.json`; SINPAD, INDECI ([datos abiertos](https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento)).

**3. ¿Qué quiere decir «crecida de 1 en 100 años»?**
Que cada año hay 1 % de probabilidad de una crecida así. No es un pronóstico para este año ni algo que pasa cada 100 años exactos.
- Cifra: en 30 años, la probabilidad de que ocurra al menos una vez es 1 − 0,99³⁰ ≈ 26 %.
- Fuente: definición del periodo de retorno; mapas JRC CEMS-GloFAS.

**4. ¿Cómo saben que la zona inundable de JRC es realista?**
La comparamos con el mapa oficial de la inundación de 2017. Cubre casi todo lo que se inundó, pero también marca mucho que no se inundó: es un escenario extremo y no considera diques.
- Cifra: cubre el 85 % del área inundada según Copernicus; solo el 32 % de lo que marca se inundó.
- Fuente: `dashboard/data/validacion_2017.json` (Copernicus EMS, EMSR199).

**5. Si el radar es satelital, ¿por qué no vio las inundaciones de estos días?**
Por cuatro razones:
- El radar ve agua abierta en el llano, no el agua entre casas.
- Excluye lo que está a más de 250 m de altura.
- Pasa por cada lugar unas 6 veces en 24 días.
- Las noticias de estos días son de calles anegadas y de la sierra.

Por eso, para anticipar usamos el pronóstico de lluvia, y el radar solo para confirmar.
- Cifra: el radar detecta el 42 % de lo inundado en 2017, y el 63 % de lo que marca coincide.
- Fuente: `docs/3_validacion/09_PRUEBA_DETECTOR_NOTICIAS.md`; `dashboard/data/validacion_2017.json`.

**6. ¿De dónde sacan la cifra real de viviendas afectadas para entrenar el modelo?**
Del SINPAD del INDECI, publicado en datos abiertos con distrito y fecha de cada emergencia, de 2003 a junio de 2026. Lo contrastamos con la cifra oficial de 2017.
- Cifra: 3 363 emergencias por lluvia o inundación en Tumbes y Piura. Para 2017, el SINPAD suma 85 960 viviendas afectadas y el informe de OCHA con cifras del INDECI, 85 743: una diferencia de 0,3 %.
- Fuente: [INDECI, datos abiertos](https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento); `01_modelo_viviendas_afectadas.md`.

**7. ¿Por qué mezclan «lluvia intensa» con «inundación» si la pregunta es por desborde de ríos?**
Porque el SINPAD registra casi todo como lluvia intensa, aunque haya desborde. Separarlos dejaría muy pocos casos. El código guarda los dos tipos por separado, para hacer la prueba solo con desbordes si se pide.
- Cifra: en Tumbes y Piura, 3 135 registros de lluvia intensa frente a 228 de inundación. En las tablas del INDECI 2003-2024 de Piura hay 997 173 afectados por lluvia intensa y 130 482 por inundación.
- Fuente: `01_modelo_viviendas_afectadas.md`; `data/modelo/indeci/7162837-piura_afect_prov_dist_peligro.xlsx`.

**8. ¿Las viviendas del censo en zona inundable incluyen a todos?**
No. El INEI nos dio las viviendas por manzana, y la vivienda rural dispersa no está en manzanas. Por eso la cifra es un mínimo.
- Cifra: 107 166 viviendas ocupadas en la zona de 1 en 100 años. En Piura, las manzanas suman 481 159 viviendas ocupadas, cerca del 80 % de las unas 598 mil que da el censo (747 mil particulares, 80 % ocupadas).
- Fuente: `dashboard/data/viviendas_censo.json`; [Panamericana, cifras del INEI](https://panamericana.pe/nacionales/471688-inei-entrega-informacion-actualizada-situacion-poblacion-viviendas-piura-llegada-fenomeno-nino).

## B. Método y validación

**9. ¿Por qué distrito y semana, y no día?**
Porque el SINPAD registra por distrito y con la fecha del reporte, que puede ser días después del desborde. Además, por día casi todo sería cero.
- Cifra: por semana, el 2,3 % de las filas tiene viviendas afectadas; por día sería menos del 0,5 %.
- Fuente: `01_modelo_viviendas_afectadas.md`, sección 2.

**10. ¿Cómo evitan que el modelo «vea el futuro»?**
Tres reglas:
- Cada año de prueba se predice entrenando solo con los años anteriores.
- Todas las variables son de la semana anterior.
- La historia del distrito se calcula solo con años pasados.
- Cifra: 14 años de prueba, de 2012 a 2025.
- Fuente: `modelo_afectados.py`.

**11. ¿El modelo es mejor que no tener modelo?**
Sí, para ordenar dónde y cuándo habrá viviendas afectadas. La referencia es el promedio histórico del distrito en ese mes.
- Cifra: PR-AUC de 0,175 frente a 0,122; correlación de orden entre distritos de 0,38 frente a 0,27; 30 % de acierto en los 10 distritos más afectados, frente a 25 %.
- Fuente: `resultados_modelo/anticipacion/metricas_resumen.csv`.

**12. ¿Por qué no reportan el error absoluto medio como métrica principal?**
Porque con tantos ceros esa métrica premia no predecir nada.
- Cifra: un modelo que siempre dice cero saca 6,96, mejor que todos los modelos (de 9,1 a 17,8). El 97,7 % de las semanas no tiene viviendas afectadas.
- Fuente: `resultados_modelo/anticipacion/metricas_resumen.csv`.

**13. ¿Cuánto se equivoca en los años que más importan?**
Ordena bien, pero subestima la cantidad en años extremos.
- Cifra: en 2017 estima 60 137 viviendas afectadas o destruidas frente a 100 621 reales (−40 %) y acierta 5 de los 10 distritos más afectados. En 2023, 33 670 frente a 131 594 (−74 %), con 7 de 10.
- Fuente: `resultados_modelo/anticipacion/ranking_2017_2023.csv`.

**14. ¿Por qué no usaron un modelo más complejo?**
Lo probamos. Con pocos eventos, los modelos complejos se aprenden los casos de memoria y no generalizan.
- Cifra: el gradient boosting saca un PR-AUC de 0,162, frente a 0,175 del modelo de dos etapas, y su error en el total varía más (77 % frente a 53 %). En el modelo de alerta anterior, LightGBM sacó 0,082, por debajo de la referencia (0,095).
- Fuente: `resultados_modelo/`; `docs/2_modelo/modelo_inundacion.md`.

**15. ¿Cuánto ganarían con un mejor pronóstico de lluvia?**
Probamos el caso ideal: usar la lluvia que de verdad cayó esa semana, como si el pronóstico fuera perfecto. Eso marca el techo.
- Cifra: el PR-AUC sube de 0,175 a 0,227.
- Fuente: `resultados_modelo/con_lluvia_de_la_semana/metricas_resumen.csv`.

**16. ¿Su aviso de lluvia es oficial? ¿Cómo decide?**
No es oficial; los avisos oficiales son del SENAMHI. Compara la lluvia pronosticada para cada distrito con lo que es extremo en su provincia, según 30 años de datos.
- Cifra: en Zarumilla es «fuerte» desde 28 mm en un día y «extremo» desde 56 mm (percentiles 95 y 99 de ERA5 1991-2020). El 5/11 marcó 2 distritos en extremo y 14 en fuerte, todos en provincias donde el SENAMHI también avisó lluvia fuerte o extrema.
- Fuente: `dashboard/data/aviso_lluvia.json`; [Andina, 4/11/2026](https://andina.pe/agencia/noticia-senamhi-piura-y-tumbes-soportaran-lluvias-extrema-intensidad-hoy-y-manana-jueves-5-1098628.aspx); `05_prueba_aviso_lluvia.md`.

## C. Uso, confidencialidad y aporte al INEI

**17. ¿Cómo protegen los datos confidenciales del censo?**
Solo publicamos totales por distrito, nunca por manzana. Ocultamos los distritos con menos de 10 viviendas en la zona y, si en un departamento queda uno solo oculto, también el siguiente más chico. Los archivos del INEI no están en GitHub.
- Cifra: regla de 10 viviendas, con supresión secundaria.
- Fuente: `dashboard/data/viviendas_censo.json` (método); `02_cruce_habitantes.md`.

**18. ¿El mapa tiene los 78 distritos de Tumbes y Piura?**
Sí, desde el 6/11/2026. Antes usábamos GADM 4.1, que tiene 76: no separaba Veintiséis de Octubre ni Canoas de Punta Sal. Ahora los límites salen del servicio oficial del INEI (Infraestructura de Datos Espaciales, capa Distrito), con su UBIGEO. Los totales casi no cambiaron: en la zona de 1 en 100 años, 400 198 personas (antes 399 506, +0,2 %) y 148 431 edificaciones (antes 148 348, +0,1 %).
- Cifra: 78 distritos (65 de Piura y 13 de Tumbes), incluidos 200115 y 240203. Detalle en `docs/1_datos/20_MAPA_78_DISTRITOS_INEI.md`.
- Fuente: `docs/1_datos/01_AUDITORIA_TECNICA_Y_DATOS.md`, sección 10.6; `dashboard/data/viviendas_censo.json`.

**19. ¿Qué tan grave es este El Niño frente al de 1997-98?**
Según los datos oficiales, el mar frente a Tumbes y Piura está más caliente que en el pico de 1997-98.
- Cifra: Niño 1+2 a +5,4 °C en la semana del 28/10/2026, frente al máximo de +4,0 °C del 13/08/1997. El ENFEN (comunicado 19-2026, 30/10/2026) está en Alerta de El Niño Costero y espera una magnitud extraordinaria hasta febrero de 2027.
- Fuente: `data/noaa_semanal.csv` (NOAA CPC); `dashboard/data/enfen.json` ([comunicado](https://www.gob.pe/institucion/senamhi/informes-publicaciones/8777166-comunicado-oficial-enfen-n-19-2026)).

**20. ¿Qué le aporta esto al INEI?**
Une el censo del INEI con el peligro, el pronóstico y los registros del INDECI, en un mismo distrito y semana. Así se puede priorizar dónde las viviendas son más frágiles.
- Cifra: de las 107 166 viviendas en zona inundable, 36 183 (34 %) tienen paredes de tierra o precarias. En La Arena son el 64 % y en Cura Mori, el 63 %.
- Fuente: `dashboard/data/viviendas_censo.json`.

---

## Tres consejos para responder

1. **Empezar por la cifra y después explicar.** «Cubre el 85 % de lo inundado en 2017; eso significa que…».
2. **Decir el límite antes de que lo pregunten.** «El radar es un mínimo: ve el 42 %». Un jurado de metodología valora más eso que una cifra grande sin contexto.
3. **No confundir los nombres:** expuesto, afectado y damnificado; vivienda y edificación; aviso del proyecto y alerta oficial.
