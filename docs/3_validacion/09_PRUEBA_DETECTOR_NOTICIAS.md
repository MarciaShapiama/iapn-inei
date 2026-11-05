# 09 · Prueba del detector con noticias reales (4 de noviembre de 2026)

Pedido del profesor Alexander: si una noticia dice que hubo inundación y el tablero no muestra nada, el detector está fallando. Probamos seis lugares con noticias de fines de octubre y comienzos de noviembre de 2026.

**Cómo se probó** (`herramientas/pruebas/prueba_noticias.py`, resultado en `docs/evidencia/prueba_noticias.json`): en un cuadrado de unos 6 km alrededor de cada localidad se repitió el cálculo de la capa "últimos 24 días" (11/10 al 4/11/2026, referencia seca del 1/8 al 10/10) y se midió cuánto quita cada regla. Las coordenadas son el centro aproximado de la localidad, no el punto exacto de la noticia.

## ¿Los datos están al día?

Sí. La capa se calculó el 4/11/2026 a las 15:05 con pasadas hasta el 3/11. Cada lugar de la costa tuvo 6 pasadas en la ventana; la última fue el **2/11 a las 18:43** (hora de Lima), el mismo día de los desbordes de Tumbes.

## Resultados

| Lugar | Noticia | ¿Pasó el satélite después? | Agua tras las reglas | Qué pasó |
|---|---|---|---|---|
| Aguas Verdes (Puerto Perú), Zarumilla | Desborde del río Zarumilla, 2/11 | Sí, 2/11 18:43 | 0,09 km² (capa publicada: 0) | En la zona inundable de JRC la señal bajó solo 0,2 dB (mediana −9,4 dB): a esa hora no había agua abierta extensa. Lo inundado son calles y casas de Puerto Perú, que el radar no ve |
| San Jacinto (río Tumbes) | Desborde en Vaquería, 2/11 | Sí | 0,19 km² (publicada: 0,09) | Se detecta muy poco. Caída mediana de 0,5 dB en la zona JRC |
| Tumbes (ciudad) | Alerta roja por caudal, 2/11 | Sí | 0,02 km² | La alerta fue por caudal; no hay reporte de desborde en la ciudad. Caída de 0,7 dB |
| Máncora | Lluvia de hora y media inunda calles; quebradas activas, 2/11 | Sí | 0 | Inundación urbana por lluvia, no desborde de río. Los 2 km² que pasaban las reglas eran mar y orilla (agua permanente) |
| Chulucanas | Aguacero inunda calles y mercado, 20/10 (también 27/10 y 2/11) | Sí, 4 pasadas | 0 | Ningún píxel bajó de −17 dB. Es lluvia sobre la ciudad, no desborde |
| Huancabamba (río Serrán) | Crecida, 30/10 | Sí, 4 pasadas | 0 | A 2 110 m de altura: la máscara de 250 m quita todo. JRC no tiene zona inundable ahí |

## Conclusiones

1. **El detector no está roto, pero mide otra cosa.** Detecta agua abierta nueva en el llano (2017: 42 % del mapa oficial de Copernicus, con 63 % de precisión). Ninguna de las noticias es de ese tipo: son calles anegadas por lluvia, desbordes dentro de poblados o crecidas en la sierra.
2. **Por qué "últimos 24 días" casi no muestra agua:** en la caja de estudio se detectan 1 500,9 km² en bruto, pero el 94,6 % se quita con la máscara de tierra (mar, orilla, Ecuador y Lambayeque) y con la limpieza de manchas pequeñas. Quedan 80,5 km². En estos 24 días no hubo una inundación abierta grande como la de 2017.
3. **La lluvia sobre la ciudad es el daño más común.** En las tablas de INDECI 2003–2024 para Piura, los afectados por lluvia intensa son 997 173 y por inundación, 130 482. El tablero no lo modela; ahora lo dice en "Lluvia y ríos".
4. **Bajar el umbral no lo arregla.** Con −15 dB o una caída de 2 dB se marcarían más arena, salinas y sombras, sin ganar las calles inundadas.

## Qué cambiamos y qué queda pendiente

