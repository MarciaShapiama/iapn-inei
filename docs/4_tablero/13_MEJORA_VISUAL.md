# 04 · Por qué el mapa se ve «tosco» al acercarse y cómo arreglarlo

Hay tres causas, y se arreglan por separado: **el agua sale en bloques**, **la foto satelital se estira** y **se puede acercar más de lo que dan los datos**.

![Hoy, celda real y propuesta](figuras/mapa_antes_despues.png)

*Zona inundable de JRC (crecida de 1 en 100 años), al oeste de la ciudad de Piura y al norte de Catacaos, unos 6,7 × 6,7 km. Las tres imágenes salen del mismo archivo del repositorio (`data/exposicion/peligro_rp100.tif`).*

## 1. Causa 1: el agua se dibuja en bloques de 180 m con borde blanco

**Qué pasa hoy** (`src/impacto.py`, función `poligonos()`):

1. `k = 2` junta 2 × 2 celdas y se queda con el máximo. La zona de JRC tiene celdas de 90 m (3 segundos de arco), así que el mapa queda en bloques de 180 m. En el radar pasa lo mismo: de 55 m a 110 m. Se ve en el GeoJSON publicado: los vértices de `capa_rp100.geojson` avanzan de 0,00167° en 0,00167° (unos 185 m).
2. `simplify(0,6 × celda)` no alcanza para quitar la escalera, porque cada escalón (180 m) es más grande que la tolerancia (108 m).
3. En el tablero 3D, la capa tiene borde blanco (`stroked:true`, `getLineColor:[255,255,255,90]`). Como cada clase de profundidad es un polígono distinto, el borde dibuja la cuadrícula.

**Qué proponemos** (archivo `codigo_mapa/poligonos_suaves.py`, que reemplaza a `poligonos()`):

1. Trabajar con la celda real de 90 m (sin `k = 2`).
2. Antes de pasar a polígonos, dividir cada celda en 4 × 4 y suavizar un poco (unos 34 m). El borde exterior sale de la máscara suavizada cortada en 0,5; así **el área no cambia**. En un tramo de 1 100 × 1 200 celdas del Bajo Piura, el área con agua pasó de 13,78 % a 13,85 %. Si se suavizara la profundidad directamente, el borde crecería entre 5 % y 36 % según la zona.
3. Las clases de profundidad (< 0,5; 0,5-1,5; 1,5-3; > 3 m) salen de la profundidad suavizada, dentro de ese borde. No quedan huecos entre clases, como sí pasaría si se suavizara cada polígono por separado. Lo probamos.
4. Procesa por ventanas de 512 celdas con margen, para usar poca memoria. Comprobamos que el resultado por ventanas es idéntico al de procesar todo junto: 0 celdas distintas de 21 millones.

**Importante:** esto es solo para dibujar. Las cifras de personas, edificaciones y colegios se siguen calculando con el ráster original, sin tocar.

Lo que no pudimos probar aquí es la conversión a polígonos (`rasterio.features.shapes`), porque este entorno no tiene rasterio. En la laptop, después de correr `python src/etl.py local`, revisen el tamaño de `capa_rp100.geojson`. Hoy pesa 1,6 MB:

- **Si queda por debajo de unos 5 MB**, se publica así. GitHub Pages lo envía comprimido.
- **Si pasa de 5 MB**, hay dos salidas:
  - **(a) Dos niveles de detalle:** guardar la versión actual como `capa_rp100.geojson` para la vista general, y la versión suave partida por departamento (`capa_rp100_piura.geojson`, `capa_rp100_tumbes.geojson`). La versión suave se carga solo con zoom ≥ 11.
  - **(b) Teselas vectoriales:** convertirlas a PMTiles con tippecanoe y leerlas con `MVTLayer`. Es lo más fluido, pero agrega una herramienta al flujo.

## 2. Causa 2: la foto satelital se estira al acercarse

**Qué pasa hoy:** en el 3D, la foto de Esri es la textura del `TerrainLayer`, que tiene `maxZoom:13`. Desde zoom 13, deck.gl ya no pide teselas nuevas: estira las de zoom 13, de unos 19 m por píxel. Al hacer clic en un colegio, el mapa vuela a zoom 14 (`I3.volarA`), y la foto se ve borrosa justo ahí.

**Arreglo rápido (una línea):** subir `maxZoom` del `TerrainLayer` de 13 a 15. Las teselas de altura que usa (terrarium de AWS) llegan hasta zoom 15. Hay que hacerlo en los dos `TerrainLayer` de `dashboard/index.html`, el de inundación y el de zonas.

