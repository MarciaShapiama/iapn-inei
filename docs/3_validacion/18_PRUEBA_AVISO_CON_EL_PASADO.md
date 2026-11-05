# 18 · ¿El aviso habría anticipado las inundaciones del pasado?

Pregunta: si el tablero hubiera estado funcionando antes de cada inundación que salió en las noticias o que registró INDECI, ¿habría marcado lluvia fuerte o extrema en los días previos? ¿Y cuántas veces habría avisado sin que pasara nada?

Se hicieron dos pruebas. Cada una se corrió tres veces con el mismo resultado.

| Prueba | Qué lluvia usa | Qué mide |
|---|---|---|
| **A. Con pronósticos reales** (`herramientas/pruebas/prueba_aviso_pronostico_real.py` → `docs/evidencia/prueba_aviso_pronostico_real.json`) | Lo que Open-Meteo pronosticaba 1, 2 y 3 días antes (archivo de corridas anteriores, desde 2024), con los mismos umbrales del tablero | Lo que el tablero habría dicho de verdad |
| **B. Con 24 años de emergencias** (`herramientas/pruebas/prueba_aviso_pasado.py` → `docs/evidencia/prueba_aviso_pasado.json`) | La lluvia que cayó (NASA POWER por distrito) y el caudal de los ríos (GloFAS), con pronóstico perfecto | Si la regla del aviso separa las semanas con daños de las demás |

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

## Qué se concluye

1. **Sí hay señal.** Con los pronósticos reales, 9 de 10 eventos recientes habrían tenido aviso entre 1 y 3 días antes. En 24 años, las semanas con aviso tienen unas 10 veces más probabilidad de daños.
2. **La lluvia sola no basta en los valles.** Las crecidas del río Tumbes (2023, 2025) y parte de las del Piura vienen de lluvia aguas arriba. El caudal detecta el 65 % de las semanas con inundación en los distritos de río; la lluvia local, el 26 %. **Mejora propuesta:** sumar el caudal al aviso de los distritos de río, que hoy solo usa la lluvia.
3. **Muchas falsas alarmas por distrito.** De cada 100 semanas con aviso de lluvia, unas 18 tuvieron viviendas afectadas en ese distrito. Es lo esperable en un aviso que busca no dejar pasar eventos, pero hay que decirlo: el aviso dice «prepárate», no «se va a inundar».
4. **Los datos de lluvia gruesos no ven tormentas locales.** El 2/11/2026 NASA POWER registró 9 mm en Tumbes y 0,1 mm en Máncora. Ese día el SENAMHI midió 110,3 mm en El Salto (Zarumilla) ([Andina](https://andina.pe/ingles/noticia-el-nino-tumbes-endures-extraordinary-rainfall-of-up-to-110-liters-per-square-meter-1098315.aspx)). Por eso la prueba B subestima los aciertos de los eventos urbanos. Los pronósticos de Open-Meteo (prueba A) sí marcaron esos días.

## Límites

- La prueba A cubre 10 eventos, todos con daño: no mide falsas alarmas. Ampliarla a toda la temporada 2025-2026 necesita miles de consultas al archivo de pronósticos.
- La prueba B usa lluvia y caudal observados (pronóstico perfecto): es la mejor nota posible de la regla, no del pronóstico.
- SINPAD registra por semana de registro, que puede ser posterior al evento.
- Los umbrales de la prueba B salen de NASA POWER por distrito; los del tablero, de ERA5 por provincia. Cada prueba usa umbrales del mismo dato que compara.
