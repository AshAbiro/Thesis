"""Study area and SUHI reference-zone construction."""

from __future__ import annotations

import ee

from config import DEFAULT_REFERENCE_BUFFER_KM, DHAKA_BOUNDARY_ASSET, GAUL_LEVEL2


def get_dhaka_boundary(asset_id: str | None = None) -> ee.FeatureCollection:
    """Return the Dhaka study-area boundary.

    A user-uploaded metropolitan boundary can be supplied through `asset_id`.
    Without that, the default is the FAO GAUL 2015 level-2 Dhaka boundary.
    """
    boundary_asset = asset_id or DHAKA_BOUNDARY_ASSET
    if boundary_asset:
        return ee.FeatureCollection(boundary_asset)

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
    return dhaka


def create_reference_zone(
    aoi: ee.FeatureCollection | ee.Geometry,
    buffer_km: float = DEFAULT_REFERENCE_BUFFER_KM,
) -> ee.FeatureCollection:
    """Create an outward buffer ring around Dhaka for SUHI reference LST.

    The reference zone is the buffered AOI minus the original AOI. This keeps
    the rural or peri-urban comparison area outside the main Dhaka boundary.
    """
    geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    buffer_m = float(buffer_km) * 1000.0
    buffered = geom.buffer(buffer_m, 1)
    ring = buffered.difference(geom, 1)
    return ee.FeatureCollection([ee.Feature(ring, {"zone": "reference", "buffer_km": buffer_km})])


def create_analysis_region(
    aoi: ee.FeatureCollection | ee.Geometry,
    reference_zone: ee.FeatureCollection | ee.Geometry,
) -> ee.FeatureCollection:
    """Return a region covering both Dhaka and the SUHI reference ring."""
    aoi_geom = aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)
    ref_geom = (
        reference_zone.geometry()
        if isinstance(reference_zone, ee.featurecollection.FeatureCollection)
        else ee.Geometry(reference_zone)
    )
    return ee.FeatureCollection([ee.Feature(aoi_geom.union(ref_geom, 1), {"zone": "analysis"})])
