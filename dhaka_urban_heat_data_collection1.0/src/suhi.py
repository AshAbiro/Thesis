"""Surface urban heat island intensity calculations."""

from __future__ import annotations

import ee

from config import DEFAULT_LANDSAT_SCALE_M


def calculate_reference_lst_mean(
    lst_image: ee.Image,
    reference_zone: ee.FeatureCollection | ee.Geometry,
    scale: int = DEFAULT_LANDSAT_SCALE_M,
) -> ee.Number:
    """Calculate mean LST in the reference zone for a matching time step."""
    geom = (
        reference_zone.geometry()
        if isinstance(reference_zone, ee.featurecollection.FeatureCollection)
        else ee.Geometry(reference_zone)
    )
    stats = lst_image.select("lst_c").reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=scale,
        maxPixels=1e13,
        bestEffort=True,
        tileScale=4,
    )
    return ee.Number(stats.get("lst_c"))


def add_suhi_band(lst_image: ee.Image, reference_mean: ee.Number) -> ee.Image:
    """Add SUHI band where SUHI = pixel LST - reference-zone mean LST."""
    suhi = lst_image.select("lst_c").subtract(reference_mean).rename("suhi")
    return lst_image.addBands(suhi, overwrite=True).set({"reference_lst_mean": reference_mean})
