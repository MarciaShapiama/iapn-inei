# 06 · ¿Funcionó en Tumbes y Piura? Validación del piloto y viabilidad de expansión

*Corte: 4/11/2026. Scripts: `herramientas/pruebas/validacion_indeci.py` y `herramientas/pruebas/viabilidad_expansion.py`. Evidencia: `docs/evidencia/validacion_indeci*.{json,csv}` y `docs/evidencia/viabilidad_expansion.json`.*

## 1. Validación del piloto

### 1.1 Validación interna (consistencia): aprobada

| Prueba | Resultado |
|---|---|
| Las sumas por distrito coinciden con el total; dentro ≤ 500 m ≤ 1 km | Se cumple (38 pruebas automáticas, también en GitHub Actions) |
| La población está en su lugar (correlación con edificaciones, fuente independiente) | r = 0,80; antes de la corrección era 0,00 |
| Población WorldPop por distrito frente a la estimación 2020 | Razón entre 0,85 y 1,10 en los distritos de más de 40 mil habitantes (Piura 1,75 porque absorbe a Veintiséis de Octubre) |
| Tablero publicado, mapa 2D y descargas | 11/11 pruebas contra `marciashapiama.github.io/iapn-inei` |

### 1.2 Validación externa contra los registros de INDECI (2003–2024)

Comparamos el **orden de los 76 distritos** con los afectados que registró INDECI (SINPAD-COEN), una fuente que no usamos para calcular nada. Usamos la correlación de rangos de Spearman (ρ).

| Comparación (ρ de Spearman, n = 76) | Afectados por **inundación** | Afectados por **lluvia intensa** |
|---|---|---|
| Edificaciones en la zona 1/100 | **0,38** (p = 0,0007) | 0,14 (p = 0,22) |
| Población en la zona 1/100 | **0,35** (p = 0,002) | 0,16 (p = 0,17) |
| Agua detectada por radar en 2017 | **0,30** (p = 0,008) | 0,11 (p = 0,34) |
| % del área del distrito en la zona 1/100 | 0,23 (p = 0,04) | −0,13 (p = 0,26) |
| *Referencia:* población total del distrito | 0,21 (p = 0,07) | **0,52** (p < 0,001) |

**Lectura:**

- **Inundación por desborde: el modelo funciona.** Los distritos con más exposición calculada son, en orden, los que más afectados por inundación registró INDECI. Además, la exposición explica ese orden **mejor que el simple tamaño de la población** (0,38 frente a 0,21). Coincidencias en el top 15: **9 de 15** (Castilla, Catacaos, Chulucanas, Colán, La Arena, La Unión, Piura, Tambo Grande y Tumbes).
- **Lluvia intensa: el modelo no la representa.** Los daños por lluvia intensa (techos, huaicos, zonas altas como Pacaipampa, Yamango o Montero) se explican sobre todo por la población, no por la zona inundable fluvial. Tiene sentido: el JRC no modela lluvia local ni quebradas. **Es la principal carencia del modelo.**
- La correlación es **moderada**, no alta. Los registros acumulan 22 años, dependen de lo que reporta cada municipalidad e incluyen eventos de distinta magnitud. La validación es de **orden**, no de cantidades.

### 1.3 Lo que no funcionó o es débil

| Componente | Evidencia | Consecuencia |
|---|---|---|
| Radar en ciudades | Catacaos 2017: 1,1 km² detectados, aunque fue de los distritos más inundados | La capa de radar es un mínimo y no puede usarse sola como «lo que pasó» |
| Modelo de alerta semanal (ML) | No supera con certeza a la climatología; captura el 5 % de las emergencias de Piura | No usarlo como alerta; sirve para ordenar años |
| Índice de riesgo relativo | ρ = 0,34 (p = 0,003) con los afectados por inundación, parecido a la exposición sola; con el total de afectados, solo 0,11 | Revisar sus pesos: el % de área favorece distritos pequeños casi cubiertos por la mancha que no registran afectados por inundación en 2003–2024 (Rinconada Llicuar y Bellavista de la Unión: 0) |

**Conclusión del piloto:** la **exposición a inundación fluvial por distrito** está validada en orden con una fuente oficial independiente y es el resultado más sólido. El radar y el índice compuesto necesitan mejoras antes de usarse para decidir.

## 2. ¿Es adecuada la base de datos?

