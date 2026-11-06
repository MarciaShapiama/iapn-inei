# 02 · Cruce de los habitantes del Censo 2025 con la zona inundable y el aviso de lluvia

El INEI va a enviar personas por vivienda o por manzana, con sexo y edad. `cruce_habitantes.py` las cruza con la zona inundable de JRC y con el aviso de lluvia. Así, el aviso podrá decir, por ejemplo: «Zarumilla: lluvia fuerte mañana; X personas viven en la zona inundable, de ellas Y niños de 0 a 4 años y Z adultos de 65 o más».

El código ya está probado, pero **solo con datos inventados**: no tenemos ni pedimos los datos del INEI. Cuando lleguen, Marcia lo corre en su laptop.

## 1. Antes de correrlo (una sola vez)

1. **Agregar `datos_inei/` al `.gitignore` del repositorio.** Hoy el `.gitignore` público no lo tiene. Sin esa línea, un `git add .` subiría los datos del INEI a GitHub.
   ```
   # Datos confidenciales del INEI: nunca se suben
   datos_inei/
   ```
2. Copiar `cruce_habitantes.py` a `src/`.
3. Poner los archivos del INEI en `datos_inei/`:
   - `datos_inei/manzanas/`: lo que ya llegó el 4/11 (los CSV por manzana con `n_viviendas_ocupadas` y el shapefile).
   - `datos_inei/habitantes...`: el archivo nuevo, con cualquier nombre que empiece con «habitantes» (CSV o Excel).

## 2. Qué hay que ajustar cuando llegue el archivo

Todo está en el bloque **CONFIGURACIÓN** al inicio del código. No hay que tocar nada más.

| Qué revisar en el archivo del INEI | Dónde se cambia | Ejemplo |
|---|---|---|
| ¿Viene una fila por persona, por vivienda o por manzana? | `NIVEL` | `"persona"` |
| ¿Cómo se llama la columna que identifica la manzana? Si no hay `idmanzana`, ¿vienen ubigeo, zona y manzana por separado? | `COL["idmanzana"]` o `COL["ubigeo"]`, `COL["zona"]`, `COL["manzana"]` | `"idmanzana"` |
| Si es por persona: ¿cómo se llaman sexo y edad? | `COL["sexo"]`, `COL["edad"]` | El nombre exacto que traiga el archivo; el diccionario del INEI lo indica |
| ¿Con qué códigos viene el sexo? | `CODIGOS_SEXO` | `{"1": "hombre", "2": "mujer"}` |
| Si viene sumado: ¿cómo se llaman las columnas de personas, hombres, mujeres, 0 a 4 y 65 o más? | `COL["personas"]`, `COL["hombres"]`… | |
| Si viene en grupos quinquenales (0-4, 5-9…): el grupo 65 o más es la suma de 65-69, 70-74, etc. | Sumar antes, o pedir al INEI el grupo 65+ | |
| ¿Separador y codificación? | `SEPARADOR`, `CODIFICACION` | `";"`, `"latin-1"` |

Si falta una columna, el programa se detiene y muestra las columnas que sí trae el archivo, para corregir el nombre.

**Cómo armar la llave si no viene `idmanzana`.** El código une ubigeo (6 dígitos) + zona + manzana. Antes de correr todo, compárelo con 5 manzanas del CSV que ya llegó. Si no coinciden (por ejemplo, porque la zona viene con ceros a la izquierda), ajústelo en la función `llave()`.

## 3. Qué hace, paso a paso

1. **Habitantes por manzana.** Suma personas, hombres, mujeres, niños de 0 a 4 años y adultos de 65 o más en cada manzana.
2. **Viviendas por manzana.** Las toma del CSV que ya mandó el INEI (`n_viviendas_ocupadas`).
3. **¿La manzana está en la zona inundable?** Usa el mismo método del cruce de viviendas que ya está publicado: un punto interior de cada manzana y la profundidad de JRC en ese punto. Lo hace para la crecida de 1 en 10 años y la de 1 en 100 años. Si ese cruce ya dejó la profundidad por manzana en `datos_inei/manzanas_profundidad.csv`, la usa directamente; si no, la calcula con geopandas y rasterio y la guarda ahí para la próxima vez.
4. **Totales por distrito**, en cuatro cortes:
   - todo el distrito;
   - zona de 1 en 10 años;
   - zona de 1 en 100 años;
   - zona de 1 en 100 años con más de 1,5 m de agua.
