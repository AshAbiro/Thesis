#!/usr/bin/env python
"""Build a thesis-grade ML-ready LULC feature table from yearly GEE exports.

Input: CSV exports created by dhaka_lulc6_extraction.js
Output:
  - combined_lulc6_features.csv
  - combined_lulc6_features.parquet (optional)
  - qc_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

FEATURE_COLS = [
    "frac_built",
    "frac_vegetation",
    "frac_cropland",
    "frac_water",
    "frac_wetland",
    "frac_bare",
]

REQUIRED_COLS = [
    "grid_id",
    "year",
    "dominant_class",
    "mixed_flag",
    "valid_obs_ratio",
    *FEATURE_COLS,
]

CLASS_TO_NAME = {
    1: "built",
    2: "vegetation",
    3: "cropland",
    4: "water",
    5: "wetland",
    6: "bare",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True, help="Directory with yearly GEE CSV exports")
    p.add_argument("--glob", default="*_1km_features_table_*.csv", help="Input filename pattern")
    p.add_argument("--output-dir", type=Path, required=True, help="Directory for ML table outputs")
    p.add_argument("--renormalize", action="store_true", help="Renormalize fractions to sum=1 when possible")
    p.add_argument(
        "--sum-tol",
        type=float,
        default=0.02,
        help="Allowed absolute tolerance for fraction sum before flagging",
    )
    return p.parse_args()


def require_columns(df: pd.DataFrame, csv_path: Path) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {csv_path.name}: {missing}")


def enforce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["dominant_class"] = pd.to_numeric(out["dominant_class"], errors="coerce").astype("Int64")
    out["mixed_flag"] = pd.to_numeric(out["mixed_flag"], errors="coerce").astype("Int64")
    out["valid_obs_ratio"] = pd.to_numeric(out["valid_obs_ratio"], errors="coerce")

    for col in FEATURE_COLS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def recompute_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    frac_arr = out[FEATURE_COLS].to_numpy(dtype=float)
    safe_frac = np.nan_to_num(frac_arr, nan=-1.0)

    max_idx = safe_frac.argmax(axis=1)
    out["dominant_class_recomputed"] = np.where(safe_frac.max(axis=1) >= 0, max_idx + 1, np.nan)

    max_frac = safe_frac.max(axis=1)
    out["mixed_flag_recomputed"] = (max_frac < 0.50).astype(int)

    for class_id, name in CLASS_TO_NAME.items():
        out[f"oh_{name}"] = (out["dominant_class_recomputed"] == class_id).astype(int)

    return out


def normalize_fractions(df: pd.DataFrame, renormalize: bool) -> pd.DataFrame:
    out = df.copy()
    frac_sum = out[FEATURE_COLS].sum(axis=1)

    if renormalize:
        valid = (out["valid_obs_ratio"] > 0) & (frac_sum > 0)
        out.loc[valid, FEATURE_COLS] = out.loc[valid, FEATURE_COLS].div(frac_sum[valid], axis=0)

    for col in FEATURE_COLS:
        out[col] = out[col].clip(lower=0.0, upper=1.0)

    return out


def build_qc_summary(df: pd.DataFrame, sum_tol: float) -> Dict[str, object]:
    frac_sum = df[FEATURE_COLS].sum(axis=1)
    valid_mask = df["valid_obs_ratio"] > 0

    abs_err = (frac_sum - 1.0).abs()
    out_tol = (abs_err > sum_tol) & valid_mask

    qc = {
        "rows": int(len(df)),
        "years": sorted([int(y) for y in df["year"].dropna().unique().tolist()]),
        "fraction_sum_mean": float(frac_sum.mean()),
        "fraction_sum_std": float(frac_sum.std()),
        "fraction_sum_max_abs_error": float(abs_err.max()),
        "fraction_sum_out_of_tolerance_rows": int(out_tol.sum()),
        "missing_rows_any_required_col": int(df[REQUIRED_COLS].isna().any(axis=1).sum()),
        "dominant_mismatch_rows": int(
            (
                (df["dominant_class"].notna())
                & (df["dominant_class_recomputed"].notna())
                & (df["dominant_class"].astype(float) != df["dominant_class_recomputed"].astype(float))
            ).sum()
        ),
    }

    # Class distribution from recomputed dominant class
    dist = (
        df["dominant_class_recomputed"]
        .value_counts(dropna=False)
        .sort_index()
        .to_dict()
    )
    qc["dominant_class_distribution"] = {str(int(k)): int(v) for k, v in dist.items() if pd.notna(k)}

    return qc


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    csv_paths: List[Path] = sorted(args.input_dir.glob(args.glob))
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found: {args.input_dir} / pattern={args.glob}")

    frames = []
    for path in csv_paths:
        df = pd.read_csv(path)
        require_columns(df, path)
        df = enforce_numeric(df)
        df["source_file"] = path.name
        frames.append(df)

    data = pd.concat(frames, ignore_index=True)
    data = normalize_fractions(data, renormalize=args.renormalize)
    data = recompute_labels(data)

    out_csv = args.output_dir / "combined_lulc6_features.csv"
    out_parquet = args.output_dir / "combined_lulc6_features.parquet"
    out_qc = args.output_dir / "qc_summary.json"

    data.to_csv(out_csv, index=False)

    try:
        data.to_parquet(out_parquet, index=False)
        parquet_written = True
    except Exception:
        parquet_written = False

    qc = build_qc_summary(data, sum_tol=args.sum_tol)
    qc["parquet_written"] = parquet_written

    with out_qc.open("w", encoding="utf-8") as f:
        json.dump(qc, f, indent=2)

    print(f"Wrote: {out_csv}")
    if parquet_written:
        print(f"Wrote: {out_parquet}")
    print(f"Wrote: {out_qc}")


if __name__ == "__main__":
    main()
