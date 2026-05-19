# Dhaka LULC + Heat Modeling Pipeline

This folder contains the main code for building a Dhaka 1 km land-cover and heat modeling table.

## Main Files

- `gee/dhaka_lulc6_extraction.js` - Earth Engine LULC extraction workflow.
- `python/run_ee_extract_grid.py` - extracts yearly 1 km LULC fractions.
- `python/build_lulc_ml_table.py` - combines yearly LULC CSVs into one ML-ready table.
- `python/run_ee_extract_lst_grid.py` - extracts Landsat heat-season LST targets.
- `python/join_lulc_with_lst.py` - joins LULC predictors with LST targets.
- `config/class_crosswalk.csv` - maps source land-cover classes to the thesis 6-class schema.
- `config/ml_feature_schema.csv` - documents the model feature columns.

## Six LULC Classes

1. Built-up
2. Vegetation
3. Cropland
4. Water
5. Wetland
6. Bare land

## Run Order

From `data collect/dhaka_lulc_pipeline/python`:

```powershell
pip install -r requirements.txt

python run_ee_extract_grid.py --years 2018 2019 2020 2021 2022 2023 2024 --output-dir "..\output\raw_csv"

python build_lulc_ml_table.py --input-dir "..\output\raw_csv" --output-dir "..\output\ml_ready" --renormalize

python run_ee_extract_lst_grid.py --years 2018 2019 2020 2021 2022 2023 2024 --output-dir "..\output\lst_csv"

python join_lulc_with_lst.py --lulc-table "..\output\ml_ready\combined_lulc6_features.csv" --lst-table "..\output\lst_csv\combined_lst_targets.csv" --output-dir "..\output\model_ready"
```

## Final Outputs

- `output/ml_ready/combined_lulc6_features.csv` - LULC predictor table.
- `output/lst_csv/combined_lst_targets.csv` - LST target table.
- `output/model_ready/combined_lulc_heat_model_table.csv` - final model-ready table.

## Main Predictors

- `frac_built`
- `frac_vegetation`
- `frac_cropland`
- `frac_water`
- `frac_wetland`
- `frac_bare`

The final modeling target is `lst_c`.
