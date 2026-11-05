# 18 · ¿El aviso habría anticipado las inundaciones del pasado?

Pregunta: si el tablero hubiera estado funcionando antes de cada inundación que salió en las noticias o que registró INDECI, ¿habría marcado lluvia fuerte o extrema en los días previos? ¿Y cuántas veces habría avisado sin que pasara nada?

Se hicieron tres pruebas. Cada una se corrió tres veces con el mismo resultado.

| Prueba | Qué lluvia usa | Qué mide |
|---|---|---|
| **A. Con pronósticos reales** (`herramientas/pruebas/prueba_aviso_pronostico_real.py` → `docs/evidencia/prueba_aviso_pronostico_real.json`) | Lo que Open-Meteo pronosticaba 1, 2 y 3 días antes (archivo de corridas anteriores, desde 2024), con los mismos umbrales del tablero | Lo que el tablero habría dicho de verdad |
| **B. Con 24 años de emergencias** (`herramientas/pruebas/prueba_aviso_pasado.py` → `docs/evidencia/prueba_aviso_pasado.json`) | La lluvia que cayó (NASA POWER por distrito) y el caudal de los ríos (GloFAS), con pronóstico perfecto | Si la regla del aviso separa las semanas con daños de las demás |
| **C. Falsas alarmas** (`herramientas/pruebas/prueba_aviso_temporada.py` → `docs/evidencia/prueba_aviso_temporada.json`) | Pronósticos reales de 1, 2 y 3 días antes, todos los días de ene-abr 2025 y del 15/10 al 4/11/2026 | Cuántos avisos habría dado y cuántos fueron seguidos de daño |

## A. Con los pronósticos que había antes de cada evento

Un evento cuenta como avisado si el pronóstico hecho 1, 2 o 3 días antes ya pasaba el percentil 95 de su provincia («fuerte»). Si pasaba el 99, el nivel es «extremo».

| Evento | 3 días antes | 2 días antes | 1 día antes | ¿Avisó? |
|---|---|---|---|---|
| 12/2/2025 · San Jacinto · desborde del río Tumbes, 1 284 ha de cultivo | normal (13 mm) | normal (11 mm) | normal (5 mm) | **No** |
| 20/10/2026 · Piura · calles inundadas | normal | **fuerte** (31 mm) | normal | Sí, 2 días antes |
| 20/10/2026 · Chulucanas · calles y mercado inundados | normal | normal | **fuerte** (34 mm) | Sí, 1 día antes |
| 25/10/2026 · Ayabaca · calles y viviendas inundadas | **fuerte** (40 mm) | normal | normal | Sí, 3 días antes |
| 28/10/2026 · Piura · calles bajo el agua | **fuerte** (48 mm) | normal | normal | Sí, 3 días antes |
| 29/10/2026 · Canchaque · desborde del río Serrán | normal | **extremo** (93 mm) | **extremo** (43 mm) | Sí, 2 días antes |
| 2/11/2026 · Aguas Verdes · desborde del río Zarumilla | **extremo** (59 mm) | **fuerte** (40 mm) | **extremo** (71 mm) | Sí, 3 días antes |
| 2/11/2026 · Tumbes · calles inundadas, quebradas activas | **fuerte** (38 mm) | **fuerte** (45 mm) | **extremo** (98 mm) | Sí, 3 días antes |
| 2/11/2026 · San Jacinto · quebrada Vaquería activada | **fuerte** (32 mm) | **extremo** (85 mm) | **extremo** (105 mm) | Sí, 3 días antes |
| 2/11/2026 · Máncora · calles inundadas | normal | **fuerte** (22 mm) | **fuerte** (22 mm) | Sí, 2 días antes |

**Resultado:**
- **9 de 10 eventos habrían tenido aviso fuerte o extremo antes de ocurrir.** 5 de ellos, con 3 días de anticipación.
- El único que no se habría avisado es el desborde del río Tumbes de febrero de 2025. Ese río nace en Ecuador: su crecida viene de la lluvia aguas arriba, no de la que cae en San Jacinto.
- El pronóstico a veces sube y baja de un día a otro (Piura, 20/10; Ayabaca, 25/10). Por eso conviene mirar el aviso de varios días seguidos.

**Límite:** solo se probaron días en que **sí** hubo daño, así que esta prueba no mide las falsas alarmas. Eso lo mide la prueba B.

## B. Con 24 años de emergencias de INDECI (2003 a junio de 2026)

Se tomaron 92 031 semanas-distrito (75 distritos) y las emergencias de SINPAD por distrito y semana (`data/modelo/sinpad_tumbes_piura_semanal.csv`). Hay aviso en una semana si algún día de esa semana, o de los 3 últimos días de la anterior, superó el umbral del distrito (2001-2020).

