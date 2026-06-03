"""Run the preprocessing pipeline for one or more exported GEE CSV files."""

from __future__ import annotations

import argparse
import importlib.util as importlib_util
import importlib.util
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUNNER_VERSION = "2.4"


def _load_pipeline_module(path: Path):
    spec = importlib.util.spec_from_file_location("selected_preprocessing_pipeline", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load preprocessing pipeline: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _metadata_for_json(meta: dict, pipe, inputs: list[Path], pipeline_file: Path) -> dict:
    result = {key: value for key, value in meta.items() if key not in {"scaler", "scaler_b"}}
    result["runner_version"] = RUNNER_VERSION
    result["input_files"] = [str(path.resolve()) for path in inputs]
    result["pipeline_file"] = str(pipeline_file.resolve())
    result["expected_dataset_identity"] = {
        "divisions": getattr(pipe, "expected_divisions", None),
        "years": getattr(pipe, "expected_years", None),
        "seasons": getattr(pipe, "expected_seasons", None),
    }
    result["scaler_mean"] = getattr(pipe._scaler, "mean_", np.array([]))
    result["scaler_scale"] = getattr(pipe._scaler, "scale_", np.array([]))
    result["scaler_b_mean"] = getattr(pipe._scaler_b, "mean_", np.array([]))
    result["scaler_b_scale"] = getattr(pipe._scaler_b, "scale_", np.array([]))
    result["feature_sets"] = {
        "config_a_features": meta.get("config_a_cols", []),
        "config_b_features": meta.get("config_b_cols", []),
        "config_a_scaled_features": [f"{col}_scaled" for col in meta.get("scale_cols", [])],
        "config_b_scaled_features": [f"{col}_scaled_b" for col in meta.get("scale_cols_b", [])],
    }
    result["audits"] = {
        "raw_panel_integrity": meta.get("raw_panel_audit", {}),
        "dataset_identity": meta.get("dataset_identity_audit", {}),
    }
    result["column_roles"] = {
        "target": meta.get("target", "lst_c_mean"),
        "split_column": "split",
        "id_context_columns": meta.get("id_cols", []),
        "passthrough_not_features": ["lst_c_max", "suhi_mean", "suhi_max", "reference_lst_mean"],
        "config_a_claim": meta.get("config_a_claim", ""),
        "config_b_claim": meta.get("config_b_claim", ""),
        "config_a_description": meta.get("config_a_description", ""),
        "config_b_description": meta.get("config_b_description", ""),
    }
    result["output_schema"] = {
        "preprocessed_combined.csv": "Full cleaned table with IDs, targets, context, and engineered columns.",
        "model_ready_config_a.csv": "Only split + target + Config-A feature columns.",
        "model_ready_config_b.csv": "Only split + target + Config-B feature columns.",
        "model_ready_config_a_scaled.csv": "Only split + target + Config-A scaled feature columns.",
        "model_ready_config_b_scaled.csv": "Only split + target + Config-B scaled feature columns.",
        "model_ready_config_a_train_scaled.csv": "Train split with Config-A scaled feature columns.",
        "model_ready_config_a_val_scaled.csv": "Validation split with Config-A scaled feature columns.",
        "model_ready_config_a_test_scaled.csv": "Test split with Config-A scaled feature columns.",
        "model_ready_config_b_train_scaled.csv": "Train split with Config-B scaled feature columns.",
        "model_ready_config_b_val_scaled.csv": "Validation split with Config-B scaled feature columns.",
        "model_ready_config_b_test_scaled.csv": "Test split with Config-B scaled feature columns.",
        "preprocessing_meta.json": "Simplified metadata for quick inspection and downstream scripts.",
        "missingness_report.csv": "Per-column missingness for train, val, test, and combined outputs.",
        "dropped_features_report.csv": "Feature removal reasons from hard drops and feature selection.",
        "feature_role_table.csv": "Column role table for target, IDs, passthrough, features, and leakage exclusions.",
        "preprocessing_report.json": "Compact validation/report summary for this run.",
        "preprocessing_report.md": "Human-readable validation/report summary for this run.",
    }
    return _json_ready(result)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)
    print(f"[Write] {path} ({len(df):,} rows x {df.shape[1]} columns)")


