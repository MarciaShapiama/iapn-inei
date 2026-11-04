# 05 · Opciones de política pública vinculadas a los resultados

## Reglas de lectura

- **Diagnóstico ≠ recomendación.** Las cifras describen **exposición potencial** ante escenarios (JRC 1/10 y 1/100 años) y detecciones de radar. Las opciones de abajo son **propuestas para evaluar** por las entidades competentes.
- **Ningún resultado estadístico sustituye una evaluación oficial de riesgo** (EVAR, CENEPRED) ni autoriza reubicaciones. Cualquier reasentamiento sigue los procedimientos de ley, con participación y consentimiento de la población.
- **Las metas son propuestas a validar** con línea base oficial. Los indicadores de línea base salen de `dashboard/data/descargas/panel_distritos.csv` y `exposicion_distritos.csv` (corte 4/11/2026).
- El costo es **relativo y cualitativo** (bajo / medio / alto), sin presupuesto.

## Resumen

| # | Política | Activador en los datos | Responsable principal | Costo |
|---|---|---|---|---|
| P1 | Continuidad educativa en locales expuestos | 682 locales escolares dentro de la zona 1/100 (124.385 alumnos); 2.633 hasta 1 km | MINEDU, DRE/UGEL, gobiernos regionales | Bajo–medio |
| P2 | Continuidad de servicios de salud | 145 establecimientos dentro; 577 hasta 1 km | MINSA, DIRESA, gobiernos regionales | Medio |
| P3 | Ordenamiento territorial: restringir la expansión en zonas inundables | Bernal, Rinconada Llicuar y Bellavista de la Unión con > 95 % de su área en 1/100 | Municipalidades provinciales, gobiernos regionales, CENEPRED | Bajo (normativo) |
| P4 | Mantenimiento de drenes y cauces focalizado y sustentado en estudios | Bajo Piura y cuenca baja del Tumbes con mucha exposición | ANA, gobiernos regionales, municipalidades | Medio–alto |
| P5 | Rutas de evacuación y refugios temporales | Distritos con gran población expuesta y profundidad > 1,5 m | Municipalidades, INDECI, gobiernos regionales | Medio |
| P6 | Comunicación de riesgo comunitaria | Brecha entre escenario, aviso y alerta oficial | Municipalidades, SENAMHI, INDECI, ENFEN | Bajo |
| P7 | Levantamiento prioritario de datos | Vacíos: radar urbano, distritos sin límites, caudal observado | INEI, ANA, SENAMHI, MINEDU | Medio |

---

## P1. Continuidad educativa en locales potencialmente expuestos

- **Problema:** los colegios en zonas inundables pierden días de clase y equipamiento, y a veces se usan como albergue sin estar preparados.
- **Evidencia que la activa:** zona 1/100: **682 locales escolares dentro**, con **124.385 alumnos** (Censo Educativo 2025), 2.001 hasta 500 m y 2.633 hasta 1 km (acumulados). Zona 1/10: 449 dentro, con 68.180 alumnos. Por distrito (1/100): Catacaos 106, Castilla 97, Piura 80, La Unión 55, La Arena 41, Tumbes 33. Fuente: padrón ESCALE (MINEDU), un local por código de local.
- **Población objetivo:** estudiantes y docentes de los locales dentro o a menos de 500 m.
- **Cobertura:** 76 distritos con UBIGEO 20xxxx y 24xxxx; empezar por Castilla (200104), Catacaos (200105), Piura (200101), La Arena (200109) y Tumbes (240101).
- **Responsables:** MINEDU (PREVAED), DRE Piura y Tumbes, UGEL, gobiernos regionales.
- **Intervención:** (1) usar la lista de locales del padrón ESCALE, que ya trae código de local y matrícula, para asignar responsables por UGEL; (2) plan de contingencia y calendario alterno; (3) evaluación estructural de los locales con profundidad > 0,5 m; (4) no usar como albergue los locales que estén dentro de la mancha.
- **Línea base:** 682 / 2.633 locales (ESCALE); 124.385 alumnos dentro. **Meta a validar:** 100 % de los locales del padrón dentro de la zona 1/100 con plan de contingencia aprobado.
- **Seguimiento:** porcentaje de locales con plan; días lectivos perdidos por evento (MINEDU).
- **Riesgos de inequidad:** unos pocos locales no tienen coordenadas o matrícula en ESCALE (28 dentro de la zona sin dato de alumnos) y podrían quedar fuera de la priorización; hay que completarlos con las UGEL.
- **Límites de la evidencia:** coordenadas del padrón por verificar en campo; el JRC no modela la inundación pluvial urbana, que también cierra colegios.