5. **Supresión.**
   - Se oculta todo distrito con menos de 10 viviendas en la zona (supresión primaria).
   - Si en un departamento queda **un solo** distrito oculto, se oculta también el siguiente más chico (supresión secundaria). Si no, alguien podría restar el total del departamento menos los demás distritos y despejar el oculto. Es la práctica normal de las oficinas de estadística, y el jurado del INEI la va a reconocer.
6. **Cruce con el aviso de lluvia.** Agrega a cada distrito del aviso (`dashboard/data/aviso_lluvia.json`) las personas de su zona inundable. Desde el 6/11/2026 el aviso usa los 78 distritos del INEI, así que Veintiséis de Octubre y Canoas de Punta Sal ya tienen su propia fila (antes se sumaban a Piura y a Zorritos).

## 4. Qué produce

| Archivo | Contenido | ¿Se publica? |
|---|---|---|
| `datos_inei/resultados/habitantes_distrito.csv` | Por distrito y corte: viviendas, personas, hombres, mujeres, 0 a 4, 65 o más y si está reservado | No, queda en la laptop |
| `datos_inei/resultados/aviso_con_habitantes.csv` | Aviso de lluvia + personas en zona inundable por distrito | No, queda en la laptop |
| `dashboard/data/habitantes_censo.json` (solo con `--publicar`) | Totales por distrito, con los reservados en blanco, y total general | Sí, cuando el profesor y el INEI lo confirmen por escrito |

Ningún archivo de salida tiene `idmanzana` ni coordenadas. El código lo comprueba antes de guardar.

```bash
python src/cruce_habitantes.py              # resultados privados
python src/cruce_habitantes.py --publicar   # además, el JSON para el tablero
```

## 5. Comprobaciones al correrlo con los datos reales

El programa imprime cada número. Revise estos antes de usar los resultados:

| Comprobación | Qué debería salir | Si no sale |
|---|---|---|
| Personas por vivienda | Entre 3 y 4 en promedio | Revisar si el archivo trae personas en viviendas colectivas o duplicadas |
| Manzanas sin habitantes | Cerca de 0 | La llave no empata: revisar `llave()` |
| «Sexo sin código conocido» | 0 | Completar `CODIGOS_SEXO` |
| Personas en zona inundable de 1 en 100 años | Del orden de las 399 506 que estima WorldPop, **pero menor**, porque las manzanas no incluyen la vivienda rural dispersa (cubren cerca del 80 % de las viviendas de Piura, según el cruce de viviendas) | Revisar la profundidad por manzana |
| Viviendas en zona de 1 en 100 años | 107 166, lo mismo que ya está publicado | Algo cambió en el cruce |

## 6. Cómo usarlo en el tablero y en el modelo

- **Aviso de lluvia:** una columna más, «personas en zona inundable (0 a 4 años / 65 o más)», para los distritos en nivel fuerte o extremo.
- **Resumen:** reemplazar la cifra de niños y adultos mayores de WorldPop (37 168 y 33 024) por la del censo, citando la fuente.
- **Modelo (tarea 1):** las personas en la zona de 1 en 100 años entran como variable fija por distrito, en lugar de las de WorldPop. Además, con las personas por vivienda de cada distrito se pueden convertir las viviendas estimadas en personas.

## 7. Qué decir si el jurado pregunta

- **«¿Por qué no publican por manzana?»** Porque el INEI entregó los datos como confidenciales, y con una manzana de pocas viviendas se puede identificar a las familias. Publicamos solo totales por distrito y ocultamos los distritos con menos de 10 viviendas, más la supresión secundaria.
- **«¿Por qué un punto por manzana y no el área inundada de la manzana?»** Es el mismo criterio del cruce de viviendas ya publicado, y las manzanas son chicas frente a la celda de 90 m de JRC. Si el jurado lo pide, se puede repetir con la proporción del área de cada manzana dentro de la zona; el código está separado en una función (`profundidad_por_manzana`).
