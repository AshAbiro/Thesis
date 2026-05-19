# Dhaka Urban Heat Data Collection 1.0

This project implements the data collection and preprocessing method for Dhaka land surface temperature and urban heat modeling. It does not train machine-learning models. It creates grid-level CSV tables that can be used later for modeling.

## Methodology

The pipeline uses satellite-based secondary data in Google Earth Engine:

1. Load Dhaka boundary from FAO GAUL level 2, or from a user-supplied Dhaka metropolitan boundary asset.
2. Create a fixed 1 km or 500 m grid over Dhaka.
3. Build seasonal Landsat Collection 2 Level 2 composites using QA_PIXEL cloud, shadow, snow, cirrus, and fill masking.
4. Convert Landsat surface temperature to LST in Celsius.
5. Add spectral indices: NDVI, NDWI, MNDWI, NDMI, NDBI, and broadband albedo.
6. Create LULC6 classes from ESRI Global LULC 10 m annual time series, refined with JRC Global Surface Water.
7. Calculate morphology features from Google Open Buildings and optional user-supplied roads.
8. Calculate distance to water from MNDWI plus JRC permanent water.
9. Calculate SUHI as grid LST minus mean LST in a 10 km outward reference ring.
10. Aggregate all variables to the fixed grid and export machine-learning-ready CSV tables.

Dhaka seasons:

- `pre_monsoon`: March to May
- `monsoon`: June to September
- `post_monsoon`: October to November
- `winter`: December to February, assigned to the ending year

## Datasets

- Landsat C2 L2: `LANDSAT/LT05/C02/T1_L2`, `LANDSAT/LE07/C02/T1_L2`, `LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2`
- ESRI Global LULC 10 m annual time series: `projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS`
- ESA WorldCover 2021 optional QA reference: `ESA/WorldCover/v200`
- JRC Global Surface Water: `JRC/GSW1_4/GlobalSurfaceWater`
- Google Open Buildings: `GOOGLE/Research/open-buildings/v3/polygons`
- FAO GAUL administrative boundary: `FAO/GAUL/2015/level2`

## Variables

Dependent variables:

- `lst_mean`
- `lst_median`
- `suhi_mean`

Main independent variables:

- `ndvi_mean`
- `ndwi_mean`
- `mndwi_mean`
- `ndmi_mean`
- `ndbi_mean`
- `albedo_mean`
- `builtup_pct`
- `vegetation_pct`
- `cropland_pct`
- `water_pct`
- `wetland_pct`
- `bare_pct`
- `building_area_ratio`
- `building_count`
- `mean_distance_to_water_m`
- `min_distance_to_water_m`
- `road_density_m_per_km2` when a road vector asset is supplied

LULC6 classes:

1. Built-up
2. Vegetation
3. Cropland
4. Water Bodies
5. Wetlands
6. Bare Land

## Authentication

Install dependencies:

```powershell
pip install -r requirements.txt
```

Authenticate Earth Engine once:

```powershell
earthengine authenticate
```

If your Earth Engine account requires a Google Cloud project, pass it when running:

```powershell
python main.py --project thesis-01-496711 --start-year 2017 --end-year 2024 --season pre_monsoon --grid-size 1000 --export-folder Dhaka_Urban_Heat_Data_Thesis_01
```

## Running

From this folder:

```powershell
python main.py --project thesis-01-496711 --start-year 2017 --end-year 2024 --season pre_monsoon --grid-size 1000 --export-folder Dhaka_Urban_Heat_Data_Thesis_01
```

Use a 500 m grid:

```powershell
python main.py --project thesis-01-496711 --start-year 2017 --end-year 2024 --season monsoon --grid-size 500 --export-folder Dhaka_Urban_Heat_Data_Thesis_01
```

Use a custom Dhaka boundary asset:

```powershell
python main.py --project thesis-01-496711 --start-year 2017 --end-year 2024 --season winter --grid-size 1000 --export-folder Dhaka_Urban_Heat_Data_Thesis_01 --boundary-asset users/your_name/dhaka_metro_boundary
```

Use an optional road vector asset:

```powershell
python main.py --project thesis-01-496711 --start-year 2017 --end-year 2024 --season post_monsoon --grid-size 1000 --export-folder Dhaka_Urban_Heat_Data_Thesis_01 --roads-asset users/your_name/dhaka_roads
```

## Expected Outputs

Google Drive CSV exports are started for each year:

- `dhaka_urban_heat_grid_<year>_<season>_<grid_size>m.csv`
- `dhaka_urban_heat_validation_<year>_<season>_<grid_size>m.csv`

One final joined table is also exported:

- `dhaka_urban_heat_grid_<start_year>_<end_year>_<season>_<grid_size>m.csv`
- `dhaka_urban_heat_validation_<start_year>_<end_year>_<season>_<grid_size>m.csv`

Local folders are included for optional outputs and logs:

- `output/raw`
- `output/processed`
- `output/logs`

## Validation

The validation report includes:

- Missing value counts for major target and predictor variables
- LST minimum, maximum, and range check
- Cloud-free valid-pixel coverage
- Pearson correlation direction checks:
  - LST should generally correlate positively with `ndbi_mean` and `builtup_pct`
  - LST should generally correlate negatively with `ndvi_mean` and `water_pct`

These checks are diagnostic, not proof of model validity.

## Limitations

- FAO GAUL level 2 represents the Dhaka administrative district, not necessarily the metropolitan study boundary. A thesis-specific metropolitan boundary asset is recommended.
- Landsat thermal data have 30 m delivered pixels derived from coarser thermal observations, so grid statistics should be interpreted at aggregated scale.
- Monsoon cloud cover can reduce valid Landsat observations. Validation CSVs should be checked before modeling.
- ESRI LULC is a global product and should be interpreted with local uncertainty, especially for wetlands, cropland, and mixed urban areas.
- Google Open Buildings is static for this workflow, so building morphology is not year-specific.
- Road density requires a user-supplied road vector asset; otherwise it is exported as blank with a note.
