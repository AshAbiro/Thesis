# Bangladesh UHI/LST/LULC Thesis Framework

## 1. Purpose

This framework is the master working document for a Bangladesh-focused thesis on Urban Heat Island (UHI), Land Surface Temperature (LST), and Land Use/Land Cover (LULC).

It has four functions:

1. extract methods from Bangladesh papers exactly as written
2. capture reported values and performance metrics without losing detail
3. compare methods across Dhaka and other Bangladesh case studies
4. convert the extracted literature into a defensible thesis methodology

This framework is designed to be cumulative. Every new paper, thesis page, figure, screenshot, or note should be added into this structure rather than summarized loosely.

## 2. Scope and Priority

### Geographic Priority

1. Dhaka
2. Rajshahi
3. Khulna
4. Gazipur
5. Chattogram
6. Sylhet
7. Barishal
8. Kushtia
9. Chuadanga
10. other Bangladesh urban or peri-urban case studies

### Evidence Priority

1. Bangladesh journal papers
2. Bangladesh theses and dissertations
3. Bangladesh technical reports
4. South Asian methodological papers when Bangladesh evidence is weak
5. non-Bangladesh papers only for methodological support

### Default Analytical Priority

1. LST retrieval consistency
2. LULC change detection
3. index-temperature relationships
4. urban thermal pattern interpretation
5. validation and reproducibility
6. Dhaka suitability

## 3. Working Thesis Position

The default thesis position is:

- Dhaka is the primary methodological anchor.
- Bangladesh-specific urban thermal analysis must account for wetlands, river corridors, monsoon seasonality, dense mixed land cover, peri-urban conversion, and rapid built-up expansion.
- Landsat-based multi-year analysis is the most defensible backbone for historical LST and LULC comparison.
- NDVI, NDBI, and a water-sensitive index such as NDWI or MNDWI should be treated as minimum explanatory variables.
- LULC class-temperature comparison is a core analytical requirement.
- validation must go beyond map presentation and include accuracy or model performance evidence

These are provisional thesis decisions. They should be revised only when stronger extracted evidence justifies a change.

## 4. Evidence Labels

Every note, value, and methodological statement must be tagged using one of the following labels:

- `Extracted`: directly stated in the source
- `Derived`: computed from values reported in the source
- `Inferred`: interpreted from text, equations, or figure content when not written explicitly
- `Thesis Decision`: selected for the final thesis after comparison

Never present a `Derived`, `Inferred`, or `Thesis Decision` item as if it were directly reported by the paper.

## 5. What Counts as a Complete Extraction

A paper is not considered fully extracted unless the following are checked:

- paper identity captured
- study area captured
- sensor and temporal coverage captured
- preprocessing steps captured
- LST method captured
- all indices captured
- LULC method captured
- validation captured
- reported values captured
- limitations captured
- thesis reuse decision captured

If any section is missing, mark it clearly as `Not reported`.

## 6. Bangladesh City Comparison Logic

Use this city-level structure when comparing papers.

| City | Typical Relevance to Thesis | Main Thermal Drivers to Check | Main Method Risks |
|---|---|---|---|
| Dhaka | Primary case | dense built-up, transport corridors, industry, wetland loss, peri-urban sprawl | mixed pixels, boundary choice, high landscape heterogeneity |
| Rajshahi | Strong comparison city | dry-season heating, vegetation loss, built-up growth | overgeneralizing dry-climate signal to Dhaka |
| Khulna | Strong comparison city | water proximity, estuarine context, urban expansion | strong water influence may distort direct Dhaka comparison |
| Gazipur | High Dhaka relevance | industrial growth, fringe urbanization, vegetation conversion | administrative boundary inconsistency |
| Chattogram | Moderate comparison | port-industry, hill-urban interaction, coastal influence | terrain and coastal effects differ from Dhaka |
| Sylhet | Moderate comparison | vegetation-water interaction, peri-urban change | cooler baseline and wet conditions reduce comparability |
| Barishal | Moderate comparison | water-dominant landscape, compact urban core | waterbody effect stronger than Dhaka |
| Kushtia | Supplementary | regional urbanization and open land conversion | smaller-city scaling issues |
| Chuadanga | Supplementary | heat-prone inland conditions | not structurally equivalent to Dhaka |

