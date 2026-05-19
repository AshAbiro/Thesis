#!/usr/bin/env python
"""Lower-memory Dhaka LULC6 extractor using 1 km grid + reduceRegions.

Produces ML-ready per-year CSVs directly to local disk.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import ee


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--years", nargs="+", type=int, default=[2018, 2019, 2020, 2021, 2022, 2023, 2024])
    p.add_argument("--output-dir", type=Path, default=Path("c:/Users/abira/chrome/Thesis/data collect/dhaka_lulc_pipeline/output/raw_csv"))
    p.add_argument("--tile-scale", type=int, default=4)
    return p.parse_args()


def get_aoi() -> ee.Geometry:
    gaul2 = ee.FeatureCollection("FAO/GAUL/2015/level2")
    dhaka = (
        gaul2.filter(ee.Filter.eq("ADM0_NAME", "Bangladesh"))
        .filter(ee.Filter.eq("ADM1_NAME", "Dhaka"))
        .filter(ee.Filter.eq("ADM2_NAME", "Dhaka"))
    )
    return dhaka.geometry()


def get_esri_lulc6(year: int, aoi: ee.Geometry) -> ee.Image:
    start = ee.Date.fromYMD(year, 1, 1)
    end = start.advance(1, "year")
    col = (
        ee.ImageCollection("projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS")
        .filterBounds(aoi)
        .filterDate(start, end)
    )
    raw = col.mosaic().select(0).rename("esri_raw")
    lulc6 = raw.remap([1, 2, 4, 5, 7, 8, 11], [4, 2, 5, 3, 1, 6, 2], 0).rename("lulc6").toInt8()
    return lulc6.clip(aoi).updateMask(raw.neq(0))


def build_grid(aoi: ee.Geometry) -> ee.FeatureCollection:
    proj = ee.Projection("EPSG:32646").atScale(1000)
    grid = aoi.coveringGrid(proj, 1000)

    def set_id(feat: ee.Feature) -> ee.Feature:
        c = feat.geometry().centroid(1).coordinates()
        lon = ee.Number(c.get(0))
        lat = ee.Number(c.get(1))
        return feat.set({"longitude": lon, "latitude": lat})

    return ee.FeatureCollection(grid.map(set_id))


def feature_collection_to_df(fc: ee.FeatureCollection) -> pd.DataFrame:
    data = fc.getInfo()
    rows = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        rows.append(p)
    return pd.DataFrame(rows)


def process_year(year: int, grid: ee.FeatureCollection, aoi: ee.Geometry, tile_scale: int) -> pd.DataFrame:
    print(f"Processing {year} ...")
    lulc6 = get_esri_lulc6(year, aoi)

    area = ee.Image.pixelArea()
    img = ee.Image.cat([
        area.updateMask(lulc6.eq(1)).rename("a_built"),
        area.updateMask(lulc6.eq(2)).rename("a_vegetation"),
        area.updateMask(lulc6.eq(3)).rename("a_cropland"),
        area.updateMask(lulc6.eq(4)).rename("a_water"),
        area.updateMask(lulc6.eq(5)).rename("a_wetland"),
        area.updateMask(lulc6.eq(6)).rename("a_bare"),
        area.updateMask(lulc6.gt(0)).rename("a_valid"),
    ])

    stats = img.reduceRegions(
        collection=grid,
        reducer=ee.Reducer.sum(),
        scale=10,
        crs="EPSG:32646",
        tileScale=tile_scale,
    )

    df = feature_collection_to_df(stats)
    if df.empty:
        return df

    for c in ["a_built", "a_vegetation", "a_cropland", "a_water", "a_wetland", "a_bare", "a_valid"]:
        if c not in df.columns:
            df[c] = np.nan

    df["year"] = year

    denom = df["a_valid"].replace(0, np.nan)
    df["frac_built"] = df["a_built"] / denom
    df["frac_vegetation"] = df["a_vegetation"] / denom
    df["frac_cropland"] = df["a_cropland"] / denom
    df["frac_water"] = df["a_water"] / denom
    df["frac_wetland"] = df["a_wetland"] / denom
    df["frac_bare"] = df["a_bare"] / denom

    frac_cols = ["frac_built", "frac_vegetation", "frac_cropland", "frac_water", "frac_wetland", "frac_bare"]
    df[frac_cols] = df[frac_cols].fillna(0.0)

    frac_arr = df[frac_cols].to_numpy(dtype=float)
    frac_sum = frac_arr.sum(axis=1)
    nz = frac_sum > 0
    frac_arr[nz] = frac_arr[nz] / frac_sum[nz, None]

    for i, c in enumerate(frac_cols):
        df[c] = frac_arr[:, i]

    df["dominant_class"] = frac_arr.argmax(axis=1) + 1
    df["mixed_flag"] = (frac_arr.max(axis=1) < 0.50).astype(int)
    df["valid_obs_ratio"] = (df["a_valid"] / 1_000_000.0).clip(0, 1)

    dom = df["dominant_class"].astype(int)
    df["oh_built"] = (dom == 1).astype(int)
    df["oh_vegetation"] = (dom == 2).astype(int)
    df["oh_cropland"] = (dom == 3).astype(int)
    df["oh_water"] = (dom == 4).astype(int)
    df["oh_wetland"] = (dom == 5).astype(int)
    df["oh_bare"] = (dom == 6).astype(int)

    df["grid_id"] = (
        "Y"
        + df["year"].astype(int).astype(str)
        + "_LAT"
        + df["latitude"].astype(float).round(5).astype(str)
        + "_LON"
        + df["longitude"].astype(float).round(5).astype(str)
    )

    keep = [
        "grid_id",
        "year",
        "longitude",
        "latitude",
        "frac_built",
        "frac_vegetation",
        "frac_cropland",
        "frac_water",
        "frac_wetland",
        "frac_bare",
        "dominant_class",
        "oh_built",
        "oh_vegetation",
        "oh_cropland",
        "oh_water",
        "oh_wetland",
        "oh_bare",
        "mixed_flag",
        "valid_obs_ratio",
        "a_valid",
    ]

    return df[keep].sort_values(["latitude", "longitude"]).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ee.Initialize()
    aoi = get_aoi()
    grid = build_grid(aoi)

    all_frames = []
    rows_per_year = {}

    for y in args.years:
        df = process_year(y, grid, aoi, args.tile_scale)
        if df.empty:
            print(f"  No output for {y}")
            continue
        out = args.output_dir / f"dhaka_lulc6_1km_features_table_{y}.csv"
        df.to_csv(out, index=False)
        print(f"  Wrote: {out} ({len(df)} rows)")
        rows_per_year[str(y)] = int(len(df))
        all_frames.append(df)

    if not all_frames:
        raise RuntimeError("No outputs produced")

    combined = pd.concat(all_frames, ignore_index=True)
    combined_path = args.output_dir / "combined_lulc6_features_raw.csv"
    combined.to_csv(combined_path, index=False)

    frac_cols = ["frac_built", "frac_vegetation", "frac_cropland", "frac_water", "frac_wetland", "frac_bare"]
    qc = {
        "years": args.years,
        "rows_per_year": rows_per_year,
        "total_rows": int(len(combined)),
        "fraction_sum_mean": float(combined[frac_cols].sum(axis=1).mean()),
        "fraction_sum_std": float(combined[frac_cols].sum(axis=1).std()),
    }
    qc_path = args.output_dir / "extract_qc_summary.json"
    with qc_path.open("w", encoding="utf-8") as f:
        json.dump(qc, f, indent=2)

    print(f"Wrote: {combined_path}")
    print(f"Wrote: {qc_path}")


if __name__ == "__main__":
    main()
