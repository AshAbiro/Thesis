"""Landsat Collection 2 Level 2 LST retrieval and seasonal compositing."""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass

import ee

from config import (
    DEFAULT_LANDSAT_SCALE_M,
    DEFAULT_MAX_CLOUD_COVER,
    LANDSAT_COLLECTIONS,
    SEASONS,
)


COMMON_LANDSAT_BANDS = (
    "blue",
    "green",
    "red",
    "nir",
    "swir1",
    "swir2",
    "thermal",
    "qa_pixel",
)

COMPOSITE_BANDS = (
    "blue",
    "green",
    "red",
    "nir",
    "swir1",
    "swir2",
    "lst_c",
)


@dataclass(frozen=True)
class SeasonWindow:
    """Concrete date range for a Dhaka season."""

    start_date: str
    end_date: str


def get_season_date_range(year: int, season: str) -> SeasonWindow:
    """Return the start and exclusive end date for a named Dhaka season."""
    if season not in SEASONS:
        raise ValueError(f"Unknown season '{season}'. Valid seasons: {', '.join(SEASONS)}")

    start_month, end_month = SEASONS[season]
    if start_month <= end_month:
        start_year = year
        end_year = year
    else:
        start_year = year - 1
        end_year = year

    start = date(start_year, start_month, 1)
    if end_month == 12:
        end = date(end_year + 1, 1, 1)
    else:
        end = date(end_year, end_month + 1, 1)
    return SeasonWindow(start.isoformat(), end.isoformat())


def _season_dates_ee(year: int, season: str) -> tuple[ee.Date, ee.Date]:
    if season not in SEASONS:
        raise ValueError(f"Unknown season '{season}'. Valid seasons: {', '.join(SEASONS)}")

    start_month, end_month = SEASONS[season]
    if start_month <= end_month:
        start = ee.Date.fromYMD(year, start_month, 1)
        end = ee.Date.fromYMD(year, end_month, 1).advance(1, "month")
    else:
        start = ee.Date.fromYMD(year - 1, start_month, 1)
        end = ee.Date.fromYMD(year, end_month, 1).advance(1, "month")
    return start, end


