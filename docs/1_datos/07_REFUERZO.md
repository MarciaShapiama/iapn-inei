# Refuerzo — Tareas 1 y 2



## Tarea 1 · Alumnos expuestos (padrón ESCALE)

**Lo que se intentó primero:** el formulario de búsqueda en escale.minedu.gob.pe/web/inicio/padron-de-iiee no da descarga masiva; por eso el script del equipo (`src/exposicion_extra.py`, función `padron_minedu`) solo deja un diagnóstico, sin descargar.

**Lo que sí funcionó:** en escale.minedu.gob.pe/bases-de-datos → UE → *B. Padrón de Servicios Educativos* hay un ZIP nacional publicado cada semana (`Padron_web_20261030.zip`, 15,4 MB, corte 30-10-2026) con descarga directa, sin bloqueo. Se descargó y se procesó completo.

**Resultado:** `padron_escale.csv`, 8 141 servicios educativos activos en Tumbes y Piura con coordenadas válidas (de 11 971 registrados en total; 180 943 a nivel nacional). Columnas: `CODLOCAL, CEN_EDU, NLAT_IE, NLONG_IE, D_NIV_MOD, TALUMNO, D_DPTO` (más `D_PROV, D_DIST, COD_MOD` de apoyo).

**Lo que no se pudo hacer — TALUMNO queda vacío.** El Padrón de Servicios Educativos no trae número de alumnos; lo confirmé contra el diccionario oficial de 45 campos del archivo y contra las columnas reales del `.dbf` — ninguna de las dos lista un campo de matrícula. El padrón solo registra qué servicio existe y dónde, no cuántos alumnos tiene. Los datos de matrícula vienen de una operación estadística distinta (Censo Educativo / SIAGIE), que no revisé todavía — lo dejo para que me digas si quieres que lo persiga como tarea aparte, porque implica otro archivo y otro cruce por `COD_MOD`.

**Comparación con los colegios de OpenStreetMap que usa hoy el tablero:** de los 7 111 puntos de `colegios.csv` (todos con el campo "alumnos" vacío, igual que ESCALE no lo tiene), el 68,9 % tiene un local de ESCALE a 100 m o menos, y el 73,5 % a 250 m o menos. El resto no coincide — puede ser un local que cerró, uno que abrió después del corte de OSM, o una coordenada distinta en OSM.

## Tarea 2 · Pobreza e IDH por distrito

Revisado tres veces, cada vez contra una fuente distinta, hasta llegar al documento oficial original (no a una compilación):

**Primera pasada:** el propio código ya declara su fuente (`src/ubigeo.py`, línea 5) y se autoexige verificarla ("verificar contra la publicación original antes de citarlas como cifra oficial"). La tabla que usa el proyecto es `jmcastagnetto/ubigeo-peru-aumentado` (GitHub, MIT) — una compilación de terceros.

**Segunda pasada:** comparé esa tabla contra dos republicaciones independientes — el paquete R `perupobreza2018` (pobreza) y el Excel del Instituto Peruano de Economía (IDH) — ambas coincidieron.

**Tercera pasada, contra el documento oficial original (no una republicación):**

- **IDH:** descargué el archivo que el propio PNUD Perú enlaza como descarga oficial en undp.org/es/peru/publicaciones/el-reto-de-la-igualdad → "Descarga los anexos estadísticos" → hoja "Distrital": `https://www.undp.org/sites/g/files/zskgke326/files/migration/pe/IDH-2019.xlsx`.
- **Pobreza:** descargué el libro completo del INEI (303 páginas, con los anexos estadísticos, no el PDF de mapas que es solo cartografía) y leí directamente la tabla: `https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1718/Libro.pdf`, página 193, **Anexo N° 03.21 — PIURA: Población, pobreza monetaria total, grupos robustos y ubicación del distrito por nivel de pobreza total, según distrito, 2018**.

**Resultado, 5 distritos al azar, contra el documento oficial original:**

