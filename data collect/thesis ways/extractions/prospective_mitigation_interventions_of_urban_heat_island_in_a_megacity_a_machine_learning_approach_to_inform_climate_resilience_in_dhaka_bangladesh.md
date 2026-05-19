# Paper Extraction

## Paper Identity

- Paper name: Prospective Mitigation Interventions of Urban Heat Island in a Megacity: A Machine Learning Approach To Inform Climate Resilience in Dhaka, Bangladesh
- Authors: A. S. M. Maksud Kamal; Shamsuddin Shahid; Anika Tabassum; Jakir Hossain
- Year: 2025
- Document type: Journal article
- Publisher or institution: Earth Systems and Environment
- DOI or URL: 10.1007/s41748-025-00810-z
- Evidence label: Extracted

## Study Area

- Study location: Dhaka Metropolitan Area / Greater Dhaka City
- Country: Bangladesh
- Urban focus: Megacity / metropolitan
- Study area boundary source: District, upazila, and study area shapefiles clipped in ArcGIS; DIVA-GIS mentioned as boundary source
- Area size: Not reported in extracted pass
- Administrative units: Dhaka South City Corporation, Dhaka North City Corporation, and suburban metropolitan extensions are referenced
- Seasonal or climatic context: Multi-year thermal assessment from 1990 to 2023

## Data Used

- Satellite source: Landsat archive through Google Earth Engine
- Sensor: Landsat 5 TM; Landsat 7 ETM+; Landsat 8 OLI/TIRS
- Acquisition dates: 1990, 1993, 1996, 1999, 2002, 2005, 2008, 2011, 2014, 2017, 2020, 2023
- Temporal coverage: 1990-2023
- Number of scenes: Twelve benchmark years reported in the extracted pass
- Path/row: Not reported
- Spatial resolution: 30 m analysis products from Landsat
- Ancillary data: Google Earth Pro imagery; study area shapefiles; climate records
- DEM: Not reported
- Meteorological data: Climate records mentioned, but station names not extracted in first pass
- Ground stations: Not reported

## Image Preprocessing

- Cloud filtering: Not fully detailed in extracted pass
- Atmospheric correction: Implemented through Google Earth Engine and Landsat processing chain; exact version not extracted in first pass
- Radiometric calibration: Handled within Landsat processing and SMW workflow
- Geometric correction: Landsat product level
- Reprojection: Maps prepared in ArcGIS; exact CRS not extracted in first pass
- Resampling: Not reported explicitly
- Clipping: Clipped to Greater Dhaka / metropolitan study area
- Seasonal harmonization: Yearly benchmark comparison across selected years
- Cross-sensor normalization: Multi-sensor workflow spanning TM, ETM+, and OLI/TIRS

## LST Extraction Workflow

- Method name: Statistical mono-window (SMW) LST retrieval
- DN to radiance step: Not fully printed in extracted pass; handled through Landsat/GEE workflow
- Brightness temperature step: Included in SMW workflow
- Emissivity estimation: Surface emissivity included in the SMW linearized radiative transfer equation
- Final LST equation: SMW algorithm following Ermida et al. (2020)
- Celsius conversion: Final LST interpreted in degrees Celsius
- UHI derivation: Multi-year LST maps used to identify hotspot evolution and support mitigation simulation
- Constants used: Sensor-specific thermal handling within TM, ETM+, and OLI/TIRS workflow
- Sensor-specific notes: Landsat 5 used for 1990-1999, Landsat 7 for 2002-2011, Landsat 8 for 2014-2023

## Variable Extraction

### NDVI

- Equation: Standard NDVI logic referenced; exact printed equation not captured in first pass
- Bands: Landsat reflective bands
- Range: Not reported numerically in extracted pass
- Thresholds: Used in correlation and ML modeling

### NDBI

- Equation: Standard NDBI logic referenced; exact printed equation not captured in first pass
- Bands: Landsat reflective bands
- Range: Not reported numerically in extracted pass
- Thresholds: Used in correlation, ML modeling, and sensitivity analysis

### NDWI

- Equation: Standard NDWI logic referenced; exact printed equation not captured in first pass
- Bands: Landsat reflective bands
- Range: Not reported numerically in extracted pass
- Thresholds: Used in correlation, ML modeling, and sensitivity analysis

### MNDWI

- Equation: Not used in the extracted pass
- Bands: Not applicable
- Range: Not reported
- Thresholds: Not applicable

### Albedo / Emissivity / UTFVI / Other

- Variable: Urban Index; Albedo
- Equation: Standard remote sensing index logic; exact printed formula not captured in first pass
- Range: Not reported numerically in extracted pass
- Thresholds: Sensitivity analysis examined +/- 25 percent variation
- Notes: Albedo, NDVI, and NDWI showed cooling relationships; UI and NDBI showed warming relationships

## LULC Classification

