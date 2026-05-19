"""Urban morphology features from building footprints and optional roads."""

from __future__ import annotations

import ee

from config import (
    DEFAULT_BUILDING_SCALE_M,
    DEFAULT_OPEN_BUILDINGS_CONFIDENCE,
    GOOGLE_OPEN_BUILDINGS,
    GRID_ID_PROPERTY,
)


def _number_or_zero(value: object) -> ee.Number:
    return ee.Number(ee.Algorithms.If(ee.Algorithms.IsEqual(value, None), 0, value))


def get_open_buildings(
    aoi: ee.FeatureCollection | ee.Geometry,
    confidence_threshold: float = DEFAULT_OPEN_BUILDINGS_CONFIDENCE,
    asset_id: str = GOOGLE_OPEN_BUILDINGS,
) -> ee.FeatureCollection:
    """Load Google Open Buildings footprints for the AOI."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    buildings = ee.FeatureCollection(asset_id).filterBounds(geom)
    return buildings.filter(ee.Filter.gte("confidence", confidence_threshold))


def _building_centroids(buildings: ee.FeatureCollection) -> ee.FeatureCollection:
    def to_centroid(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        return ee.Feature(feature.geometry().centroid(1)).copyProperties(feature).set(
            {"footprint_area_m2": feature.geometry().area(1)}
        )

    return buildings.map(to_centroid)


def _add_building_counts(area_fc: ee.FeatureCollection, buildings: ee.FeatureCollection) -> ee.FeatureCollection:
    centroids = _building_centroids(buildings)
    joined = ee.Join.saveAll("building_hits").apply(
        primary=area_fc,
        secondary=centroids,
        condition=ee.Filter.intersects(leftField=".geo", rightField=".geo", maxError=1),
    )

    def summarize(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        hits = ee.List(feature.get("building_hits"))
        return feature.set({"building_count": hits.size()}).select(
            [GRID_ID_PROPERTY, "building_area_m2", "building_area_ratio", "building_count"]
        )

    return ee.FeatureCollection(joined).map(summarize)


def _add_road_density(
    morphology_fc: ee.FeatureCollection,
    roads_asset_id: str | None,
) -> ee.FeatureCollection:
    if not roads_asset_id:
        def set_missing_road_density(feature: ee.Feature) -> ee.Feature:
            feature = ee.Feature(feature)
            return feature.set(
                {
                    "road_density_m_per_km2": None,
                    "road_density_available": False,
                    "road_density_note": "No road vector asset supplied.",
                }
            )

        return morphology_fc.map(set_missing_road_density)

    roads = ee.FeatureCollection(roads_asset_id)

    def add_density(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        geom = feature.geometry()

        def length_inside(road: ee.Feature) -> ee.Feature:
            road = ee.Feature(road)
            line = road.geometry().intersection(geom, 1)
            return ee.Feature(None, {"length_m": line.length(1)})

        length_m = _number_or_zero(roads.filterBounds(geom).map(length_inside).aggregate_sum("length_m"))
        area_km2 = ee.Number(geom.area(1)).divide(1_000_000)
        density = ee.Algorithms.If(area_km2.gt(0), length_m.divide(area_km2), None)
        return feature.set(
            {
                "road_density_m_per_km2": density,
                "road_density_available": True,
                "road_density_note": "Calculated from supplied road vector asset.",
            }
        )

    return morphology_fc.map(add_density)


def calculate_morphology_features(
    grid: ee.FeatureCollection,
    aoi: ee.FeatureCollection | ee.Geometry,
    buildings_asset_id: str | None = GOOGLE_OPEN_BUILDINGS,
    roads_asset_id: str | None = None,
    confidence_threshold: float = DEFAULT_OPEN_BUILDINGS_CONFIDENCE,
    scale: int = DEFAULT_BUILDING_SCALE_M,
) -> ee.FeatureCollection:
    """Calculate grid-level morphology features.

    Returns building footprint area ratio, building count, and road density when
    a road vector asset is supplied. Without a road asset, road density is left
    null and a note is written to the table.
    """
    if not buildings_asset_id:
        def set_missing_buildings(feature: ee.Feature) -> ee.Feature:
            feature = ee.Feature(feature)
            return feature.set(
                {
                    "building_area_m2": None,
                    "building_area_ratio": None,
                    "building_count": None,
                }
            )

        morphology = grid.map(set_missing_buildings)
        return _add_road_density(morphology, roads_asset_id)

    buildings = get_open_buildings(aoi, confidence_threshold=confidence_threshold, asset_id=buildings_asset_id)
    building_area_image = (
        ee.Image(0)
        .byte()
        .paint(buildings, 1)
        .selfMask()
        .multiply(ee.Image.pixelArea())
        .rename("building_area_m2")
    )
    area_fc = building_area_image.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.sum(),
        scale=scale,
        tileScale=4,
    )

    def add_area_ratio(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        building_area = _number_or_zero(feature.get("building_area_m2"))
        cell_area = ee.Number(feature.geometry().area(1))
        ratio = ee.Algorithms.If(cell_area.gt(0), building_area.divide(cell_area), None)
        return feature.set({"building_area_m2": building_area, "building_area_ratio": ratio})

    with_area = area_fc.map(add_area_ratio)
    with_counts = _add_building_counts(with_area, buildings)
    return _add_road_density(with_counts, roads_asset_id)