| Distrito | UBIGEO | Pobreza del proyecto | Intervalo oficial INEI (Anexo 03.21, pág. 193) | IDH del proyecto | IDH oficial PNUD (hoja Distrital) |
|---|---|---|---|---|---|
| Sapillica | 200208 | 61,99 % (punto medio) | 50,7 % – 73,3 % | 0,170731 | 0,170731230381… |
| Santo Domingo | 200409 | 40,74 % | 28,4 % – 53,1 % | 0,349786 | 0,349785883948… |
| Bernal | 200803 | 33,41 % | 23,0 % – 43,8 % | 0,441738 | 0,441738057538… |
| Colán | 200504 | 29,24 % | 20,8 % – 37,6 % | 0,466561 | 0,466561076241… |
| Sechura | 200801 | 25,80 % | 15,3 % – 36,3 % | 0,486072 | 0,486072469370… |

El IDH coincide **exacto hasta la sexta cifra decimal** en los cinco distritos, directo contra el archivo del propio PNUD. La pobreza del proyecto cae exactamente en el punto medio del intervalo de confianza al 95 % que publica el INEI — así reporta el INEI su cifra puntual, no es un error ni una invención: el propio anexo da el intervalo, no un solo número, y la tabla que usa el proyecto ya hizo ese punto medio correctamente.

**Conclusión:** la pobreza y el IDH del proyecto están bien citados y verificados contra el documento oficial original, no solo contra una compilación. No hay nada que corregir en las cifras.

**Corrección que sí propongo (de redacción, no de datos):** en `src/metadatos.py` y `src/panel.py`, cambiar "fuente declarada INEI, compilación de terceros" por: *"Pobreza: INEI, Mapa de Pobreza Monetaria Provincial y Distrital 2018, Anexo N° 03.21 (punto medio del intervalo de confianza al 95 %). IDH: PNUD, Índice de Desarrollo Humano Perú 2019, hoja Distrital. Verificado el 2026-11-05 contra ambos documentos oficiales originales — ver docs/1_datos/07_REFUERZO.md."* Ya no hace falta decir "sin verificar": ya se verificó, tres veces, contra la fuente primaria.

## Fuentes usadas en esta sesión (todas oficiales, descarga directa del organismo que las produce)

- Padrón de Servicios Educativos, corte 30-10-2026 — MINEDU/ESCALE: https://escale.minedu.gob.pe/documents/10156/958881/Padron_web_20261030.zip (descargado 2026-11-04)
- Mapa de Pobreza Monetaria Provincial y Distrital 2018, libro completo con anexos — INEI: https://www.inei.gob.pe/media/MenuRecursivo/publicaciones_digitales/Est/Lib1718/Libro.pdf, Anexo N° 03.21, página 193 (descargado 2026-11-05)
- Índice de Desarrollo Humano Perú 2019, anexo estadístico distrital — PNUD: https://www.undp.org/sites/g/files/zskgke326/files/migration/pe/IDH-2019.xlsx, hoja "Distrital" (descargado 2026-11-05)

Fuentes de apoyo usadas solo para la primera verificación cruzada (ya no hacen falta, el dato quedó confirmado contra el original):
- `jmcastagnetto/ubigeo-peru-aumentado` (GitHub) — tabla que usa el proyecto.
- `CalderonSamuel/perupobreza2018` (GitHub) y el Excel del Instituto Peruano de Economía — republicaciones usadas para la segunda pasada.

## Pendiente

- TALUMNO (alumnos por institución): necesita el Censo Educativo o SIAGIE, no revisado.
- Tareas 3, 4 y 5 (lluvia PISCO, validación del radar 2017, emergencias 2016-2025): no empezadas, estaban marcadas opcionales.

## Incorporación al repositorio (4/11/2026)

- `padron_escale.csv` se guardó en `data/exposicion/`. Los colegios del tablero ahora salen del padrón ESCALE y no de OpenStreetMap.
- Se cuenta **un local escolar por CODLOCAL** (5 761 locales con 8 141 servicios), para no contar el mismo edificio varias veces cuando tiene inicial, primaria y secundaria.
- Con ESCALE, los locales dentro de la zona inundable de 1 en 100 años eran 686; con OpenStreetMap eran 684. Las dos fuentes, independientes, casi coinciden. (Desde el 4/11/2026 son 682: la zona inundable se recorta a los distritos de Tumbes y Piura.)
- Se repitió la comprobación de los 5 distritos contra `docs/evidencia/IDH-2019-PNUD-oficial.xlsx` y el extracto del INEI: coincide.
- Se actualizó la descripción de la fuente de pobreza e IDH en `src/metadatos.py` y `src/panel.py`.