## P2. Continuidad de servicios de salud

- **Problema:** perder un establecimiento durante una emergencia corta la atención justo cuando aumentan la demanda y las enfermedades asociadas a las lluvias.
- **Evidencia:** zona 1/100: **145 establecimientos dentro**, 429 hasta 500 m y 577 hasta 1 km (RENIPRESS, activos, I-1 a III). Castilla tiene 50 dentro y Piura 17.
- **Población objetivo:** usuarios de los establecimientos expuestos; priorizar hospitales y centros con internamiento (I-4 o más).
- **Responsables:** MINSA (DIGERD), DIRESA Piura y Tumbes, gobiernos regionales; EsSalud y privados según el caso.
- **Intervención:** plan de continuidad operativa, reubicación de equipos críticos por encima de la cota de inundación, rutas alternas de referencia y stock prepositado.
- **Línea base:** 145 / 577. **Meta a validar:** todos los establecimientos con internamiento dentro de la zona 1/100 con plan de continuidad probado en simulacro.
- **Seguimiento:** simulacros realizados; días de cierre por evento.
- **Riesgos de inequidad:** las postas I-1 rurales son las más frágiles y también las que menos aparecen en los planes.
- **Límites:** las coordenadas declaradas en RENIPRESS pueden estar desplazadas; hay que verificar en campo los establecimientos cerca del borde.

## P3. Ordenamiento territorial y restricción de expansión en zonas inundables

- **Problema:** la ocupación nueva de llanuras de inundación aumenta la exposición futura.
- **Evidencia:** porcentaje del área distrital en la zona 1/100: Rinconada Llicuar 98,7 %, Bernal 98,5 %, Bellavista de la Unión 95,2 %, Colán 70,2 %, El Tallán 49,5 %, La Arena 46,3 %. Catacaos tiene **85 %** de su población modelada en la zona 1/100.
- **Responsables:** municipalidades provinciales (planes de desarrollo urbano y de acondicionamiento territorial), gobiernos regionales, CENEPRED (lineamientos), MVCS.
- **Intervención:** usar el mapa como **insumo de alerta temprana para la planificación**, para identificar dónde pedir primero estudios EVAR de detalle antes de aprobar habilitaciones urbanas. **No** usar este mapa de 90 m para zonificar lote por lote.
- **Línea base:** edificaciones dentro de la zona 1/100 por distrito (148.348 en total en Tumbes y Piura). **Meta a validar:** cero habilitaciones nuevas aprobadas en zona 1/100 sin estudio de riesgo de detalle.
- **Seguimiento:** comparar la versión de Open Buildings (o la próxima fuente de edificaciones) con la actual: crecimiento de edificaciones dentro de la mancha.
- **Riesgos de inequidad:** las restricciones pueden empujar la ocupación informal hacia zonas peores si no hay oferta de suelo seguro y asequible.
- **Límites:** el JRC no considera diques ni defensas locales y tiene 90 m de resolución.

## P4. Mantenimiento de drenes y limpieza de cauces focalizado y sustentado en estudios

- **Problema:** el mantenimiento se hace sin un criterio territorial explícito y a veces sin estudio hidráulico.
- **Evidencia:** prioridad «Alta» del panel en el Bajo Piura: La Arena, La Unión, El Tallán, Cura Mori, Catacaos, Bernal, Cristo Nos Valga, Rinconada Llicuar y Vice. En el Chira, Colán y Vichayal.
- **Responsables:** ANA (autoridades administrativas del agua y ALA), Proyecto Especial Chira-Piura, gobiernos regionales, municipalidades y juntas de usuarios.
- **Intervención:** cronograma de mantenimiento antes de enero, priorizado por el índice del panel **y validado con estudios hidráulicos**. Las limpiezas deben respetar los criterios ambientales y no trasladar el problema aguas abajo.
- **Línea base:** km de drenes y cauces mantenidos por año (dato de ANA o del gobierno regional, que no está en el proyecto). **Meta a validar:** 100 % de los tramos críticos identificados por ANA mantenidos antes del 31 de diciembre.
- **Riesgos de inequidad:** puede beneficiar a quienes tienen más voz (zonas urbanas o grandes agricultores) frente a caseríos dispersos.
- **Límites:** el panel **no evalúa la capacidad hidráulica**; solo orienta dónde revisar primero.