def load_landsat_by_date(
    aoi: ee.FeatureCollection | ee.Geometry,
    start_date: str | ee.Date,
    end_date: str | ee.Date,
    max_cloud_cover: float = DEFAULT_MAX_CLOUD_COVER,
) -> ee.ImageCollection:
    """Load and merge Landsat 5, 7, 8, and 9 C2 L2 scenes for a date range."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    merged = ee.ImageCollection([])
    for collection_id in LANDSAT_COLLECTIONS:
        collection = (
            ee.ImageCollection(collection_id)
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lte("CLOUD_COVER", max_cloud_cover))
        )
        merged = merged.merge(collection)
    return merged


def harmonize_band_names(image: ee.Image) -> ee.Image:
    """Rename Landsat sensor-specific C2 L2 bands to a common schema."""
    image = ee.Image(image)
    spacecraft = ee.String(image.get("SPACECRAFT_ID"))

    def rename_landsat_8_9() -> ee.Image:
        return image.select(
            ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7", "ST_B10", "QA_PIXEL"],
            list(COMMON_LANDSAT_BANDS),
        )

    def rename_landsat_5_7() -> ee.Image:
        return image.select(
            ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7", "ST_B6", "QA_PIXEL"],
            list(COMMON_LANDSAT_BANDS),
        )

    is_landsat_8_9 = ee.List(["LANDSAT_8", "LANDSAT_9"]).contains(spacecraft)
    harmonized = ee.Image(ee.Algorithms.If(is_landsat_8_9, rename_landsat_8_9(), rename_landsat_5_7()))
    return harmonized.copyProperties(image, image.propertyNames())


def mask_clouds_and_shadows(image: ee.Image) -> ee.Image:
    """Mask fill, dilated cloud, cirrus, cloud, cloud shadow, and snow pixels."""
    image = ee.Image(image)
    qa = image.select("qa_pixel")
    fill = qa.bitwiseAnd(1 << 0).eq(0)
    dilated_cloud = qa.bitwiseAnd(1 << 1).eq(0)
    cirrus = qa.bitwiseAnd(1 << 2).eq(0)
    cloud = qa.bitwiseAnd(1 << 3).eq(0)
    cloud_shadow = qa.bitwiseAnd(1 << 4).eq(0)
    snow = qa.bitwiseAnd(1 << 5).eq(0)
    thermal_valid = image.select("thermal").gt(0)
    mask = fill.And(dilated_cloud).And(cirrus).And(cloud).And(cloud_shadow).And(snow).And(thermal_valid)
    return image.updateMask(mask)


def scale_optical_bands(image: ee.Image) -> ee.Image:
    """Apply Landsat C2 L2 surface-reflectance scale and offset."""
    image = ee.Image(image)
    optical = image.select(["blue", "green", "red", "nir", "swir1", "swir2"]).multiply(0.0000275).add(-0.2)
    return image.addBands(optical, overwrite=True)


def scale_thermal_band(image: ee.Image) -> ee.Image:
    """Apply Landsat C2 L2 surface-temperature scale and offset to Kelvin."""
    image = ee.Image(image)
    lst_kelvin = image.select("thermal").multiply(0.00341802).add(149.0).rename("lst_kelvin")
    return image.addBands(lst_kelvin, overwrite=True)


def calculate_lst_celsius(image: ee.Image) -> ee.Image:
    """Calculate land surface temperature in degrees Celsius."""
    image = ee.Image(image)
    lst_c = image.select("lst_kelvin").subtract(273.15).rename("lst_c")
    return image.addBands(lst_c, overwrite=True)


def prepare_landsat_image(image: ee.Image) -> ee.Image:
    """Run the full per-scene Landsat preparation chain."""
    image = ee.Image(image)
    harmonized = harmonize_band_names(image)
    masked = mask_clouds_and_shadows(harmonized)
    scaled = scale_optical_bands(masked)
    scaled = scale_thermal_band(scaled)
    return calculate_lst_celsius(scaled).select(list(COMPOSITE_BANDS))


def _empty_composite() -> ee.Image:
    zeros = ee.Image.constant([0] * len(COMPOSITE_BANDS)).rename(list(COMPOSITE_BANDS))
    valid_obs = ee.Image.constant(0).rename("valid_obs")
    return zeros.addBands(valid_obs).updateMask(ee.Image.constant(0))


def create_seasonal_composite(
    collection: ee.ImageCollection,
    year: int,
    season: str,
    aoi: ee.FeatureCollection | ee.Geometry,
    reducer: str = "median",
) -> ee.Image:
    """Create a seasonal Landsat composite with a valid-observation count band."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    start, end = _season_dates_ee(year, season)
    seasonal = collection.filterDate(start, end)
    valid_obs = seasonal.select("lst_c").count().rename("valid_obs")

    if reducer == "median":
        reduced = seasonal.select(list(COMPOSITE_BANDS)).median()
    elif reducer == "mean":
        reduced = seasonal.select(list(COMPOSITE_BANDS)).mean()
    else:
        raise ValueError("reducer must be 'median' or 'mean'.")

    composite = reduced.addBands(valid_obs).clip(geom)
    fallback = _empty_composite().clip(geom)
    return ee.Image(ee.Algorithms.If(seasonal.size().gt(0), composite, fallback)).set(
        {"year": year, "season": season, "landsat_scene_count": seasonal.size()}
    )


def get_landsat_lst_composite(
    aoi: ee.FeatureCollection | ee.Geometry,
    year: int,
    season: str,
    max_cloud_cover: float = DEFAULT_MAX_CLOUD_COVER,
    reducer: str = "median",
) -> ee.Image:
    """Return a Landsat C2 L2 seasonal LST composite for Dhaka."""
    start, end = _season_dates_ee(year, season)
    raw = load_landsat_by_date(aoi, start, end, max_cloud_cover=max_cloud_cover)
    prepared = raw.map(prepare_landsat_image)
    composite = create_seasonal_composite(prepared, year, season, aoi, reducer=reducer)
    return composite.set(
        {
            "source": "Landsat Collection 2 Level 2",
            "lst_units": "degrees Celsius",
            "scale_m": DEFAULT_LANDSAT_SCALE_M,
        }
    )
