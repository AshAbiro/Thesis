/**
 * Dhaka 6-class LULC extraction pipeline for urban heat/LST ML modeling.
 *
 * Data sources:
 * - ESRI Annual LULC 10m TS: projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS
 * - ESA WorldCover v200: ESA/WorldCover/v200
 * - JRC Global Surface Water v1.4: JRC/GSW1_4/GlobalSurfaceWater
 * - Sentinel-2 SR Harmonized: COPERNICUS/S2_SR_HARMONIZED
 *
 * Final classes:
 * 1 Built-up, 2 Vegetation, 3 Cropland, 4 Water, 5 Wetlands, 6 Bare Land
 */

var cfg = {
  // Use your own thesis AOI boundary asset for best reproducibility.
  aoiAssetPath: 'users/your_username/dhaka_boundary',

  // Optional fallback when AOI asset is not set: Dhaka district from FAO GAUL L2.
  useGaulFallback: true,

  years: [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],

  outputCrs: 'EPSG:32646',   // UTM zone 46N (Dhaka)
  gridScale: 1000,           // 1 km ML grid
  pixelScale: 10,            // source harmonization scale

  mixedThreshold: 0.50,      // mixed_flag=1 when dominant fraction < threshold
  exportFolder: 'Dhaka_LULC6',
  exportPrefix: 'dhaka_lulc6',

  // Conservative wetland/water refinement toggles.
  refineWaterWetland: true,
  persistentWaterSeasonalityMinMonths: 10,
  persistentWaterOccurrenceMinPct: 90,
  wetlandSeasonalityMinMonths: 2,
  wetlandSeasonalityMaxMonths: 9,
  wetlandNDVIMin: 0.35,
  wetlandMNDWIMin: 0.05
};

var CLASS_INFO = {
  built: 1,
  vegetation: 2,
  cropland: 3,
  water: 4,
  wetland: 5,
  bare: 6
};

var BAND_NAMES = [
  'frac_built', 'frac_vegetation', 'frac_cropland',
  'frac_water', 'frac_wetland', 'frac_bare'
];

function getDhakaAoi() {
  if (cfg.aoiAssetPath && cfg.aoiAssetPath !== 'users/your_username/dhaka_boundary') {
    return ee.FeatureCollection(cfg.aoiAssetPath).geometry();
  }

  if (cfg.useGaulFallback) {
    var gaul2 = ee.FeatureCollection('FAO/GAUL/2015/level2');
    var dhaka = gaul2
      .filter(ee.Filter.eq('ADM0_NAME', 'Bangladesh'))
      .filter(ee.Filter.eq('ADM1_NAME', 'Dhaka'))
      .filter(ee.Filter.eq('ADM2_NAME', 'Dhaka'));
    return dhaka.geometry();
  }

  throw 'No AOI defined. Set cfg.aoiAssetPath to a boundary asset.';
}

function maskS2(image) {
  var qa60 = image.select('QA60');
  var cloud = qa60.bitwiseAnd(1 << 10).eq(0);
  var cirrus = qa60.bitwiseAnd(1 << 11).eq(0);
  var scl = image.select('SCL');
  var sclMask = scl.neq(3)  // cloud shadow
    .and(scl.neq(8))        // medium cloud
    .and(scl.neq(9))        // high cloud
    .and(scl.neq(10))       // cirrus
    .and(scl.neq(11));      // snow/ice

  return image
    .updateMask(cloud)
    .updateMask(cirrus)
    .updateMask(sclMask)
    .select(['B2', 'B3', 'B4', 'B8', 'B11'], ['blue', 'green', 'red', 'nir', 'swir1'])
    .multiply(0.0001)
    .copyProperties(image, ['system:time_start']);
}

function yearlySentinelIndices(year, aoi) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');

  var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(start, end)
    .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2);

  var composite = s2.median().clip(aoi);

  var ndvi = composite.normalizedDifference(['nir', 'red']).rename('ndvi');
  var mndwi = composite.normalizedDifference(['green', 'swir1']).rename('mndwi');

  return ee.Image.cat([ndvi, mndwi]).float();
}

function getEsriYearImage(year, aoi) {
  var start = ee.Date.fromYMD(year, 1, 1);
  var end = start.advance(1, 'year');

  var esriCol = ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS')
    .filterBounds(aoi)
    .filterDate(start, end);

  var hasData = esriCol.size().gt(0);

  var img = ee.Image(ee.Algorithms.If(
    hasData,
    esriCol.mosaic().select(0).rename('esri_raw'),
    ee.Image(0).rename('esri_raw').updateMask(ee.Image(0))
  ));

  return img;
}