## 7. Working Research Questions

These can be refined later, but they provide structure for extraction.

### RQ1

How has LULC change influenced spatial and temporal variation of LST in Dhaka and comparable Bangladesh urban areas?

### RQ2

Which land surface indices consistently explain thermal variation in Bangladesh urban environments?

### RQ3

Which LST retrieval and LULC classification workflows are most reproducible and thesis-grade for Dhaka?

### RQ4

How robust are Bangladesh UHI findings across years, seasons, sensors, and validation strategies?

## 8. Working Hypotheses

- `H1`: built-up expansion increases mean and maximum LST in Bangladesh urban areas
- `H2`: NDVI shows a negative relationship with LST
- `H3`: NDBI shows a positive relationship with LST
- `H4`: water-rich or vegetated classes have significantly lower LST than dense built-up classes
- `H5`: same-season multi-year designs are more robust than mixed-season comparisons

## 9. Master Source Intake Protocol

Use this protocol for every new source.

### Step 1. Source Identity

Record:

- full title
- authors
- year
- source type
- publisher or institution
- DOI or link if available
- Bangladesh city or region

### Step 2. Method Capture

Extract:

- data source
- sensor
- years
- resolution
- preprocessing
- LST workflow
- indices
- LULC method
- meteorological integration
- statistics or ML
- validation

### Step 3. Equation Capture

Write down every equation exactly if shown.

If the paper does not print an equation but clearly describes a standard formula:

- mark the method as `Inferred`
- write the assumed standard formula separately
- do not merge it with `Extracted` content

### Step 4. Value Capture

Capture every numeric value available:

- ranges
- means
- coefficients
- percentages
- thresholds
- class areas
- performance metrics

### Step 5. Critical Appraisal

Judge:

- reproducibility
- robustness
- Bangladesh suitability
- Dhaka suitability
- validation strength
- thesis reuse potential

### Step 6. Final Use Decision

Assign one:

- `Directly reusable`
- `Reusable with modification`
- `Comparative only`
- `Weak support`
- `Do not use for methodology`

## 10. Master Extraction Structure

For each paper, complete the following sections.

### A. Paper Identity

- Paper name
- Authors
- Year
- Document type
- Publisher or institution
- DOI or URL
- Study objective
- Bangladesh relevance

### B. Study Area Perspective

- City or district
- Urban, peri-urban, metropolitan, watershed, or mixed focus
- Study area boundary source
- Area size if reported
- administrative units covered
- urban expansion context
- hydro-ecological context
- climate or seasonal context used by authors

### C. Data Used

- satellite data source
- satellite sensor
- acquisition dates
- temporal coverage
- number of scenes
- path/row if reported
- spatial resolution
- ancillary data
- DEM usage
- meteorological data source
- ground station names
- secondary spatial data such as roads or population

### D. Image Preprocessing

- cloud filtering criteria
- atmospheric correction method
- radiometric calibration
- geometric correction
- reprojection
- mosaicking if used
- band stacking or clipping
- resampling method
- study area masking
- seasonal harmonization logic
- cross-sensor normalization logic
- quality control masking

### E. LST Extraction Workflow

Capture the exact sequence used in the paper:

1. image selection and thermal band identification
2. DN to radiance or top-of-atmosphere conversion
3. radiance to brightness temperature
4. emissivity estimation logic
5. final LST calculation
6. Celsius conversion if applicable
7. UHI or hotspot derivation if applied

Record:

- equations used
- constants used
- wavelength term used
- sensor-specific constants
- emissivity formula
- NDVI threshold logic
- whether the method is single-channel, mono-window, split-window, or other

### F. Variable Extraction

