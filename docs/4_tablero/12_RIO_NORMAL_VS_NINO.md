# 03 · Río normal frente al río con El Niño

Pedido del profesor Alexander: mostrar primero el río en estado normal, luego en 2017 y luego estos días, para ver cuánto se desbordó.

## 1. La idea en una frase

Una línea de tiempo de cuatro pasos (**Normal → 2017 → 2023 → Hoy**) sobre la foto satelital de cada momento. El cauce normal queda siempre dibujado como una línea azul oscuro, y el agua de cada evento se pinta encima en celeste. Así se ve de un vistazo cuánto se salió el río. Una cifra acompaña cada paso: «el agua ocupa X veces el área del cauce normal».

## 2. El dato que más impacta (ya calculado con archivos del repositorio)

El mapa oficial de Copernicus EMS de 2017 (activación EMSR199, Bajo Piura, área de estudio de 1 892 km²) trae dos capas que sirven justo para esto:

| Capa oficial | Fecha | Área |
|---|---|---|
| Ríos, lagunas y reservorios de referencia (`hydrography_poly`) | Referencia de 2011 | 23,4 km² (el río solo: 8,2 km²) |
| Área inundada (`crisis_information_poly`, tipo «Flood») | 26 de marzo de 2017 | 80,8 km² |
| Área inundada | 30 de marzo de 2017 | 73,0 km² |
| Área inundada, unión de las dos fechas | 26 y 30 de marzo | 97,2 km² (la misma cifra de `dashboard/data/validacion_2017.json`) |

**En el Bajo Piura, el agua de marzo de 2017 cubrió unas 12 veces el área del cauce del río y 4 veces toda el agua que hay normalmente (río, lagunas y reservorios).** Medido con los shapefiles de `data/validacion/ems2017/` (archivo `EMSR199_10PIURA_DELINEATION_OVERVIEW_v2_vector.zip`), en UTM 17S. Las capas de ríos e inundación son iguales en la versión de monitoreo (MONIT01).

## 3. Capas, en el orden en que se muestran

| Paso | Qué se ve | Capa del agua | Foto de fondo (Sentinel-2) | Fuente y límite |
|---|---|---|---|---|
| 1. Normal | El río en temporada seca | Agua permanente de JRC Global Surface Water (agua presente en al menos el 75 % del tiempo entre 1984 y 2021). En el Bajo Piura, además, los ríos de referencia de Copernicus | Seca 2016: Piura 8/12/2016, Tumbes 21/11/2016 | Es el mismo criterio que usa el radar para separar agua permanente de agua nueva (`src/huellas.py`) |
| 2. El Niño 2017 | El desborde más grande de la década | Radar Sentinel-1, febrero a abril de 2017 (`data/huellas/2017.tif`). En el Bajo Piura, el área inundada oficial de Copernicus del 26 y 30 de marzo | Piura 7/4/2017; Tumbes 20/4/2017 | El radar detecta el 42 % de lo inundado en 2017 según Copernicus: es un mínimo. No hay foto óptica sin nubes del pico (26-27 de marzo) |
| 3. Ciclón Yaku 2023 | Un evento de lluvia sin El Niño fuerte en el mar | Radar, 1 de marzo a 15 de abril de 2023 (`data/huellas/2023.tif`) | Piura 14/4/2023; Tumbes 4/5/2023 | Sin mapa oficial para comparar |
| 4. Hoy | Lo que pasa estos días | Radar, últimos 24 días (`data/huellas/vivo.tif`, hoy del 12/10 al 3/11/2026) | Piura y Tumbes 5/10/2026 | La foto de Piura tiene 38 % de nubes en la zona. Mientras no haya una crecida grande, se verá poco agua nueva |

En todos los pasos, el cauce normal queda dibujado debajo, como línea. Sin esa referencia no se puede apreciar el desborde.

## 4. Cómo se vería

Recomendamos **línea de tiempo + comparador** dentro de la pestaña «Antes y después», que ya tiene las fotos y el control deslizable de Maykol:

```
┌─ Río Piura: ciudad de Piura y Bajo Piura ▼ ─────────────────────────────┐
│  [ Normal ]──[ 2017 ]──[ 2023 ]──[ Hoy ]        ☐ Mostrar mapa oficial 2017 │
│ ┌──────────────────────────┬──────────────────────────┐                 │
│ │  foto seca 2016          │  foto del paso elegido    │  ← deslizador   │
│ │  ─── cauce normal        │  ─── cauce normal         │                 │
│ │                          │  ▓▓▓ agua del evento      │                 │
│ └──────────────────────────┴──────────────────────────┘                 │
│  2017: el agua cubrió 97 km², unas 12 veces el cauce del río (Copernicus)  │
│  Radar del proyecto: X km² (es un mínimo: ve el 42 % de lo inundado)      │
└────────────────────────────────────────────────────────────────────────┘
```