## P5. Rutas de evacuación y refugios temporales

- **Problema:** muchas personas viven en zonas que pueden inundarse a más de 1,5 m sin rutas ni refugios identificados.
- **Evidencia:** en la zona 1/100, **65.843 edificaciones** están donde el JRC estima más de 1,5 m de profundidad y 61.832 entre 0,5 y 1,5 m.
- **Responsables:** municipalidades (plataformas de defensa civil), INDECI, gobiernos regionales.
- **Intervención:** identificar refugios **fuera** de la mancha y a menos de 1 km de la población expuesta (los colegios fuera de la mancha son candidatos); señalizar rutas; hacer simulacros.
- **Línea base:** refugios señalizados por distrito (no disponible en el proyecto). **Meta a validar:** cada sector con población expuesta tiene un refugio a menos de 1 km fuera de la zona 1/100.
- **Riesgos de inequidad:** personas con discapacidad y adultos mayores (falta el dato; ver P7).
- **Límites:** la profundidad del JRC es del escenario, no de un evento concreto.

## P6. Comunicación de riesgo comunitaria

- **Problema:** se confunden el escenario («1 en 100 años»), el aviso meteorológico (SENAMHI), el estado del sistema de alerta ENFEN y una alerta de evacuación. Hoy la anomalía del mar es muy alta (Piura +7,4 °C el 2/11/2026; Niño 1+2 semanal 5,4 °C), y eso puede generar alarma o, al contrario, desgaste de la atención.
- **Evidencia:** el índice provincial del tablero da la mitad del puntaje al mar, aunque no llueva.
- **Responsables:** municipalidades, SENAMHI, INDECI y ENFEN, cada uno en su ámbito.
- **Intervención:** mensajes estandarizados que distingan qué es oficial y qué no; fichas distritales en lenguaje sencillo (el panel ya genera una por distrito); radios locales.
- **Meta a validar:** comprensión correcta de la diferencia entre aviso y escenario en una encuesta corta antes y después.
- **Riesgos de inequidad:** las poblaciones sin internet ni smartphone necesitan canales analógicos.
- **Límites:** el proyecto no emite alertas; solo enlaza a las fuentes oficiales.

## P7. Levantamiento prioritario de datos (aporte directo del INEI)

- **Problema:** las decisiones anteriores dependen de datos que faltan o son de baja calidad.
- **Evidencia (vacíos medidos):**
  - el radar casi no detecta agua en ciudades (Catacaos 2017: 1,1 km²);
  - faltan dos distritos en los límites usados (200115 Veintiséis de Octubre, con ~130 mil habitantes, y 240203 Canoas de Punta Sal);
  - no hay emergencias fechadas después de 2015;
  - el caudal es modelado;
  - los colegios no vienen del padrón oficial;
  - la pobreza está agrupada (57 valores únicos en 78 distritos).
- **Responsables:** INEI (cartografía, censo, vulnerabilidad), ANA y SENAMHI (hidrometría), INDECI (registro fechado de daños), MINEDU (ESCALE georreferenciado).
- **Intervención:** convenio de intercambio de datos (doc 03); puntos de control en campo después de cada evento para validar el radar; publicar límites oficiales con licencia abierta.
- **Meta a validar:** los 78 distritos con límites oficiales; serie de emergencias fechadas 2016–2026 disponible.
- **Riesgos de inequidad:** los distritos con menos registros parecen «menos riesgosos». El modelo del caso C ya lo muestra: captura el 46 % de las emergencias en Tumbes y solo el 5 % en Piura.
- **Límites:** depende de acuerdos interinstitucionales.
