"""Water-distance feature calculation."""

from __future__ import annotations

import ee

from config import DEFAULT_GRID_CRS, DEFAULT_LANDSAT_SCALE_M, GRID_ID_PROPERTY, JRC_GLOBAL_SURFACE_WATER


def _jrc_water_mask(aoi: ee.FeatureCollection | ee.Geometry) -> ee.Image:
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    jrc = ee.Image(JRC_GLOBAL_SURFACE_WATER).clip(geom)
    occurrence = jrc.select("occurrence")
    seasonality = jrc.select("seasonality")
    return occurrence.gte(50).Or(seasonality.gte(10)).rename("water_mask")


def calculate_distance_to_water(
    aoi: ee.FeatureCollection | ee.Geometry,
    year: int,
    season: str,
    spectral_image: ee.Image | None = None,
    mndwi_threshold: float = 0.0,
    scale: int = DEFAULT_LANDSAT_SCALE_M,
    max_distance_m: int = 30000,
) -> ee.Image:
    """Calculate distance to water from MNDWI and JRC water evidence.

    If `spectral_image` is supplied, MNDWI > threshold is combined with JRC
    permanent water. If not, JRC water alone is used.
    """
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    jrc_water = _jrc_water_mask(aoi)
    if spectral_image is not None:
        mndwi_water = spectral_image.select("mndwi").gt(mndwi_threshold).rename("water_mask")
        water = mndwi_water.Or(jrc_water).rename("water_mask")
    else:
        water = jrc_water

    max_pixels = int(max_distance_m / scale)
    water_source = water.unmask(0).reproject(crs=DEFAULT_GRID_CRS, scale=scale)
    distance = water_source.fastDistanceTransform(max_pixels, "pixels").sqrt().multiply(scale)
    return distance.rename("distance_to_water_m").clip(geom).set({"year": year, "season": season})


def aggregate_distance_to_grid(
    distance_image: ee.Image,
    grid: ee.FeatureCollection,
    scale: int = DEFAULT_LANDSAT_SCALE_M,
) -> ee.FeatureCollection:
    """Aggregate distance-to-water mean and minimum to each grid cell."""
    stats = distance_image.select("distance_to_water_m").reduceRegions(
        collection=grid,
        reducer=ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True),
        scale=scale,
        tileScale=4,
    )

    def rename_stats(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        mean_distance = feature.get("mean")
        min_distance = feature.get("min")
        return feature.set(
            {
                "mean_distance_to_water_m": mean_distance,
                "min_distance_to_water_m": min_distance,
                "distance_to_water": mean_distance,
            }
        ).select(
            [GRID_ID_PROPERTY, "mean_distance_to_water_m", "min_distance_to_water_m", "distance_to_water"],
            None,
            False,
        )

    return stats.map(rename_stats)