Extract the exact method for each variable used:

- NDVI
- NDBI
- NDWI
- MNDWI
- SAVI
- albedo
- emissivity
- vegetation fraction or proportion of vegetation
- built-up density
- impervious surface proxy
- UTFVI
- SUHI intensity
- any other thermal comfort or environment index

For each variable, capture:

- equation
- bands used
- thresholds
- normalization
- range
- interpretation class breaks

### G. LULC Classification

- source imagery
- classification years
- training sample source
- classes used
- class definition logic
- classifier
- supervised or unsupervised status
- object-based or pixel-based status
- ML or deep learning status
- post-classification refinement
- change detection method
- accuracy assessment method
- overall accuracy
- kappa
- producer's accuracy
- user's accuracy

### H. Meteorological Integration

- air temperature source
- humidity source
- rainfall source
- wind or radiation source
- urban-rural station comparison
- satellite-station date matching
- calibration or bias correction logic
- interpretation use of meteorological variables

### I. Modeling and Statistics

- correlation test
- significance level
- regression model type
- feature selection method
- spatial autocorrelation test
- hotspot analysis
- temporal trend analysis
- machine learning workflow
- explainability method such as SHAP
- performance metrics

### J. Reported Values

Always capture:

- LST range
- mean LST
- maximum LST
- minimum LST
- NDVI range
- NDBI range
- NDWI range
- MNDWI range
- albedo range
- UTFVI range
- class area percentages
- correlation coefficients
- regression coefficients
- RMSE
- MAE
- R2
- AUC
- F1
- accuracy
- kappa
- temperature difference between classes
- urban-rural thermal contrast
- any Bangladesh-specific constants or thresholds

### K. Validation and Testing

- validation dataset
- ground truth source
- train-test split
- cross-validation design
- date alignment logic
- sensitivity analysis
- uncertainty sources
- limitations acknowledged by authors
- reproducibility level

### L. Thesis Use Decision

After extraction, decide:

- what can be reused directly
- what should be modified for Dhaka
- what is too weak for thesis-grade methodology
- what should remain comparative only
- what exact contribution this paper makes to the thesis

## 11. Paper Extraction Template

Use this structure each time a new paper is added.

### Paper Name

### Study Location

### Document Type

### Data Used

### Temporal Coverage

### Spatial Resolution

### Image Preprocessing

### LST Extraction Workflow

### Variable Extraction

### LULC Classification

### Meteorological Integration

### Modeling and Statistics

### Equations Used

### Reported Values

### Validation and Testing

### Limitations

### Bangladesh Relevance

### Dhaka Relevance

### How It Can Be Used in the Thesis

### Reuse Decision

## 12. Harmonization Rules Across Papers

Papers will use different sensors, years, class systems, and seasons. Use the following harmonization rules before comparison.

### Season Harmonization

- compare same-season scenes first
- keep dry-season, pre-monsoon, monsoon, and post-monsoon results separate unless the paper proves seasonal comparability
- never treat wet-season and dry-season LST values as directly equivalent without caution

### Spatial Harmonization

- note whether values refer to full metropolitan area, municipal core, or selected wards
- check whether waterbodies and wetlands are included inside the study boundary
- do not compare city-wide means across incompatible extents without annotation

### Sensor Harmonization

- record the exact sensor generation
- note thermal band resolution differences
- note if Landsat 7 SLC-off data are involved
- note if Landsat 8 band 11 was used despite known caution in many workflows

### LULC Harmonization

Where class systems differ, map them into a standard comparison set:

- built-up
- vegetation
- waterbody
- bare land/open soil
- wetland
- agriculture
- mixed/other

Do not force categories where the paper did not support them. If necessary, use both the original class system and the mapped class system.

## 13. Sensor and Band Reference

Use this table when extracting formulas and checking band usage.