| Señal | Semanas con inundación que tuvieron aviso | De las semanas con aviso, cuántas tuvieron viviendas afectadas | Una semana con aviso tiene viviendas afectadas… | Viviendas afectadas que cayeron en semanas con aviso | Avisos por distrito y año |
|---|---|---|---|---|---|
| Lluvia > p95 (todos los distritos) | 30 % | 18 % | 10,8 veces más que una sin aviso | 49 % | 2,2 |
| Lluvia > p99 (todos los distritos) | 10 % | 20 % | 9,7 veces más | 19 % | 0,7 |
| Caudal del río > p95 (distritos de los ríos Piura, Chira y Tumbes) | 65 % | 11 % | 18,2 veces más | 83 % | 5,9 |
| Lluvia o caudal (mismos distritos de río) | 70 % | 11 % | 20,6 veces más | 86 % | 6,3 |

**¿No es solo la temporada de lluvias?** En los distritos de río se repitió la cuenta solo con las semanas de febrero a abril. Aun así, una semana con caudal alto tuvo viviendas afectadas el 11,3 % de las veces, frente a 2,3 % sin caudal alto. Con lluvia fuerte, 26,4 % frente a 4,0 %. Las dos señales agregan información más allá de la estación.

**Las 15 semanas-distrito con más viviendas afectadas:** 8 tuvieron aviso de lluvia (fuerte o extremo) y 7 no. Entre las que no:
- Tumbes, febrero de 2006 (13 072 viviendas);
- Tambogrande, abril de 2023 (10 124);
- Catacaos, abril de 2023 (3 918).

Esas fueron crecidas de río o registros que INDECI hizo días después del evento.

## C. Falsas alarmas con pronósticos reales

La prueba A solo miró los días con daño, así que no dice cuántas veces el aviso habría sonado sin que pasara nada. Esta prueba mira **todos los días y todos los distritos** de dos temporadas y cuenta tres cosas:

- **avisos**: cuántas veces el tablero habría marcado «fuerte» o «extremo»;
- **avisos seguidos de daño**: de esos avisos, cuántos tuvieron daño registrado después;
- **daños con aviso previo**: de los daños registrados, cuántos tuvieron aviso antes.

Script: `herramientas/pruebas/prueba_aviso_temporada.py`. Salida: `docs/evidencia/prueba_aviso_temporada.json` (tablas) y `docs/evidencia/prueba_aviso_temporada_distritos.csv` (cada distrito en cada temporada). Se corrió tres veces y dio lo mismo.

### Cómo se hizo

**Lluvia.** Se usó lo que Open-Meteo pronosticaba 1, 2 y 3 días antes (archivo de corridas anteriores), en el punto central de los 76 distritos y con los mismos umbrales del tablero (p95 y p99 de su provincia). No se usa la lluvia que cayó: se usa lo que se sabía antes.

**Caudal.** Solo para los 38 distritos de los ríos Piura, Chira y Tumbes. El nivel sube a «fuerte» si el río pasa su p95 del caudal diario 2001-2020, y a «extremo» si pasa su p99:

| Río | p95 (m³/s) | p99 (m³/s) |
|---|---|---|
| Chira | 1 387,7 | 2 419,8 |
| Piura | 305,9 | 854,0 |
| Tumbes | 764,2 | 1 277,9 |

Open-Meteo no guarda los pronósticos de caudal tal como salieron cada día. Por eso se probaron dos versiones:

- **caudal conocido**: el caudal del día en que se habría dado el aviso, o sea, lo que ya se sabía;
- **caudal real**: el caudal del mismo día del daño, como si el pronóstico del río fuera perfecto.

Las dos dan casi lo mismo, así que esa falta no cambia la conclusión.

**Daños.**

- 2025: semanas con registro de lluvia intensa o inundación en el SINPAD del INDECI (`data/modelo/sinpad_tumbes_piura_semanal.csv`). La unidad es distrito-semana, como en la prueba B. Una semana tiene aviso si hubo aviso algún día de esa semana o en los tres últimos días de la semana anterior.
- 2026: el SINPAD aún no publica estos meses. Se usaron los 7 eventos de `data/eventos/catalogo_verificado.csv` y, aparte, otros 7 titulares que `src/noticias.py` ubicó por distrito. La unidad es distrito-día. Un aviso cuenta como «seguido de daño» si hubo daño ese día o el siguiente. Un daño cuenta como «con aviso previo» si hubo aviso para ese día o el anterior.

### Enero a abril de 2025 (76 distritos × 18 semanas = 1 368 distrito-semanas)

De las 1 368 distrito-semanas, 252 tuvieron daño en el SINPAD (18,4 %). Si el aviso sonara al azar, 18,4 % de sus avisos irían seguidos de daño.

