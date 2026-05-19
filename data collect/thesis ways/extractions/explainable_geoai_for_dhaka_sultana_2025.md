# Paper Extraction

## Paper Identity

- Paper name: Understanding Urban Heat Islands in Dhaka City Through Explainable GeoAI
- Authors: Maria Sultana; Md Didarul Islam; Bradford Johnson
- Year: 2025
- Document type: Research article / preprint
- Publisher or institution: Research Square preprint
- DOI or URL: 10.21203/rs.3.rs-7547419/v1
- Evidence label: Extracted

## Study Area

- Study location: Dhaka City
- Country: Bangladesh
- Urban focus: Megacity / metropolitan grid analysis
- Study area boundary source: Dhaka city divided into 500 m x 500 m grid cells
- Area size: Not reported in extracted pass
- Administrative units: Grid-based citywide coverage
- Seasonal or climatic context: Tropical monsoon city; summer median composite used for Apr-Aug 2020 / May-Aug 2020 analysis

## Data Used

- Satellite source: Landsat 8 plus multi-source urban form datasets
- Sensor: Landsat 8 TIRS/OLI; Google Open Buildings; Meta Canopy Height; Dynamic World
- Acquisition dates: LST and NDVI from Apr-Aug 2020; canopy height 2019-2020; Dynamic World 2020
- Temporal coverage: 2020 summer-focused model with supporting 2019-2020 canopy data
- Number of scenes: Median composite; exact scene count not reported
- Path/row: Not reported
- Spatial resolution: 30 m LST and NDVI; 10 m canopy and Dynamic World; aggregated to 500 m grid
- Ancillary data: Building footprints, bare land percentage, water percentage, tree cover above 2 m, spatial coordinates
- DEM: Not used in extracted pass
- Meteorological data: Not used
- Ground stations: Not used

## Image Preprocessing

- Cloud filtering: Median summer composite used to reduce cloud noise
- Atmospheric correction: Not fully detailed in extracted pass
- Radiometric calibration: Landsat 8 processing chain embedded in LST workflow
- Geometric correction: Inputs reprojected to common CRS
- Reprojection: UTM Zone 45N, EPSG:32645
- Resampling: Canopy height resampled to 10 m, then aggregated to 500 m grid; all variables standardized to 500 m cells
- Clipping: Dhaka city grid
- Seasonal harmonization: Summer composite used to represent seasonal thermal conditions
- Cross-sensor normalization: Not applicable

## LST Extraction Workflow

- Method name: Landsat 8 mono-window LST with NDVI-based emissivity correction
- DN to radiance step: Not fully printed in extracted pass
- Brightness temperature step: Derived from Landsat 8 TIRS Band 10
- Emissivity estimation: NDVI-based emissivity correction
- Final LST equation: Mono-window form using brightness temperature, wavelength term, rho = 1.438 x 10^-2 m K, and emissivity
- Celsius conversion: Final performance metrics reported in degrees Celsius
- UHI derivation: Mean LST modeled across 500 m grid cells rather than simple urban-rural subtraction
- Constants used: rho = 1.438 x 10^-2 m K reported in the LST equation
- Sensor-specific notes: Landsat 8 Band 10 used as the thermal response variable

## Variable Extraction

### NDVI

- Equation: (NIR - Red) / (NIR + Red)
- Bands: Landsat 8 Band 5 and Band 4
- Range: Not reported numerically in extracted pass
- Thresholds: GeoShapley shows strongest cooling as NDVI rises from about 0.2 to 0.5

### NDBI

- Equation: Not used
- Bands: Not applicable
- Range: Not applicable
- Thresholds: Not applicable

### NDWI

- Equation: Not used directly; water percentage derived from Dynamic World
- Bands: Not applicable
- Range: Not reported as an index range
- Thresholds: Cooling influence becomes stronger beyond about 20 percent water coverage

### MNDWI

- Equation: Not used
- Bands: Not applicable
- Range: Not applicable
- Thresholds: Not applicable

### Albedo / Emissivity / UTFVI / Other

- Variable: Building area ratio; bare land percentage; water percentage; tree cover above 2 m; SHAP and GeoShapley feature contributions
- Equation: Building footprints aggregated to ratio; Dynamic World classes aggregated to percentages
- Range: Not reported numerically in extracted pass
- Thresholds: Bare land shows sharp positive thermal effect beyond about 10 percent; tree cover above 30 percent begins to show clearer cooling contribution
- Notes: Built area ratio is the dominant predictor in both SHAP and GeoShapley results

## LULC Classification

