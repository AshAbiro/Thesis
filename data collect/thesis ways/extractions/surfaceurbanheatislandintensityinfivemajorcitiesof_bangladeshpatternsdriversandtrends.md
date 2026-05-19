# Paper Extraction

## Paper Identity

- Paper name: Surface urban heat island intensity in five major cities of Bangladesh: Patterns, drivers and trends
- Authors: Ashraf Dewan; Grigory Kiselev; Dirk Botje; Golam Iftekhar Mahmud; Md. Hanif Bhuian; Quazi K. Hassan
- Year: 2021
- Document type: Journal article
- Publisher or institution: Sustainable Cities and Society, Elsevier
- DOI or URL: 10.1016/j.scs.2021.102926
- Evidence label: Extracted

## Study Area

- Study location: Dhaka; Chittagong; Khulna; Rajshahi; Sylhet
- Country: Bangladesh
- Urban focus: Major metropolitan cities
- Study area boundary source: Planning boundaries acquired from relevant city development authorities
- Area size: Not reported in extracted pass
- Administrative units: Five city planning areas
- Seasonal or climatic context: Annual and monthly day and night SUHII analysis; dry-month versus wet-month contrast discussed

## Data Used

- Satellite source: MODIS and nighttime lights products
- Sensor: MOD11A2 v006 LST; MCD12Q1 LULC; MOD09A1 surface reflectance; MCD19A2 AOD; MCD43A3 albedo; MOD44B vegetation continuous fields; DMSP-OLS; VIIRS
- Acquisition dates: Annual and monthly composites, 2000-2019
- Temporal coverage: 2000-2019
- Number of scenes: Not reported directly; 8-day composites aggregated to monthly and annual scales
- Path/row: Not applicable
- Spatial resolution: 1 km nominal resolution
- Ancillary data: LandScan annual gridded population; city planning boundary shapefiles
- DEM: Not reported
- Meteorological data: No station meteorology integrated in the extracted pass
- Ground stations: Not reported

## Image Preprocessing

- Cloud filtering: Uses clear-sky MODIS pixels only; retained pixels with LST error <= 2 K
- Atmospheric correction: Product-level MODIS v006 processing
- Radiometric calibration: Product-derived
- Geometric correction: Product-derived
- Reprojection: Nominal 1 km harmonization across inputs
- Resampling: All datasets brought to nominal 1 km
- Clipping: Clipped to each city planning boundary
- Seasonal harmonization: Monthly and annual aggregations used
- Cross-sensor normalization: DMSP-OLS intercalibrated; VIIRS cross-calibrated to DMSP-OLS annual series

## LST Extraction Workflow

- Method name: MODIS product-based SUHII assessment
- DN to radiance step: Not applicable because MOD11A2 product LST was used directly
- Brightness temperature step: Product-derived
- Emissivity estimation: Product-derived generalized split-window retrieval from MODIS bands 31 and 32
- Final LST equation: Not re-derived in the paper; MOD11A2 v006 used as input
- Celsius conversion: Product-derived LST used for SUHII analysis
- UHI derivation: SUHII defined as the difference between urban and surrounding rural areas after urban/non-urban delineation and rural buffering
- Constants used: MODIS v006 quality filtering with LST error <= 2 K
- Sensor-specific notes: Day and night observations represent approximately 10:30 am and 10:30 pm

## Variable Extraction

### NDVI

- Equation: Not used; EVI preferred over NDVI
- Bands: Not applicable
- Range: Not reported
- Thresholds: Not applicable

### NDBI

- Equation: Not used; BCI used as imperviousness proxy
- Bands: Not applicable
- Range: Not reported
- Thresholds: Not applicable

### NDWI

- Equation: McFeeters NDWI from MODIS surface reflectance
- Bands: Product-derived from MOD09A1
- Range: Not reported
- Thresholds: Not reported

### MNDWI

- Equation: Not used
- Bands: Not applicable
- Range: Not reported
- Thresholds: Not applicable

### Albedo / Emissivity / UTFVI / Other

- Variable: EVI, BCI, MSI, white-sky albedo, vegetation cover fraction, aerosol optical depth, population, nighttime lights
- Equation: Equations for indices are reported in supplementary material; EVI used instead of NDVI due to NDVI saturation
- Range: Not fully reported in extracted pass
- Thresholds: Variables with strong collinearity removed using VIF screening
- Notes: White-sky albedo was used because black-sky and white-sky albedo gave similar outcomes in cited literature