def _model_ready_columns(df: pd.DataFrame, feature_cols: list[str]) -> list[str]:
    """Columns safe for direct supervised training tables.

    Full context columns remain in preprocessed_combined.csv. These compact files
    intentionally avoid SUHI/reference/ID columns so downstream scripts cannot
    accidentally treat them as predictors.
    """
    ordered = ["split", "lst_c_mean"] + feature_cols
    return list(dict.fromkeys(col for col in ordered if col in df.columns))


def _scaled_model_ready_columns(
    df: pd.DataFrame,
    feature_cols: list[str],
    suffix: str,
) -> list[str]:
    scaled_features = [f"{col}{suffix}" for col in feature_cols]
    ordered = ["split", "lst_c_mean"] + scaled_features
    return list(dict.fromkeys(col for col in ordered if col in df.columns))


def _split_counts(df: pd.DataFrame) -> dict:
    if "split" not in df.columns:
        return {}
    counts = df["split"].value_counts(dropna=False).to_dict()
    return {str(key): int(value) for key, value in counts.items()}


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(payload), handle, indent=2)
    print(f"[Write] {path}")


def _simplified_meta(meta_json: dict, output_files: dict[str, Path]) -> dict:
    return {
        "pipeline": {
            "name": meta_json.get("pipeline_name"),
            "version": meta_json.get("pipeline_version"),
            "runner_version": meta_json.get("runner_version"),
            "file": meta_json.get("pipeline_file"),
        },
        "expected_dataset_identity": meta_json.get("expected_dataset_identity", {}),
        "observed_dataset_identity": meta_json.get("dataset_identity_audit", {}),
        "target": meta_json.get("target", "lst_c_mean"),
        "splits": {
            "train_years": meta_json.get("train_years", []),
            "val_years": meta_json.get("val_years", []),
            "test_years": meta_json.get("test_years", []),
        },
        "config_a": {
            "description": meta_json.get("config_a_description", ""),
            "feature_count": len(meta_json["feature_sets"]["config_a_features"]),
            "features": meta_json["feature_sets"]["config_a_features"],
            "scaled_features": meta_json["feature_sets"]["config_a_scaled_features"],
        },
        "config_b": {
            "description": meta_json.get("config_b_description", ""),
            "feature_count": len(meta_json["feature_sets"]["config_b_features"]),
            "features": meta_json["feature_sets"]["config_b_features"],
            "scaled_features": meta_json["feature_sets"]["config_b_scaled_features"],
        },
        "unit_fits": {
            "impervious_divisor": meta_json.get("impervious_divisor"),
            "water_occurrence_multiplier": meta_json.get("water_occurrence_multiplier"),
        },
        "spatial_lags": {
            "radius_km": meta_json.get("spatial_lag_radius_km"),
            "grid_scale_km": meta_json.get("grid_scale_km"),
            "radius_grid_units": (
                meta_json.get("spatial_lag_radius_km") / meta_json.get("grid_scale_km")
                if meta_json.get("spatial_lag_radius_km") is not None
                and meta_json.get("grid_scale_km") not in (None, 0)
                else None
            ),
        },
        "dropped_feature_counts": {
            "unusable": len(meta_json.get("dropped_unusable", [])),
            "high_missing": len(meta_json.get("dropped_high_missing", [])),
            "spearman": len(meta_json.get("dropped_by_spearman", [])),
            "vif": len(meta_json.get("dropped_by_vif", [])),
        },
        "outputs": {name: str(path.resolve()) for name, path in output_files.items()},
    }