- Source imagery: Landsat imagery interpreted through indices; no standalone supervised LULC map accuracy table extracted in first pass
- Classification years: Multi-year interpretation from 1990 to 2023
- Class list: Urbanized, vegetated, water, and related thermal classes interpreted from maps and indices
- Classifier: No standalone supervised classifier extracted in first pass
- Supervised or unsupervised: Not clearly reported
- Training sample source: Field observations used to verify land cover classes and hotspot/coolspot locations
- Post-classification refinement: Not reported
- Change detection method: Multi-year visual and quantitative comparison of LST and index maps

## Meteorological Integration

- Variables integrated: Climate records are mentioned; detailed variables not fully extracted in first pass
- Data source: Climate records plus remote sensing
- Station names: Not reported
- Date matching logic: Not clearly extracted
- Calibration or comparison method: No direct ground LST validation table extracted; field observation used for spatial confirmation

## Modeling and Statistics

- Correlation method: Correlation matrix between LST and NDVI, NDWI, NDBI, UI, and Albedo
- Regression method: Linear regression benchmark model
- Spatial statistics: Map comparison and hotspot interpretation
- Trend analysis: Multi-year spatiotemporal LST and index change assessment
- Machine learning workflow: Linear Regression, SVM, Random Forest, and ANN compared for LST prediction
- Feature selection: Not reported separately
- Explainability: Not used
- Performance metrics: RMSE, PBIAS, rSD, R2, KGE

## Reported Values

- LST range: Reference Landsat 8 image for 2023 shows approximately 19 C to 35 C across Dhaka
- Mean LST: Not reported in extracted pass
- Max LST: Approximately 35 C in 2023 map discussion
- Min LST: Approximately 19 C in 2023 map discussion
- NDVI range: Not reported numerically in extracted pass
- NDBI range: Not reported numerically in extracted pass
- NDWI range: Not reported numerically in extracted pass
- MNDWI range: Not used in extracted pass
- Albedo range: Not reported numerically in extracted pass
- UTFVI range: Not used in extracted pass
- Correlation coefficients: LST inversely related to NDVI, NDWI, and Albedo; directly related to UI and NDBI
- Regression coefficients: Not extracted in first pass
- RMSE / MAE / R2: SVM RMSE 0.78, R2 0.70, PBIAS 1.0, rSD 1.24, KGE 0.71; RF RMSE 0.85, R2 0.68; ANN RMSE 0.87, R2 0.69, KGE 0.72; Linear regression RMSE 1.00, R2 0.69
- Accuracy / Kappa: No confusion-matrix OA/Kappa reported
- Class fractions: Not extracted in first pass
- Thresholds: Sensitivity analysis used +/- 25 percent variation in predictors
- Temperature differences: A 10 percent reduction in NDBI could reduce LST by up to 2 C; a 10 percent reduction in UI could reduce LST by about 0.5 C; a 25 percent increase in NDVI may reduce ambient temperature by about 2-3 C
- Urban-rural contrast: Not explicitly reported as a single SUHII value in extracted pass
- Bangladesh-specific parameters: A 20 percent increase in NDVI and NDWI can reduce LST by about 12 percent and 7 percent, respectively

## Validation and Testing

- Validation dataset: 10,000 randomly selected metropolitan map spots used for modeling
- Ground truth source: Field observations used to confirm land cover classes and hot/cool spots
- Train-test split: Not explicitly extracted in first pass
- Cross-validation: 10-fold cross-validation for hyperparameter tuning
- Accuracy assessment: Model comparison using RMSE, PBIAS, rSD, R2, KGE
- Sensitivity analysis: Sobol variance-based sensitivity analysis with +/- 25 percent test range
- Limitations: Data and model uncertainties acknowledged; no full in-situ LST validation table extracted in first pass
- Reproducibility notes: High for broad workflow, but exact index equations and some preprocessing details should be captured in a second pass

## Appraisal

- Reproducibility score: 4
- Robustness score: 4
- Bangladesh suitability score: 5
- Dhaka suitability score: 5
- Validation strength score: 4
- Numerical extraction richness score: 4
- Thesis reuse potential score: 5

## Thesis Use Decision

- Directly reusable components: Multi-year Dhaka Landsat design, index-LST relationship framework, ML model benchmarking, mitigation sensitivity logic
- Components needing modification: Exact preprocessing and station-climate integration should be clarified before final thesis method adoption
- Comparative-only components: ANN and RF can remain comparison models if thesis chooses a single preferred model
- Main contribution to thesis: Direct Dhaka benchmark for combining Landsat-derived LST, urban indices, and machine learning for mitigation analysis
- Reuse decision: Directly reusable with minor technical clarification

## Notes

- Source note 1: This is one of the strongest Dhaka-specific methodology papers in the current folder.
- Source note 2: SVM is the best model by RMSE and R2, while ANN has the highest KGE.
- Source note 3: A second extraction pass should capture the printed equations for NDVI, NDWI, NDBI, UI, and Albedo.
