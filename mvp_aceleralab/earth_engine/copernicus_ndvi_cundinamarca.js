/**
 * AbejaVerde·EO — NDVI Copernicus Sentinel-2 para los apiarios de Cundinamarca
 * Google Earth Engine (pegar completo en https://code.earthengine.google.com y pulsar Run)
 *
 * Qué hace:
 *  1. Calcula el NDVI promedio de los últimos DIAS_VENTANA días en un radio de 1 km
 *     alrededor de cada apiario (área de pecoreo cercana), sin nubes.
 *  2. Lo muestra en el mapa con colores tipo semáforo y lo imprime en la consola.
 *  3. Dibuja la serie mensual de NDVI del apiario piloto (San Juan de Rioseco) desde 2024.
 *  4. Exporta una tabla CSV a Google Drive para pegar la columna NDVI en la hoja
 *     BD_AbejaVerde_EO → Bitacora_Colmenas (pestaña Tasks → RUN).
 *
 * Para agregar un apiario: añada una línea en APIARIOS con su ID, municipio y coordenadas.
 */

// ── 1. Apiarios (ID, municipio, latitud, longitud) ────────────────────────────
var APIARIOS = [
  ['API-01', 'Pacho',               5.1326, -74.1602],
  ['API-02', 'Fusagasugá',          4.3365, -74.3638],
  ['API-03', 'San Juan de Rioseco', 4.8750, -74.6350],
  ['API-04', 'La Mesa',             4.6337, -74.4617]
];
var RADIO_M      = 1000;  // radio de análisis alrededor del apiario
var DIAS_VENTANA = 45;    // ventana para armar una imagen sin nubes
var MAX_NUBES    = 30;    // % máximo de nubes por escena

var apiarios = ee.FeatureCollection(APIARIOS.map(function (a) {
  return ee.Feature(ee.Geometry.Point([a[3], a[2]]).buffer(RADIO_M),
                    {ID_Apiario: a[0], Municipio: a[1], Coordenadas_GPS: a[2] + ', ' + a[3]});
}));

// ── 2. Máscara de nubes con la capa de clasificación de escena (SCL) ─────────
function enmascararNubes(img) {
  var scl = img.select('SCL');
  // 3 sombra, 8-9 nubes, 10 cirros, 11 nieve
  var limpio = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return img.updateMask(limpio);
}
function conNdvi(img) {
  return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'));
}

var hoy    = ee.Date(Date.now());
var inicio = hoy.advance(-DIAS_VENTANA, 'day');

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(apiarios)
  .filterDate(inicio, hoy)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_NUBES))
  .map(enmascararNubes)
  .map(conNdvi);

print('Escenas Sentinel-2 usadas (últimos ' + DIAS_VENTANA + ' días):', s2.size());

var ndvi = s2.select('NDVI').median();

// ── 3. NDVI promedio por apiario ─────────────────────────────────────────────
var resultado = ndvi.reduceRegions({
  collection: apiarios, reducer: ee.Reducer.mean(), scale: 10
}).map(function (f) {
  var v = ee.Number(f.get('mean'));
  var etiqueta = ee.Algorithms.If(v.lt(0.35), 'Floración Muy Baja',
                 ee.Algorithms.If(v.lt(0.50), 'Floración Baja',
                 ee.Algorithms.If(v.lt(0.60), 'Floración Media', 'Floración Óptima')));
  return f.set({
    NDVI_Satelite_Copernicus: v.format('%.2f'),
    Floracion: etiqueta,
    Fecha_Calculo: hoy.format('YYYY-MM-dd')
  });
});

print('NDVI por apiario (copie NDVI_Satelite_Copernicus a la hoja):',
      resultado.select(['ID_Apiario', 'Municipio', 'NDVI_Satelite_Copernicus', 'Floracion']));

// ── 4. Mapa ──────────────────────────────────────────────────────────────────
Map.centerObject(apiarios, 9);
Map.addLayer(ndvi.clip(apiarios.geometry().buffer(3000)),
             {min: 0.1, max: 0.8, palette: ['#E06A5A', '#F2994A', '#F2C94C', '#8CC98C', '#2E7D32']},
             'NDVI Copernicus (rojo = sin floración, verde = floración)');
Map.addLayer(apiarios.style({color: '1F3A2B', fillColor: '00000000', width: 2}), {}, 'Apiarios (1 km)');

// ── 5. Serie mensual del apiario piloto ──────────────────────────────────────
var piloto = apiarios.filter(ee.Filter.eq('ID_Apiario', 'API-03')).geometry();
var meses = ee.List.sequence(0, hoy.difference(ee.Date('2024-01-01'), 'month').floor());
var serie = ee.FeatureCollection(meses.map(function (m) {
  var ini = ee.Date('2024-01-01').advance(m, 'month');
  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(piloto).filterDate(ini, ini.advance(1, 'month'))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(enmascararNubes).map(conNdvi).select('NDVI');
  var valor = ee.Algorithms.If(col.size().gt(0),
    col.median().reduceRegion(ee.Reducer.mean(), piloto, 10).get('NDVI'), null);
  return ee.Feature(null, {mes: ini.millis(), NDVI: valor});
})).filter(ee.Filter.notNull(['NDVI']));

print(ui.Chart.feature.byFeature(serie, 'mes', 'NDVI').setOptions({
  title: 'NDVI mensual — Apiario piloto San Juan de Rioseco (Copernicus Sentinel-2)',
  hAxis: {title: 'Mes', format: 'MMM yyyy'}, vAxis: {title: 'NDVI', viewWindow: {min: 0, max: 1}},
  lineWidth: 2, pointSize: 3, colors: ['#2E7D32'], legend: {position: 'none'}
}));

// ── 6. Exportar a Google Drive (pestaña Tasks → RUN) ─────────────────────────
Export.table.toDrive({
  collection: resultado,
  description: 'NDVI_Apiarios_AbejaVerde',
  folder: 'AbejaVerde_EO',
  fileFormat: 'CSV',
  selectors: ['ID_Apiario', 'Municipio', 'Coordenadas_GPS', 'NDVI_Satelite_Copernicus', 'Floracion', 'Fecha_Calculo']
});