| Aviso con… | Semanas con aviso | Seguidas de daño | Daños con aviso previo | Semanas con aviso por distrito (de 18) |
|---|---|---|---|---|
| Lluvia, 1 día antes | 194 | 43,8 % | 33,7 % | 2,6 |
| Lluvia, 2 días antes | 133 | 51,9 % | 27,4 % | 1,8 |
| Lluvia, 3 días antes | 129 | 49,6 % | 25,4 % | 1,7 |
| **Lluvia (1, 2 o 3 días antes)**, el aviso de antes | **247** | **42,9 %** | **42,1 %** | **3,2** |
| **Lluvia o caudal conocido**, el aviso nuevo | **597** | **26,3 %** | **62,3 %** | **7,9** |
| Lluvia o caudal real | 564 | 27,8 % | 62,3 % | 7,4 |
| Lluvia o caudal conocido sobre p99 | 328 | 33,5 % | 43,7 % | 4,3 |
| Lluvia o caudal real sobre p99 | 315 | 35,9 % | 44,8 % | 4,1 |

Solo los 38 distritos de los tres ríos (684 distrito-semanas, de las que 72 tuvieron daño, o sea 10,5 %):

| Aviso con… | Semanas con aviso | Con aviso y daño | Seguidas de daño | Daños con aviso previo |
|---|---|---|---|---|
| Lluvia (1, 2 o 3 días antes) | 36 | 15 | 41,7 % | 20,8 % |
| Lluvia o caudal conocido | 386 | 66 | 17,1 % | 91,7 % |
| Lluvia o caudal real | 353 | 66 | 18,7 % | 91,7 % |
| Lluvia o caudal conocido sobre p99 | 117 | 19 | 16,2 % | 26,4 % |
| Lluvia o caudal real sobre p99 | 104 | 22 | 21,2 % | 30,6 % |

Si solo se cuentan las semanas con viviendas afectadas o destruidas (240 semanas), queda casi igual. Con la lluvia, 40,9 % de los avisos van seguidos de daño y 42,1 % de los daños tuvieron aviso. Con lluvia o caudal conocido, esas cifras son 25,0 % y 62,1 %.

Por qué el caudal agrega tantos avisos: entre enero y abril de 2025 el Chira pasó su p95 en 27 de 120 días, el Piura en 39 y el Tumbes en 21. Un río alto se mantiene así varias semanas. Mientras tanto, el aviso queda encendido en todos sus distritos, haya o no daño registrado.

El caso de San Jacinto del 12/2/2025, que la prueba A no avisó, tampoco lo habría avisado el río. El caudal más alto del Tumbes esos días fue 759,3 m³/s el 9/2, apenas debajo de su p95 (764,2).

### 15 de octubre al 4 de noviembre de 2026 (76 distritos × 21 días = 1 596 distrito-días)

| Aviso con… | Días con aviso | Seguidos de daño | Daños verificados con aviso previo (de 7) | Con noticias ubicadas: daños con aviso previo (de 14) |
|---|---|---|---|---|
| Lluvia, 1 día antes | 185 | 5,4 % | 6 | 9 |
| Lluvia, 2 días antes | 186 | 3,8 % | 6 | 8 |
| Lluvia, 3 días antes | 165 | 3,6 % | 3 | 7 |
| **Lluvia (1, 2 o 3 días antes)** | **317** | **3,8 %** | **7** | **12** |
| **Lluvia o caudal conocido** | **334** | **3,6 %** | **7** | **12** |
| Lluvia o caudal real | 334 | 3,6 % | 7 | 12 |
| Lluvia o caudal conocido sobre p99 | 320 | 3,8 % | 7 | 12 |

«Seguidos de daño» usa solo los 7 eventos verificados. Con las noticias, esa cifra sube a 6,0 % para la lluvia y a 5,7 % con el caudal. Un mismo daño puede venir después de dos días con aviso, por eso hay 12 días con aviso seguidos de daño para 7 daños.

En promedio, cada distrito tuvo aviso 4,2 de los 21 días. Hay distritos con muchos avisos y ningún daño conocido: Sapillica 15 días, y Frías, Pampas de Hospital y Matapalo 14 días cada uno. Los dos daños de noticias que no tuvieron aviso son Piura el 2/11 y Tumbes el 22/10.

En esta temporada el río casi no cambia nada. Solo el Tumbes pasó su p95 (6 de los 21 días): agregó 17 distrito-días con aviso y ningún daño más con aviso, porque esos daños ya tenían aviso por lluvia.

### Qué se concluye de la prueba C

