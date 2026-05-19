"""Configuration constants for the Dhaka urban heat data collection pipeline."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
RAW_OUTPUT_DIR = OUTPUT_DIR / "raw"
PROCESSED_OUTPUT_DIR = OUTPUT_DIR / "processed"
LOG_OUTPUT_DIR = OUTPUT_DIR / "logs"


# Replace with your uploaded Dhaka metropolitan boundary asset if available.
# Example: "users/your_username/dhaka_metro_boundary"
DHAKA_BOUNDARY_ASSET: str | None = None

GAUL_LEVEL2 = "FAO/GAUL/2015/level2"

LANDSAT_COLLECTIONS = (
    "LANDSAT/LT05/C02/T1_L2",
    "LANDSAT/LE07/C02/T1_L2",
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LC09/C02/T1_L2",
)

ESRI_LULC_TS = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
ESA_WORLDCOVER_2021 = "ESA/WorldCover/v200"
JRC_GLOBAL_SURFACE_WATER = "JRC/GSW1_4/GlobalSurfaceWater"
GOOGLE_OPEN_BUILDINGS = "GOOGLE/Research/open-buildings/v3/polygons"


# Dhaka seasonal bins used in the thesis data collection method.
# Winter is assigned to the named year by using Dec of year - 1 through Feb.
SEASONS = {
    "pre_monsoon": (3, 5),
    "monsoon": (6, 9),
    "post_monsoon": (10, 11),
    "winter": (12, 2),
}


LULC6_CLASSES = {
    1: "Built-up",
    2: "Vegetation",
    3: "Cropland",
    4: "Water Bodies",
    5: "Wetlands",
    6: "Bare Land",
}

LULC_PERCENT_FIELDS = (
    "builtup_pct",
    "vegetation_pct",
    "cropland_pct",
    "water_pct",
    "wetland_pct",
    "bare_pct",
)

SPECTRAL_BANDS = ("blue", "green", "red", "nir", "swir1", "swir2")

CONTINUOUS_AGGREGATION_BANDS = (
    "lst_c",
    "suhi",
    "ndvi",
    "ndwi",
    "mndwi",
    "ndmi",
    "ndbi",
    "albedo",
    "distance_to_water_m",
    "valid_obs",
)

DEFAULT_GRID_SIZE_M = 1000
DEFAULT_GRID_CRS = "EPSG:32646"  # UTM zone 46N, suitable for Dhaka.
DEFAULT_LANDSAT_SCALE_M = 30
DEFAULT_LULC_SCALE_M = 10
DEFAULT_BUILDING_SCALE_M = 10
DEFAULT_REFERENCE_BUFFER_KM = 10
DEFAULT_MAX_CLOUD_COVER = 80.0
DEFAULT_OPEN_BUILDINGS_CONFIDENCE = 0.75


YEAR_PROPERTY = "year"
SEASON_PROPERTY = "season"
GRID_ID_PROPERTY = "grid_id"