```js
new deck.TerrainLayer({id:"terreno-"+I3.modo, minZoom:0, maxZoom:15, /* antes 13 */ strategy:"no-overlap",
  operation:"terrain+draw", elevationDecoder:{...}, elevationData:"...terrarium/{z}/{x}/{y}.png", texture:TEX[I3.modo]})
```

**Arreglo mejor:** separar el relieve de la foto. El relieve se queda en zoom 14, que basta para la forma del terreno, y la foto va en su propia capa de teselas hasta zoom 18, apoyada sobre el relieve. Es la forma que propone deck.gl para dibujar teselas sobre un terreno. Pruébenlo en el navegador. Si la foto no se apoya bien en el relieve, queden con el arreglo rápido.

```js
const T = new deck._TerrainExtension();
const terreno = new deck.TerrainLayer({id:"terreno", minZoom:0, maxZoom:14, strategy:"no-overlap",
  operation:"terrain",                      // solo la forma; sin textura
  elevationDecoder:{rScaler:256*2.5, gScaler:2.5, bScaler:2.5/256, offset:-32768*2.5},
  elevationData:"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"});
const foto = new deck.TileLayer({id:"foto-"+I3.modo, data:TEX[I3.modo], minZoom:0, maxZoom:18, tileSize:256,
  extensions:[T],
  renderSubLayers: p => new deck.BitmapLayer(p, {data:null, image:p.data,
    bounds:[p.tile.bbox.west, p.tile.bbox.south, p.tile.bbox.east, p.tile.bbox.north]})});
const capas = [terreno, foto /* , agua, distritos, colegios... igual que hoy */];
```

## 3. Causa 3: se puede acercar más de lo que dan los datos

Hoy el 3D no tiene zoom máximo, y el 2D llega a 18. La zona inundable tiene celdas de 90 m y el radar de 55 m: desde zoom 15, una celda ocupa más de 15 píxeles. Por mucho que se suavice el borde, acercarse más no muestra más detalle, solo da una falsa sensación de precisión.

**3D** (`dashboard/index.html`):

```js
// límites en la vista inicial y en las vistas de VISTAS
initialViewState:{...VISTAS.piura, minZoom:6, maxZoom:16}
// aviso honesto cuando se acerca mucho
onViewStateChange:({viewState}) => {
  document.getElementById("aviso-zoom").hidden = viewState.zoom < 14;   // «La zona inundable tiene celdas de 90 m;
  return viewState;                                                      //   acercarse más no agrega detalle»
}
```

**2D** (`dashboard/mapa2d.html`): la foto de Esri no llega con el mismo detalle a todas las zonas. Con `maxNativeZoom`, Leaflet estira la última foto disponible en lugar de mostrar recuadros grises.

```js
mapa = L.map("mapa", {preferCanvas:true, zoomSnap:.5, maxZoom:17}).setView([-4.9,-80.5], 8);
base = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                   {maxNativeZoom:17, maxZoom:17, attribution:"Imágenes © Esri y proveedores"});
```

## 4. Otros detalles que mejoran la vista

| Cambio | Dónde | Por qué |
|---|---|---|
| `stroked:false` en la capa de agua | 3D, `GeoJsonLayer` «agua-…» | Quita la cuadrícula blanca entre clases (causa 1, punto 3) |
| Opacidad de la capa de agua en 0,8 desde zoom 12 | 3D, prop `opacity` | Con el agua al 100 %, no se ve qué hay debajo (casas, chacras) |
| Leyenda de profundidad con los cortes en metros («menos de 0,5 m», «0,5 a 1,5 m»…) | Ambos | El color solo, sin número, no se entiende |
| Mismos azules en 2D y 3D | `COL_PEL` (2D) y `AZUL.peligro` (3D) | Las dos clases más claras no coinciden: el 2D usa #c6dbef y #6baed6; el 3D, #9ecae1 y #4292c6 |

## 5. Orden sugerido

1. `maxZoom:15` en los `TerrainLayer` y `stroked:false` en el agua: 10 minutos, sin riesgo.
2. Límite de zoom y aviso de 90 m: 20 minutos.
3. `poligonos_suaves.py` en `impacto.py`, correr `python src/etl.py local` y revisar el tamaño de los GeoJSON: 1 hora.
4. Separar foto y relieve (arreglo mejor de la causa 2): probarlo con calma, porque toca la parte más delicada del 3D.
