# ============================================================
# Dhaka Urban Heat Data Workflow (FULL - single cell)
# - Landsat C2 L2 (L5/7/8/9) LST backbone
# - MODIS 8-day LST for temporal continuity (optional gap-filling)
# - Correct cross-sensor band harmonization
# - QA cloud/shadow masking
# - Seasonal composites (Dhaka seasons)
# - Spectral indices (NDVI, NDWI, MNDWI, NDMI, NDBI)
# - Terrain (SRTM) + optional morphology (buildings/roads/waterways)
# - Distance to water (from MNDWI)
# - Fixed grid (e.g., 1 km) and fast aggregation via reduceRegions
# - SUHI intensity = grid LST - reference-zone mean LST (same time-step)
# - Validation outputs: range/coverage + mechanism correlations (direction checks)
# - Exports: optional image + table exports to Google Drive
#
# REQUIREMENTS:
#   pip install earthengine-api pandas
#   earthengine authenticate
#   ee.Initialize() works
# ============================================================

import argparse
import ee
import pandas as pd

def initialize_earth_engine(project: str | None = None) -> None:
    """Initialize Earth Engine once per run to avoid import-time side effects."""
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except Exception as e:
        raise RuntimeError(
            "Earth Engine not initialized. Run ee.Authenticate(); ee.Initialize(project='...')"
        ) from e


# ============================================================
# A) AOI + zones (Dhaka)
# ============================================================

def get_dhaka_boundary() -> ee.FeatureCollection:
    """
    Demonstration boundary source (FAO GAUL level2).
    You may replace this with your own Dhaka metro boundary (recommended).
    """
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    bd = gaul.filter(ee.Filter.eq('ADM0_CODE', 23))  # Bangladesh code in GAUL
    # Try both ADM2_NAME and ADM2_EN
    dhaka = bd.filter(
        ee.Filter.Or(
            ee.Filter.stringContains('ADM2_NAME', 'Dhaka'),
            ee.Filter.stringContains('ADM2_EN', 'Dhaka')
        )
    )
    return dhaka

def create_zones(aoi: ee.FeatureCollection, urban_buffer_km: float = 0.0, periurban_buffer_km: float = 10.0):
    """
    urban_core: AOI (optionally eroded)
    reference_zone: AOI buffer outward minus AOI
    """
    urban_m = urban_buffer_km * 1000.0
    peri_m = periurban_buffer_km * 1000.0

    if urban_m > 0:
        urban_core = aoi.map(lambda f: f.buffer(-urban_m))
    else:
        urban_core = aoi

    peri = aoi.map(lambda f: f.buffer(peri_m))
    ref_zone = peri.map(lambda f: f.difference(aoi.geometry(), 1))

    return {"urban_core": urban_core, "reference_zone": ref_zone}


# ============================================================
# B) Landsat C2 L2 retrieval + harmonization + scaling + masking
# ============================================================

LANDSAT_C2_L2 = [
    'LANDSAT/LT05/C02/T1_L2',
    'LANDSAT/LE07/C02/T1_L2',
    'LANDSAT/LC08/C02/T1_L2',
    'LANDSAT/LC09/C02/T1_L2'
]

MODIS_LST_8DAY = [
    'MODIS/006/MOD11A2',
    'MODIS/006/MYD11A2'
]

def get_landsat_raw(start_date: str, end_date: str, aoi: ee.FeatureCollection, max_cloud_cover: float = 70.0):
    def load(col_id):
        col = (ee.ImageCollection(col_id)
               .filterBounds(aoi.geometry())
               .filterDate(start_date, end_date)
               .filter(ee.Filter.lte('CLOUD_COVER', max_cloud_cover)))
        return col
    merged = load(LANDSAT_C2_L2[0])
    for cid in LANDSAT_C2_L2[1:]:
        merged = merged.merge(load(cid))
    return merged

