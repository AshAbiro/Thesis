"""Earth Engine Drive and small local CSV export helpers."""

from __future__ import annotations

import csv
from pathlib import Path

import ee


def _as_geometry(region: ee.FeatureCollection | ee.Geometry) -> ee.Geometry:
    return region.geometry() if isinstance(region, ee.featurecollection.FeatureCollection) else ee.Geometry(region)


def export_table_to_drive(
    feature_collection: ee.FeatureCollection,
    description: str,
    folder: str,
    file_name: str,
) -> ee.batch.Task:
    """Start a Google Drive CSV export for a feature collection."""
    task = ee.batch.Export.table.toDrive(
        collection=feature_collection,
        description=description,
        folder=folder,
        fileNamePrefix=file_name,
        fileFormat="CSV",
    )
    task.start()
    return task


def export_image_to_drive(
    image: ee.Image,
    region: ee.FeatureCollection | ee.Geometry,
    description: str,
    folder: str,
    scale: int,
) -> ee.batch.Task:
    """Start a Google Drive GeoTIFF export for an image."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        fileNamePrefix=description,
        region=_as_geometry(region),
        scale=scale,
        maxPixels=1e13,
    )
    task.start()
    return task


def feature_collection_to_local_csv(
    fc: ee.FeatureCollection,
    output_path: str | Path,
    max_features: int = 5000,
) -> Path:
    """Write a small feature collection to a local CSV using getInfo().

    This is intentionally guarded for small tables only. Use Drive exports for
    full Dhaka grids or multi-year runs.
    """
    size = int(fc.size().getInfo())
    if size > max_features:
        raise ValueError(
            f"FeatureCollection has {size} rows. Use Drive export or raise max_features explicitly."
        )

    info = fc.getInfo()
    rows = [feature.get("properties", {}) for feature in info.get("features", [])]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output
