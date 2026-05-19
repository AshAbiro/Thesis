"""Six-class LULC extraction and grid percentages."""

from __future__ import annotations

import ee

from config import (
    DEFAULT_LULC_SCALE_M,
    ESA_WORLDCOVER_2021,
    ESRI_LULC_TS,
    GRID_ID_PROPERTY,
    JRC_GLOBAL_SURFACE_WATER,
    LULC_PERCENT_FIELDS,
)


ESRI_TO_LULC6_FROM = [7, 2, 11, 5, 1, 4, 8]
ESRI_TO_LULC6_TO = [1, 2, 2, 3, 4, 5, 6]

ESA_TO_LULC6_FROM = [50, 10, 20, 30, 40, 80, 90, 95, 60]
ESA_TO_LULC6_TO = [1, 2, 2, 2, 3, 4, 5, 5, 6]


def _first_band(image: ee.Image) -> ee.Image:
    return image.select(0)


def _number_or_zero(value: object) -> ee.Number:
    return ee.Number(ee.Algorithms.If(ee.Algorithms.IsEqual(value, None), 0, value))


def get_esri_lulc_image(year: int, aoi: ee.FeatureCollection | ee.Geometry) -> ee.Image:
    """Load the annual ESRI 10 m LULC image for a year."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    collection = ee.ImageCollection(ESRI_LULC_TS).filterBounds(geom)
    by_date = collection.filterDate(f"{year}-01-01", f"{year + 1}-01-01")
    by_index = collection.filter(ee.Filter.stringContains("system:index", str(year)))
    annual = ee.Image(ee.Algorithms.If(by_date.size().gt(0), by_date.first(), by_index.first()))
    image = _first_band(ee.Image(annual)).rename("esri_lulc")
    return image.clip(geom).set({"year": year, "source": "ESRI Global LULC 10m TS"})


def get_esa_worldcover_lulc6(aoi: ee.FeatureCollection | ee.Geometry) -> ee.Image:
    """Return ESA WorldCover 2021 remapped to the six thesis LULC classes."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    esa = ee.ImageCollection(ESA_WORLDCOVER_2021).first().select("Map")
    lulc6 = esa.remap(ESA_TO_LULC6_FROM, ESA_TO_LULC6_TO, 0).rename("esa_lulc6")
    return lulc6.updateMask(lulc6.gt(0)).clip(geom).set({"source": "ESA WorldCover 2021"})


def refine_with_jrc_water(lulc6: ee.Image, aoi: ee.FeatureCollection | ee.Geometry) -> ee.Image:
    """Refine water and wetland classes using JRC Global Surface Water."""
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    jrc = ee.Image(JRC_GLOBAL_SURFACE_WATER).clip(geom)
    occurrence = jrc.select("occurrence")
    seasonality = jrc.select("seasonality")

    permanent_water = occurrence.gte(50).Or(seasonality.gte(10))
    seasonal_water_or_wet = occurrence.gte(5).And(occurrence.lt(50)).Or(seasonality.gte(2).And(seasonality.lt(10)))

    refined = lulc6.where(seasonal_water_or_wet.And(lulc6.neq(1)), 5)
    refined = refined.where(permanent_water, 4)
    return refined.rename("lulc6")


def get_lulc6_image(year: int, aoi: ee.FeatureCollection | ee.Geometry) -> ee.Image:
    """Return the thesis six-class LULC image for a year.

    Classes:
    1 Built-up, 2 Vegetation, 3 Cropland, 4 Water Bodies, 5 Wetlands, 6 Bare Land.
    """
    esri = get_esri_lulc_image(year, aoi)
    lulc6 = esri.remap(ESRI_TO_LULC6_FROM, ESRI_TO_LULC6_TO, 0).rename("lulc6")
    lulc6 = lulc6.updateMask(lulc6.gt(0))
    refined = refine_with_jrc_water(lulc6, aoi)
    return refined.set(
        {
            "year": year,
            "class_schema": "1=Built-up;2=Vegetation;3=Cropland;4=Water Bodies;5=Wetlands;6=Bare Land",
            "source": "ESRI Global LULC 10m TS refined with JRC Global Surface Water",
        }
    )


def calculate_lulc_percentages(
    lulc_image: ee.Image,
    grid: ee.FeatureCollection,
    scale: int = DEFAULT_LULC_SCALE_M,
) -> ee.FeatureCollection:
    """Calculate six-class LULC percentage variables for each grid cell."""
    pixel_area = ee.Image.pixelArea()
    class_area_bands = [
        pixel_area.updateMask(lulc_image.eq(1)).rename("builtup_area_m2"),
        pixel_area.updateMask(lulc_image.eq(2)).rename("vegetation_area_m2"),
        pixel_area.updateMask(lulc_image.eq(3)).rename("cropland_area_m2"),
        pixel_area.updateMask(lulc_image.eq(4)).rename("water_area_m2"),
        pixel_area.updateMask(lulc_image.eq(5)).rename("wetland_area_m2"),
        pixel_area.updateMask(lulc_image.eq(6)).rename("bare_area_m2"),
    ]
    area_image = ee.Image.cat(class_area_bands)
    area_fc = area_image.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.sum(),
        scale=scale,
        tileScale=4,
    )

    area_fields = (
        "builtup_area_m2",
        "vegetation_area_m2",
        "cropland_area_m2",
        "water_area_m2",
        "wetland_area_m2",
        "bare_area_m2",
    )

    def add_percentages(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        total_area = ee.Number(feature.geometry().area(1))
        areas = [_number_or_zero(feature.get(field)) for field in area_fields]
        percentages = [
            ee.Algorithms.If(total_area.gt(0), area.divide(total_area).multiply(100), None)
            for area in areas
        ]
        max_area = ee.Number(ee.List(areas).reduce(ee.Reducer.max()))
        dominant_index = ee.Number(ee.List(areas).indexOf(max_area)).add(1)
        return feature.set(dict(zip(LULC_PERCENT_FIELDS, percentages))).set(
            {
                "dominant_lulc6": dominant_index,
                "lulc_total_area_m2": total_area,
                "lulc_year": lulc_image.get("year"),
            }
        )

    keep_properties = [GRID_ID_PROPERTY, *LULC_PERCENT_FIELDS, "dominant_lulc6", "lulc_total_area_m2", "lulc_year"]
    return area_fc.map(add_percentages).select(keep_properties, None, False)
