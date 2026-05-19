"""Fixed analysis grid generation."""

from __future__ import annotations

import ee

from config import DEFAULT_GRID_CRS, DEFAULT_GRID_SIZE_M, GRID_ID_PROPERTY


def _as_geometry(aoi: ee.FeatureCollection | ee.Geometry) -> ee.Geometry:
    return aoi.geometry() if isinstance(aoi, ee.featurecollection.FeatureCollection) else ee.Geometry(aoi)


def create_grid(
    aoi: ee.FeatureCollection | ee.Geometry,
    grid_size_m: int = DEFAULT_GRID_SIZE_M,
    crs: str = DEFAULT_GRID_CRS,
) -> ee.FeatureCollection:
    """Generate a fixed square grid over Dhaka with a unique `grid_id`.

    Parameters
    ----------
    aoi:
        Dhaka study-area boundary.
    grid_size_m:
        Cell size in meters. Use 1000 for 1 km grids or 500 for 500 m grids.
    crs:
        Projected CRS used to create equal-size meter-based cells.
    """
    if grid_size_m not in (500, 1000):
        raise ValueError("grid_size_m must be 500 or 1000 for this thesis workflow.")

    geom = _as_geometry(aoi)
    projection = ee.Projection(crs).atScale(grid_size_m)
    coords = ee.Image.pixelCoordinates(projection)
    x = coords.select("x").toInt64()
    y = coords.select("y").toInt64()
    grid_code = x.multiply(1000000).add(y).toInt64().rename("grid_code")
    grid_image = grid_code.addBands([x.rename("grid_x"), y.rename("grid_y")])

    vectors = grid_image.reduceToVectors(
        geometry=geom,
        crs=projection,
        scale=grid_size_m,
        geometryType="polygon",
        labelProperty="grid_code",
        reducer=ee.Reducer.first(),
        maxPixels=1e13,
        tileScale=4,
    )

    def add_grid_id(cell: ee.Feature) -> ee.Feature:
        cell = ee.Feature(cell)
        grid_code_value = ee.Number(cell.get("grid_code")).format("%.0f")
        grid_id = ee.String("g_").cat(grid_code_value)
        area_m2 = cell.geometry().area(1)
        return cell.set(
            {
                GRID_ID_PROPERTY: grid_id,
                "grid_size_m": grid_size_m,
                "grid_crs": crs,
                "cell_area_m2": area_m2,
            }
        )

    return vectors.map(add_grid_id).filter(ee.Filter.gt("cell_area_m2", 0))
