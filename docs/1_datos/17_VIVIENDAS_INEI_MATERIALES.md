# 17 · Viviendas del Censo 2025: materiales, zona inundable y radar

## Datos

El INEI entregó al equipo, en noviembre de 2026, las **viviendas ocupadas por manzana** de Tumbes y Piura de los Censos Nacionales 2025, con la proporción de cada material de paredes, techos y pisos (preguntas S2_P1 a S2_P3 de la cédula) y el polígono de cada manzana. Son datos confidenciales: **no están en el repositorio** (`datos_inei/` y `docs_recibidos/` están en `.gitignore`). El tablero publica solo totales por distrito, con autorización del profesor, y no detalla los distritos con menos de 10 viviendas en una capa.

| | Tumbes | Piura | Total |
|---|---|---|---|
| Viviendas ocupadas en manzanas | 67 820 | 481 159 | 548 979 |

La vivienda rural dispersa (fuera de manzanas) no está, así que todas las cifras son un mínimo.

## Un solo cálculo (`src/vivienda_inei.py`)

Antes había dos cálculos con los mismos datos: uno de Marcia (zona inundable) y otro de Maykol (materiales y radar). Daban casi lo mismo: 107 166 frente a 107 115 viviendas en la zona de 1 en 100 años. La diferencia (51 viviendas, 0,05 %) venía de que el segundo recortaba el mapa de JRC con los polígonos de distrito, que son simplificados y dejan fuera algunas manzanas de la orilla en La Cruz. Ahora hay **un solo script**, que:

1. ubica cada manzana por un punto interior;
2. toma la profundidad de JRC en ese punto, sin recortar (la manzana ya trae su UBIGEO);
3. mira si el punto cae en el agua nueva del radar **tal como se publica en el mapa**: sin agua permanente, sin la orilla del mar y sin manchas sueltas;
4. calcula las viviendas por material como viviendas de la manzana × proporción con ese material;
5. escribe `dashboard/data/viviendas_censo.json` y `dashboard/data/descargas/viviendas_censo_distritos.csv`.

Se corrió tres veces con el mismo resultado (archivo idéntico byte a byte).

## Resultados

| Crecida | Viviendas | Piura | Tumbes | Paredes de tierra | Paredes precarias | Techo precario | Piso de tierra | Precarias* | Con más de 1,5 m de agua |
|---|---|---|---|---|---|---|---|---|---|
| 1 en 10 años | 75 723 | 71 647 | 4 076 | 11 847 | 15 455 | 795 | 31 058 | 34 747 | 23 536 |
| 1 en 100 años | 107 166 | 101 056 | 6 110 | 16 305 | 19 878 | 1 081 | 40 061 | 45 634 | 47 501 |

\* Precarias = el mayor de (paredes de tierra o precarias) y (piso de tierra) en cada manzana. Es una cota inferior, porque no se sabe cuántas viviendas tienen las dos cosas.

Definiciones: paredes de tierra = adobe, tapia, quincha o piedra con barro; paredes precarias = madera, triplay, calamina o estera; techo precario = caña o estera con barro, triplay, estera, carrizo o paja; piso de tierra = S2_P3 código 6.

### Viviendas dentro del agua que vio el radar

| Capa | Viviendas | De ellas precarias | Manzanas |
|---|---|---|---|
| 2017 (febrero a abril) | 155 | 138 | 51 |
| 2023 (marzo y abril) | 0 | 0 | 0 |
| Últimos 24 días | 0 | 0 | 0 |

Las 155 de 2017 están en San Juan de Bigote (87) y San Miguel de El Faique (55), en el valle del Alto Piura; 13 más están repartidas en Colán y Paita (menos de 10 por distrito, no se detallan). Ese año el SINPAD (INDECI, datos abiertos) registró en Piura **65 467 viviendas afectadas y 13 165 destruidas** por todas las emergencias del año (lluvias, inundaciones y huaicos; `data/modelo/sinpad_tumbes_piura_semanal.csv`).

## Cómo leerlo

- **Exposición no es daño.** Una vivienda en la zona de 1 en 100 años está en un lugar que JRC marca para una crecida extrema, no una vivienda que se inundó.
- **El radar casi no ve viviendas.** Detecta agua abierta en el campo, no entre casas ni en calles. Por eso no sirve, por sí solo, para contar viviendas afectadas, y el tablero cuenta viviendas con la zona inundable de JRC.
- **Punto interior:** una manzana grande puede estar parcialmente en la zona y contarse fuera (o al revés). Con manzanas de decenas de metros y capas de 55-90 m, el error es pequeño frente al total del distrito.

## Pendiente con el INEI

Personas por vivienda (sexo y edad), que permitirían pasar de viviendas a personas con datos del censo y no del modelo de WorldPop (`src/cruce_habitantes.py`, `docs/1_datos/11_CRUCE_HABITANTES.md`).

Uso: `python src/vivienda_inei.py` (los archivos del INEI en `datos_inei/manzana/` o en la carpeta de `IAPN_INEI_MANZANAS`).