def harmonize_landsat_sr_bands(img: ee.Image) -> ee.Image:
    """
    Rename mission-specific SR + ST band names to a common schema:
      Blue, Green, Red, NIR, SWIR1, SWIR2, ST, QA_PIXEL
    L8/9:  Green=SR_B3, Red=SR_B4, NIR=SR_B5, SWIR1=SR_B6, SWIR2=SR_B7, ST=ST_B10
    L5/7:  Green=SR_B2, Red=SR_B3, NIR=SR_B4, SWIR1=SR_B5, SWIR2=SR_B7, ST=ST_B6
    """
    sc = ee.String(img.get('SPACECRAFT_ID'))

    def rename_l89():
        return img.select(
            ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7','ST_B10','QA_PIXEL'],
            ['Blue','Green','Red','NIR','SWIR1','SWIR2','ST','QA_PIXEL']
        )

    def rename_l57():
        return img.select(
            ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7','ST_B6','QA_PIXEL'],
            ['Blue','Green','Red','NIR','SWIR1','SWIR2','ST','QA_PIXEL']
        )

    is_l89 = ee.List(['LANDSAT_8', 'LANDSAT_9']).contains(sc)
    return ee.Image(ee.Algorithms.If(
        is_l89,
        rename_l89(),
        rename_l57()
    )).copyProperties(img, img.propertyNames())

def mask_landsat_qa(img: ee.Image) -> ee.Image:
    """
    Mask clouds, shadows, cirrus, snow, fill based on QA_PIXEL bits:
      bit 0 fill
      bit 1 dilated cloud
      bit 2 cirrus
      bit 3 cloud
      bit 4 cloud shadow
      bit 5 snow
    """
    qa = img.select('QA_PIXEL')
    bad = (qa.bitwiseAnd(1 << 0).neq(0)
           .Or(qa.bitwiseAnd(1 << 1).neq(0))
           .Or(qa.bitwiseAnd(1 << 2).neq(0))
           .Or(qa.bitwiseAnd(1 << 3).neq(0))
           .Or(qa.bitwiseAnd(1 << 4).neq(0))
           .Or(qa.bitwiseAnd(1 << 5).neq(0)))
    return img.updateMask(bad.Not())

def apply_l2_scaling(img: ee.Image) -> ee.Image:
    """
    Landsat C2 L2 scaling:
    - SR:  scale=0.0000275, offset=-0.2
    - ST:  scale=0.00341802, offset=149.0  (Kelvin), then convert to Celsius
    """
    sr = img.select(['Blue','Green','Red','NIR','SWIR1','SWIR2']).multiply(0.0000275).add(-0.2)
    lst_k = img.select('ST').multiply(0.00341802).add(149.0)
    lst_c = lst_k.subtract(273.15).rename('LST_C')
    out = (img.addBands(sr, overwrite=True)
              .addBands(lst_c, overwrite=True))
    return out

def get_prepared_landsat(start_date: str, end_date: str, aoi: ee.FeatureCollection, max_cloud_cover: float = 70.0):
    raw = get_landsat_raw(start_date, end_date, aoi, max_cloud_cover=max_cloud_cover)
    prepared = (raw
        .map(harmonize_landsat_sr_bands)
        .map(mask_landsat_qa)
        .map(apply_l2_scaling)
    )
    return prepared


def get_modis_raw(start_date: str, end_date: str, aoi: ee.FeatureCollection):
    def load(col_id):
        return (ee.ImageCollection(col_id)
                .filterBounds(aoi.geometry())
                .filterDate(start_date, end_date))
    merged = load(MODIS_LST_8DAY[0])
    for cid in MODIS_LST_8DAY[1:]:
        merged = merged.merge(load(cid))
    return merged


def mask_modis_qa(img: ee.Image) -> ee.Image:
    qc = img.select('QC_Day')
    good = qc.lte(1)
    return img.updateMask(good)


def scale_modis_lst(img: ee.Image) -> ee.Image:
    lst_k = img.select('LST_Day_1km').multiply(0.02)
    lst_c = lst_k.subtract(273.15).rename('LST_C')
    return img.addBands(lst_c, overwrite=True)


def get_prepared_modis(start_date: str, end_date: str, aoi: ee.FeatureCollection):
    raw = get_modis_raw(start_date, end_date, aoi)
    prepared = (raw
        .map(mask_modis_qa)
        .map(scale_modis_lst)
    )
    return prepared


# ============================================================
# C) Seasons (Dhaka) + seasonal compositing
# ============================================================

def define_seasons():
    # Dhaka-appropriate seasonal bins
    return {
        "pre_monsoon": (3, 4),     # Mar-Apr
        "monsoon": (5, 9),         # May-Sep
        "post_monsoon": (10, 11),  # Oct-Nov
        "winter": (12, 2)          # Dec-Feb (wraps year)
    }

