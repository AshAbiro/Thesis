# Heat Model Run

Generated: 2026-04-22 21:24:16

- Dataset: C:\Users\abira\chrome\Thesis\data collect\dhaka_lulc_pipeline\output\model_ready\combined_lulc_heat_model_table.csv
- Target: lst_c
- Feature count: 10
- Features: year, longitude, latitude, frac_built, frac_vegetation, frac_cropland, frac_water, frac_wetland, frac_bare, ndvi
- Total rows: 11658
- Rows used: 11658
- Rows dropped for missing values: 0
- Train rows: 9326
- Test rows: 2332
- Best model by RMSE: RandomForest

| Model | RMSE | MAE | R2 | PBIAS | Bias |
| --- | --- | --- | --- | --- | --- |
| RandomForest | 1.3065 | 0.9155 | 0.8629 | -0.0196 | -0.0068 |
| ANN | 1.4868 | 1.0587 | 0.8224 | -0.0923 | -0.0322 |
| SVM | 2.2213 | 1.4790 | 0.6035 | 0.1492 | 0.0520 |
| LinearRegression | 2.6831 | 1.9644 | 0.4216 | -0.0874 | -0.0305 |