def _missingness_report(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for split, frame in frames.items():
        total = len(frame)
        for col in frame.columns:
            missing = int(frame[col].isna().sum())
            rows.append(
                {
                    "split": split,
                    "column": col,
                    "dtype": str(frame[col].dtype),
                    "missing_count": missing,
                    "missing_pct": (100.0 * missing / total) if total else 0.0,
                    "non_missing_count": int(total - missing),
                    "row_count": int(total),
                }
            )
    return pd.DataFrame(rows)


def _dropped_features_report(
    meta_json: dict,
    raw_columns: list[str],
    pipeline_module,
) -> pd.DataFrame:
    rows = []

    def add_many(features, stage, reason):
        for feature in features:
            rows.append({"feature": feature, "stage": stage, "reason": reason})

    hard_drop_cols = [
        col for col in getattr(pipeline_module, "HARD_DROP_COLS", [])
        if col in raw_columns
    ]
    add_many(
        hard_drop_cols,
        "hard_drop",
        "Definitionally redundant, leakage-prone, scale-dependent, or intentionally excluded before modeling.",
    )
    add_many(
        meta_json.get("dropped_unusable", []),
        "feature_selection_unusable",
        "All-null or constant after preprocessing; cannot contribute signal.",
    )
    add_many(
        meta_json.get("dropped_high_missing", []),
        "feature_selection_high_missing",
        "Missingness exceeded max_feature_missingness threshold.",
    )
    add_many(
        meta_json.get("dropped_by_spearman", []),
        "feature_selection_spearman",
        "Removed by high absolute Spearman correlation pruning.",
    )
    add_many(
        meta_json.get("dropped_by_vif", []),
        "feature_selection_vif",
        "Removed by VIF multicollinearity pruning.",
    )
    return pd.DataFrame(rows, columns=["feature", "stage", "reason"])


def _feature_role_table(meta_json: dict, pipeline_module) -> pd.DataFrame:
    rows_by_col = {}

    def add(column, role, in_config_a=False, in_config_b=False, notes=""):
        if not column:
            return
        existing = rows_by_col.setdefault(
            column,
            {
                "column": column,
                "role": role,
                "in_config_a": bool(in_config_a),
                "in_config_b": bool(in_config_b),
                "notes": notes,
            },
        )
        if existing["role"] != role and role not in existing["role"].split("; "):
            existing["role"] += f"; {role}"
        existing["in_config_a"] = existing["in_config_a"] or bool(in_config_a)
        existing["in_config_b"] = existing["in_config_b"] or bool(in_config_b)
        if notes and notes not in existing["notes"]:
            existing["notes"] = (existing["notes"] + "; " + notes).strip("; ")

    config_a = set(meta_json["feature_sets"]["config_a_features"])
    config_b = set(meta_json["feature_sets"]["config_b_features"])
    target = meta_json.get("target", "lst_c_mean")
    add(target, "target", notes="Primary supervised target, never a predictor.")

    for col in meta_json.get("id_cols", []):
        add(col, "id_context", notes="Kept for joining, grouping, validation, and mapping; not a model feature.")

    for col in meta_json.get("column_roles", {}).get("passthrough_not_features", []):
        add(col, "passthrough_not_feature", notes="Context/secondary target column; not a predictor.")

    for col in sorted(config_a):
        add(col, "config_a_feature", in_config_a=True, in_config_b=col in config_b)
    for col in sorted(config_b - config_a):
        if col in set(meta_json.get("target_lag_features", [])):
            add(
                col,
                "config_b_only_target_lag",
                in_config_b=True,
                notes="Predictive/nowcasting only; do not use for causal interpretation.",
            )
        elif col in set(meta_json.get("thermal_features", [])):
            add(
                col,
                "config_b_only_thermal",
                in_config_b=True,
                notes="Same-season thermal/emissivity predictor; predictive/nowcasting only.",
            )
        else:
            add(col, "config_b_only_feature", in_config_b=True, notes="Predictive-only feature.")

    leakage_excluded = set(getattr(pipeline_module, "TARGET_COLS", []))
    leakage_excluded.update(getattr(pipeline_module, "PASSTHROUGH_COLS", []))
    leakage_excluded.update(["suhi_derived", "reference_lst_derived", "lst_background_du", "suhi_du"])
    for col in sorted(leakage_excluded):
        add(col, "leakage_excluded", notes="Excluded from Config A/B feature lists.")

    for col in getattr(pipeline_module, "HARD_DROP_COLS", []):
        add(col, "hard_drop", notes="Dropped before feature selection.")
    for col in meta_json.get("dropped_unusable", []):
        add(col, "dropped_unusable", notes="All-null or constant.")
    for col in meta_json.get("dropped_high_missing", []):
        add(col, "dropped_high_missing", notes="Exceeded missingness threshold.")
    for col in meta_json.get("dropped_by_spearman", []):
        add(col, "dropped_spearman", notes="Removed by Spearman correlation pruning.")
    for col in meta_json.get("dropped_by_vif", []):
        add(col, "dropped_vif", notes="Removed by VIF pruning.")

    rows = sorted(rows_by_col.values(), key=lambda row: (row["role"], row["column"]))
    return pd.DataFrame(rows, columns=["column", "role", "in_config_a", "in_config_b", "notes"])


def _write_preprocessing_reports(
    output_dir: Path,
    combined: pd.DataFrame,
    meta_json: dict,
    output_files: dict[str, Path],
) -> None:
    target = meta_json["column_roles"]["target"]
    duplicate_keys = ["division", "district", "grid_id", "year", "season"]
    duplicate_keys = [col for col in duplicate_keys if col in combined.columns]
    summary = {
        "runner_version": RUNNER_VERSION,
        "pipeline_name": meta_json.get("pipeline_name"),
        "pipeline_version": meta_json.get("pipeline_version"),
        "rows": {
            "combined": int(len(combined)),
            "by_split": _split_counts(combined),
        },
        "dataset_identity": {
            "divisions": sorted(combined["division"].dropna().unique().tolist())
            if "division" in combined.columns else [],
            "years": sorted(int(y) for y in combined["year"].dropna().unique())
            if "year" in combined.columns else [],
            "seasons": sorted(combined["season"].dropna().unique().tolist())
            if "season" in combined.columns else [],
        },
        "quality_checks": {
            "duplicate_panel_keys": int(combined.duplicated(duplicate_keys).sum())
            if duplicate_keys else None,
            "duplicate_panel_key_columns": duplicate_keys,
            f"null_{target}": int(combined[target].isna().sum()) if target in combined.columns else None,
            f"zero_{target}": int((combined[target] == 0).sum()) if target in combined.columns else None,
            "impervious_pct_range": [
                float(combined["impervious_pct"].min()),
                float(combined["impervious_pct"].max()),
            ] if "impervious_pct" in combined.columns else None,
            "water_occurrence_pct_range": [
                float(combined["water_occurrence_pct"].min()),
                float(combined["water_occurrence_pct"].max()),
            ] if "water_occurrence_pct" in combined.columns else None,
        },
        "features": {
            "config_a_count": len(meta_json["feature_sets"]["config_a_features"]),
            "config_b_count": len(meta_json["feature_sets"]["config_b_features"]),
            "config_a_scaled_count": len(meta_json["feature_sets"]["config_a_scaled_features"]),
            "config_b_scaled_count": len(meta_json["feature_sets"]["config_b_scaled_features"]),
            "dropped_unusable": meta_json.get("dropped_unusable", []),
            "dropped_high_missing": meta_json.get("dropped_high_missing", []),
            "dropped_by_spearman": meta_json.get("dropped_by_spearman", []),
            "dropped_by_vif": meta_json.get("dropped_by_vif", []),
        },
        "config_descriptions": {
            "config_a": meta_json["column_roles"].get("config_a_description", ""),
            "config_b": meta_json["column_roles"].get("config_b_description", ""),
        },
        "outputs": {name: str(path.resolve()) for name, path in output_files.items()},
    }

    report_json_path = output_dir / "preprocessing_report.json"
    with report_json_path.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(summary), handle, indent=2)
    print(f"[Write] {report_json_path}")

    report_md_path = output_dir / "preprocessing_report.md"
    lines = [
        "# Preprocessing Report",
        "",
        f"- Pipeline: {summary['pipeline_name']} v{summary['pipeline_version']}",
        f"- Rows: {summary['rows']['combined']:,}",
        f"- Splits: {summary['rows']['by_split']}",
        f"- Divisions: {summary['dataset_identity']['divisions']}",
        f"- Years: {summary['dataset_identity']['years']}",
        f"- Seasons: {summary['dataset_identity']['seasons']}",
        f"- Duplicate panel keys: {summary['quality_checks']['duplicate_panel_keys']}",
        f"- Null {target}: {summary['quality_checks'][f'null_{target}']}",
        f"- Zero {target}: {summary['quality_checks'][f'zero_{target}']}",
        "",
        "## Config A",
        "",
        summary["config_descriptions"]["config_a"],
        "",
        f"- Raw feature count: {summary['features']['config_a_count']}",
        f"- Scaled feature count: {summary['features']['config_a_scaled_count']}",
        "",
        "## Config B",
        "",
        summary["config_descriptions"]["config_b"],
        "",
        f"- Raw feature count: {summary['features']['config_b_count']}",
        f"- Scaled feature count: {summary['features']['config_b_scaled_count']}",
        "",
        "## Outputs",
        "",
    ]
    for name, path in output_files.items():
        lines.append(f"- `{name}`: `{path}`")
    report_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[Write] {report_md_path}")


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        engine = "calamine" if importlib_util.find_spec("python_calamine") else None
        return pd.read_excel(path, engine=engine)
    raise ValueError(f"Unsupported input file type: {path}")


