"""Export Dhaka satellite raster images from Google Earth Engine.

This script collects satellite images only. It exports GeoTIFF rasters to
Google Drive for Dhaka, Bangladesh:

- Landsat heat-season LST_C
- NDVI, NDBI, NDWI, MNDWI, NDMI
- Combined Landsat stack
- ESRI annual LULC
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

import ee


LANDSAT8_C2_L2 = "LANDSAT/LC08/C02/T1_L2"
LANDSAT9_C2_L2 = "LANDSAT/LC09/C02/T1_L2"
ESRI_LULC_TS = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
GAUL_LEVEL2 = "FAO/GAUL/2015/level2"

LANDSAT_SCALE_M = 30
ESRI_LULC_SCALE_M = 10


def initialize_earth_engine(project: str | None = None) -> None:
    """Initialize Earth Engine with an optional Google Cloud project."""
    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except Exception as exc:
        project_hint = f" --project {project}" if project else ""
        raise RuntimeError(
            "Google Earth Engine is not initialized. Run `earthengine authenticate`, "
            f"then retry `python satellite_collect1_0.py{project_hint}`."
        ) from exc


def parse_mmdd(mmdd: str, year: int) -> date:
    """Parse MM-DD into a Python date for the selected year."""
    try:
        month, day = mmdd.split("-")
        return date(year, int(month), int(day))
    except Exception as exc:
        raise argparse.ArgumentTypeError("Date must use MM-DD format, for example 04-01.") from exc


def build_date_range(year: int, start_mmdd: str, end_mmdd: str) -> tuple[date, date, date]:
    """Return inclusive start/end dates plus exclusive Earth Engine end date."""
    start_date = parse_mmdd(start_mmdd, year)
    end_date = parse_mmdd(end_mmdd, year)
    if start_date > end_date:
        raise ValueError("This script expects start-mmdd to be before end-mmdd in the same year.")
    return start_date, end_date, end_date + timedelta(days=1)


def get_dhaka_aoi(aoi_asset: str | None = None) -> tuple[ee.FeatureCollection, str]:
    """Load Dhaka AOI from a user asset or FAO GAUL level-2 fallback."""
    if aoi_asset:
        return ee.FeatureCollection(aoi_asset), f"user asset: {aoi_asset}"

    gaul = ee.FeatureCollection(GAUL_LEVEL2)
    bangladesh = gaul.filter(
        ee.Filter.Or(
            ee.Filter.eq("ADM0_NAME", "Bangladesh"),
            ee.Filter.eq("ADM0_CODE", 23),
        )
    )
    dhaka = bangladesh.filter(
        ee.Filter.Or(
            ee.Filter.stringContains("ADM2_NAME", "Dhaka"),
            ee.Filter.stringContains("ADM2_EN", "Dhaka"),
        )
    )
    return dhaka, "FAO GAUL 2015 level2: Bangladesh/Dhaka"


def load_landsat_collection(
    aoi: ee.FeatureCollection,
    start_date: date,
    exclusive_end_date: date,
    max_cloud: float,
) -> ee.ImageCollection:
    """Load merged Landsat 8 and 9 Collection 2 Level 2 images."""
    geom = aoi.geometry()

    def load(collection_id: str) -> ee.ImageCollection:
        return (
            ee.ImageCollection(collection_id)
            .filterBounds(geom)
            .filterDate(start_date.isoformat(), exclusive_end_date.isoformat())
            .filter(ee.Filter.lt("CLOUD_COVER", max_cloud))
        )

    return load(LANDSAT8_C2_L2).merge(load(LANDSAT9_C2_L2))


def mask_landsat_qa(image: ee.Image) -> ee.Image:
    """Mask fill, dilated cloud, cirrus, cloud, cloud shadow, and snow."""
    image = ee.Image(image)
    qa = image.select("QA_PIXEL")
    clear = (
        qa.bitwiseAnd(1 << 0)
        .eq(0)
        .And(qa.bitwiseAnd(1 << 1).eq(0))
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    valid_temperature = image.select("ST_B10").gt(0)
    return image.updateMask(clear.And(valid_temperature))


def scale_and_rename_landsat(image: ee.Image) -> ee.Image:
    """Scale Landsat C2 L2 optical and surface-temperature bands."""
    image = ee.Image(image)
    optical = (
        image.select(["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"])
        .multiply(0.0000275)
        .add(-0.2)
        .rename(["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"])
    )
    lst_c = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("LST_C")
    return ee.Image.cat([optical, lst_c]).copyProperties(image, image.propertyNames())


def prepare_landsat_image(image: ee.Image) -> ee.Image:
    """Apply QA masking, scaling, and band renaming to one Landsat image."""
    return scale_and_rename_landsat(mask_landsat_qa(image))


def create_landsat_composite(
    collection: ee.ImageCollection,
    aoi: ee.FeatureCollection,
) -> ee.Image:
    """Create a heat-season median Landsat composite clipped to Dhaka."""
    prepared = collection.map(prepare_landsat_image)
    return prepared.median().clip(aoi.geometry())


def normalized_index(image: ee.Image, band_a: str, band_b: str, out_name: str) -> ee.Image:
    """Calculate (A - B) / (A + B), guarding against a zero denominator."""
    a = image.select(band_a)
    b = image.select(band_b)
    denominator = a.add(b)
    safe_denominator = denominator.where(denominator.abs().lt(1e-6), 1e-6)
    return a.subtract(b).divide(safe_denominator).rename(out_name)


def add_indices(composite: ee.Image) -> ee.Image:
    """Add NDVI, NDBI, NDWI, MNDWI, and NDMI to the Landsat composite."""
    ndvi = normalized_index(composite, "NIR", "Red", "NDVI")
    ndbi = normalized_index(composite, "SWIR1", "NIR", "NDBI")
    ndwi = normalized_index(composite, "Green", "NIR", "NDWI")
    mndwi = normalized_index(composite, "Green", "SWIR1", "MNDWI")
    ndmi = normalized_index(composite, "NIR", "SWIR1", "NDMI")
    return composite.addBands([ndvi, ndbi, ndwi, mndwi, ndmi], overwrite=True)


def get_esri_lulc_image(year: int, aoi: ee.FeatureCollection) -> ee.Image:
    """Load ESRI Annual LULC image for Dhaka and selected year."""
    collection = ee.ImageCollection(ESRI_LULC_TS).filterBounds(aoi.geometry())
    by_date = collection.filterDate(f"{year}-01-01", f"{year + 1}-01-01")
    by_index = collection.filter(ee.Filter.stringContains("system:index", str(year)))

    by_date_count = int(by_date.size().getInfo())
    by_index_count = int(by_index.size().getInfo())
    if by_date_count > 0:
        annual = ee.Image(by_date.first())
    elif by_index_count > 0:
        annual = ee.Image(by_index.first())
    else:
        raise RuntimeError(
            f"No ESRI Annual LULC image was found for {year}. "
            "Try a different year supported by the ESRI time series."
        )

    return annual.select(0).rename("ESRI_LULC").clip(aoi.geometry())


def export_geotiff_to_drive(
    image: ee.Image,
    region: ee.Geometry,
    description: str,
    file_prefix: str,
    drive_folder: str,
    scale: int,
    crs: str,
) -> ee.batch.Task:
    """Start one Earth Engine image-to-Drive GeoTIFF export."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=drive_folder,
        fileNamePrefix=file_prefix,
        region=region,
        scale=scale,
        crs=crs,
        fileFormat="GeoTIFF",
        maxPixels=1e13,
    )
    task.start()
    return task


