"""Grid-level aggregation and table joins."""

from __future__ import annotations

import ee

from config import CONTINUOUS_AGGREGATION_BANDS, DEFAULT_LANDSAT_SCALE_M, GRID_ID_PROPERTY


def aggregate_image_to_grid(
    image: ee.Image,
    grid: ee.FeatureCollection,
    scale: int = DEFAULT_LANDSAT_SCALE_M,
) -> ee.FeatureCollection:
    """Aggregate continuous raster variables to grid cells.

    The output includes mean, median, min, and max for continuous bands. Common
    thesis field aliases such as `lst_mean`, `lst_median`, and `suhi_mean` are
    added for model-ready use.
    """
    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.median(), sharedInputs=True)
        .combine(ee.Reducer.minMax(), sharedInputs=True)
    )
    fc = image.select(list(CONTINUOUS_AGGREGATION_BANDS)).reduceRegions(
        collection=grid,
        reducer=reducer,
        scale=scale,
        tileScale=4,
    )

    def add_aliases(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        return feature.set(
            {
                "lst_mean": feature.get("lst_c_mean"),
                "lst_median": feature.get("lst_c_median"),
                "lst_min": feature.get("lst_c_min"),
                "lst_max": feature.get("lst_c_max"),
                "suhi_mean": feature.get("suhi_mean"),
                "ndvi_mean": feature.get("ndvi_mean"),
                "ndwi_mean": feature.get("ndwi_mean"),
                "mndwi_mean": feature.get("mndwi_mean"),
                "ndmi_mean": feature.get("ndmi_mean"),
                "ndbi_mean": feature.get("ndbi_mean"),
                "albedo_mean": feature.get("albedo_mean"),
                "distance_to_water": feature.get("distance_to_water_m_mean"),
                "mean_distance_to_water_m": feature.get("distance_to_water_m_mean"),
                "min_distance_to_water_m": feature.get("distance_to_water_m_min"),
                "valid_obs_mean": feature.get("valid_obs_mean"),
            }
        )

    return fc.map(add_aliases)


def join_feature_collections(
    left: ee.FeatureCollection,
    right: ee.FeatureCollection,
    join_property: str = GRID_ID_PROPERTY,
    right_properties: list[str] | None = None,
) -> ee.FeatureCollection:
    """Copy selected properties from `right` to matching features in `left`."""
    joined = ee.Join.saveFirst("matched_feature").apply(
        primary=left,
        secondary=right,
        condition=ee.Filter.equals(leftField=join_property, rightField=join_property),
    )

    def merge_properties(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        match = ee.Feature(feature.get("matched_feature"))
        if right_properties:
            merged = feature.copyProperties(match, right_properties)
        else:
            merged = feature.copyProperties(match)
        return merged.set("matched_feature", None)

    return ee.FeatureCollection(joined).map(merge_properties)


def add_run_metadata(
    fc: ee.FeatureCollection,
    year: int,
    season: str,
    reference_lst_mean: ee.Number,
) -> ee.FeatureCollection:
    """Attach year, season, and reference LST metadata to every grid row."""
    def set_metadata(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        return feature.set(
            {
                "year": year,
                "season": season,
                "reference_lst_mean": reference_lst_mean,
            }
        )

    return fc.map(set_metadata)