def _parse_years(value: str | None) -> list[int] | None:
    if not value:
        return None
    if ":" in value:
        start, end = value.split(":", 1)
        return list(range(int(start), int(end) + 1))
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path, help="GEE CSV/XLSX export files")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--pipeline-file",
        type=Path,
        default=Path(__file__).with_name("preprocessing version2.py"),
    )
    parser.add_argument(
        "--expected-division",
        action="append",
        dest="expected_divisions",
        required=True,
        help="Expected division. Repeat for multi-division runs.",
    )
    parser.add_argument(
        "--expected-years",
        required=True,
        help="Expected years, e.g. 2015:2025 or 2015,2016",
    )
    parser.add_argument(
        "--expected-seasons",
        default="winter,pre_monsoon,monsoon,post_monsoon",
        help="Comma-separated expected seasons",
    )
    parser.add_argument(
        "--spatial-lag-radius-km",
        type=float,
        default=3.0,
        help="Physical radius for spatial lag features.",
    )
    parser.add_argument(
        "--grid-scale-km",
        type=float,
        default=1.0,
        help="Kilometres represented by one grid_x/grid_y index unit.",
    )
    args = parser.parse_args()
    expected_years = _parse_years(args.expected_years)
    expected_seasons = [
        season.strip()
        for season in args.expected_seasons.split(",")
        if season.strip()
    ]
    if expected_years is None or not expected_seasons:
        parser.error("Expected dataset identity is required: division, years, and seasons.")

    inputs = sorted(args.inputs)
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing input files: {missing}")
    if not args.pipeline_file.is_file():
        raise FileNotFoundError(f"Missing pipeline file: {args.pipeline_file}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pipeline_module = _load_pipeline_module(args.pipeline_file)
    frames = []
    for path in inputs:
        frame = _read_table(path)
        frames.append(frame)
        print(f"[Read] {path} ({len(frame):,} rows x {frame.shape[1]} columns)")

    raw = pd.concat(frames, ignore_index=True)
    print(f"[Combine] {len(raw):,} rows x {raw.shape[1]} columns")

    print(f"[Pipeline] {args.pipeline_file.resolve()}")
    pipe = pipeline_module.PreprocessingPipeline(
        expected_divisions=args.expected_divisions,
        expected_years=expected_years,
        expected_seasons=expected_seasons,
        spatial_lag_radius_km=args.spatial_lag_radius_km,
        grid_scale_km=args.grid_scale_km,
    )
    train, val, test, meta = pipe.fit_transform(raw)

    train = train.copy()
    val = val.copy()
    test = test.copy()
    train["split"] = "train"
    val["split"] = "val"
    test["split"] = "test"
    combined = pd.concat([train, val, test], ignore_index=True)
    combined_scaled_a = pipe.apply_scaler(combined)
    combined_scaled_b = pipe.apply_scaler_config_b(combined)

    output_files = {
        "preprocessed_train.csv": args.output_dir / "preprocessed_train.csv",
        "preprocessed_val.csv": args.output_dir / "preprocessed_val.csv",
        "preprocessed_test.csv": args.output_dir / "preprocessed_test.csv",
        "preprocessed_combined.csv": args.output_dir / "preprocessed_combined.csv",
        "model_ready_config_a.csv": args.output_dir / "model_ready_config_a.csv",
        "model_ready_config_b.csv": args.output_dir / "model_ready_config_b.csv",
        "model_ready_config_a_scaled.csv": args.output_dir / "model_ready_config_a_scaled.csv",
        "model_ready_config_b_scaled.csv": args.output_dir / "model_ready_config_b_scaled.csv",
        "model_ready_config_a_train_scaled.csv": args.output_dir / "model_ready_config_a_train_scaled.csv",
        "model_ready_config_a_val_scaled.csv": args.output_dir / "model_ready_config_a_val_scaled.csv",
        "model_ready_config_a_test_scaled.csv": args.output_dir / "model_ready_config_a_test_scaled.csv",
        "model_ready_config_b_train_scaled.csv": args.output_dir / "model_ready_config_b_train_scaled.csv",
        "model_ready_config_b_val_scaled.csv": args.output_dir / "model_ready_config_b_val_scaled.csv",
        "model_ready_config_b_test_scaled.csv": args.output_dir / "model_ready_config_b_test_scaled.csv",
        "preprocessing_metadata.json": args.output_dir / "preprocessing_metadata.json",
        "preprocessing_meta.json": args.output_dir / "preprocessing_meta.json",
        "missingness_report.csv": args.output_dir / "missingness_report.csv",
        "dropped_features_report.csv": args.output_dir / "dropped_features_report.csv",
        "feature_role_table.csv": args.output_dir / "feature_role_table.csv",
        "preprocessing_pipeline_state.pkl": args.output_dir / "preprocessing_pipeline_state.pkl",
        "preprocessing_report.json": args.output_dir / "preprocessing_report.json",
        "preprocessing_report.md": args.output_dir / "preprocessing_report.md",
    }

    _write_csv(train, output_files["preprocessed_train.csv"])
    _write_csv(val, output_files["preprocessed_val.csv"])
    _write_csv(test, output_files["preprocessed_test.csv"])
    _write_csv(combined, output_files["preprocessed_combined.csv"])
    _write_csv(
        combined[_model_ready_columns(combined, meta["config_a_cols"])],
        output_files["model_ready_config_a.csv"],
    )
    _write_csv(
        combined[_model_ready_columns(combined, meta["config_b_cols"])],
        output_files["model_ready_config_b.csv"],
    )
    _write_csv(
        combined_scaled_a[
            _scaled_model_ready_columns(combined_scaled_a, meta["scale_cols"], "_scaled")
        ],
        output_files["model_ready_config_a_scaled.csv"],
    )
    _write_csv(
        combined_scaled_b[
            _scaled_model_ready_columns(combined_scaled_b, meta["scale_cols_b"], "_scaled_b")
        ],
        output_files["model_ready_config_b_scaled.csv"],
    )
    for split in ["train", "val", "test"]:
        split_a = combined_scaled_a[combined_scaled_a["split"] == split]
        split_b = combined_scaled_b[combined_scaled_b["split"] == split]
        _write_csv(
            split_a[_scaled_model_ready_columns(split_a, meta["scale_cols"], "_scaled")],
            output_files[f"model_ready_config_a_{split}_scaled.csv"],
        )
        _write_csv(
            split_b[_scaled_model_ready_columns(split_b, meta["scale_cols_b"], "_scaled_b")],
            output_files[f"model_ready_config_b_{split}_scaled.csv"],
        )

    meta_json = _metadata_for_json(meta, pipe, inputs, args.pipeline_file)
    _write_json(output_files["preprocessing_metadata.json"], meta_json)
    _write_json(output_files["preprocessing_meta.json"], _simplified_meta(meta_json, output_files))
    _write_csv(
        _missingness_report(
            {
                "train": train,
                "val": val,
                "test": test,
                "combined": combined,
            }
        ),
        output_files["missingness_report.csv"],
    )
    _write_csv(
        _dropped_features_report(meta_json, raw.columns.tolist(), pipeline_module),
        output_files["dropped_features_report.csv"],
    )
    _write_csv(
        _feature_role_table(meta_json, pipeline_module),
        output_files["feature_role_table.csv"],
    )

    with output_files["preprocessing_pipeline_state.pkl"].open("wb") as handle:
        pickle.dump(pipe.__dict__, handle)
    print(f"[Write] {output_files['preprocessing_pipeline_state.pkl']}")
    _write_preprocessing_reports(args.output_dir, combined, meta_json, output_files)

    stale_pipeline_pickle = args.output_dir / "preprocessing_pipeline.pkl"
    if stale_pipeline_pickle.exists():
        stale_pipeline_pickle.unlink()


if __name__ == "__main__":
    main()
