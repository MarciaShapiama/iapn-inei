# 16 · Inundaciones reportadas: que ningún evento quede fuera del tablero

## El problema

En la reunión del 4 de noviembre el profesor buscó en las noticias inundaciones recientes (Huancabamba, Máncora, Chulucanas) y el tablero no mostraba nada. El equipo supuso que era por un filtro de cercanía a postas, hospitales y colegios. **No era eso:** la capa azul del radar no se filtra por cercanía a ningún local. Lo que pasa es que el radar solo ve agua abierta en el llano, y la mayoría de los reportes son de otro tipo.

Para comprobarlo se probó el detector con 13 eventos de noticias (2017, 2023 y 2026) y se agregó al tablero una capa que muestra **toda** inundación reportada en Tumbes y Piura, la vea o no el radar.

## Qué cambió en el tablero

- **Puntos ◆ en el mapa 3D y en el 2D** («Inundaciones reportadas»): cada evento con su lugar, fecha, tipo, enlaces a las notas y la respuesta a «¿lo vio el radar?»: verde = sí, rojo = no, naranja = fuera de su alcance (sierra o calles inundadas por lluvia).
- **Lista en el panel del mapa 3D** («Inundaciones reportadas: ¿las ve el radar?»), con el resumen del periodo. Al hacer clic, el mapa vuela al lugar y muestra las fuentes.
- Con una capa de radar elegida (2017, 2023, últimos 24 días) se ven los reportes de ese periodo; con un escenario de JRC, todos.

## De dónde salen los eventos (`src/noticias.py`, corre cada día en el perfil `diario`)

1. **Noticias del día:** Google Noticias (RSS, sin clave), titulares en español de los últimos 14 días con palabras de inundación y «Piura» o «Tumbes». Cada titular se guarda en `data/eventos/noticias_registro.csv`, que nunca se borra: un evento sigue en el tablero aunque la noticia ya no salga en el RSS.
2. **Filtro de hechos:** cuenta solo si dice que algo pasó («inundan», «se desborda», «damnificados», «activan quebradas»). Los avisos («riesgo de inundación», «alerta», «podría»), las verificaciones de noticias falsas, las redes sociales y los titulares sobre otros años («las inundaciones de 2017») se descartan.
3. **Ubicación:** el titular se busca en `data/eventos/lugares.csv`, 392 centros poblados y lugares de Tumbes y Piura con su distrito, coordenadas y altura (`herramientas/datos/crear_lugares.py`, a partir de los centros poblados urbanos del INEI). Si el titular dice «… en Tumbes», no se ubica en un homónimo de Piura. Si solo dice «Piura» o «Tumbes», se pone en la ciudad y se marca como ubicación aproximada. Un titular sin un lugar de la zona no entra.
4. **Catálogo verificado:** `data/eventos/catalogo_verificado.csv`, 13 eventos revisados por el equipo con su fuente. Las noticias del mismo distrito y con menos de 3 días de diferencia se suman al evento verificado como fuentes adicionales.
5. **¿Lo vio el radar?** Se mide el agua de la capa publicada (la misma que se ve en el mapa) a menos de 3 km. Para los eventos del catálogo se usa la prueba dedicada (abajo).

**Límite:** los eventos de noticias son reportes de prensa ubicados por el nombre del lugar. No están verificados ni son cifras oficiales (INDECI/COEN). Un titular puede nombrar un lugar que no es el exacto de la inundación.

## Prueba del detector con 13 noticias (`herramientas/pruebas/prueba_noticias_verificadas.py`)

Para cada evento se repitió el cálculo de `src/huellas.py` en un cuadrado de ~6 km, con una ventana propia (2 días antes a 12 días después) frente a la temporada seca anterior, con tres variantes de reglas:

- **V0:** reglas actuales del tablero.
- **V1:** sin el límite de 250 m de altura.
- **V2:** sin altura ni pendiente.

Se cuenta como detectado a partir de 0,05 km². Resultados en `docs/evidencia/prueba_noticias_verificadas.json`:

| Evento | Tipo | Altura | 1.ª pasada después | Agua V0 (km²) | V1 | V2 | Resultado |
|---|---|---|---|---|---|---|---|
| 2017 · Piura ciudad | desborde | 35 m | 1/4 (5 días después) | 0,03 | 0,03 | 0,03 | no |
| 2017 · Catacaos | desborde | 26 m | 1/4 | 0,09 | 0,09 | 0,09 | **sí** |
| 2017 · Cura Mori | desborde | 25 m | 1/4 | 1,45 | 1,45 | 1,45 | **sí** |
| 2017 · Chulucanas | desborde | 92 m | 26/3 | 0,18 | 0,18 | 0,18 | **sí** |
| 2017 · Tambogrande | desborde | 73 m | 26/3 | 0,19 | 0,19 | 0,19 | **sí** |
| 2023 · Tambogrande | desborde | 73 m | 10/3 | 0 | 0 | 0 | no |
| 2026 · Piura, calles | lluvia urbana | 35 m | 21/10 | 0,05 | 0,05 | 0,05 | no (en el umbral) |
| 2026 · Chulucanas | lluvia urbana | 92 m | 21/10 | 0 | 0 | 0 | no |
| 2026 · río Serrán (Canchaque) | desborde en la sierra | 1 188 m | 30/10 | 0 | 0 | **0** | no |
| 2026 · Puerto Perú | desborde | 4 m | 2/11 | 0 | 0 | 0 | no |
| 2026 · Vaquería (San Jacinto) | desborde | 33 m | 2/11 | 0 | 0 | 0 | no |
| 2026 · Tumbes, calles | lluvia urbana | 37 m | 2/11 | 0 | 0 | 0 | no |
| 2026 · Máncora | lluvia urbana | 2 m | 2/11 | 0 | 0 | 0 | no |

## Conclusiones

1. **El filtro de altura y pendiente no escondió ningún evento.** Las tres variantes dan lo mismo en los 13 casos. En el río Serrán el radar no marca agua ni sin filtros: el río es más angosto que un píxel (~55 m) y corre en un valle encajonado.
2. **El radar ve desbordes grandes en el llano:** 4 de 5 en 2017 (Catacaos, Cura Mori, Chulucanas, Tambogrande). En la ciudad de Piura no, porque el agua ya había bajado cuando pasó el satélite, 5 días después.
3. **No ve inundaciones de calles por lluvia** (Piura, Chulucanas, Tumbes, Máncora) **ni desbordes dentro de poblados** (Puerto Perú, Vaquería). En esos casos la señal casi no cambió.
4. **Bajar umbrales no es la solución:** marcaría más arena, salinas y sombras sin ganar las calles. La solución es mostrar el evento reportado aunque el radar no lo vea, con la explicación de por qué. Eso es lo que hace la nueva capa.

## Cómo agregar un evento verificado

Agregar una fila a `data/eventos/catalogo_verificado.csv`. El `lugar` debe existir en `data/eventos/lugares.csv`; si no existe, se agrega en `EXTRA` de `herramientas/datos/crear_lugares.py`. Luego correr `python herramientas/pruebas/prueba_noticias_verificadas.py` y `python src/noticias.py`. La prueba `tests/test_eventos.py` falla si un evento verificado no aparece en el tablero.
