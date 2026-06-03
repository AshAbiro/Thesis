# Preprocessing Report

- Pipeline: preprocessing version2.py v2.4
- Rows: 694,982
- Splits: {'train': 570030, 'test': 63806, 'val': 61146}
- Divisions: ['Rangpur']
- Years: [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
- Seasons: ['monsoon', 'post_monsoon', 'pre_monsoon', 'winter']
- Duplicate panel keys: 0
- Null lst_c_mean: 0
- Zero lst_c_mean: 0

## Config A

Config A is the driver/causal feature set: non-thermal environmental and built-environment predictors only. It excludes same-season thermal products, emissivity, targets, passthrough SUHI/reference columns, IDs, and target lags.

- Raw feature count: 32
- Scaled feature count: 32

## Config B

Config B is the predictive/forecasting feature set: Config A plus target history and same-season thermal/emissivity predictors where available. Use it for accuracy benchmarks, not causal interpretation.

- Raw feature count: 38
- Scaled feature count: 38

## Outputs

- `preprocessed_train.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessed_train.csv`
- `preprocessed_val.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessed_val.csv`
- `preprocessed_test.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessed_test.csv`
- `preprocessed_combined.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessed_combined.csv`
- `model_ready_config_a.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_a.csv`
- `model_ready_config_b.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_b.csv`
- `model_ready_config_a_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_a_scaled.csv`
- `model_ready_config_b_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_b_scaled.csv`
- `model_ready_config_a_train_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_a_train_scaled.csv`
- `model_ready_config_a_val_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_a_val_scaled.csv`
- `model_ready_config_a_test_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_a_test_scaled.csv`
- `model_ready_config_b_train_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_b_train_scaled.csv`
- `model_ready_config_b_val_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_b_val_scaled.csv`
- `model_ready_config_b_test_scaled.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\model_ready_config_b_test_scaled.csv`
- `preprocessing_metadata.json`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessing_metadata.json`
- `preprocessing_meta.json`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessing_meta.json`
- `missingness_report.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\missingness_report.csv`
- `dropped_features_report.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\dropped_features_report.csv`
- `feature_role_table.csv`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\feature_role_table.csv`
- `preprocessing_pipeline_state.pkl`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessing_pipeline_state.pkl`
- `preprocessing_report.json`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessing_report.json`
- `preprocessing_report.md`: `Preprocessed Files\Rangpur_2015_2025_v2_4_final\preprocessing_report.md`
