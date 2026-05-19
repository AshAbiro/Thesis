# Modeling Workflow

This workspace now includes a runnable LST model pipeline in `scripts/run_lst_models.py`.

## What It Runs

The runner trains four regression models that align with the papers already extracted in this workspace:

- Linear Regression
- Support Vector Machine using `SVR`
- Random Forest
- Artificial Neural Network using `MLPRegressor`

For each model it reports:

- RMSE
- MAE
- R2
- PBIAS
- mean bias

## Commands

### 1. Smoke Test the Pipeline

```powershell
python scripts/run_lst_models.py demo-run
```

This creates a synthetic LST dataset and runs the full pipeline so you can verify the code path and output format.

### 2. Create Synthetic Demo Data Only

```powershell
python scripts/run_lst_models.py demo-data
```

### 3. Run on a Real Thesis Dataset

```powershell
python scripts/run_lst_models.py run `
  --dataset modeling\your_input.csv `
  --target lst_c `
  --features ndvi,ndbi,ndwi,albedo,ui,built_area_ratio,water_pct,tree_cover_gt2m_pct
```

If `--features` is omitted, the runner uses all numeric columns except the target.

## Required Real Input Format

The script expects a flat CSV where each row is one sample unit such as:

- a pixel
- a grid cell
- a polygon summary unit

Minimum requirements:

- one numeric target column, usually `lst_c`
- numeric predictor columns such as `ndvi`, `ndbi`, `ndwi`, `albedo`, `ui`, `built_area_ratio`, `water_pct`, `tree_cover_gt2m_pct`

Good practice for the thesis:

- use one row per 30 m pixel, 100 m block, or 500 m grid depending on your study design
- keep coordinate columns such as `x_coord` and `y_coord` if spatial effects matter
- remove obvious duplicate samples
- ensure all predictors refer to the same date or compositing window as the target LST

## Outputs

Each run writes to `modeling/results/<run_name>/`:

- `report.md`
- `metrics.json`
- `predictions.csv`

## Current Limitation

This workspace still does not contain your real Dhaka modeling table or raster-derived feature table. The runner is ready, but actual thesis model execution requires that dataset to exist first.