- Source imagery: Dynamic World land use/land cover dataset
- Classification years: 2020
- Class list: Water and bare land explicitly used in extracted pass
- Classifier: Dynamic World class aggregation into grid-level percentages; no new supervised classifier built
- Supervised or unsupervised: Product-based class aggregation
- Training sample source: Not applicable
- Post-classification refinement: Reclassified and aggregated to 500 m grid cells
- Change detection method: Not temporal change detection; explanatory grid modeling for 2020

## Meteorological Integration

- Variables integrated: None
- Data source: Not applicable
- Station names: Not applicable
- Date matching logic: Not applicable
- Calibration or comparison method: Not applicable

## Modeling and Statistics

- Correlation method: Correlation matrix between mean LST and environmental / urban variables
- Regression method: AutoML-selected LightGBM regression
- Spatial statistics: Spatially varying coefficients interpreted through GeoShapley
- Trend analysis: Not a temporal trend study
- Machine learning workflow: FLAML AutoML explored candidate regressors and selected LightGBM under an R2-based optimization; 80:20 split and five-fold cross-validation
- Feature selection: Predictor set consisted of bare_pct, water_pct, tree_cover_gt2m_pct, mean_NDVI, building_area_ratio, and X/Y spatial coordinates
- Explainability: SHAP and GeoShapley
- Performance metrics: R2, RMSE, MAE, bias

## Reported Values

- LST range: Not explicitly tabulated in extracted pass
- Mean LST: Mean_LST modeled at 500 m grid scale
- Max LST: Not reported numerically in extracted pass
- Min LST: Not reported numerically in extracted pass
- NDVI range: Not reported numerically; strongest cooling effect observed as NDVI rises from about 0.2 to around 0.5
- NDBI range: Not applicable
- NDWI range: Not applicable
- MNDWI range: Not applicable
- Albedo range: Not used directly in model features
- UTFVI range: Not used
- Correlation coefficients: Correlation matrix referenced but first-pass extraction focused on model metrics and thresholds
- Regression coefficients: Not provided as simple linear coefficients; explainability delivered through SHAP and GeoShapley
- RMSE / MAE / R2: R2 = 0.725; RMSE = 1.18 C; MAE = 0.83 C; bias about -0.04 C
- Accuracy / Kappa: Not applicable for standalone classification
- Class fractions: Not reported in first-pass extraction
- Thresholds: Bare land thermal effect rises sharply beyond about 10 percent; water coverage above about 20 percent shows stronger cooling; tree cover above about 30 percent shows meaningful cooling; NDVI cooling strengthens from about 0.2 to 0.5 before plateau
- Temperature differences: Not reported as class-wise absolute temperature differences in first pass
- Urban-rural contrast: Not the main design; focus is intra-urban grid prediction
- Bangladesh-specific parameters: 500 m grid design for Dhaka; Landsat 8 summer median composite

## Validation and Testing

- Validation dataset: Random 80:20 train-test split over grid cells
- Ground truth source: Observed Landsat-derived mean LST
- Train-test split: 80:20
- Cross-validation: Five-fold cross-validation
- Accuracy assessment: R2, RMSE, MAE, and bias
- Sensitivity analysis: Interpretable nonlinear threshold reading through GeoShapley partial dependence plots
- Limitations: Unmeasured factors such as wind corridors, albedo, and building configuration may still affect residual spatial patterns
- Reproducibility notes: Strong and thesis-grade; equations, data sources, split design, and metrics are clearly reported

## Appraisal

- Reproducibility score: 5
- Robustness score: 4
- Bangladesh suitability score: 5
- Dhaka suitability score: 5
- Validation strength score: 4
- Numerical extraction richness score: 4
- Thesis reuse potential score: 5

## Thesis Use Decision

- Directly reusable components: 500 m Dhaka grid strategy, Landsat 8 mono-window LST workflow, LightGBM + SHAP/GeoShapley interpretability framework
- Components needing modification: Temporal depth should be expanded if the final thesis requires multi-year change analysis
- Comparative-only components: Dynamic World and Open Buildings variables may supplement, not replace, core Landsat time-series indicators
- Main contribution to thesis: Provides a Dhaka-specific explainable ML framework that is highly defensible for feature importance and spatial heterogeneity analysis
- Reuse decision: Directly reusable for advanced Dhaka modeling section

## Notes

- Source note 1: This is the strongest explainable-ML paper in the current Bangladesh set.
- Source note 2: It is not a long-term temporal study, so it complements rather than replaces the Landsat multi-year design.
- Source note 3: A second pass can extract the exact feature ranking order from the SHAP and GeoShapley figures if needed.