| Sensor | Red | NIR | SWIR1 | SWIR2 | Thermal | Native Thermal Resolution | Notes |
|---|---|---|---|---|---|---|---|
| Landsat 5 TM | B3 | B4 | B5 | B7 | B6 | 120 m | thermal often resampled to 30 m in products |
| Landsat 7 ETM+ | B3 | B4 | B5 | B7 | B6 | 60 m | SLC-off issue after 2003 must be noted |
| Landsat 8 OLI/TIRS | B4 | B5 | B6 | B7 | B10, B11 | 100 m | band 10 is commonly preferred for LST |
| Landsat 9 OLI-2/TIRS-2 | B4 | B5 | B6 | B7 | B10, B11 | 100 m | same logic as Landsat 8 |
| Sentinel-2 MSI | B4 | B8 | B11 | B12 | no thermal band | not applicable | useful for LULC and indices, not direct LST |

## 14. Equation Bank for Method Extraction

These equations should be used as a checking reference. Only mark them as `Extracted` if the paper explicitly uses them.

### 14.1 DN to Spectral Radiance

For Landsat 8/9 style metadata-based conversion:

`L_lambda = M_L * Qcal + A_L`

where:

- `L_lambda` = spectral radiance
- `M_L` = radiance multiplicative scaling factor from metadata
- `A_L` = radiance additive scaling factor from metadata
- `Qcal` = quantized calibrated pixel value

For older Landsat workflows, authors may use:

`L_lambda = ((Lmax - Lmin) / (Qcalmax - Qcalmin)) * (Qcal - Qcalmin) + Lmin`

### 14.2 Brightness Temperature

`BT = K2 / ln((K1 / L_lambda) + 1)`

where `K1` and `K2` are thermal conversion constants from metadata or documentation.

### 14.3 NDVI

`NDVI = (NIR - Red) / (NIR + Red)`

### 14.4 NDBI

`NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)`

### 14.5 NDWI

`NDWI = (Green - NIR) / (Green + NIR)`

### 14.6 MNDWI

`MNDWI = (Green - SWIR1) / (Green + SWIR1)`

### 14.7 SAVI

`SAVI = ((NIR - Red) / (NIR + Red + L)) * (1 + L)`

Record the exact `L` value used if reported.

### 14.8 Proportion of Vegetation

`Pv = ((NDVI - NDVImin) / (NDVImax - NDVImin))^2`

### 14.9 Surface Emissivity

A frequently used NDVI-based approximation is:

`epsilon = 0.004 * Pv + 0.986`

If papers use threshold-based emissivity classes instead, extract those classes exactly.

### 14.10 Land Surface Temperature

`LST = BT / (1 + (lambda * BT / rho) * ln(epsilon))`

with Celsius conversion:

`LST(C) = LST(K) - 273.15`

where:

- `lambda` = effective wavelength used in the workflow
- `rho` = `h * c / sigma`, often represented as `1.438 x 10^-2 m K`

### 14.11 UTFVI

Common form:

`UTFVI = (Ts - Tmean) / Tmean`

Always record if the paper uses a different form or different class thresholds.

### 14.12 SUHI Intensity

Common operational form:

`SUHI = LSTurban - LSTreference`

Record:

- how urban and reference areas were defined
- whether reference means rural, vegetated, peripheral, or non-built-up land

## 15. Bangladesh-Specific Methodological Risks

Every source and every final thesis method should be tested against the following Bangladesh-specific risks.

### 15.1 Seasonal Risk

- monsoon cloud contamination
- large seasonal waterbody expansion or contraction
- high humidity affecting interpretation
- comparing April scenes with December scenes without adjustment

### 15.2 Spatial Risk

- Dhaka mixed pixels
- built-up and bare soil confusion
- wetland and shallow water confusion
- industrial surfaces behaving differently from residential built-up

### 15.3 Sensor Risk

- Landsat 7 SLC-off striping or gap handling
- thermal resampling artifacts
- mixing Landsat 5, 7, 8, and 9 without documenting transition effects

### 15.4 Classification Risk

- inconsistent LULC classes between years
- training samples not temporally aligned with the imagery
- accuracy reported only for one year
- no independent validation