| Para qué | ¿Adecuada? | Qué falta |
|---|---|---|
| Peligro fluvial (JRC 1/10 y 1/100) | **Sí, como punto de partida** (global, abierta, validada en la literatura) | Estudios oficiales CENEPRED/SIGRID, inundación pluvial y quebradas (la carencia de §1.2), defensas ribereñas |
| Población (WorldPop 2026) | **Sí, ya corregida** | Censo 2017 y proyecciones oficiales del INEI por distrito o manzana |
| Edificaciones (Open Buildings) | Sí para contar estructuras | Uso residencial y material de la vivienda (censo) |
| Colegios (OpenStreetMap) | **No es la ideal** | Padrón ESCALE (MINEDU) con código modular y matrícula |
| Salud (RENIPRESS) | Sí | Verificar coordenadas en campo |
| Límites distritales (GADM) | **No es la ideal**: faltan 2 distritos y la licencia impide redistribuirlos | Límites oficiales INEI/IGN |
| Vulnerabilidad (pobreza 2018, IDH 2019) | Parcial | Edad, discapacidad, vivienda y saneamiento (Censo 2017) |
| Daños para validar y entrenar | Parcial: DesInventar llega hasta 2015 y las tablas INDECI no tienen fecha | Serie fechada SINPAD 2016–2026 |
| Lluvia y caudal | Modelados (Open-Meteo, GloFAS, NASA POWER) | Estaciones SENAMHI/ANA y avisos oficiales |

## 3. Viabilidad de expandir

### 3.1 Escala (calculada con los costos medidos en el piloto)

| Escenario | Departamentos | Distritos | Población 2020 (est.) | Área de la caja vs piloto | Radar por evento (una caja, secuencial) | Edificaciones (MB) |
|---|---|---|---|---|---|---|
| **Piloto** Tumbes y Piura | 2 | 78 | 2,3 M | 1× | ~40 min | 12 |
| **Norte costero** (+ Lambayeque, La Libertad) | 4 | 199 | 5,8 M | 3,6× | ~2,4 h | 31 |
| **Norte ampliado** (+ Cajamarca, Áncash) | 6 | 492 | 8,6 M | 4,9× | ~3,3 h | 46 |
| **Perú** | 25 | 1.893 | 34,4 M | 33,5× | ~22 h | 182 |

Límites del plan gratuito de GitHub: 6 h por job, unos 16 GB de RAM por runner, sitio de Pages de 1 GB y archivos de hasta 100 MB.

### 3.2 Veredicto

| Escenario | Viable | Condiciones |
|---|---|---|
| **Norte costero** | **Sí, a corto plazo (recomendado como siguiente paso)** | Procesar **por departamento** (una caja por departamento en trabajos paralelos de Actions); el radar solo en costa baja; usar el mismo código con la caja y los departamentos como parámetros |
| **Norte ampliado** | Sí, con ajustes | Cajamarca y Áncash son sobre todo sierra: allí manda la lluvia intensa y los huaicos (§1.2), que el JRC no cubre. Hace falta otra capa de peligro (CENEPRED/SIGRID o susceptibilidad a movimientos en masa del INGEMMET) |
| **Perú** | **Técnicamente posible, pero no con la arquitectura actual sin cambios** | (i) dividir por departamento los datos y las descargas del tablero (Open Buildings nacional supera los 100 MB por archivo); (ii) pasar las capas pesadas a teselas en lugar de GeoJSON (las llanuras amazónicas generan polígonos enormes); (iii) correr el radar solo por evento y por cuenca, no nacional cada semana; (iv) en la Amazonía la inundación es estacional y prolongada: hay otra lógica de «agua normal» |

### 3.3 Cambios de código necesarios (estimación)

| Cambio | Esfuerzo |
|---|---|
| Pasar `CAJA` y `DEPARTAMENTOS` de constantes a configuración por departamento (`config/departamentos.yml`) | 1–2 días |
| Salidas por departamento (`dashboard/data/<UBIGEO_dpto>/…`) y selector en el mapa | 2–3 días |
| Workflow con *matrix* por departamento y consolidación | 1 día |
| Límites oficiales INEI para los 1.874 distritos | Depende del acceso a los datos |
| Pruebas parametrizadas por departamento (las actuales ya sirven de plantilla) | 1 día |

**Recomendación para consultar con el docente:**

1. Consolidar el piloto con límites del INEI y padrón ESCALE.
2. Ampliar a la **costa norte** (4 departamentos, ~1–2 semanas) para mostrar que el método se transfiere.
3. Dejar la cobertura nacional como fase posterior, con las adaptaciones de §3.2. La prioridad del norte se justifica porque concentra el impacto de El Niño costero (1983, 1998, 2017, 2023).