def start_exports(
    landsat_with_indices: ee.Image,
    esri_lulc: ee.Image,
    aoi: ee.FeatureCollection,
    year: int,
    drive_folder: str,
    crs: str,
) -> list[tuple[str, str, str]]:
    """Start all required GeoTIFF exports and return task metadata."""
    region = aoi.geometry()
    export_specs = [
        ("dhaka_lst", landsat_with_indices.select("LST_C"), LANDSAT_SCALE_M),
        ("dhaka_ndvi", landsat_with_indices.select("NDVI"), LANDSAT_SCALE_M),
        ("dhaka_ndbi", landsat_with_indices.select("NDBI"), LANDSAT_SCALE_M),
        ("dhaka_ndwi", landsat_with_indices.select("NDWI"), LANDSAT_SCALE_M),
        ("dhaka_mndwi", landsat_with_indices.select("MNDWI"), LANDSAT_SCALE_M),
        ("dhaka_ndmi", landsat_with_indices.select("NDMI"), LANDSAT_SCALE_M),
        (
            "dhaka_landsat_stack",
            landsat_with_indices.select(["LST_C", "NDVI", "NDBI", "NDWI", "MNDWI", "NDMI"]),
            LANDSAT_SCALE_M,
        ),
        ("dhaka_esri_lulc", esri_lulc, ESRI_LULC_SCALE_M),
    ]

    tasks: list[tuple[str, str, str]] = []
    for prefix, image, scale in export_specs:
        file_prefix = f"{prefix}_{year}"
        description = file_prefix
        task = export_geotiff_to_drive(
            image=image,
            region=region,
            description=description,
            file_prefix=file_prefix,
            drive_folder=drive_folder,
            scale=scale,
            crs=crs,
        )
        tasks.append((description, task.id, f"{file_prefix}.tif"))
    return tasks


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export Dhaka Landsat LST, indices, stack, and ESRI LULC GeoTIFFs from Earth Engine."
    )
    parser.add_argument("--project", type=str, default=None, help="Optional Earth Engine Google Cloud project ID.")
    parser.add_argument("--year", type=int, default=2024, help="Observation year. Default: 2024.")
    parser.add_argument("--start-mmdd", type=str, default="04-01", help="Heat-season start date as MM-DD.")
    parser.add_argument("--end-mmdd", type=str, default="08-31", help="Heat-season end date as MM-DD.")
    parser.add_argument("--max-cloud", type=float, default=70.0, help="Maximum Landsat CLOUD_COVER percent.")
    parser.add_argument("--aoi-asset", type=str, default=None, help="Optional user AOI FeatureCollection asset.")
    parser.add_argument("--drive-folder", type=str, default="Dhaka_Satellite_Images", help="Google Drive folder.")
    parser.add_argument("--crs", type=str, default="EPSG:32645", help="Export CRS. Default: EPSG:32645.")
    return parser.parse_args()