### 15.5 Statistical Risk

- using correlation only without significance
- ignoring multicollinearity among indices
- inferring causality from cross-sectional association
- reporting strong spatial pattern claims without spatial statistics

## 16. Standardized Bangladesh LULC Class Dictionary

Use this dictionary to harmonize class names across studies.

| Standard Class | Typical Synonyms in Papers | Core Meaning |
|---|---|---|
| Built-up | urban, settlement, impervious, developed land | residential, commercial, industrial, roads, built structures |
| Vegetation | green area, forest, tree cover, cropland vegetation, grassland | photosynthetically active vegetated surfaces |
| Waterbody | river, lake, pond, canal, open water | permanent or semi-permanent open water |
| Wetland | marsh, lowland, seasonally inundated land | waterlogged or hydrologically transitional land |
| Bare Land/Open Soil | fallow land, exposed soil, sand, barren land | non-vegetated exposed surfaces |
| Agriculture | cropland, agricultural land | cultivated land, often seasonally variable |
| Mixed/Other | mixed land, shadow, unclassified | ambiguous or residual class |

## 17. Reusable Bangladesh Thesis Methodology Blueprint

This is the current default methodology for the thesis. Replace parts of it only when extracted evidence suggests a stronger alternative.

### 17.1 Study Area Design

- primary area: Dhaka metropolitan region
- recommended subzones:
  - dense core
  - mixed residential-commercial belt
  - industrial belt
  - peri-urban expansion belt
  - waterbody and wetland system
  - vegetation/open land reference zone
- boundary should be kept constant across all years
- if different administrative boundaries appear in literature, record them separately

### 17.2 Temporal Design

- use multiple years rather than a single-date comparison
- prioritize same-month or same-season images
- preferred strategy:
  - historical baseline year
  - intermediate transition year(s)
  - recent year
- if more than three dates are available, keep the month window narrow

### 17.3 Data Strategy

#### Primary LST Backbone

- Landsat 5 TM for early years
- Landsat 7 ETM+ where necessary with explicit SLC-off caution
- Landsat 8 OLI/TIRS for recent years
- Landsat 9 if the contemporary period is included

#### LULC and Finer Feature Support

- Landsat for longitudinal consistency
- Sentinel-2 for improved classification detail where year matching is feasible

#### Ancillary Support

- administrative boundary
- road network
- waterbody or wetland inventory if available
- meteorological station data
- population or built-up proxy if needed

### 17.4 Data Selection Rules

- cloud cover should be as low as possible
- scenes should represent similar seasonal conditions
- scene dates should avoid immediately post-heavy-rain anomalies unless explicitly studied
- use one coordinate system across all layers
- record data source, product level, and download date

### 17.5 Preprocessing Rules

- apply sensor-appropriate radiometric conversion
- apply atmospheric correction where the paper or workflow requires it
- clip to a constant study boundary
- mask cloud, cloud shadow, and bad pixels
- resample outputs to a common analysis grid
- keep a processing log for each year and scene

### 17.6 Recommended LST Workflow

1. select thermal scenes with acceptable cloud cover and comparable season
2. perform radiometric conversion and brightness temperature calculation
3. calculate NDVI
4. estimate proportion of vegetation
5. estimate emissivity using the reported or chosen method
6. derive LST
7. convert to Celsius
8. generate thermal classes, hotspots, and zonal summaries

### 17.7 Recommended Explanatory Variables

Minimum required:

- NDVI
- NDBI
- NDWI or MNDWI
- LULC class

Strong optional additions:

- albedo
- built-up density
- distance to water
- distance to major road
- population or nighttime light proxy
- vegetation fraction

### 17.8 Recommended LULC Workflow

Preferred thesis-grade option:

1. define a stable class system
2. prepare training samples using high-resolution reference imagery
3. classify each year with a reproducible supervised classifier
4. apply post-classification cleaning if justified
5. validate using an independent sample
6. calculate change trajectories by class

