# 17 · Viviendas del INEI: vulnerabilidad física y exposición a inundaciones

## Datos

El INEI entregó al equipo, en noviembre de 2026, las **viviendas ocupadas por manzana** de Tumbes y Piura con la proporción de cada material de paredes, techos y pisos (preguntas S2_P1 a S2_P3 de la cédula), y el polígono de cada manzana.

| | Tumbes | Piura |
|---|---|---|
| Manzanas con viviendas ocupadas | 6 333 | 41 200 |
| Viviendas ocupadas | 67 820 | 481 159 |

**Pendiente de confirmar con el INEI:** año de referencia, método de recolección y si incluye viviendas rurales dispersas (fuera de manzanas). Los archivos por manzana **no se suben** al repositorio (`docs_recibidos/` está en `.gitignore`): el tablero publica solo totales por distrito.

## Método (`src/vivienda_inei.py`)

1. Por manzana: viviendas con paredes precarias (adobe, tapia, quincha, piedra con barro, madera, triplay/calamina/estera), techo precario (caña o estera con barro, triplay/estera/carrizo, paja), piso de tierra. *Viviendas precarias* = el mayor de paredes precarias y piso de tierra (cota inferior, porque no se sabe cuántas viviendas tienen las dos cosas).
2. Exposición: se toma el punto interior de cada manzana y se mira si cae en la zona inundable de JRC (1 en 10 y 1 en 100 años) o en el agua nueva del radar (2017, 2023, últimos 24 días), con las mismas capas y máscaras de `src/impacto.py`.
3. Se suma por distrito (UBIGEO). Salidas: `dashboard/data/vivienda_inei_distritos.json` y `dashboard/data/descargas/vivienda_inei_distritos.csv`.

## Resultados (4 de noviembre de 2026)

| | Tumbes | Piura |
|---|---|---|
| Viviendas precarias (paredes o piso) | 29 968 (44 %) | 202 807 (42 %) |
| Paredes precarias | 28 965 (43 %) | 173 104 (36 %) |
| Piso de tierra | 17 108 (25 %) | 161 373 (34 %) |
| Viviendas en zona inundable 1/10 años | 4 026 | 71 646 |
| Viviendas en zona inundable 1/100 años | 6 060 | 101 055 |
| … de ellas precarias (1/100) | 2 580 | 43 023 |
| Viviendas dentro del agua del radar, 2017 | 0 | 155 |
| Viviendas dentro del agua del radar, últimos 24 días | 0 | 0 |

## Cómo leerlo

- **Exposición no es daño.** Una vivienda en la zona de 1 en 100 años no se inundó ni se va a inundar este año: está en un lugar que el modelo de JRC marca para una crecida extrema.
- **El radar casi no ve viviendas.** En 2017 INDECI registró unas 74 000 viviendas afectadas en Piura (lluvias, inundaciones y huaicos), pero solo 155 viviendas del INEI caen dentro del agua del radar. El radar detecta agua abierta en el campo y no entre casas; por eso no sirve, por sí solo, como etiqueta de viviendas afectadas.
- **Punto interior:** una manzana grande puede estar parcialmente en la zona inundable y contarse fuera (o al revés). Con manzanas de decenas de metros y capas de 55–90 m, el error es pequeño frente al total del distrito.
- Los criterios de "precario" son de trabajo y se pueden ajustar en `src/vivienda_inei.py`.
