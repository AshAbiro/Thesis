#!/usr/bin/env python
"""Extract a 1 km Landsat surface temperature target table from Earth Engine.

The default target is a Dhaka heat-season composite (April-August) for each
year, aggregated to the same 1 km grid used by the LULC feature pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import ee


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2018, 2019, 2020, 2021, 2022, 2023, 2024])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("c:/Users/abira/chrome/Thesis/data collect/dhaka_lulc_pipeline/output/lst_csv"),
    )
    parser.add_argument("--tile-scale", type=int, default=4)
    parser.add_argument("--start-month", type=int, default=4, help="First month of the seasonal window")
    parser.add_argument("--end-month", type=int, default=8, help="Last month of the seasonal window")
    parser.add_argument("--cloud-cover-max", type=float, default=70.0)
    return parser.parse_args()


def get_aoi() -> ee.Geometry:
    gaul2 = ee.FeatureCollection("FAO/GAUL/2015/level2")
    dhaka = (
        gaul2.filter(ee.Filter.eq("ADM0_NAME", "Bangladesh"))
        .filter(ee.Filter.eq("ADM1_NAME", "Dhaka"))
        .filter(ee.Filter.eq("ADM2_NAME", "Dhaka"))
    )
    return dhaka.geometry()


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
    for feature in data.get("features", []):
        rows.append(feature.get("properties", {}))
    return pd.DataFrame(rows)


def preprocess_landsat(image: ee.Image) -> ee.Image:
    # Collection 2 Level-2 QA mask for Landsat 8/9:
    # fill, dilated cloud, cirrus, cloud, cloud shadow all cleared.
    qa_mask = image.select("QA_PIXEL").bitwiseAnd(int("11111", 2)).eq(0)
    sat_mask = image.select("QA_RADSAT").eq(0)

    red_nir = image.select(["SR_B4", "SR_B5"], ["red", "nir"]).multiply(0.0000275).add(-0.2)
    ndvi = red_nir.normalizedDifference(["nir", "red"]).rename("ndvi")

    lst_c = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("lst_c")

    return (
        ee.Image.cat([lst_c, ndvi])
        .updateMask(qa_mask)
        .updateMask(sat_mask)
        .copyProperties(image, ["system:time_start"])
    )


def seasonal_landsat_collection(
    year: int,
    aoi: ee.Geometry,
    start_month: int,
    end_month: int,
    cloud_cover_max: float,
) -> ee.ImageCollection:
    start = ee.Date.fromYMD(year, start_month, 1)
    end = ee.Date.fromYMD(year, end_month, 1).advance(1, "month")

    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")

    return (
        l8.merge(l9)
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("PROCESSING_LEVEL", "L2SP"))
        .filter(ee.Filter.lte("CLOUD_COVER", cloud_cover_max))
        .map(preprocess_landsat)
    )


def build_lst_composite(col: ee.ImageCollection, aoi: ee.Geometry) -> ee.Image:
    lst_c = col.select("lst_c").median().clip(aoi).rename("lst_c")
    ndvi = col.select("ndvi").median().clip(aoi).rename("ndvi")
    obs_count = col.select("lst_c").count().clip(aoi).rename("lst_obs_count")
    valid = ee.Image(1).updateMask(lst_c.mask()).rename("lst_valid").unmask(0)
    return ee.Image.cat([lst_c, ndvi, obs_count, valid])


def process_year(
    year: int,
    grid: ee.FeatureCollection,
    aoi: ee.Geometry,
    start_month: int,
    end_month: int,
    cloud_cover_max: float,
    tile_scale: int,
) -> tuple[pd.DataFrame, int]:
    print(f"Processing LST for {year} ({start_month:02d}-{end_month:02d}) ...")

    col = seasonal_landsat_collection(year, aoi, start_month, end_month, cloud_cover_max)
    scene_count = int(col.size().getInfo())
    if scene_count == 0:
        return pd.DataFrame(), 0

    composite = build_lst_composite(col, aoi)

    reducer = (
        ee.Reducer.mean()
        .combine(reducer2=ee.Reducer.median(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.stdDev(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.minMax(), sharedInputs=True)
    )

    stats = composite.reduceRegions(
        collection=grid,
        reducer=reducer,
        scale=30,
        crs="EPSG:32646",
        tileScale=tile_scale,
    )

    df = feature_collection_to_df(stats)
    if df.empty:
        return df, scene_count

    for col_name in [
        "lst_c_mean",
        "lst_c_median",
        "lst_c_stdDev",
        "lst_c_min",
        "lst_c_max",
        "ndvi_mean",
        "lst_obs_count_mean",
        "lst_valid_mean",
        "longitude",
        "latitude",
    ]:
        if col_name not in df.columns:
            df[col_name] = np.nan

    df["year"] = year
    df["scene_count"] = scene_count
    df["lst_c"] = pd.to_numeric(df["lst_c_mean"], errors="coerce")
    df["lst_c_median"] = pd.to_numeric(df["lst_c_median"], errors="coerce")
    df["lst_c_stddev"] = pd.to_numeric(df["lst_c_stdDev"], errors="coerce")
    df["lst_c_min"] = pd.to_numeric(df["lst_c_min"], errors="coerce")
    df["lst_c_max"] = pd.to_numeric(df["lst_c_max"], errors="coerce")
    df["ndvi"] = pd.to_numeric(df["ndvi_mean"], errors="coerce")
    df["mean_pixel_obs_count"] = pd.to_numeric(df["lst_obs_count_mean"], errors="coerce")
    df["valid_lst_ratio"] = pd.to_numeric(df["lst_valid_mean"], errors="coerce")

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
        "scene_count",
        "lst_c",
        "lst_c_median",
        "lst_c_stddev",
        "lst_c_min",
        "lst_c_max",
        "ndvi",
        "mean_pixel_obs_count",
        "valid_lst_ratio",
    ]
    return df[keep].sort_values(["latitude", "longitude"]).reset_index(drop=True), scene_count


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ee.Initialize()
    aoi = get_aoi()
    grid = build_grid(aoi)

    frames = []
    rows_per_year: dict[str, int] = {}
    scenes_per_year: dict[str, int] = {}

    for year in args.years:
        df, scene_count = process_year(
            year=year,
            grid=grid,
            aoi=aoi,
            start_month=args.start_month,
            end_month=args.end_month,
            cloud_cover_max=args.cloud_cover_max,
            tile_scale=args.tile_scale,
        )
        scenes_per_year[str(year)] = int(scene_count)
        if df.empty:
            print(f"  No LST output for {year}")
            continue

        out = args.output_dir / f"dhaka_lst_1km_target_table_{year}.csv"
        df.to_csv(out, index=False)
        print(f"  Wrote: {out} ({len(df)} rows, {scene_count} scenes)")
        rows_per_year[str(year)] = int(len(df))
        frames.append(df)

    if not frames:
        raise RuntimeError("No LST outputs produced")

    combined = pd.concat(frames, ignore_index=True)
    combined_path = args.output_dir / "combined_lst_targets.csv"
    qc_path = args.output_dir / "extract_lst_qc_summary.json"

    combined.to_csv(combined_path, index=False)

    qc = {
        "years": args.years,
        "season_window": {
            "start_month": args.start_month,
            "end_month": args.end_month,
        },
        "cloud_cover_max": args.cloud_cover_max,
        "rows_per_year": rows_per_year,
        "scenes_per_year": scenes_per_year,
        "total_rows": int(len(combined)),
        "missing_target_rows": int(combined["lst_c"].isna().sum()),
        "target_mean_c": float(combined["lst_c"].dropna().mean()),
        "target_std_c": float(combined["lst_c"].dropna().std()),
        "valid_lst_ratio_mean": float(combined["valid_lst_ratio"].dropna().mean()),
    }

    with qc_path.open("w", encoding="utf-8") as handle:
        json.dump(qc, handle, indent=2)

    print(f"Wrote: {combined_path}")
    print(f"Wrote: {qc_path}")


if __name__ == "__main__":
    main()
