# satellite_collect1_0

Executable Google Earth Engine Python workflow for collecting Dhaka satellite raster images for an urban heat / LST thesis.

This project exports satellite images only. It does not create machine-learning models, prediction models, or thesis text.

## Outputs

The script exports GeoTIFF rasters to Google Drive:

- `dhaka_lst_<year>.tif`
- `dhaka_ndvi_<year>.tif`
- `dhaka_ndbi_<year>.tif`
- `dhaka_ndwi_<year>.tif`
- `dhaka_mndwi_<year>.tif`
- `dhaka_ndmi_<year>.tif`
- `dhaka_landsat_stack_<year>.tif`
- `dhaka_esri_lulc_<year>.tif`

The Landsat stack contains:

- `LST_C`
- `NDVI`
- `NDBI`
- `NDWI`
- `MNDWI`
- `NDMI`

## Datasets

- Landsat 8 Collection 2 Level 2: `LANDSAT/LC08/C02/T1_L2`
- Landsat 9 Collection 2 Level 2: `LANDSAT/LC09/C02/T1_L2`
- ESRI Annual LULC: `projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS`
- Default AOI fallback: `FAO/GAUL/2015/level2`, filtered to Bangladesh and Dhaka

## Setup

From the VS Code terminal:

```bash
cd satellite_collect1_0
pip install -r requirements.txt
earthengine authenticate
```

## Run

Default year is 2024 and default heat season is April 1 to August 31.

```bash
python satellite_collect1_0.py --year 2024 --project YOUR_GEE_PROJECT_ID
```

For your current project:

```bash
python satellite_collect1_0.py --year 2024 --project thesis-01-496711
```

Use a custom Drive folder:

```bash
python satellite_collect1_0.py --year 2024 --project thesis-01-496711 --drive-folder Dhaka_Satellite_Images
```

Change heat-season dates:

```bash
python satellite_collect1_0.py --year 2024 --project thesis-01-496711 --start-mmdd 04-01 --end-mmdd 08-31
```

Use a user-uploaded Dhaka AOI asset:

```bash
python satellite_collect1_0.py --year 2024 --project thesis-01-496711 --aoi-asset users/your_name/dhaka_boundary
```

## Arguments

- `--project`: optional Earth Engine Google Cloud project ID
- `--year`: export year, default `2024`
- `--start-mmdd`: start date in `MM-DD`, default `04-01`
- `--end-mmdd`: end date in `MM-DD`, default `08-31`
- `--max-cloud`: maximum Landsat `CLOUD_COVER`, default `70`
- `--aoi-asset`: optional Earth Engine FeatureCollection asset for Dhaka AOI
- `--drive-folder`: Google Drive export folder, default `Dhaka_Satellite_Images`
- `--crs`: export CRS, default `EPSG:32645`

## Processing

The workflow:

1. Initializes Earth Engine.
2. Loads Dhaka AOI from `--aoi-asset` or FAO GAUL.
3. Loads Landsat 8 and 9 C2 L2 images for the selected heat season.
4. Filters by AOI, date, and `CLOUD_COVER`.
5. Masks QA_PIXEL fill, dilated cloud, cirrus, cloud, cloud shadow, and snow.
6. Scales optical bands with scale `0.0000275` and offset `-0.2`.
7. Scales `ST_B10` to Kelvin using `0.00341802` and `149.0`, then converts to Celsius.
8. Builds a median heat-season composite.
9. Calculates NDVI, NDBI, NDWI, MNDWI, and NDMI.
10. Clips all rasters to Dhaka.
11. Starts Google Drive GeoTIFF exports.

## Notes

Earth Engine exports are asynchronous. After running the script, open:

```text
https://code.earthengine.google.com/tasks
```

Then check the selected Google Drive folder after tasks become `COMPLETED`.
