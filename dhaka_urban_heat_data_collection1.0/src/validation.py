"""Validation and quality checks for grid-level data collection outputs."""

from __future__ import annotations

import ee

from config import DEFAULT_LANDSAT_SCALE_M


DEFAULT_VALIDATION_COLUMNS = (
    "lst_mean",
    "lst_median",
    "suhi_mean",
    "ndvi_mean",
    "ndwi_mean",
    "mndwi_mean",
    "ndmi_mean",
    "ndbi_mean",
    "albedo_mean",
    "builtup_pct",
    "vegetation_pct",
    "cropland_pct",
    "water_pct",
    "wetland_pct",
    "bare_pct",
    "building_area_ratio",
    "mean_distance_to_water_m",
)


def missing_value_counts(
    grid_fc: ee.FeatureCollection,
    columns: tuple[str, ...] = DEFAULT_VALIDATION_COLUMNS,
) -> ee.Dictionary:
    """Count missing values in selected table columns."""
    row_count = ee.Number(grid_fc.size())
    result = ee.Dictionary({"row_count": row_count})
    for column in columns:
        non_null = ee.Number(grid_fc.aggregate_count(column))
        result = result.set(f"missing_{column}", row_count.subtract(non_null))
    return result


def lst_min_max_range_check(
    grid_fc: ee.FeatureCollection,
    column: str = "lst_mean",
    min_c: float = 10.0,
    max_c: float = 60.0,
) -> ee.Dictionary:
    """Check that aggregated LST values are in a plausible Celsius range."""
    stats = ee.Dictionary(
        grid_fc.reduceColumns(
            reducer=ee.Reducer.minMax().combine(ee.Reducer.mean(), sharedInputs=True),
            selectors=[column],
        )
    )
    lst_min = ee.Number(stats.get("min"))
    lst_max = ee.Number(stats.get("max"))
    return ee.Dictionary(
        {
            "lst_min": lst_min,
            "lst_max": lst_max,
            "lst_mean_of_grid_means": stats.get("mean"),
            "lst_range_ok": lst_min.gte(min_c).And(lst_max.lte(max_c)),
        }
    )


def cloud_free_pixel_coverage(
    image: ee.Image,
    aoi: ee.FeatureCollection | ee.Geometry,
    band: str = "lst_c",
    scale: int = DEFAULT_LANDSAT_SCALE_M,
) -> ee.Number:
    """Estimate the fraction of valid cloud-free pixels for a raster band."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    coverage = image.select(band).mask().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=scale,
        maxPixels=1e13,
        bestEffort=True,
        tileScale=4,
    )
    return ee.Number(coverage.get(band))


def _pearson(grid_fc: ee.FeatureCollection, x: str, y: str) -> ee.Number:
    result = ee.Dictionary(
        grid_fc.reduceColumns(
            reducer=ee.Reducer.pearsonsCorrelation(),
            selectors=[x, y],
        )
    )
    return ee.Number(result.get("correlation"))


def mechanism_correlation_checks(grid_fc: ee.FeatureCollection) -> ee.Dictionary:
    """Run simple mechanism checks against expected LST relationships."""
    corr_ndbi = _pearson(grid_fc, "ndbi_mean", "lst_mean")
    corr_built = _pearson(grid_fc, "builtup_pct", "lst_mean")
    corr_ndvi = _pearson(grid_fc, "ndvi_mean", "lst_mean")
    corr_water = _pearson(grid_fc, "water_pct", "lst_mean")
    return ee.Dictionary(
        {
            "corr_lst_ndbi": corr_ndbi,
            "corr_lst_builtup_pct": corr_built,
            "corr_lst_ndvi": corr_ndvi,
            "corr_lst_water_pct": corr_water,
            "lst_ndbi_positive_ok": corr_ndbi.gt(0),
            "lst_builtup_positive_ok": corr_built.gt(0),
            "lst_ndvi_negative_ok": corr_ndvi.lt(0),
            "lst_water_negative_ok": corr_water.lt(0),
        }
    )


def build_validation_report(
    grid_fc: ee.FeatureCollection,
    image: ee.Image,
    aoi: ee.FeatureCollection | ee.Geometry,
    year: int,
    season: str,
) -> ee.FeatureCollection:
    """Create a one-row validation report for a year-season output table."""
    missing = missing_value_counts(grid_fc)
    lst_range = lst_min_max_range_check(grid_fc)
    mechanism = mechanism_correlation_checks(grid_fc)
    coverage = cloud_free_pixel_coverage(image, aoi)
    report = ee.Dictionary(
        {
            "year": year,
            "season": season,
            "cloud_free_pixel_coverage": coverage,
        }
    ).combine(missing).combine(lst_range).combine(mechanism)
    return ee.FeatureCollection([ee.Feature(None, report)])