function remapEsriToLulc6(esriRaw) {
  // ESRI classes used:
  // 1 Water, 2 Trees, 4 Flooded vegetation, 5 Crops, 7 Built Area, 8 Bare Ground, 11 Rangeland
  var from = [1, 2, 4, 5, 7, 8, 11];
  var to = [4, 2, 5, 3, 1, 6, 2];

  return esriRaw
    .remap(from, to, 0)
    .rename('lulc6')
    .toInt8();
}

function remapEsaToLulc6(esaRaw) {
  // ESA WorldCover v200 classes used:
  // 10 Tree, 20 Shrubland, 30 Grassland, 40 Cropland, 50 Built-up,
  // 60 Bare/sparse vegetation, 80 Water, 90 Herbaceous wetland, 95 Mangroves
  var from = [10, 20, 30, 40, 50, 60, 80, 90, 95];
  var to =   [ 2,  2,  2,  3,  1,  6,  4,  5,  5];

  return esaRaw
    .remap(from, to, 0)
    .rename('esa_lulc6')
    .toInt8();
}

function refineWaterWetland(lulc6, indices, jrc) {
  var seasonality = jrc.select('seasonality');
  var occurrence = jrc.select('occurrence');

  var persistentWater = seasonality.gte(cfg.persistentWaterSeasonalityMinMonths)
    .or(occurrence.gte(cfg.persistentWaterOccurrenceMinPct));

  var seasonalWater = seasonality.gte(cfg.wetlandSeasonalityMinMonths)
    .and(seasonality.lte(cfg.wetlandSeasonalityMaxMonths));

  var ndvi = indices.select('ndvi');
  var mndwi = indices.select('mndwi');

  var isWetland = lulc6.eq(CLASS_INFO.wetland);
  var isWater = lulc6.eq(CLASS_INFO.water);

  var wetlandToWater = isWetland.and(persistentWater).and(mndwi.gte(0));

  var waterToWetland = isWater
    .and(seasonalWater)
    .and(ndvi.gte(cfg.wetlandNDVIMin))
    .and(mndwi.gte(cfg.wetlandMNDWIMin));

  var refined = lulc6
    .where(wetlandToWater, CLASS_INFO.water)
    .where(waterToWetland, CLASS_INFO.wetland)
    .rename('lulc6');

  return refined;
}

function to1kmFraction(binaryImage) {
  return binaryImage
    .reduceResolution({
      reducer: ee.Reducer.mean(),
      maxPixels: 65535
    })
    .reproject({
      crs: cfg.outputCrs,
      scale: cfg.gridScale
    });
}

function buildFractionStack(lulc6) {
  var built = to1kmFraction(lulc6.eq(CLASS_INFO.built)).rename('frac_built');
  var vegetation = to1kmFraction(lulc6.eq(CLASS_INFO.vegetation)).rename('frac_vegetation');
  var cropland = to1kmFraction(lulc6.eq(CLASS_INFO.cropland)).rename('frac_cropland');
  var water = to1kmFraction(lulc6.eq(CLASS_INFO.water)).rename('frac_water');
  var wetland = to1kmFraction(lulc6.eq(CLASS_INFO.wetland)).rename('frac_wetland');
  var bare = to1kmFraction(lulc6.eq(CLASS_INFO.bare)).rename('frac_bare');

  var validObsRatio = to1kmFraction(lulc6.gt(0)).rename('valid_obs_ratio');

  var fracStack = ee.Image.cat([built, vegetation, cropland, water, wetland, bare]).float();

  // Normalization step to enforce sum(frac_*)=1 over valid area.
  var fracSum = fracStack.reduce(ee.Reducer.sum());
  var normalized = fracStack.divide(fracSum.max(1e-6)).rename(BAND_NAMES);

  var dominantClass = normalized
    .toArray()
    .arrayArgmax()
    .arrayGet([0])
    .add(1)
    .rename('dominant_class')
    .toInt8();

  var mixedFlag = normalized
    .reduce(ee.Reducer.max())
    .lt(cfg.mixedThreshold)
    .rename('mixed_flag')
    .toInt8();

  return normalized
    .addBands([dominantClass, mixedFlag, validObsRatio]);
}

