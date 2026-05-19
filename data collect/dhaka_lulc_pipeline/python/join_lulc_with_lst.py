#!/usr/bin/env python
"""Join the 1 km LULC feature table with the extracted LST target table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lulc-table", type=Path, required=True, help="Combined LULC feature CSV")
    parser.add_argument("--lst-table", type=Path, required=True, help="Combined LST target CSV")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for joined model table")
    parser.add_argument("--target-col", default="lst_c", help="Target column from the LST table")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    lulc = pd.read_csv(args.lulc_table)
    lst = pd.read_csv(args.lst_table)

    for frame in (lulc, lst):
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")

    key_cols = ["grid_id", "year"]
    lst_keep_cols = [
        "grid_id",
        "year",
        args.target_col,
        "scene_count",
        "lst_c_median",
        "lst_c_stddev",
        "lst_c_min",
        "lst_c_max",
        "ndvi",
        "mean_pixel_obs_count",
        "valid_lst_ratio",
    ]
    lst_keep_cols = [col for col in lst_keep_cols if col in lst.columns]

    merged = lulc.merge(lst[lst_keep_cols], on=key_cols, how="left", indicator=True)
    trainable = merged[merged[args.target_col].notna()].copy()

    out_csv = args.output_dir / "combined_lulc_heat_model_table.csv"
    qc_path = args.output_dir / "join_qc_summary.json"

    trainable.to_csv(out_csv, index=False)

    qc = {
        "lulc_rows": int(len(lulc)),
        "lst_rows": int(len(lst)),
        "merged_rows": int(len(merged)),
        "matched_rows": int((merged["_merge"] == "both").sum()),
        "trainable_rows": int(len(trainable)),
        "coverage_ratio": float((merged["_merge"] == "both").mean()),
        "years": sorted([int(y) for y in trainable["year"].dropna().unique().tolist()]),
        "target_col": args.target_col,
        "target_mean_c": float(trainable[args.target_col].mean()),
        "target_std_c": float(trainable[args.target_col].std()),
    }

    with qc_path.open("w", encoding="utf-8") as handle:
        json.dump(qc, handle, indent=2)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {qc_path}")


if __name__ == "__main__":
    main()