def seasonal_composite(prepared: ee.ImageCollection, year: int, season: str, aoi: ee.FeatureCollection, reducer_name: str = "median") -> ee.Image:
    """
    Returns an image with:
      LST_C, Blue, Green, Red, NIR, SWIR1, SWIR2, valid_obs
    Note: valid_obs counts LST_C observations in the season.
    """
    seasons = define_seasons()
    sm, em = seasons[season]

    if sm <= em:
        start = ee.Date.fromYMD(year, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')
    else:
        start = ee.Date.fromYMD(year - 1, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')

    subset = prepared.filterDate(start, end)

    valid_obs = subset.select('LST_C').count().rename('valid_obs')

    if reducer_name == "median":
        comp = subset.median()
    elif reducer_name == "mean":
        comp = subset.mean()
    else:
        raise ValueError("reducer_name must be 'median' or 'mean'")

    out = (comp.select(['LST_C','Blue','Green','Red','NIR','SWIR1','SWIR2'])
              .addBands(valid_obs)
              .set({'year': year, 'season': season})
              .clip(aoi))
    return out


def seasonal_composite_modis(prepared: ee.ImageCollection, year: int, season: str, aoi: ee.FeatureCollection, reducer_name: str = "median") -> ee.Image:
    seasons = define_seasons()
    sm, em = seasons[season]

    if sm <= em:
        start = ee.Date.fromYMD(year, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')
    else:
        start = ee.Date.fromYMD(year - 1, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')

    subset = prepared.filterDate(start, end)

    if reducer_name == "median":
        comp = subset.median()
    elif reducer_name == "mean":
        comp = subset.mean()
    else:
        raise ValueError("reducer_name must be 'median' or 'mean'")

    out = (comp.select(['LST_C'])
              .set({'year': year, 'season': season})
              .clip(aoi))
    return out


# ============================================================
# D) Predictors (indices, terrain, water distance, built density)
# ============================================================

def sanitize_reflectance(img: ee.Image) -> ee.Image:
    """
    Clamp reflectance to a physically plausible range to avoid index blow-ups.
    """
    sr = img.select(['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']).clamp(0, 1)
    return img.addBands(sr, overwrite=True)


def add_spectral_indices_safe(img: ee.Image, eps: float = 1e-6) -> ee.Image:
    nir = img.select('NIR')
    red = img.select('Red')
    green = img.select('Green')
    sw1 = img.select('SWIR1')

    d_ndvi = nir.add(red)
    d_ndwi = green.add(nir)
    d_mndwi = green.add(sw1)
    d_ndmi = nir.add(sw1)
    d_ndbi = sw1.add(nir)

    good = (d_ndvi.abs().gt(eps)
            .And(d_ndwi.abs().gt(eps))
            .And(d_mndwi.abs().gt(eps))
            .And(d_ndmi.abs().gt(eps))
            .And(d_ndbi.abs().gt(eps)))

    img = img.updateMask(good)

    ndvi = nir.subtract(red).divide(d_ndvi).rename('NDVI')
    ndwi = green.subtract(nir).divide(d_ndwi).rename('NDWI')
    mndwi = green.subtract(sw1).divide(d_mndwi).rename('MNDWI')
    ndmi = nir.subtract(sw1).divide(d_ndmi).rename('NDMI')
    ndbi = sw1.subtract(nir).divide(d_ndbi).rename('NDBI')

    return img.addBands([ndvi, ndwi, mndwi, ndmi, ndbi])

def add_terrain(img: ee.Image, aoi: ee.FeatureCollection) -> ee.Image:
    dem = ee.Image('USGS/SRTMGL1_003').clip(aoi)
    terr = ee.Algorithms.Terrain(dem)
    elev = dem.rename('elevation')
    slope = terr.select('slope')
    aspect = terr.select('aspect')
    return img.addBands([elev, slope, aspect])

def add_built_up_density(img: ee.Image, threshold: float = 0.1, radius_px: int = 5) -> ee.Image:
    built = img.select('NDBI').gt(threshold).rename('built_mask')
    kernel = ee.Kernel.circle(radius_px)
    density = built.reduceNeighborhood(ee.Reducer.mean(), kernel).rename('built_density')
    return img.addBands(density)

def add_building_density_from_fc(img: ee.Image, buildings_fc: ee.FeatureCollection, radius_px: int = 5) -> ee.Image:
    """
    Add building coverage/density from a footprint feature collection.
    """
    building_mask = ee.Image().byte().paint(buildings_fc, 1).selfMask()
    kernel = ee.Kernel.circle(radius_px)
    density = building_mask.reduceNeighborhood(ee.Reducer.mean(), kernel).rename('building_density')
    return img.addBands(density)

def add_distance_to_features(img: ee.Image, fc: ee.FeatureCollection, band_name: str) -> ee.Image:
    """
    Compute distance to vector features (e.g., roads, waterways).
    """
    mask = ee.Image().byte().paint(fc, 1).selfMask()
    proj = img.select('LST_C').projection()
    dist_px = mask.Not().fastDistanceTransform(256, 'pixels').sqrt()
    dist_m = dist_px.multiply(proj.nominalScale()).rename(band_name)
    return img.addBands(dist_m)

def add_distance_to_water(img: ee.Image) -> ee.Image:
    """
    Derive water mask from MNDWI > 0, then compute distance to water (meters).
    """
    water = img.select('MNDWI').gt(0).selfMask()
    proj = img.select('LST_C').projection()
    # fastDistanceTransform distance in pixels -> convert to meters by nominal scale
    dist_px = water.Not().fastDistanceTransform(256, 'pixels').sqrt()
    dist_m = dist_px.multiply(proj.nominalScale()).rename('dist_water')
    return img.addBands(dist_m)

def reproject_to_target(img: ee.Image, crs: str, scale: int) -> ee.Image:
    return img.reproject(crs=crs, scale=scale)

def get_sentinel1_seasonal(year: int, season: str, aoi: ee.FeatureCollection) -> ee.Image:
    seasons = define_seasons()
    sm, em = seasons[season]
    if sm <= em:
        start = ee.Date.fromYMD(year, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')
    else:
        start = ee.Date.fromYMD(year - 1, sm, 1)
        end = ee.Date.fromYMD(year, em, 1).advance(1, 'month')

    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
          .filterBounds(aoi.geometry())
          .filterDate(start, end)
          .filter(ee.Filter.eq('instrumentMode', 'IW'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
          .select(['VV', 'VH']))
    return s1.median().rename(['VV', 'VH']).clip(aoi)

def enrich_composite(comp: ee.Image,
                     aoi: ee.FeatureCollection,
                     buildings_fc: ee.FeatureCollection | None = None,
                     roads_fc: ee.FeatureCollection | None = None,
                     waterways_fc: ee.FeatureCollection | None = None) -> ee.Image:
    comp = sanitize_reflectance(comp)
    comp = add_spectral_indices_safe(comp)
    comp = add_terrain(comp, aoi)
    comp = add_built_up_density(comp, threshold=0.1, radius_px=5)
    if buildings_fc is not None:
        comp = add_building_density_from_fc(comp, buildings_fc, radius_px=5)
    if roads_fc is not None:
        comp = add_distance_to_features(comp, roads_fc, 'dist_roads')
    if waterways_fc is not None:
        comp = add_distance_to_features(comp, waterways_fc, 'dist_waterways')
    comp = add_distance_to_water(comp)
    return comp


# ============================================================
# E) Analysis grid (fixed) + fast aggregation
# ============================================================

def generate_grid(aoi: ee.FeatureCollection, cell_size_m: int = 1000) -> ee.FeatureCollection:
    """
    Square grid using EPSG:3857 at cell_size_m. Output has grid_id.
    """
    proj = ee.Projection('EPSG:3857').atScale(cell_size_m)
    coords = ee.Image.pixelCoordinates(proj)
    x = coords.select('x').divide(cell_size_m).floor().toInt()
    y = coords.select('y').divide(cell_size_m).floor().toInt()
    grid_id = x.multiply(1000000).add(y).rename('grid_id')
    grid_img = grid_id.addBands(x.rename('grid_x'))

    vectors = grid_img.reduceToVectors(
        geometry=aoi.geometry(),
        scale=cell_size_m,
        geometryType='polygon',
        labelProperty='grid_id',
        reducer=ee.Reducer.first(),
        maxPixels=1e13
    )
    return vectors

def aggregate_to_grid(img: ee.Image, grid: ee.FeatureCollection, scale: int = 30) -> ee.FeatureCollection:
    """
    Fast aggregation: one reduceRegions call
    """
    year = img.get('year')
    season = img.get('season')

    fc = img.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean(),
        scale=scale
    )
    return fc.map(lambda f: f.set({'year': year, 'season': season}))

def compute_reference_lst(img: ee.Image, reference_zone: ee.FeatureCollection, scale: int = 30) -> ee.Number:
    """
    Reference mean LST inside reference zone (same timestep).
    """
    ref = img.select('LST_C').reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=reference_zone.geometry(),
        scale=scale,
        maxPixels=1e13,
        bestEffort=True
    )
    return ee.Number(ref.get('LST_C'))

def add_suhi_to_grid(grid_fc: ee.FeatureCollection, ref_lst: ee.Number) -> ee.FeatureCollection:
    """
    SUHI = grid mean LST - reference mean LST
    """
    return grid_fc.map(lambda f: f.set({
        'reference_lst': ref_lst,
        'SUHI': ee.Number(f.get('LST_C')).subtract(ref_lst)
    }))


# ============================================================
# F) Validation tests (B) "How to test these"
# ============================================================

def raster_range_and_coverage_tests(img: ee.Image, aoi: ee.FeatureCollection) -> ee.Dictionary:
    """
    1) Sensor/processing correctness tests:
       - value range sanity for LST + indices
       - valid fraction within AOI
       - valid_obs mean
    """
    lst_stats = img.select('LST_C').reduceRegion(
        reducer=ee.Reducer.minMax().combine(ee.Reducer.mean(), sharedInputs=True),
        geometry=aoi.geometry(),
        scale=30,
        maxPixels=1e13,
        bestEffort=True
    )

    idx_stats = img.select(['NDVI','NDBI','NDWI','MNDWI','NDMI']).reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi.geometry(),
        scale=30,
        maxPixels=1e13,
        bestEffort=True
    )

    # valid fraction = mean(mask)
    valid_frac = img.select('LST_C').mask().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi.geometry(),
        scale=30,
        maxPixels=1e13,
        bestEffort=True
    )

    valid_obs_mean = img.select('valid_obs').reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi.geometry(),
        scale=30,
        maxPixels=1e13,
        bestEffort=True
    )

    return ee.Dictionary({
        'lst_stats': lst_stats,
        'index_minmax': idx_stats,
        'valid_fraction': valid_frac,
        'valid_obs_mean': valid_obs_mean
    })

def mechanism_consistency_tests(grid_fc: ee.FeatureCollection) -> ee.Dictionary:
    """
    4) Mechanism consistency tests:
       - corr direction checks at grid level (Pearson r)
    """
    def corr(x, y):
        d = ee.Dictionary(grid_fc.reduceColumns(
            ee.Reducer.pearsonsCorrelation(),
            selectors=[x, y]
        ))
        p_value = ee.Algorithms.If(
            d.contains('pValue'),
            d.get('pValue'),
            None
        )
        return ee.Dictionary({
            'correlation': d.get('correlation'),
            'p_value': p_value
        })

    return ee.Dictionary({
        'r_NDVI_LST': corr('NDVI', 'LST_C'),
        'r_NDBI_LST': corr('NDBI', 'LST_C'),
        'r_NDWI_LST': corr('NDWI', 'LST_C'),
        'r_MNDWI_LST': corr('MNDWI', 'LST_C'),
        'r_builtDensity_LST': corr('built_density', 'LST_C'),
        'r_distWater_LST': corr('dist_water', 'LST_C')
    })


# ============================================================
# G) Export helpers (optional)
# ============================================================

def export_table_to_drive(fc: ee.FeatureCollection, description: str, folder: str):
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=description,
        folder=folder,
        fileFormat='CSV'
    )
    task.start()
    return task

