# Thesis Methodology Blueprint

This file converts the master framework into a chapter-ready methodology structure for a Bangladesh-focused thesis on UHI, LST, and LULC with Dhaka as the primary case.

## 1. Study Design

The study will analyze the spatial and temporal relationship between urban expansion, land use/land cover transformation, and land surface temperature in Dhaka. Other Bangladesh case studies will be used as comparative evidence to justify methodological choices and interpret the Dhaka results within the national context.

## 2. Study Area

The primary study area is Dhaka metropolitan region. The boundary used for analysis should remain constant across all selected years. If literature uses DCC, DNCC/DSCC, RAJUK, DMDP, or metropolitan extents, those differences should be documented and a single defensible thesis boundary should be chosen.

Recommended internal zones:

- dense urban core
- industrial and transport corridor
- mixed residential-commercial zone
- peri-urban expansion zone
- wetlands and river corridor
- vegetation and open land reference zone

## 3. Data Sources

### Satellite Data

- Landsat 5 TM for historical analysis where required
- Landsat 7 ETM+ where necessary, with explicit treatment of SLC-off issues
- Landsat 8 OLI/TIRS for recent multi-year analysis
- Landsat 9 OLI-2/TIRS-2 if a current-year extension is included
- Sentinel-2 MSI for higher-resolution LULC support where temporal compatibility exists

### Ancillary Data

- administrative boundary shapefiles
- road network if urban accessibility or density is analyzed
- meteorological station observations
- high-resolution imagery for training and validation
- optional population or nighttime light proxies if supported by the literature

## 4. Temporal Design

The analysis should use multiple years selected from comparable months or seasons. Same-season imagery is preferred to reduce seasonal bias. Mixed-season comparisons should be avoided unless justified and explicitly tested.

Preferred design logic:

- one historical baseline year
- one transitional year
- one recent year
- more years can be added if scene comparability remains strong

## 5. Image Preprocessing

All selected scenes should be processed using a consistent workflow:

1. identify scenes with low cloud cover
2. apply radiometric conversion
3. apply atmospheric correction if required by the selected workflow
4. mask cloud, cloud shadow, and bad pixels
5. clip all layers to the common study boundary
6. resample outputs to a consistent spatial grid
7. document product level, processing assumptions, and metadata constants

## 6. LST Extraction

The default LST retrieval chain is:

1. convert thermal DN to spectral radiance or use metadata-based radiance scaling
2. convert radiance to brightness temperature
3. calculate NDVI from reflective bands
4. estimate vegetation proportion
5. estimate surface emissivity
6. calculate land surface temperature
7. convert Kelvin to Celsius

Core equations:

`BT = K2 / ln((K1 / L_lambda) + 1)`

`NDVI = (NIR - Red) / (NIR + Red)`

`Pv = ((NDVI - NDVImin) / (NDVImax - NDVImin))^2`

`epsilon = 0.004 * Pv + 0.986`

`LST = BT / (1 + (lambda * BT / rho) * ln(epsilon))`

`LST(C) = LST(K) - 273.15`

Any paper-specific constants or variants should be recorded separately rather than overwritten by the default method.

## 7. Variable Extraction

The minimum explanatory variable set should include:

- NDVI
- NDBI
- NDWI or MNDWI
- LULC class

Optional strengthening variables:

- albedo
- emissivity
- vegetation fraction
- UTFVI
- distance to water
- built-up density
- population proxy

## 8. LULC Classification

The thesis should use a stable class system across all years. The minimum class set is:

- built-up
- vegetation
- waterbody
- bare land/open soil

Wetland and agriculture can be separated if the data and reference evidence support stable discrimination.

Recommended classifier:

- Random Forest as the primary thesis-grade option

Comparison option:

- Maximum Likelihood for comparison with legacy Bangladesh studies

Minimum LULC workflow:

1. define class schema
2. collect training samples from high-resolution reference sources
3. classify each year using the same logic
4. refine the output only when justified
5. validate with independent samples
6. compute class areas and change trajectories

## 9. Validation Framework

Classification validation should report:

- confusion matrix
- overall accuracy
- kappa
- producer's accuracy if available
- user's accuracy if available

Thermal or statistical validation should report:

- correlation coefficient
- significance level
- RMSE, MAE, or R2 if model-based
- sensitivity or uncertainty notes where available

## 10. Statistical Analysis

Minimum required tests:

- correlation between LST and NDVI
- correlation between LST and NDBI
- correlation between LST and NDWI or MNDWI
- mean LST by LULC class
- change in LULC fractions over time

Stronger recommended tests:

- multiple regression
- ANOVA or Kruskal-Wallis for class-wise thermal differences
- Moran's I for spatial autocorrelation
- hotspot analysis using Getis-Ord Gi*
- feature importance or SHAP if a predictive ML model is used

## 11. Meteorological Integration

Meteorological observations should be used to contextualize satellite-based LST results. At minimum, the study should document station name, observation date, and air temperature. If available, humidity, rainfall, and wind should be incorporated into interpretation.

The thesis should explicitly note that air temperature and land surface temperature are related but not identical measures.

## 12. Expected Outputs

The final methodology should support the following outputs:

- multi-year LST maps
- multi-year LULC maps
- index maps
- class-wise temperature tables
- hotspot maps
- comparative Bangladesh literature matrix
- methodology decision table

## 13. Methodological Cautions

- avoid mixed-season comparison unless justified
- document boundary differences carefully
- do not assume all Bangladesh cities are directly equivalent to Dhaka
- do not use unvalidated classification outputs
- do not treat correlation as causation

## 14. Final Method Selection Logic

The final thesis method should prefer the workflow that is:

- most reproducible
- most suitable for Dhaka
- best supported by Bangladesh evidence
- strongest in validation quality
- stable across years and sensors