1. **El aviso por lluvia acierta más que el azar, pero da muchas falsas alarmas.** En 2025, 43 de cada 100 semanas con aviso tuvieron daño registrado, frente a 18 si el aviso sonara al azar. Avisó antes de 42 de cada 100 semanas con daño. En 2026 avisó antes de los 7 daños verificados, pero solo 4 de cada 100 días con aviso fueron seguidos de un daño conocido.
2. **Mirar 1, 2 y 3 días antes ayuda.** Con solo el pronóstico de 1 día antes se avisan 34 de cada 100 semanas con daño. Con los tres se avisan 42.
3. **El caudal sube mucho la detección en los distritos de los ríos, pero también las falsas alarmas.** En 2025 pasó de 21 a 92 de cada 100 semanas con daño, y los avisos pasaron de 36 a 386. Para que el río no encienda el aviso semanas seguidas, una opción es subir su umbral al p99, aunque así se pierde casi toda la ganancia en detección (26 %). La otra es dejar el p95 y mostrar el motivo del aviso, como ya hace el tablero, para que se vea cuándo es por el río y cuándo por la lluvia. El equipo debe decidir cuál usar. Esta prueba no basta para elegir.
4. **«Falsa alarma» aquí quiere decir «sin daño registrado», no «no pasó nada».** Muchos daños pequeños no llegan al SINPAD ni a las noticias.

### Límites de la prueba C

- **Pronóstico de caudal.** No existe un archivo de los pronósticos de caudal tal como salieron. Las dos versiones (caudal conocido y caudal real) encierran al pronóstico real y dan casi lo mismo.
- **Cálculo de la lluvia.** La lluvia pronosticada se descargó y se pasó a niveles desde el navegador, con el mismo método del script: suma de las horas del día en hora de Lima y los mismos umbrales. Se guardaron los niveles (`docs/evidencia/aviso_temporada_niveles.txt`), no los milímetros. El archivo con los milímetros (`docs/evidencia/aviso_temporada_pronosticos.csv`) se arma corriendo el script sin `--niveles`; eso necesita red y no se pudo correr aquí. Se comprobó un caso contra la prueba A: San Jacinto, 1/11/2026, con 105,1, 84,9 y 32,4 mm, da extremo, extremo y fuerte.
- **Fechas del SINPAD.** La semana del SINPAD es la semana en que se registró la emergencia, que no siempre es el día del daño. Por eso se usa la semana y no el día.
- **Pocos casos en 2026.** Hay solo 7 eventos verificados en 21 días, así que un evento más o menos cambia mucho los porcentajes. Las 7 noticias extra se ubicaron de forma automática y nadie las revisó.
- **Un punto por distrito.** El pronóstico se toma en un solo punto por distrito. En distritos grandes de la sierra, la lluvia de un extremo no siempre llega a ese punto.
- **Distritos unidos.** Veintiséis de Octubre se cuenta dentro de Piura y Canoas de Punta Sal dentro de Zorritos, porque el mapa de distritos que usa el tablero no los separa.

## Qué se concluye

1. **Sí hay señal.** Con los pronósticos reales, 9 de 10 eventos recientes habrían tenido aviso entre 1 y 3 días antes. En 24 años, las semanas con aviso tienen unas 10 veces más probabilidad de daños.
2. **La lluvia sola no basta en los valles.** Las crecidas del río Tumbes (2023, 2025) y parte de las del Piura vienen de lluvia aguas arriba. El caudal detecta el 65 % de las semanas con inundación en los distritos de río; la lluvia local, el 26 %. **Hecho (5/11/2026):** el aviso del tablero ya suma el caudal en los distritos de río (`src/aviso_lluvia.py`). La prueba C muestra el costo: más avisos. Queda por decidir la regla del río (p95, p99 u otra).
3. **Muchas falsas alarmas por distrito.** De cada 100 semanas con aviso de lluvia, unas 18 tuvieron viviendas afectadas en ese distrito. Es lo esperable en un aviso que busca no dejar pasar eventos, pero hay que decirlo: el aviso dice «prepárate», no «se va a inundar».
4. **Los datos de lluvia gruesos no ven tormentas locales.** El 2/11/2026 NASA POWER registró 9 mm en Tumbes y 0,1 mm en Máncora. Ese día el SENAMHI midió 110,3 mm en El Salto (Zarumilla) ([Andina](https://andina.pe/ingles/noticia-el-nino-tumbes-endures-extraordinary-rainfall-of-up-to-110-liters-per-square-meter-1098315.aspx)). Por eso la prueba B subestima los aciertos de los eventos urbanos. Los pronósticos de Open-Meteo (prueba A) sí marcaron esos días.

## Límites

- La prueba A cubre 10 eventos, todos con daño: no mide falsas alarmas. Ampliarla a toda la temporada 2025-2026 necesita miles de consultas al archivo de pronósticos.
- La prueba B usa lluvia y caudal observados (pronóstico perfecto): es la mejor nota posible de la regla, no del pronóstico.
- SINPAD registra por semana de registro, que puede ser posterior al evento.
- Los umbrales de la prueba B salen de NASA POWER por distrito; los del tablero, de ERA5 por provincia. Cada prueba usa umbrales del mismo dato que compara.
