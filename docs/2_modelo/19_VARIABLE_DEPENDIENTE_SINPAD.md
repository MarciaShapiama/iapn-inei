# 10 · La variable dependiente ahora sale del SINPAD (fuente oficial)

*5 de noviembre de 2026. Scripts: `src/etiqueta_sinpad.py`, `src/modelo_inundacion.py`, `herramientas/pruebas/auditoria_sinpad.py`. Evidencia: `data/modelo/sinpad/procedencia.json`, `docs/evidencia/auditoria_sinpad.json`, `docs/evidencia/ml_evaluacion.json`.*

## Por qué se cambió

La Y del modelo de alerta salía de DesInventar, que (1) termina en noviembre de 2015, (2) mezcla marejadas, que no dependen de la lluvia, y (3) en años antiguos recoge prensa. Además, comparada con el SINPAD en 2003-2015, solo **37 de 118** semanas-distrito con registro en DesInventar aparecen en el SINPAD la misma semana (51 con ±2 semanas): son fuentes distintas y **no se pueden unir** en una sola serie. Por eso se usa **solo el SINPAD** para todo el periodo.

## La fuente

| | |
|---|---|
| Dataset | INDECI, «Emergencias y daños a nivel nacional por departamento» |
| Dónde | https://www.datosabiertos.gob.pe/dataset/emergencias-y-da%C3%B1os-nivel-nacional-por-departamento |
| Qué dice la fuente | Consolida los registros de emergencias procesados en el SINPAD |
| Licencia | ODC-By |
| Archivos | `BD_2003-2025_EMERGENCIAS.csv` (27 MB) y `BD_2026_Semestre_I.csv` (1,7 MB) + diccionario de datos |
| Huella | SHA-256 de cada archivo en `data/modelo/sinpad/procedencia.json` |

Los crudos no se suben a GitHub (`data/modelo/sinpad/crudo/` está en `.gitignore`); se vuelven a bajar con `python src/etiqueta_sinpad.py --descargar` y la huella permite comprobar que son los mismos.

## Cómo se construye (con el conteo de cada paso)

| Paso | Registros |
|---|---|
| 1. Registros en los archivos oficiales (todo el Perú, 2003-2026) | 151 491 |
| 2. Tumbes y Piura (UBIGEO 20xxxx y 24xxxx) | 8 556 |
| 3. Peligros de agua: contienen «INUND» o «LLUVI» (INUNDACION, LLUVIA INTENSA; en 2026 LLUVIAS INTENSAS e INUNDACIÓN POR DESBORDE DE RIO/CANALES) | 3 363 |
| 4. Fecha válida y coherente con las columnas AÑO y MES (el diccionario dice «DD/MM/AAAA o MM/DD/AA») | 3 363 (0 descartados) |
| 5. Distrito identificado (Veintiséis de Octubre → Piura; Canoas de Punta Sal → Zorritos) | 3 363 |
| 6. Distrito-semanas con al menos una emergencia de agua | 2 678 |
| Registros dentro del periodo de la etiqueta (enero 2003 a diciembre 2025), unidos a la base | 3 062 de 3 062 |

Quedan fuera, entre otros: incendios (2 564 registros en Tumbes y Piura), vientos fuertes (1 601), sismos (107) y **marejadas (39)**. Huaycos (14) también quedan fuera para mantener la definición «inundación o lluvia intensa».

**Definición:** Y(d, t) = 1 si el SINPAD registra al menos una emergencia por inundación o lluvia intensa en el distrito d en alguna de las semanas t+1 a t+4; 0 si no. Se usa de enero de 2003 al 29 de diciembre de 2025. El semestre 2026 se excluye de la etiqueta: el archivo solo cubre enero a junio y trae errores (la columna de viviendas destruidas repite el número de personas afectadas en muchos registros).

Se corrigió además un error de la base: los dos distritos llamados **Salitral** (Morropón y Sullana) compartían la misma clave; ahora se separan con la provincia.

## Auditoría (¿concuerda con la realidad?)