Current default classifier decision:

- `Primary recommendation`: Random Forest for stronger reproducibility and performance
- `Secondary comparison option`: Maximum Likelihood when the Bangladesh literature repeatedly uses it and comparability matters

### 17.9 Recommended Statistical Testing

Minimum thesis-grade tests:

- Pearson or Spearman correlation between LST and NDVI
- Pearson or Spearman correlation between LST and NDBI
- correlation between LST and NDWI or MNDWI
- mean LST by LULC class
- class-wise temperature difference
- temporal change in class fractions
- hotspot overlay with built-up expansion

Recommended stronger tests:

- multiple linear regression
- spatial regression if spatial dependency is strong
- ANOVA or Kruskal-Wallis for LST differences by class
- Moran's I for spatial autocorrelation
- Getis-Ord Gi* for hotspot detection
- SHAP or equivalent importance analysis if a predictive ML model is used

### 17.10 Meteorological Integration

Minimum meteorological integration:

- station name
- location
- observation date
- air temperature
- relation to image date

Preferred stronger integration:

- humidity
- rainfall
- wind
- seasonal context
- discussion of why air temperature and satellite LST are not identical but still analytically related

### 17.11 Output Products

The thesis should produce:

- yearly LST maps
- yearly LULC maps
- yearly index maps
- class-area change table
- class-wise LST table
- correlation table
- hotspot map
- comparative Bangladesh review matrix
- final methodology decision table

## 18. Minimum Thesis-Grade Acceptance Criteria

A method should not be used as the core thesis method unless most of the following are satisfied.

### Data and Scene Selection

- study area is clearly defined
- acquisition dates are stated
- scene season is appropriate and comparable
- sensor is identified correctly

### LST Method

- equation chain is explicit
- constants are identifiable
- emissivity logic is stated
- final Celsius conversion is clear

### LULC Method

- class system is explicit
- classifier is stated
- training or reference sample logic is stated
- accuracy assessment is reported

### Validation

- OA and kappa are reported for classification when relevant
- statistical significance is reported for correlations or models where appropriate
- ML papers report RMSE, MAE, R2, AUC, F1, or similar metrics as appropriate

### Interpretation

- findings are tied to land cover or urban form, not only map color
- limitations are acknowledged
- results are reproducible from the described workflow

## 19. Validation and Testing Framework

For every extracted method, score the following from `1` to `5`.

### 19.1 Reproducibility

- `5`: equations, dates, sensors, and parameters fully clear
- `4`: mostly clear with minor missing details
- `3`: general method clear but some steps must be inferred
- `2`: major gaps in reproducibility
- `1`: cannot be replicated reliably

### 19.2 Robustness

- `5`: stable multi-year logic with strong control of seasonal and sensor issues
- `4`: generally strong but some manageable risks
- `3`: usable with caution
- `2`: substantial methodological fragility
- `1`: unreliable

### 19.3 Bangladesh Suitability

- `5`: strongly reflects Bangladesh environmental and urban conditions
- `4`: suitable with small adjustments
- `3`: partially transferable
- `2`: weakly transferable
- `1`: not appropriate

### 19.4 Dhaka Suitability

- `5`: highly suitable for dense, mixed, wetland-influenced Dhaka
- `4`: suitable with boundary or classification refinements
- `3`: moderate fit only
- `2`: weak fit
- `1`: unsuitable

### 19.5 Validation Strength

- `5`: strong independent validation with complete metrics
- `4`: acceptable validation with minor gaps
- `3`: limited validation
- `2`: weak validation
- `1`: validation absent or poor

### 19.6 Numerical Extraction Richness

- `5`: rich reported values and metrics
- `4`: enough values for strong comparison
- `3`: moderate numeric content
- `2`: sparse values
- `1`: almost entirely narrative

### 19.7 Thesis Reuse Potential

- `5`: directly reusable as a core thesis method
- `4`: reusable with small modification
- `3`: useful as support or comparison
- `2`: weak support only
- `1`: avoid for core methodology