- **Por qué no solo capas:** con casillas para prender y apagar, el profesor tiene que armar la comparación él mismo. La línea de tiempo cuenta la historia en orden.
- **Por qué no solo comparador:** el comparador muestra dos momentos; la línea de tiempo deja recorrer los cuatro.
- **En celular:** el deslizador cuesta usarlo; ahí bastan los cuatro botones.

## 5. Código

### 5.1 Datos (`rio_normal_vs_nino.py`, se entrega aparte)

Genera, en `dashboard/data/rio/`:

- `rio_normal.geojson`: el agua permanente de JRC GSW.
- `ems2017_rio.geojson` y `ems2017_inundado.geojson`: las capas oficiales del Bajo Piura.
- `rio_pasos.json`: para cada tramo y paso, los km² de agua, cuántas veces el cauce normal y qué foto usar.

Reutiliza las huellas de radar, las fotos y los archivos de Copernicus que ya están en el repositorio; solo descarga JRC GSW, igual que `src/huellas.py`. **No pudimos correrlo aquí**, porque este entorno no tiene geopandas ni rasterio. Hay que probarlo en la laptop con `python src/rio_normal_vs_nino.py`.

Un detalle importante: las huellas de radar usan 255 como «sin dato». El código lo excluye; si no, contaría el borde vacío como agua.

### 5.2 Tablero (pseudocódigo para `dashboard/index.html`)

Las fotos de `dashboard/data/sat/` están en grados (EPSG:4326) y cubren la caja de cada tramo. Por eso las capas se pueden dibujar encima con un SVG y una regla de tres, sin otra librería de mapas:

```js
// x, y dentro de la foto a partir de lon, lat
const px = (lon, lat, caja, W, H) => [
  (lon - caja[0]) / (caja[2] - caja[0]) * W,
  (caja[3] - lat) / (caja[3] - caja[1]) * H];

async function mostrarPaso(tramo, paso) {
  const d = await (await fetch('data/rio/rio_pasos.json')).json();
  const t = d.tramos[tramo], p = t.pasos.find(x => x.paso === paso);
  fotoDerecha.src = 'data/' + p.foto;                                      // foto del paso
  dibujar(svgCauce, await geo('data/rio/rio_normal.geojson'), t.caja, {stroke: '#0b3d91', fill: 'none'});
  if (paso !== 'normal')
    dibujar(svgEvento, await capaRadar(paso), t.caja, {fill: '#38bdf8', opacity: .75});
  if (paso === '2017' && tramo === 'bajo_piura' && chkOficial.checked)
    dibujar(svgOficial, await geo('data/rio/ems2017_inundado.geojson'), t.caja, {stroke: '#f97316', fill: 'none'});
  cifra.textContent = paso === 'normal'
    ? `Cauce normal: ${fmt(p.km2_agua)} km²`
    : `${p.etiqueta}: ${fmt(p.km2_agua)} km² de agua, ${fmt(p.veces_normal)} veces el cauce normal`;
  pie.textContent = `Foto Sentinel-2 del ${p.foto_fecha} · nubes en la zona: ${fmt(p.foto_nubes_pct)} %`;
}
// capaRadar('2017') usa las capas que ya existen: data/capa_2017.geojson, capa_2023 y capa_vivo
// fmt() con espacio de miles y coma decimal, como el resto del tablero
```

## 6. Imágenes Sentinel-2 sin nubes

Búsqueda en el catálogo de Microsoft Planetary Computer (colección `sentinel-2-l2a`, 5/11/2026), con las mismas cajas del comparador: Piura (−80,76; −5,40; −80,52; −5,14), tesela 17MNQ, y Tumbes (−80,58; −3,76; −80,36; −3,52), tesela 17MNR. «Nubes» es el porcentaje de **toda la escena** que informa el catálogo. Las marcadas con ✔ son las que ya usa el tablero, y en ellas la nubosidad **dentro de la caja** viene de `satelite.json`, porque `src/satelite.py` la mide con la capa de clasificación de escena.

### Río Piura (tesela 17MNQ)