function buildFeatureTable(featureImage, aoi, year) {
  var withLonLat = featureImage
    .addBands(ee.Image.pixelLonLat())
    .clip(aoi);

  var sampled = withLonLat.sample({
    region: aoi,
    projection: ee.Projection(cfg.outputCrs).atScale(cfg.gridScale),
    scale: cfg.gridScale,
    geometries: true,
    tileScale: 4
  });

  var withIds = sampled.map(function(f) {
    var lon = ee.Number(f.get('longitude')).format('%.5f');
    var lat = ee.Number(f.get('latitude')).format('%.5f');
    var gridId = ee.String('Y').cat(ee.Number(year).format())
      .cat('_LAT').cat(lat)
      .cat('_LON').cat(lon);

    return f.set({
      'year': year,
      'grid_id': gridId
    });
  });

  return withIds;
}

function qaAgreement2021(lulc6Year, aoi) {
  var esaRaw = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map');
  var esa6 = remapEsaToLulc6(esaRaw).clip(aoi);

  var agreement = lulc6Year.eq(esa6).rename('agree');
  var stats = agreement.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: aoi,
    scale: cfg.pixelScale,
    maxPixels: 1e13
  });

  return stats;
}

function runYear(year, aoi, jrc) {
  var esriRaw = getEsriYearImage(year, aoi);
  var baseLulc6 = remapEsriToLulc6(esriRaw).clip(aoi).updateMask(esriRaw.neq(0));

  var lulc6 = ee.Image(ee.Algorithms.If(
    cfg.refineWaterWetland,
    refineWaterWetland(baseLulc6, yearlySentinelIndices(year, aoi), jrc),
    baseLulc6
  )).rename('lulc6');

  var featureImage = buildFractionStack(lulc6).clip(aoi);
  var featureTable = buildFeatureTable(featureImage, aoi, year);

  // Export 10 m categorical raster.
  Export.image.toDrive({
    image: lulc6,
    description: cfg.exportPrefix + '_10m_' + year,
    folder: cfg.exportFolder,
    fileNamePrefix: cfg.exportPrefix + '_10m_' + year,
    region: aoi,
    crs: cfg.outputCrs,
    scale: cfg.pixelScale,
    maxPixels: 1e13
  });

  // Export 1 km ML feature raster (fractions + dominant + flags).
  Export.image.toDrive({
    image: featureImage,
    description: cfg.exportPrefix + '_1km_features_' + year,
    folder: cfg.exportFolder,
    fileNamePrefix: cfg.exportPrefix + '_1km_features_' + year,
    region: aoi,
    crs: cfg.outputCrs,
    scale: cfg.gridScale,
    maxPixels: 1e13
  });

  // Export 1 km feature table for ML (CSV).
  Export.table.toDrive({
    collection: featureTable,
    description: cfg.exportPrefix + '_1km_features_table_' + year,
    folder: cfg.exportFolder,
    fileNamePrefix: cfg.exportPrefix + '_1km_features_table_' + year,
    fileFormat: 'CSV'
  });

  print('Prepared exports for year:', year);

  return {
    lulc6: lulc6,
    featureImage: featureImage
  };
}

// ------------------ Main ------------------
var aoi = getDhakaAoi();
Map.centerObject(aoi, 10);
Map.addLayer(aoi, {color: 'red'}, 'Dhaka AOI', false);

var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').clip(aoi);

var firstYearResult = null;
for (var i = 0; i < cfg.years.length; i++) {
  var year = cfg.years[i];
  var result = runYear(year, aoi, jrc);
  if (i === 0) {
    firstYearResult = result;
  }

  if (year === 2021) {
    var agreementStats = qaAgreement2021(result.lulc6, aoi);
    print('Pixel-level agreement with ESA WorldCover (2021):', agreementStats);
  }
}

if (firstYearResult) {
  var palette = [
    'd73027', // 1 built
    '1a9850', // 2 vegetation
    '66bd63', // 3 cropland
    '4575b4', // 4 water
    '74add1', // 5 wetlands
    'd9bf77'  // 6 bare
  ];

  Map.addLayer(
    firstYearResult.lulc6,
    {min: 1, max: 6, palette: palette},
    'LULC6 10m (first year)'
  );

  Map.addLayer(
    firstYearResult.featureImage.select(['frac_built', 'frac_vegetation', 'frac_water']),
    {min: 0, max: 1},
    '1km Fractions RGB (built, veg, water)',
    false
  );
}

print('Pipeline initialized. Start the queued Export tasks from the Tasks tab.');