- **Eventos verificados con noticias:** los 6 eventos de 2017 y 2023 del catálogo tienen registro SINPAD de agua en el mismo distrito a menos de 14 días (5 de 6 a menos de 7 días). Ejemplos: Cura Mori, código 86087, 27/03/2017, INUNDACION; Catacaos, código 84821, 27/03/2017, INUNDACION. Los 7 eventos de octubre y noviembre de 2026 no se pueden comprobar: el archivo 2026 solo llega a junio.
- **Muestra para revisión manual:** 20 registros al azar con su código SINPAD en `docs/evidencia/auditoria_sinpad.json`.
- **Distribución:** 90 896 distrito-semanas con Y; **7 173 con Y = 1 (7,9 %)**; 2 431 distrito-semanas con registro (de 3 062 registros). Años más altos: 2023 (398 semanas con registro), 2017 (322), 2025 (266). El 89 % de las semanas con registro cae entre enero y abril. Los 76 distritos tienen al menos un registro; los que más: Tumbes (109), Huancabamba (87), Pacaipampa (71), Zarumilla (69) y Ayabaca (65).
- **Actualización 6/11/2026, mapa de 78 distritos del INEI** (`docs/1_datos/20_MAPA_78_DISTRITOS_INEI.md`): sin unir distritos, la base tiene 93 288 distrito-semanas con Y y **7 243 con Y = 1 (7,8 %)**. Los 78 distritos tienen al menos un registro.

**Límites que siguen:** el SINPAD depende de lo que reporta cada municipalidad (puede haber subregistro o registros de daños menores); la fecha es la de la emergencia según el registro; «lluvia intensa» incluye daños por lluvia que no son inundaciones (techos, viviendas precarias).

## Resultados del modelo con la nueva Y (validación por años 2008-2025)

| Modelo | PR-AUC | ROC-AUC | Captura 5 % |
|---|---|---|---|
| Al azar (tasa base) | 0,093 | 0,500 | 5 % |
| Climatología (referencia) | **0,397** | 0,865 | 27 % |
| Logística simple (principal) | 0,372 | **0,875** | 24 % |
| Logística completa | 0,385 | 0,867 | 26 % |
| LightGBM | 0,396 | 0,869 | 27 % |

Antes, con DesInventar (2008-2015): climatología 0,095 y logística simple 0,114. Los valores no se comparan directamente, porque la tasa base cambió de 1 % a 9 %.

Con el mapa de 78 distritos del INEI (6/11/2026) las cifras casi no cambian: climatología 0,395, logística simple 0,369, logística completa 0,382 y LightGBM 0,393 (PR-AUC); la logística supera a la climatología con 14 % de probabilidad y LightGBM con 46 %. 2017 y 2023 siguen en los puestos 1 y 2.

**Lectura honesta:**

1. Con la Y oficial **2017 y 2023 se evalúan con métricas reales**, sin que el modelo los haya visto: PR-AUC 0,65 (2017) y 0,66 (2023) para la logística, y siguen siendo los años 1 y 2 de 2016-2025 en riesgo medio de enero a abril.
2. **La lluvia y el mar ahora sí pesan.** Coeficiente estandarizado de la lluvia de 30 días: 0,39 (antes 0,024); Niño 1+2: 0,36 (antes 0,039).
3. **Ningún modelo supera con claridad a la climatología** en PR-AUC (probabilidad de superarla: logística 14 %, LightGBM 47 %). La época del año y la historia del distrito siguen explicando la mayor parte.
4. Captura: el 76 % de las emergencias queda fuera del 5 % de semanas más riesgosas; en Piura se captura el 18 % y en Tumbes el 43 %.

**Experimento (no incorporado):** una logística que usa la climatología como variable y le suma lluvia, caudal y Niño 1+2 llega a PR-AUC 0,425 frente a 0,397, pero gana solo en 7 de 18 años. Es el siguiente paso a evaluar con cuidado.

## Cómo reproducir

```bash
python src/etiqueta_sinpad.py --descargar
python src/modelo_inundacion.py
python src/ml_evaluacion.py
python herramientas/pruebas/auditoria_sinpad.py
python -m pytest -q tests/test_sinpad.py
```

La versión anterior con DesInventar sigue disponible para comparar: `python src/modelo_inundacion.py --fuente desinventar` (resultados en `data/modelo/resultados_desinventar/`).