| Momento | Fecha | Nubes en la escena | Escena | Nota |
|---|---|---|---|---|
| Seca antes de 2017 | 10/08/2016 | 0,3 % | S2A_MSIL2A_20160810T153622_R068_T17MNQ_20210212T130314 | |
| Seca antes de 2017 | 21/11/2016 | 1,0 % | S2A_MSIL2A_20161121T155222_R111_T17MNQ_20210414T184139 | |
| Seca antes de 2017 | 08/12/2016 | 1,5 % | S2A_MSIL2A_20161208T153612_R068_T17MNQ_20210213T190407 | ✔ 0,1 % en la caja |
| Seca antes de 2017 | 31/12/2016 | 0,6 % | S2A_MSIL2A_20161231T155212_R111_T17MNQ_20210214T021245 | |
| Evento 2017 (más cercana al pico) | 11/03/2017 | 53,0 % | S2A_MSIL2A_20170311T155211_R111_T17MNQ_20210208T213741 | Revisar nubes en la caja |
| Evento 2017 | 07/04/2017 | 54,3 % | S2A_MSIL2A_20170407T153621_R068_T17MNQ_20210209T053655 | ✔ 1,8 % en la caja: las nubes estaban fuera |
| Evento 2017 | 20/04/2017 | 35,1 % | S2A_MSIL2A_20170420T155221_R111_T17MNQ_20210209T091659 | |
| Seca después de 2017 | 19/10/2017 | 0,3 % | S2B_MSIL2A_20171019T153609_R068_T17MNQ_20201015T010058 | |
| Seca después de 2017 | 01/12/2017 | 0,3 % | S2B_MSIL2A_20171201T155209_R111_T17MNQ_20201014T113759 | |
| Seca después de 2017 | 18/12/2017 | 0,2 % | S2B_MSIL2A_20171218T153609_R068_T17MNQ_20201014T145915 | |
| Seca antes de 2023 | 05/12/2022 | 0,0 % | S2B_MSIL2A_20221205T155219_R111_T17MNQ_20250205T180104 | ✔ 0,1 % en la caja |
| Evento 2023 | 14/04/2023 | 0,9 % | S2B_MSIL2A_20230414T155219_R111_T17MNQ_20240808T180318 | ✔ 0,6 % en la caja |
| Hoy | 05/10/2026 | 1,5 % | S2B_MSIL2A_20261005T155219_R111_T17MNQ_20261005T204634 | ✔ pero 38 % en la caja |

### Río Tumbes (tesela 17MNR)

| Momento | Fecha | Nubes en la escena | Escena | Nota |
|---|---|---|---|---|
| Seca antes de 2017 | 24/06/2016 | 0,1 % | S2A_MSIL2A_20160624T155222_R111_T17MNR_20210211T224729 | |
| Seca antes de 2017 | 10/08/2016 | 0,4 % | S2A_MSIL2A_20160810T153622_R068_T17MNR_20210212T130312 | |
| Seca antes de 2017 | 21/11/2016 | 0,1 % | S2A_MSIL2A_20161121T155222_R111_T17MNR_20210414T184142 | ✔ 0,0 % en la caja |
| Evento 2017 | 26/02/2017 | 18,1 % | S2A_MSIL2A_20170226T153611_R068_T17MNR_20210208T173009 | La de menos nubes del evento |
| Evento 2017 | 31/03/2017 | 48,9 % | S2A_MSIL2A_20170331T155221_R111_T17MNR_20210209T032940 | Más cercana al pico; revisar la caja |
| Evento 2017 | 20/04/2017 | 45,7 % | S2A_MSIL2A_20170420T155221_R111_T17MNR_20210209T091659 | ✔ 12,8 % en la caja |
| Seca después de 2017 | 17/10/2017 | 5,6 % | S2A_MSIL2A_20171017T155221_R111_T17MNR_20201015T001901 | |
| Seca después de 2017 | 24/10/2017 | 1,7 % | S2A_MSIL2A_20171024T153621_R068_T17MNR_20201015T015837 | |
| Seca después de 2017 | 18/12/2017 | 3,1 % | S2B_MSIL2A_20171218T153609_R068_T17MNR_20201014T145910 | |
| Seca antes de 2023 | 05/12/2022 | 0,2 % | S2B_MSIL2A_20221205T155219_R111_T17MNR_20250205T180104 | ✔ 0,6 % en la caja |
| Evento 2023 | 03/02/2023 | 2,3 % | S2B_MSIL2A_20230203T155219_R111_T17MNR_20240731T132332 | |
| Evento 2023 | 04/05/2023 | 7,9 % | S2B_MSIL2A_20230504T155229_R111_T17MNR_20240812T072325 | ✔ 1,9 % en la caja |
| Hoy | 05/10/2026 | 6,0 % | S2B_MSIL2A_20261005T155219_R111_T17MNR_20261005T204634 | ✔ 0,7 % en la caja |

**Para el paso «Normal» conviene la seca de 2016**, porque es justo antes de 2017. Si se quiere mostrar que el río volvió a su cauce después del desborde, se puede agregar un quinto paso con la seca de fines de 2017: hay imágenes casi sin nubes del 1/12/2017 (Piura) y del 24/10/2017 (Tumbes).

## 7. Lo que hay que decir con honestidad

- **El pico de marzo de 2017 no tiene foto óptica limpia.** Las escenas del 11/3 y del 31/3 tienen la mitad de nubes. Además, en 2017 solo operaba un satélite Sentinel-2 (el segundo empezó a mediados de ese año), así que pasaba cada 10 días. Por eso el agua del pico se muestra con el radar y con el mapa oficial, y no con la foto.
- **La foto de abril de 2017 llega cuando el agua ya bajaba.** Hay que decirlo en el pie de foto.
- **Tumbes no tiene mapa oficial de Copernicus para 2017**: solo se puede mostrar el radar.
- **«Hoy» no es una inundación grande todavía.** El paso existe para que, si llega la crecida, el tablero la muestre con el mismo formato.
