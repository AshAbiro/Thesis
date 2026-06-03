"""Merge final division preprocessing outputs into Bangladesh-level datasets.

The final division CSVs are large, so this script writes compressed CSV files.
It intentionally builds national model-ready tables from common Config-A/B
features instead of concatenating per-division scaled outputs, because each
division's scaled files were fitted with that division's own scaler.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import pandas as pd


FINAL_SUFFIX = "_2015_2025_v2_4_final"
TARGET = "lst_c_mean"
CONTEXT_COLS = ["division", "district", "grid_id", "grid_x", "grid_y", "year", "season"]
MODEL_PREFIX_COLS = ["split", TARGET]


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ordered_common(feature_lists: list[list[str]]) -> list[str]:
    if not feature_lists:
        return []
    common = set(feature_lists[0])
    for features in feature_lists[1:]:
        common &= set(features)
    return [feature for feature in feature_lists[0] if feature in common]


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Bangladesh Merge Report",
        "",
        f"- Rows: {report['rows']['combined']:,}",
        f"- Divisions: {', '.join(report['dataset_identity']['divisions'])}",
        f"- Years: {report['dataset_identity']['years']}",
        f"- Seasons: {report['dataset_identity']['seasons']}",
        f"- Null {TARGET}: {report['quality_checks']['null_lst_c_mean']}",
        f"- Zero {TARGET}: {report['quality_checks']['zero_lst_c_mean']}",
        f"- Config A common features: {len(report['feature_sets']['config_a_common_features'])}",
        f"- Config B common features: {len(report['feature_sets']['config_b_common_features'])}",
        "",
        "## Splits",
        "",
    ]
    for split, count in report["rows"]["by_split"].items():
        lines.append(f"- {split}: {count:,}")
    lines += ["", "## Division Rows", ""]
    for division, count in report["rows"]["by_division"].items():
        lines.append(f"- {division}: {count:,}")
    lines += ["", "## Outputs", ""]
    for name, path_value in report["outputs"].items():
        lines.append(f"- `{name}`: `{path_value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge_outputs(input_root: Path, output_dir: Path, chunksize: int) -> dict:
    division_dirs = sorted(
        path for path in input_root.glob(f"*{FINAL_SUFFIX}")
        if path.is_dir() and (path / "preprocessed_combined.csv").is_file()
    )
    if not division_dirs:
        raise FileNotFoundError(f"No final division folders found in {input_root}")

    output_dir.mkdir(parents=True, exist_ok=True)

    metas = [_read_json(path / "preprocessing_meta.json") for path in division_dirs]
    reports = [_read_json(path / "preprocessing_report.json") for path in division_dirs]
    config_a_common = _ordered_common([meta["config_a"]["features"] for meta in metas])
    config_b_common = _ordered_common([meta["config_b"]["features"] for meta in metas])

    union_cols: list[str] = []
    for path in division_dirs:
        cols = pd.read_csv(path / "preprocessed_combined.csv", nrows=0).columns.tolist()
        for col in cols:
            if col not in union_cols:
                union_cols.append(col)

    config_a_cols = MODEL_PREFIX_COLS + config_a_common
    config_b_cols = MODEL_PREFIX_COLS + config_b_common
    missing_a = sorted(set(config_a_cols) - set(union_cols))
    missing_b = sorted(set(config_b_cols) - set(union_cols))
    if missing_a or missing_b:
        raise ValueError(
            "Common feature columns are missing from preprocessed schemas: "
            f"Config A missing={missing_a}; Config B missing={missing_b}"
        )

    outputs = {
        "preprocessed_combined.csv.gz": output_dir / "preprocessed_combined.csv.gz",
        "model_ready_config_a_common.csv.gz": output_dir / "model_ready_config_a_common.csv.gz",
        "model_ready_config_b_common.csv.gz": output_dir / "model_ready_config_b_common.csv.gz",
        "bangladesh_feature_sets.json": output_dir / "bangladesh_feature_sets.json",
        "bangladesh_merge_report.json": output_dir / "bangladesh_merge_report.json",
        "bangladesh_merge_report.md": output_dir / "bangladesh_merge_report.md",
    }

    stats = {
        "combined": 0,
        "by_split": {},
        "by_division": {},
        "null_target": 0,
        "zero_target": 0,
    }

    with gzip.open(outputs["preprocessed_combined.csv.gz"], "wt", encoding="utf-8", newline="") as full_out, \
            gzip.open(outputs["model_ready_config_a_common.csv.gz"], "wt", encoding="utf-8", newline="") as a_out, \
            gzip.open(outputs["model_ready_config_b_common.csv.gz"], "wt", encoding="utf-8", newline="") as b_out:
        full_header = True
        a_header = True
        b_header = True
        for path in division_dirs:
            source = path / "preprocessed_combined.csv"
            print(f"[Merge] {source}")
            for chunk in pd.read_csv(source, chunksize=chunksize, low_memory=False):
                stats["combined"] += len(chunk)
                if "split" in chunk.columns:
                    for split, count in chunk["split"].value_counts(dropna=False).items():
                        stats["by_split"][str(split)] = stats["by_split"].get(str(split), 0) + int(count)
                if "division" in chunk.columns:
                    for division, count in chunk["division"].value_counts(dropna=False).items():
                        stats["by_division"][str(division)] = stats["by_division"].get(str(division), 0) + int(count)
                stats["null_target"] += int(chunk[TARGET].isna().sum())
                stats["zero_target"] += int((chunk[TARGET] == 0).sum())

                chunk.reindex(columns=union_cols).to_csv(full_out, index=False, header=full_header)
                chunk.reindex(columns=config_a_cols).to_csv(a_out, index=False, header=a_header)
                chunk.reindex(columns=config_b_cols).to_csv(b_out, index=False, header=b_header)
                full_header = False
                a_header = False
                b_header = False

    all_divisions = sorted(
        division
        for report in reports
        for division in report["dataset_identity"].get("divisions", [])
    )
    all_years = sorted({
        int(year)
        for report in reports
        for year in report["dataset_identity"].get("years", [])
    })
    all_seasons = sorted({
        season
        for report in reports
        for season in report["dataset_identity"].get("seasons", [])
    })
    duplicate_key_total = sum(
        int(report["quality_checks"].get("duplicate_panel_keys") or 0)
        for report in reports
    )

    feature_sets = {
        "target": TARGET,
        "context_columns": CONTEXT_COLS,
        "model_prefix_columns": MODEL_PREFIX_COLS,
        "config_a_common_features": config_a_common,
        "config_b_common_features": config_b_common,
        "config_a_note": "Common Config-A features present in every division run; use for driver/interpretation models.",
        "config_b_note": "Common Config-B features present in every division run; use for predictive/forecasting models.",
        "scaling_note": (
            "These merged tables are not pre-scaled. Fit any scaler on the Bangladesh train split "
            "inside the modeling workflow to avoid mixing per-division scalers."
        ),
    }

    report = {
        "merge_name": "Bangladesh_2015_2025_v2_4_merged",
        "source_division_folders": [str(path.resolve()) for path in division_dirs],
        "rows": {
            "combined": int(stats["combined"]),
            "by_split": {key: int(value) for key, value in sorted(stats["by_split"].items())},
            "by_division": {key: int(value) for key, value in sorted(stats["by_division"].items())},
        },
        "dataset_identity": {
            "divisions": all_divisions,
            "years": all_years,
            "seasons": all_seasons,
        },
        "quality_checks": {
            "source_duplicate_panel_keys_total": int(duplicate_key_total),
            "null_lst_c_mean": int(stats["null_target"]),
            "zero_lst_c_mean": int(stats["zero_target"]),
            "duplicate_key_note": (
                "Duplicate keys are validated per source division report using "
                "division/district/grid_id/year/season."
            ),
        },
        "feature_sets": feature_sets,
        "outputs": {name: str(path.resolve()) for name, path in outputs.items()},
    }

    _write_json(outputs["bangladesh_feature_sets.json"], feature_sets)
    _write_json(outputs["bangladesh_merge_report.json"], report)
    _write_markdown(outputs["bangladesh_merge_report.md"], report)
    for name, path in outputs.items():
        size_mb = path.stat().st_size / 1024**2
        print(f"[Write] {name} ({size_mb:.1f} MB)")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=Path("Preprocessed Files"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Preprocessed Files") / "Bangladesh_2015_2025_v2_4_merged",
    )
    parser.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()
    merge_outputs(args.input_root, args.output_dir, args.chunksize)


if __name__ == "__main__":
    main()