## 20. Comparative Review Matrix

Use this table after extracting papers.

| Paper | Location | Year(s) Studied | Sensor | LST Method | Indices | LULC Method | Validation | Key Reported Values | Main Finding | Dhaka Suitability | Reuse Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| To be filled |  |  |  |  |  |  |  |  |  |  |  |

## 21. Value Extraction Matrix

Use this for direct numeric comparison.

| Paper | LST Range | Mean LST | NDVI Range | NDBI Range | NDWI/MNDWI Range | OA | Kappa | RMSE/MAE/R2 | Urban-Rural Contrast | Key Thresholds |
|---|---|---|---|---|---|---|---|---|---|---|
| To be filled |  |  |  |  |  |  |  |  |  |  |

## 22. Method Decision Matrix

Use this to turn literature into the final thesis method.

| Method Component | Options Found in Literature | Most Common Bangladesh Practice | Strongest Practice | Final Thesis Decision | Reason |
|---|---|---|---|---|---|
| Scene selection |  |  |  |  |  |
| LST retrieval |  |  |  |  |  |
| Emissivity estimation |  |  |  |  |  |
| LULC classifier |  |  |  |  |  |
| Validation design |  |  |  |  |  |
| Statistical test |  |  |  |  |  |
| Meteorological integration |  |  |  |  |  |

## 23. Bangladesh Interpretation Rules

Interpretation should remain Bangladesh-specific and not generic.

### Always Discuss

- wetland and waterbody cooling effects
- conversion of vegetation or open land to built-up surfaces
- peri-urban expansion
- dense urban morphology
- seasonal variability and monsoon influence
- infrastructural and industrial concentration

### Avoid

- claiming causality from simple correlation
- importing non-Bangladesh thresholds without justification
- treating all urban areas as structurally equivalent to Dhaka
- comparing different seasons as if they were directly comparable

## 24. Thesis Writing Structure

Use this chapter structure when converting the framework into prose.

### Chapter 1

- background
- problem statement
- objectives
- research questions
- significance

### Chapter 2

- Bangladesh UHI/LST/LULC literature
- Dhaka-focused evidence
- other Bangladesh case comparisons
- methodological gaps

### Chapter 3

- study area
- data sources
- preprocessing
- LST methodology
- index methodology
- LULC methodology
- validation framework
- statistical analysis
- limitations

### Chapter 4

- LULC change results
- LST distribution results
- index distribution
- class-wise thermal contrasts
- hotspot results
- model or correlation outputs

### Chapter 5

- Bangladesh interpretation
- Dhaka comparison with other Bangladesh cities
- methodological implications
- policy and planning implications
- limitations and future work

## 25. Immediate Use Workflow

Whenever new material is provided:

1. extract the source using the paper template
2. populate the CSV row
3. update the comparative matrix
4. update the value extraction matrix
5. score the paper
6. revise the method decision matrix if the new evidence is stronger
7. update the thesis methodology blueprint if needed

## 26. Current Default Thesis Decisions

These remain provisional until evidence accumulates.

- Dhaka remains the primary methodological anchor.
- multi-year Landsat analysis remains the default temporal backbone
- same-season image selection remains mandatory unless unavailable
- NDVI, NDBI, and NDWI or MNDWI remain minimum explanatory variables
- built-up, vegetation, waterbody, and bare/open land remain minimum LULC classes
- Random Forest is the current preferred thesis classifier, with Maximum Likelihood retained as a comparison point if strongly represented in Bangladesh papers
- LST-class comparison and hotspot analysis remain required outputs
- validation must be explicit and numerical

## 27. Definition of a Completed Framework

This framework is considered operationally complete when:

- the extraction template is stable
- the comparison matrices are stable
- the thesis method blueprint is stable
- the validation rubric is stable
- the first batch of Bangladesh papers can be entered without adding new structural fields

The framework is now intended to be stable enough for continuous source integration.