## LULC Classification

- Source imagery: MODIS MCD12Q1 yearly land cover
- Classification years: 2000-2019
- Class list: IGBP classes reclassified into urban and non-urban
- Classifier: Product reclassification; not a new supervised classification
- Supervised or unsupervised: Not applicable
- Training sample source: Not applicable
- Post-classification refinement: Iterative urban and rural delineation; rural boundary generated via buffering
- Change detection method: Annual and monthly SUHII comparison with trend testing

## Meteorological Integration

- Variables integrated: Aerosol optical depth only as an environmental driver; no station weather series
- Data source: MCD19A2 AOD
- Station names: Not applicable
- Date matching logic: MODIS composite scale
- Calibration or comparison method: None with ground stations

## Modeling and Statistics

- Correlation method: Pearson correlation between annual and monthly SUHII and candidate drivers
- Regression method: No predictive regression model used
- Spatial statistics: Spatial SUHII pattern examined by pixel-wise urban-rural mean difference
- Trend analysis: Mann-Kendall tests for annual and monthly day/night SUHII
- Machine learning workflow: Not used
- Feature selection: VIF-based removal of collinear variables
- Explainability: Not applicable
- Performance metrics: Pearson r; across-city day-night temperature relationship R2 = 0.50, p = 0.00

## Reported Values

- LST range: Raw LST range not reported in the extracted pass
- Mean LST: Not reported in the extracted pass
- Max LST: Not reported in the extracted pass
- Min LST: Not reported in the extracted pass
- NDVI range: Not applicable
- NDBI range: Not applicable
- NDWI range: Not reported numerically in extracted pass
- MNDWI range: Not applicable
- Albedo range: Not reported numerically in extracted pass
- UTFVI range: Not used
- Correlation coefficients: Across-city day versus night relationship R2 = 0.50, p = 0.00; daytime population differential versus SUHII for Dhaka r = 0.92
- Regression coefficients: Not applicable
- RMSE / MAE / R2: R2 = 0.50 for cross-city day-night relationship
- Accuracy / Kappa: No separate classification accuracy reported
- Class fractions: Not reported in extracted pass
- Thresholds: LST error <= 2 K retained; VIF threshold < 10 after variable screening
- Temperature differences: Annual daytime SUHII Dhaka 2.74 C; Chittagong 1.92 C. Annual nighttime SUHII Chittagong 1.90 C; Dhaka 1.57 C
- Urban-rural contrast: SUHII reported as urban-rural contrast
- Bangladesh-specific parameters: Dry months generally show stronger SUHII than wet months

## Validation and Testing

- Validation dataset: None beyond product quality controls
- Ground truth source: Not used
- Train-test split: Not applicable
- Cross-validation: Not applicable
- Accuracy assessment: MODIS product quality filtering and statistical significance testing
- Sensitivity analysis: Not reported
- Limitations: No in-situ UHI measurements; remotely sensed drivers only; monsoon cloudiness reduces valid pixel counts
- Reproducibility notes: High for product-based SUHII workflow, though supplementary equations should be checked for exact index formulas

## Appraisal

- Reproducibility score: 4
- Robustness score: 4
- Bangladesh suitability score: 5
- Dhaka suitability score: 4
- Validation strength score: 3
- Numerical extraction richness score: 4
- Thesis reuse potential score: 5

## Thesis Use Decision

- Directly reusable components: Bangladesh-scale SUHII benchmarking, urban-rural SUHII definition, long-term trend logic, driver interpretation
- Components needing modification: Spatial resolution is too coarse for detailed Dhaka intra-urban LST mapping
- Comparative-only components: MODIS-based city-scale comparison should complement, not replace, Landsat-based Dhaka analysis
- Main contribution to thesis: Provides a Bangladesh benchmark showing Dhaka as a high-intensity SUHII city and identifies major drivers
- Reuse decision: Directly reusable as Bangladesh comparative benchmark

## Notes

- Source note 1: This is a Bangladesh-priority benchmark paper for national comparison.
- Source note 2: It uses EVI instead of NDVI because the authors considered NDVI prone to saturation.
- Source note 3: Follow-up extraction can capture more table-level coefficients from Table 2 if needed.