def main() -> None:
    """Run the satellite image collection and export workflow."""
    args = parse_args()
    start_date, end_date, exclusive_end_date = build_date_range(args.year, args.start_mmdd, args.end_mmdd)

    initialize_earth_engine(args.project)
    aoi, aoi_source = get_dhaka_aoi(args.aoi_asset)

    landsat = load_landsat_collection(
        aoi=aoi,
        start_date=start_date,
        exclusive_end_date=exclusive_end_date,
        max_cloud=args.max_cloud,
    )
    landsat_count = int(landsat.size().getInfo())
    if landsat_count == 0:
        raise RuntimeError(
            "No Landsat 8/9 C2 L2 images found for this AOI/date/cloud filter. "
            "Try increasing --max-cloud or changing the date range."
        )

    composite = create_landsat_composite(landsat, aoi)
    landsat_with_indices = add_indices(composite).clip(aoi.geometry())
    esri_lulc = get_esri_lulc_image(args.year, aoi)

    print("Dhaka satellite image export")
    print(f"Selected year: {args.year}")
    print(f"Date range: {start_date.isoformat()} to {end_date.isoformat()} inclusive")
    print(f"AOI source: {aoi_source}")
    print(f"Landsat images before compositing: {landsat_count}")
    print(f"Drive folder: {args.drive_folder}")
    print(f"Export CRS: {args.crs}")
    print("")

    tasks = start_exports(
        landsat_with_indices=landsat_with_indices,
        esri_lulc=esri_lulc,
        aoi=aoi,
        year=args.year,
        drive_folder=args.drive_folder,
        crs=args.crs,
    )

    print("Started Earth Engine GeoTIFF export tasks:")
    for description, task_id, filename in tasks:
        print(f"- {description} -> {filename} | task_id={task_id}")

    print("")
    print("Exports run asynchronously.")
    print("Open the Earth Engine Tasks tab to monitor status:")
    print("https://code.earthengine.google.com/tasks")
    print(f"When tasks complete, check Google Drive folder: {args.drive_folder}")


if __name__ == "__main__":
    main()
