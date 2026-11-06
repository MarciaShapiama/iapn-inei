# 17 · Viviendas y personas del Censo 2025: zona inundable, materiales y radar

## Datos

El INEI entregó al equipo los datos de los Censos Nacionales 2025 para Tumbes y Piura en dos partes:

- **4/11/2026:** viviendas ocupadas por manzana, con la proporción de cada material de paredes, techos y pisos (preguntas S2_P1 a S2_P3 de la cédula), y el polígono de cada manzana.
- **6/11/2026:**
  - las viviendas que no están en manzanas, agrupadas por centro poblado (código de 10 caracteres: ubigeo + código del centro poblado);
  - las personas de cada manzana y centro poblado por sexo y grupo de edad (0-4, 5-14, 15-64 y 65 o más);
  - el punto de cada centro poblado. Los centros poblados no tienen límites, solo coordenadas.

El INEI no entrega datos con un nivel de detalle menor a la manzana.

Son datos confidenciales: **no están en el repositorio** (`datos_inei/` y `docs_recibidos/` están en `.gitignore`). El tablero publica solo totales por distrito, con autorización del profesor. No se detallan los distritos con menos de 10 viviendas en una capa, y no se publica ninguna cifra de personas menor a 10.

| | Tumbes | Piura | Total |
|---|---|---|---|
| Viviendas ocupadas | 72 709 | 591 942 | 664 651 |
| — en manzanas | | | 548 979 |
| — en centros poblados (fuera de manzanas) | | | 115 672 |
| Personas | 250 997 | 2 089 044 | 2 340 041 |
| — en centros poblados | | | 372 884 |

Controles hechos al recibir los datos:

- Las 47 533 manzanas de la segunda entrega son las mismas de la primera, con las mismas viviendas.
- En todas las filas, la suma de los grupos de sexo y edad es igual al total de personas.
- Los 2 627 centros poblados con viviendas tienen su punto en el shapefile.
- Hay 35 unidades con personas pero sin viviendas ocupadas (6 709 personas, probablemente viviendas colectivas). Se cuentan en las personas.

## Un solo cálculo (`src/vivienda_inei.py`)

1. Cada manzana se ubica por un punto interior y cada centro poblado por su punto.
2. Se toma la profundidad de JRC en ese punto, sin recortar: la unidad ya trae su UBIGEO.
3. Se mira si el punto cae en el agua nueva del radar tal como se publica en el mapa: sin agua permanente, sin la orilla del mar y sin manchas sueltas.
4. Viviendas por material = viviendas de la unidad × proporción con ese material.
5. Se escriben `dashboard/data/viviendas_censo.json` y `dashboard/data/descargas/viviendas_censo_distritos.csv`.

Se corrió dos veces con el mismo resultado (archivo idéntico byte a byte).

## Resultados

| Crecida | Viviendas | Personas | Mujeres | 0-4 años | 65 o más | En centros poblados (viviendas / personas) |
|---|---|---|---|---|---|---|
| 1 en 10 años | 77 718 | 290 735 | 147 630 | 22 541 | 22 215 | 1 995 / 6 750 |
| 1 en 100 años | 109 602 | 407 877 | 207 303 | 30 338 | 35 057 | 2 436 / 8 129 |

| Crecida | Paredes de tierra | Paredes precarias | Techo precario | Piso de tierra | Precarias* | Con más de 1,5 m de agua |
|---|---|---|---|---|---|---|
| 1 en 10 años | 12 817 | 15 877 | 829 | 32 421 | 36 299 | 24 359 |
| 1 en 100 años | 17 457 | 20 392 | 1 116 | 41 707 | 47 493 | 48 703 |

\* Precarias = el mayor de (paredes de tierra o precarias) y (piso de tierra) en cada unidad. Es una cota inferior, porque no se sabe cuántas viviendas tienen las dos cosas.

Definiciones: paredes de tierra = adobe, tapia, quincha o piedra con barro; paredes precarias = madera, triplay, calamina o estera; techo precario = caña o estera con barro, triplay, estera, carrizo o paja; piso de tierra = S2_P3 código 6.

Solo en manzanas, las cifras de la zona de 1 en 100 años no cambian respecto de la primera entrega: 107 166 viviendas. Las 2 436 de los centros poblados se suman a esas.

### El censo confirma el modelo de población del tablero

El resto del tablero usa WorldPop 2026 (un modelo) para contar personas. Con el censo:

| Crecida | Personas, censo | Personas, WorldPop | Diferencia |
|---|---|---|---|
| 1 en 10 años | 290 735 | 277 634 | WorldPop 4,5 % menos |
| 1 en 100 años | 407 877 | 399 506 | WorldPop 2,1 % menos |

Por distrito, la correlación entre los dos es 0,98 (50 distritos). La diferencia grande de Piura distrito (35 430 en el censo frente a 55 762 en WorldPop) se debe a que el mapa de distritos del tablero junta Piura y Veintiséis de Octubre. El censo los separa: Veintiséis de Octubre tiene 27 271 personas en la zona.

### Viviendas dentro del agua que vio el radar

| Capa | Viviendas | De ellas precarias | Personas | Manzanas / centros poblados |
|---|---|---|---|---|
| 2017 (febrero a abril) | 172 | 155 | 464 | 51 / 1 |
| 2023 (marzo y abril) | 0 | 0 | 0 | 0 |
| Últimos 24 días | 0 | 0 | 0 | 0 |

Las viviendas de 2017 están casi todas en dos distritos del valle del Alto Piura:
- **San Juan de Bigote:** 104 viviendas y 276 personas;
- **San Miguel de El Faique:** 55 viviendas y 134 personas.

Las demás están en Colán y Paita, con menos de 10 por distrito, así que no se detallan. Ese año el SINPAD (INDECI, datos abiertos) registró en Piura **65 467 viviendas afectadas y 13 165 destruidas** por lluvias intensas e inundaciones (`data/modelo/sinpad_tumbes_piura_semanal.csv`).

## Cómo leerlo

- **Exposición no es daño.** Una vivienda en la zona de 1 en 100 años está en un lugar que JRC marca para una crecida extrema, no es una vivienda que se inundó.
- **El radar casi no ve viviendas.** Detecta agua abierta en el campo, no entre casas ni en calles. Por eso el tablero cuenta viviendas y personas con la zona inundable de JRC.
- **Ubicación por punto.** Una manzana grande puede quedar parcialmente en la zona y contarse fuera, o al revés. Con los centros poblados el efecto es mayor: todas sus viviendas dispersas cuentan según caiga su punto. Por eso la población rural en la zona (8 129 personas) es solo una aproximación.

Uso: `python src/vivienda_inei.py` (los archivos del INEI en `datos_inei/manzana/` o en la carpeta de `IAPN_INEI_MANZANAS`).