| Acción | Estado |
|---|---|
| Agregar Morropón (Chulucanas), Huancabamba y Ayabaca a "Lluvia y ríos", con su río | Hecho (`src/descargar_zonas.py`, `src/construir.py`) |
| Decir el alcance en el tablero: desborde de ríos en la costa; no huaicos ni deslizamientos | Hecho (`dashboard/index.html`) |
| Explicar en las slides por qué el radar no ve la ciudad | Hecho (`docs/6_presentacion/presentacion/presentacion_agua_paso_a_paso.tex`) |
| Agua en zonas urbanas con coherencia interferométrica de Sentinel-1 (Chini et al., 2019, doi:10.3390/rs11020107) | Pendiente: necesita datos SLC, que no están en Planetary Computer |
| Revisar con Sentinel-2 (óptico) las fechas sin nubes | Pendiente |
| Comparar con el registro de emergencias de INDECI de estos días | Pendiente: pedir a INDECI |

Fuentes de las noticias: [El Comercio](https://elcomercio.pe/peru/tumbes/tumbes-desborde-del-rio-zarumilla-afecta-a-puerto-peru-y-tomas-arizola-fenomeno-el-nino-fen-apuesplan-ultimas-noticia/), [Infobae](https://www.infobae.com/peru/2026/11/03/lluvias-en-tumbes-activan-quebradas-elevan-el-caudal-de-los-rios-y-dejan-aislados-a-agricultores-en-zonas-rurales-y-fronterizas/), [El Búho](https://elbuho.pe/2026/11/fenomeno-el-nino-alerta-roja-por-incremento-del-caudal-del-rio-tumbes-tras-intensas-precipitaciones/), [Andina](https://andina.pe/agencia/noticia-fenomeno-nino-piura-lluvia-hora-y-media-inunda-calles-distrito-mancora-1098350.aspx), [RPP](https://rpp.pe/peru/piura/piura-lluvias-torrenciales-inundan-calles-y-obligan-a-cerrar-el-mercado-modelo-en-chulucanas-noticia-1713517).

## Segunda prueba (5/11/2026): inundaciones que duraron varios días

Para descartar que el problema fuera solo el paso del satélite cada ~4 días, se probaron dos desbordes del río Tumbes que dejaron cultivos bajo el agua varios días (`herramientas/pruebas/prueba_eventos_pasados.py`, resultado en `docs/evidencia/prueba_eventos_pasados.json`). Mismas reglas del radar, en un cuadrado de unos 13 km sobre el valle bajo del río Tumbes, desde un día antes hasta 7 días después de la noticia.

| Evento | Noticia | Pasadas de Sentinel-1 | Agua nueva detectada | Caudal GloFAS en el tablero |
|---|---|---|---|---|
| 12/2/2025 | 1 284 ha de cultivo inundadas en San Jacinto, Corrales, Pampas de Hospital y San Juan de la Virgen ([Andina](https://andina.pe/agencia/noticia-tumbes-alerta-desborde-del-rio-tumbes-deja-mas-1200-hectareas-cultivo-inundadas-1018652.aspx)) | 12/2 y 15/2 (el mismo día) | 0,09 km² (9 ha) | 699 m³/s el 12/2, sobre el percentil 90 (581) varios días seguidos |
| 29/4/2023 | Unas 1 600 ha de banano, limón y arroz afectadas o perdidas ([Andina](https://andina.pe/agencia/noticia-desborde-del-rio-tumbes-inunda-mas-500-hectareas-cultivo-y-cientos-viviendas-938318.aspx)) | Solo el 6/5 (7 días después) | 0,02 km² (2 ha) | 1 182 m³/s el 29/4, cerca del percentil 99 (1 326) |

**Conclusión.** Aunque el satélite pasó el mismo día (2025), el radar casi no vio agua. La señal en la zona inundable bajó apenas 0,4 dB (mediana −8,8 dB): el agua estaba bajo banano y arroz, donde la señal rebota entre el agua y los tallos y se vuelve más brillante, no más oscura. El método (agua oscura < −17 dB) sirve para agua abierta en terreno sin vegetación alta, como el Bajo Piura en 2017, no para cultivos inundados. En cambio, el **caudal del río** del tablero sí marcó los dos eventos como anormalmente altos: la anticipación debe venir del río y de la lluvia, y el radar queda como confirmación en terreno abierto. GloFAS subestima el pico (699 frente a 1 100 m³/s medidos en 2025; 1 182 frente a 1 833 en 2023), así que se usa para saber si el río está alto frente a lo normal, no como cifra exacta.
