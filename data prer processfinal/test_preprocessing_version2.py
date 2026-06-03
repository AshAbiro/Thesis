"""Focused regression checks for preprocessing version2.py."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def _load_module():
    path = Path(__file__).with_name("preprocessing version2.py")
    spec = importlib.util.spec_from_file_location("preprocessing_version2_tested", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runner():
    path = Path(__file__).with_name("run_preprocessing_batch.py")
    spec = importlib.util.spec_from_file_location("run_preprocessing_batch_tested", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_impervious_unit_conversion(module) -> None:
    pipe = module.PreprocessingPipeline()
    raw = pd.DataFrame({"impervious_pct": [0.0] * 94 + [2.0, 5.0, 10.0, 25.0, 50.0, 100.0]})
    pipe._fit_impervious_units(raw)
    converted = pipe._apply_impervious_units(raw)
    assert pipe._impervious_divisor == 100.0
    assert converted["impervious_pct"].max() == 1.0
    inference = pipe._step1_physical_range(pd.DataFrame({"impervious_pct": [50.0]}))
    assert inference["impervious_pct"].iloc[0] == 0.5


def test_presplit_physical_filter_does_not_fit_impervious(module) -> None:
    pipe = module.PreprocessingPipeline()
    raw = pd.DataFrame({"impervious_pct": [50.0], "lst_c_mean": [30.0]})
    filtered = pipe._step1_physical_range(raw, process_impervious=False)
    assert pipe._impervious_divisor == 1.0
    assert filtered["impervious_pct"].iloc[0] == 50.0


def test_invalid_zero_lst_is_nulled(module) -> None:
    pipe = module.PreprocessingPipeline()
    raw = pd.DataFrame(
        {
            "lst_c_mean": [0.0, 30.0],
            "lst_c_max": [0.0, 35.0],
            "modis_lst_day_mean": [0.0, 28.0],
            "building_area_ratio": [0.0, 0.1],
        }
    )
    filtered = pipe._step1_physical_range(raw, process_impervious=False)
    assert filtered["lst_c_mean"].isna().tolist() == [True, False]
    assert filtered["lst_c_max"].isna().tolist() == [True, False]
    assert filtered["modis_lst_day_mean"].isna().tolist() == [True, False]
    assert filtered["building_area_ratio"].tolist() == [0.0, 0.1]


def test_water_scale_conversion(module) -> None:
    pipe = module.PreprocessingPipeline()
    train = pd.DataFrame({"water_occurrence_pct": [0.0, 0.2, 1.0]})
    pipe._fit_water_occurrence_units(train)
    out = pipe._apply_water_occurrence_units(pd.DataFrame({"water_occurrence_pct": [0.5]}))
    assert pipe._water_occurrence_multiplier == 100.0
    assert out["water_occurrence_pct"].iloc[0] == 50.0


def test_dataset_identity_validation(module) -> None:
    rows = pd.DataFrame(
        {
            "grid_id": [1, 2],
            "division": ["Dhaka", "Dhaka"],
            "year": [2015, 2016],
            "season": ["winter", "monsoon"],
        }
    )
    module.validate_dataset_identity(
        rows,
        expected_divisions=["Dhaka"],
        expected_years=[2015, 2016],
        expected_seasons=["monsoon", "winter"],
    )
    try:
        module.validate_dataset_identity(rows, expected_divisions=["Barisal"])
    except ValueError as exc:
        assert "divisions expected" in str(exc)
    else:
        raise AssertionError("Expected dataset identity failure")


def test_panel_duplicate_keys_include_division(module) -> None:
    rows = pd.DataFrame(
        {
            "grid_id": [1, 1],
            "division": ["Dhaka", "Mymensingh"],
            "year": [2020, 2020],
            "season": ["winter", "winter"],
        }
    )
    report = module.validate_dataset_identity(rows)
    assert report["duplicate_panel_keys"] == 0
    assert report["panel_key_cols"] == ["division", "grid_id", "year", "season"]

    duplicated = pd.concat([rows, rows.iloc[[0]]], ignore_index=True)
    try:
        module.validate_dataset_identity(duplicated)
    except ValueError as exc:
        assert "duplicate division/grid_id/year/season keys" in str(exc)
    else:
        raise AssertionError("Expected duplicate panel-key failure")


def test_unknown_season_fails_before_encoding(module) -> None:
    pipe = module.PreprocessingPipeline()
    try:
        pipe._step7_cyclic_season(pd.DataFrame({"season": ["not_a_season"]}))
    except ValueError as exc:
        assert "Unknown season labels" in str(exc)
    else:
        raise AssertionError("Expected unknown-season failure")


def test_exact_temporal_lags(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "grid_id": ["A", "A", "A", "A"],
            "year": [2020, 2020, 2020, 2021],
            "season": ["winter", "monsoon", "post_monsoon", "winter"],
            "lst_c_mean": [1.0, 3.0, 4.0, 5.0],
        }
    )
    lagged = pipe._step9_temporal_lags(rows)
    monsoon = lagged[lagged["season"] == "monsoon"].iloc[0]
    winter_2021 = lagged[lagged["year"] == 2021].iloc[0]
    assert np.isnan(monsoon["lst_c_mean_lag1"])
    assert winter_2021["lst_c_mean_lag1"] == 4.0
    assert winter_2021["lst_c_mean_lag4"] == 1.0


def test_temporal_lags_are_division_isolated(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "division": ["Dhaka", "Dhaka", "Mymensingh", "Mymensingh"],
            "grid_id": ["A", "A", "A", "A"],
            "year": [2020, 2021, 2020, 2021],
            "season": ["winter", "winter", "winter", "winter"],
            "lst_c_mean": [1.0, 2.0, 100.0, 200.0],
        }
    )
    lagged = pipe._step9_temporal_lags(rows)
    dhaka_2021 = lagged[(lagged["division"] == "Dhaka") & (lagged["year"] == 2021)].iloc[0]
    mymensingh_2021 = lagged[
        (lagged["division"] == "Mymensingh") & (lagged["year"] == 2021)
    ].iloc[0]
    assert dhaka_2021["lst_c_mean_lag4"] == 1.0
    assert mymensingh_2021["lst_c_mean_lag4"] == 100.0


def test_temporal_lags_raise_on_duplicate_panel_period(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "division": ["Dhaka", "Dhaka"],
            "grid_id": ["A", "A"],
            "year": [2020, 2020],
            "season": ["winter", "winter"],
            "lst_c_mean": [1.0, 2.0],
        }
    )
    try:
        pipe._step9_temporal_lags(rows)
    except ValueError as exc:
        assert "Duplicate panel period rows" in str(exc)
    else:
        raise AssertionError("Expected duplicate temporal panel-key failure")


def test_spatial_snapshot_isolation(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "grid_x": [0, 0, 1, 1],
            "grid_y": [0, 0, 0, 0],
            "year": [2020] * 4,
            "season": ["winter", "monsoon", "winter", "monsoon"],
            "ndvi_mean": [1.0, 100.0, 10.0, 20.0],
        }
    )
    lagged = pipe._step10_spatial_lags_fast(rows, radius_km=3.0)
    assert lagged["ndvi_mean_spatial_lag"].tolist() == [10.0, 20.0, 1.0, 100.0]


def test_spatial_lag_grid_scale_is_explicit(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "grid_x": [0.0, 2.0, 4.0],
            "grid_y": [0.0, 0.0, 0.0],
            "year": [2020, 2020, 2020],
            "season": ["winter", "winter", "winter"],
            "ndvi_mean": [1.0, 10.0, 100.0],
        }
    )
    one_km_grid = pipe._step10_spatial_lags_fast(rows, radius_km=3.0, grid_scale_km=1.0)
    two_km_grid = pipe._step10_spatial_lags_fast(rows, radius_km=3.0, grid_scale_km=2.0)
    assert one_km_grid["ndvi_mean_spatial_lag"].tolist() == [10.0, 50.5, 10.0]
    assert two_km_grid["ndvi_mean_spatial_lag"].isna().all()


def test_spatial_lags_are_division_snapshot_isolated(module) -> None:
    pipe = module.PreprocessingPipeline()
    rows = pd.DataFrame(
        {
            "division": ["Dhaka", "Dhaka", "Mymensingh", "Mymensingh"],
            "grid_x": [0.0, 1.0, 0.0, 1.0],
            "grid_y": [0.0, 0.0, 0.0, 0.0],
            "year": [2020, 2020, 2020, 2020],
            "season": ["winter", "winter", "winter", "winter"],
            "ndvi_mean": [1.0, 10.0, 100.0, 1000.0],
        }
    )
    lagged = pipe._step10_spatial_lags_fast(rows, radius_km=2.0, grid_scale_km=1.0)
    assert lagged["ndvi_mean_spatial_lag"].tolist() == [10.0, 1.0, 1000.0, 100.0]


def test_scaler_schema_error(module) -> None:
    pipe = module.PreprocessingPipeline()
    pipe._step13_fit_scaler(pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}), ["a", "b"])
    pipe._fitted = True
    try:
        pipe.apply_scaler(pd.DataFrame({"a": [1.0]}))
    except ValueError as exc:
        assert "missing fitted columns" in str(exc)
    else:
        raise AssertionError("Expected missing-column scaler failure")


def test_config_b_scaler(module) -> None:
    pipe = module.PreprocessingPipeline()
    train = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    pipe._step13_fit_config_b_scaler(train, ["a", "b"])
    pipe._fitted = True
    scaled = pipe.apply_scaler_config_b(train)
    assert "a_scaled_b" in scaled.columns
    assert "b_scaled_b" in scaled.columns


def test_spearman_runs_without_statsmodels(module) -> None:
    previous = module._HAS_STATSMODELS
    module._HAS_STATSMODELS = False
    try:
        pipe = module.PreprocessingPipeline()
        rows = pd.DataFrame(
            {
                "a": [1.0, 2.0, 3.0, 4.0, 5.0],
                "b": [2.0, 4.0, 6.0, 8.0, 10.0],
                "c": [3.0, 1.0, 5.0, 2.0, 4.0],
                "constant": [1.0] * 5,
                "all_null": [np.nan] * 5,
            }
        )
        kept = pipe._step11_collinearity_prune(rows, list(rows.columns))
        assert len({"a", "b"} & set(kept)) == 1
        assert "constant" not in kept
        assert "all_null" not in kept
    finally:
        module._HAS_STATSMODELS = previous


def test_config_a_excludes_target_lags(module) -> None:
    pipe = module.PreprocessingPipeline()
    df = pd.DataFrame(
        {
            "ndvi_mean": [0.1, 0.2],
            "lst_c_mean_lag1": [29.0, 30.0],
            "modis_lst_day_mean": [31.0, 32.0],
        }
    )
    config_a, config_b = pipe._step12_build_feature_matrices(
        df, ["ndvi_mean", "lst_c_mean_lag1"]
    )
    assert "lst_c_mean_lag1" not in config_a
    assert "lst_c_mean_lag1" in config_b
    assert "modis_lst_day_mean" not in config_a
    assert "modis_lst_day_mean" in config_b
    module.audit_feature_roles({"config_a_cols": config_a, "config_b_cols": config_b})


def test_validate_no_leakage_raises_on_overlap(module) -> None:
    train = pd.DataFrame({"year": [2020], "grid_id": [1]})
    val = pd.DataFrame({"year": [2020], "grid_id": [1]})
    test = pd.DataFrame({"year": [2021], "grid_id": [1]})
    try:
        module.validate_no_leakage(train, val, test)
    except ValueError as exc:
        assert "Leakage validation failed" in str(exc)
    else:
        raise AssertionError("Expected leakage validation failure")


def test_validate_no_leakage_allows_pilot_spatial_two_years(module) -> None:
    train = pd.DataFrame({"year": [2020, 2021], "grid_id": [1, 1]})
    val = pd.DataFrame({"year": [2020, 2021], "grid_id": [2, 2]})
    test = pd.DataFrame({"year": [2020, 2021], "grid_id": [3, 3]})
    module.validate_no_leakage(train, val, test)


def test_model_ready_columns_exclude_context() -> None:
    runner = _load_runner()
    df = pd.DataFrame(
        columns=[
            "split",
            "lst_c_mean",
            "grid_id",
            "year",
            "suhi_mean",
            "reference_lst_mean",
            "ndvi_mean",
        ]
    )
    cols = runner._model_ready_columns(df, ["ndvi_mean"])
    assert cols == ["split", "lst_c_mean", "ndvi_mean"]


def test_scaled_model_ready_columns() -> None:
    runner = _load_runner()
    df = pd.DataFrame(
        columns=[
            "split",
            "lst_c_mean",
            "ndvi_mean_scaled",
            "ndvi_mean",
            "suhi_mean",
        ]
    )
    cols = runner._scaled_model_ready_columns(df, ["ndvi_mean"], "_scaled")
    assert cols == ["split", "lst_c_mean", "ndvi_mean_scaled"]


def test_reporting_helpers(module) -> None:
    runner = _load_runner()
    meta_json = {
        "pipeline_name": "preprocessing version2.py",
        "pipeline_version": "2.4",
        "runner_version": "2.4",
        "pipeline_file": "pipeline.py",
        "expected_dataset_identity": {
            "divisions": ["Dhaka"],
            "years": [2020],
            "seasons": ["winter"],
        },
        "dataset_identity_audit": {"divisions": ["Dhaka"]},
        "target": "lst_c_mean",
        "train_years": [2020],
        "val_years": [2021],
        "test_years": [2022],
        "feature_sets": {
            "config_a_features": ["ndvi_mean"],
            "config_b_features": ["ndvi_mean", "lst_c_mean_lag1", "modis_lst_day_mean"],
            "config_a_scaled_features": ["ndvi_mean_scaled"],
            "config_b_scaled_features": [
                "ndvi_mean_scaled_b",
                "lst_c_mean_lag1_scaled_b",
                "modis_lst_day_mean_scaled_b",
            ],
        },
        "config_a_description": "Config A description",
        "config_b_description": "Config B description",
        "column_roles": {
            "target": "lst_c_mean",
            "passthrough_not_features": ["suhi_mean"],
        },
        "id_cols": ["grid_id", "year", "season"],
        "target_lag_features": ["lst_c_mean_lag1"],
        "thermal_features": ["modis_lst_day_mean"],
        "impervious_divisor": 100.0,
        "water_occurrence_multiplier": 1.0,
        "dropped_unusable": ["constant_col"],
        "dropped_high_missing": ["mostly_missing"],
        "dropped_by_spearman": ["ndbi_mean"],
        "dropped_by_vif": ["dist_to_any_water_m"],
    }
    outputs = {"preprocessing_meta.json": Path("preprocessing_meta.json")}
    simple = runner._simplified_meta(meta_json, outputs)
    assert simple["config_a"]["feature_count"] == 1
    assert simple["config_b"]["feature_count"] == 3

    frame = pd.DataFrame(
        {
            "split": ["train", "train"],
            "lst_c_mean": [30.0, np.nan],
            "ndvi_mean": [0.5, 0.6],
        }
    )
    missing = runner._missingness_report({"train": frame})
    target_row = missing[
        (missing["split"] == "train") & (missing["column"] == "lst_c_mean")
    ].iloc[0]
    assert target_row["missing_count"] == 1

    dropped = runner._dropped_features_report(
        meta_json,
        raw_columns=["lst_k_mean", "constant_col"],
        pipeline_module=module,
    )
    assert {"hard_drop", "feature_selection_unusable"} <= set(dropped["stage"])

    roles = runner._feature_role_table(meta_json, module)
    role_map = roles.set_index("column")["role"].to_dict()
    assert "target" in role_map["lst_c_mean"]
    assert "config_a_feature" in role_map["ndvi_mean"]
    assert "config_b_only_target_lag" in role_map["lst_c_mean_lag1"]
    assert "config_b_only_thermal" in role_map["modis_lst_day_mean"]

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        runner._write_json(out / "preprocessing_meta.json", simple)
        assert (out / "preprocessing_meta.json").is_file()


if __name__ == "__main__":
    pipeline = _load_module()
    test_impervious_unit_conversion(pipeline)
    test_presplit_physical_filter_does_not_fit_impervious(pipeline)
    test_invalid_zero_lst_is_nulled(pipeline)
    test_water_scale_conversion(pipeline)
    test_dataset_identity_validation(pipeline)
    test_panel_duplicate_keys_include_division(pipeline)
    test_unknown_season_fails_before_encoding(pipeline)
    test_exact_temporal_lags(pipeline)
    test_temporal_lags_are_division_isolated(pipeline)
    test_temporal_lags_raise_on_duplicate_panel_period(pipeline)
    test_spatial_snapshot_isolation(pipeline)
    test_spatial_lag_grid_scale_is_explicit(pipeline)
    test_spatial_lags_are_division_snapshot_isolated(pipeline)
    test_scaler_schema_error(pipeline)
    test_config_b_scaler(pipeline)
    test_spearman_runs_without_statsmodels(pipeline)
    test_config_a_excludes_target_lags(pipeline)
    test_validate_no_leakage_raises_on_overlap(pipeline)
    test_validate_no_leakage_allows_pilot_spatial_two_years(pipeline)
    test_model_ready_columns_exclude_context()
    test_scaled_model_ready_columns()
    test_reporting_helpers(pipeline)
    print("preprocessing version2 regression checks passed")