def export_image_to_drive(img: ee.Image, aoi: ee.FeatureCollection, description: str, folder: str, scale: int = 30):
    task = ee.batch.Export.image.toDrive(
        image=img,
        description=description,
        folder=folder,
        region=aoi.geometry(),
        scale=scale,
        maxPixels=1e13
    )
    task.start()
    return task


# ============================================================
# H) Main runner (single call)
# ============================================================

def run_workflow(
    start_year: int = 2015,
    end_year: int = 2025,
    cell_size_m: int = 1000,
    max_cloud_cover: float = 70.0,
    reducer_name: str = "median",
    min_valid_fraction: float = 0.60,   # drop composites with too much missingness
    min_valid_obs_mean: float = 4.0,    # minimum mean valid observations
    export_folder: str = None,          # if set, exports artifacts to this Drive folder
    export_images: bool = False,        # export key rasters too (can be heavy)
    project: str | None = None,
    qa_mode: str = "basic",             # "basic", "full", or "none"
    seasons: list[str] | None = None,
    use_modis: bool = True,
    use_radar: bool = False,
    target_crs: str = "EPSG:32646",
    buildings_fc_id: str | None = None,
    roads_fc_id: str | None = None,
    waterways_fc_id: str | None = None
):
    initialize_earth_engine(project)
    aoi = get_dhaka_boundary()
    zones = create_zones(aoi, urban_buffer_km=0.0, periurban_buffer_km=10.0)

    grid = generate_grid(aoi, cell_size_m=cell_size_m)

    prepared = get_prepared_landsat(f"{start_year}-01-01", f"{end_year}-12-31", aoi, max_cloud_cover=max_cloud_cover)
    prepared_modis = None
    if use_modis:
        prepared_modis = get_prepared_modis(f"{start_year}-01-01", f"{end_year}-12-31", aoi)

    buildings_fc = ee.FeatureCollection(buildings_fc_id) if buildings_fc_id else None
    roads_fc = ee.FeatureCollection(roads_fc_id) if roads_fc_id else None
    waterways_fc = ee.FeatureCollection(waterways_fc_id) if waterways_fc_id else None

    all_seasons = list(define_seasons().keys())
    if seasons is None:
        seasons = all_seasons
    else:
        invalid = [s for s in seasons if s not in all_seasons]
        if invalid:
            raise ValueError(f"Invalid season(s): {', '.join(invalid)}")

    all_tables = []
    qa_features = []
    empty_fc = ee.FeatureCollection([])

    for year in range(start_year, end_year + 1):
        for season in seasons:
            comp = seasonal_composite(prepared, year, season, aoi, reducer_name=reducer_name)
            if use_modis and prepared_modis is not None:
                modis_comp = seasonal_composite_modis(prepared_modis, year, season, aoi, reducer_name=reducer_name)
                modis_lst = reproject_to_target(modis_comp.select('LST_C'), target_crs, cell_size_m)
                comp = comp.addBands(comp.select('LST_C').unmask(modis_lst).rename('LST_C'), overwrite=True)

            if use_radar:
                radar = get_sentinel1_seasonal(year, season, aoi)
                radar = reproject_to_target(radar, target_crs, cell_size_m)
                comp = comp.addBands(radar)

            comp = reproject_to_target(comp, target_crs, cell_size_m)
            comp = enrich_composite(comp, aoi, buildings_fc, roads_fc, waterways_fc)

            # ----- coverage filter (percent valid LST within AOI)
            valid_frac_dict = comp.select('LST_C').mask().reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi.geometry(),
                scale=30,
                maxPixels=1e13,
                bestEffort=True
            )
            valid_frac = ee.Number(valid_frac_dict.get('LST_C'))
            valid_obs_mean_dict = comp.select('valid_obs').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi.geometry(),
                scale=30,
                maxPixels=1e13,
                bestEffort=True
            )
            valid_obs_mean = ee.Number(valid_obs_mean_dict.get('valid_obs'))

            # Only keep if valid fraction >= threshold
            keep = valid_frac.gte(min_valid_fraction).And(valid_obs_mean.gte(min_valid_obs_mean))

            grid_fc = aggregate_to_grid(comp, grid, scale=30)
            ref_lst = compute_reference_lst(comp, zones['reference_zone'], scale=30)
            grid_fc = add_suhi_to_grid(grid_fc, ref_lst)
            grid_fc = grid_fc.map(lambda f: f.set({'sensor_group': 'Landsat_C2_L2'}))

            grid_fc_for_merge = ee.FeatureCollection(ee.Algorithms.If(keep, grid_fc, empty_fc))
            all_tables.append(grid_fc_for_merge)

            if qa_mode != "none":
                qa = ee.Dictionary({
                    'year': year,
                    'season': season,
                    'valid_fraction': valid_frac,
                    'valid_obs_mean': valid_obs_mean,
                    'kept': keep
                })
                if qa_mode == "full":
                    mech = ee.Dictionary(ee.Algorithms.If(keep, mechanism_consistency_tests(grid_fc), ee.Dictionary({})))
                    ras = raster_range_and_coverage_tests(comp, aoi)
                    qa = qa.combine(ee.Dictionary({'mechanism': mech, 'raster': ras}), overwrite=True)
                qa_features.append(ee.Feature(None, qa))

            # If you want to export artifacts, do it here
            if export_folder:
                # Export per timestep grid table (only if kept)
                def do_exports():
                    desc = f"dhaka_grid_{year}_{season}_{reducer_name}_cell{cell_size_m}"
                    export_table_to_drive(grid_fc, desc, export_folder)

                    if export_images:
                        # Export key rasters (LST + indices + valid_obs)
                        img_desc = f"dhaka_rasters_{year}_{season}_{reducer_name}"
                        export_image_to_drive(
                            comp.select(['LST_C','NDVI','NDBI','NDWI','MNDWI','NDMI','built_density','dist_water','valid_obs']),
                            aoi,
                            img_desc,
                            export_folder,
                            scale=30
                        )
                    return True

                ee.Algorithms.If(keep, do_exports(), False).getInfo()

    # Merge all tables (server-side)
    merged_fc = None
    if all_tables:
        merged_fc = all_tables[0]
        for fc in all_tables[1:]:
            merged_fc = merged_fc.merge(fc)

    qa_df = pd.DataFrame()
    if qa_features:
        qa_fc = ee.FeatureCollection(qa_features)
        qa_info = qa_fc.getInfo()
        if qa_info and qa_info.get('features'):
            qa_df = pd.json_normalize([f['properties'] for f in qa_info['features']])

    return merged_fc, qa_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Dhaka SUHI workflow.")
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2020)
    parser.add_argument("--cell-size-m", type=int, default=1000)
    parser.add_argument("--max-cloud-cover", type=float, default=70.0)
    parser.add_argument("--reducer-name", choices=["median", "mean"], default="median")
    parser.add_argument("--min-valid-fraction", type=float, default=0.60)
    parser.add_argument("--min-valid-obs-mean", type=float, default=4.0)
    parser.add_argument("--export-folder", type=str, default=None)
    parser.add_argument("--export-images", action="store_true")
    parser.add_argument("--project", type=str, default=None)
    parser.add_argument("--qa-mode", choices=["basic", "full", "none"], default="basic")
    parser.add_argument("--no-modis", action="store_true", help="Disable MODIS gap-filling.")
    parser.add_argument("--use-radar", action="store_true", help="Add Sentinel-1 VV/VH seasonal medians.")
    parser.add_argument("--target-crs", type=str, default="EPSG:32646")
    parser.add_argument("--buildings-fc-id", type=str, default=None)
    parser.add_argument("--roads-fc-id", type=str, default=None)
    parser.add_argument("--waterways-fc-id", type=str, default=None)
    parser.add_argument("--output-csv", type=str, default=None)
    parser.add_argument("--seasons", type=str, default=None,
                        help="Comma-separated season list (e.g., pre_monsoon,monsoon).")

    args = parser.parse_args()

    seasons = None
    if args.seasons:
        seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]

    merged_fc, qa_df = run_workflow(
        start_year=args.start_year,
        end_year=args.end_year,
        cell_size_m=args.cell_size_m,
        max_cloud_cover=args.max_cloud_cover,
        reducer_name=args.reducer_name,
        min_valid_fraction=args.min_valid_fraction,
        min_valid_obs_mean=args.min_valid_obs_mean,
        export_folder=args.export_folder,
        export_images=args.export_images,
        project=args.project,
        qa_mode=args.qa_mode,
        seasons=seasons,
        use_modis=not args.no_modis,
        use_radar=args.use_radar,
        target_crs=args.target_crs,
        buildings_fc_id=args.buildings_fc_id,
        roads_fc_id=args.roads_fc_id,
        waterways_fc_id=args.waterways_fc_id
    )

    if not qa_df.empty:
        print("QA report (first rows):")
        print(qa_df.head())
    else:
        print("QA report is empty.")

    if args.output_csv:
        qa_df.to_csv(args.output_csv, index=False)
