"""Spectral index calculation from harmonized Landsat bands."""

from __future__ import annotations

import ee


def _normalized_difference(image: ee.Image, band_a: str, band_b: str, out_name: str) -> ee.Image:
    numerator = image.select(band_a).subtract(image.select(band_b))
    denominator = image.select(band_a).add(image.select(band_b))
    index = numerator.divide(denominator.where(denominator.abs().lt(1e-6), 1e-6))
    return index.rename(out_name)


def add_spectral_indices(image: ee.Image) -> ee.Image:
    """Add NDVI, NDWI, MNDWI, NDMI, NDBI, and broadband albedo bands."""
    ndvi = _normalized_difference(image, "nir", "red", "ndvi")
    ndwi = _normalized_difference(image, "green", "nir", "ndwi")
    mndwi = _normalized_difference(image, "green", "swir1", "mndwi")
    ndmi = _normalized_difference(image, "nir", "swir1", "ndmi")
    ndbi = _normalized_difference(image, "swir1", "nir", "ndbi")

    # Liang-style Landsat broadband shortwave albedo approximation.
    albedo = (
        image.select("blue").multiply(0.356)
        .add(image.select("red").multiply(0.130))
        .add(image.select("nir").multiply(0.373))
        .add(image.select("swir1").multiply(0.085))
        .add(image.select("swir2").multiply(0.072))
        .subtract(0.0018)
        .clamp(0, 1)
        .rename("albedo")
    )

    return image.addBands([ndvi, ndwi, mndwi, ndmi, ndbi, albedo], overwrite=True)
