# Bangladesh UHI Extraction CSV Dictionary

This file explains how to fill the columns in `bangladesh_uhi_extraction_master.csv`.

## Identity Fields

- `paper_id`: short stable identifier such as `dhaka_rahman_2022_lst`
- `title`: full paper title
- `authors`: authors exactly as listed
- `year`: publication year
- `document_type`: journal article, thesis, report, conference paper
- `study_location`: city, district, or region
- `country`: usually Bangladesh
- `study_objective`: one-sentence objective
- `bangladesh_relevance`: why the paper matters to the thesis
- `urban_focus`: urban, peri-urban, metropolitan, watershed, mixed

## Study Area and Data Fields

- `study_area_boundary_source`: administrative, metropolitan, watershed, author-defined, or not reported
- `study_area_size_km2`: numeric area if reported
- `climate_or_seasonal_context`: dry season, pre-monsoon, monsoon, winter, etc.
- `data_sources`: Landsat, Sentinel, meteorological stations, field survey, etc.
- `satellite_sensors`: sensor names such as Landsat 8 OLI/TIRS
- `acquisition_dates`: image dates
- `temporal_coverage`: year span or individual years
- `number_of_scenes`: total scenes used
- `path_row`: Landsat path/row if reported
- `spatial_resolution_m`: numeric spatial resolution
- `ancillary_data`: roads, DEM, population, administrative boundary, etc.
- `meteorological_data_source`: BMD or other station source
- `ground_station_names`: station names if given

## Preprocessing Fields

- `cloud_filtering`: cloud cover threshold or masking logic
- `atmospheric_correction`: DOS, LEDAPS, LaSRC, Sen2Cor, or not reported
- `radiometric_calibration`: conversion logic used
- `geometric_correction`: correction or registration notes
- `reprojection`: target CRS
- `resampling`: nearest neighbor, bilinear, cubic, or not reported
- `clipping_mask`: boundary used for clipping
- `seasonal_harmonization`: how seasonal comparability was handled
- `cross_sensor_normalization`: how different sensor years were harmonized

## Thermal and Index Fields

- `lst_method`: single-channel, mono-window, split-window, or descriptive name
- `brightness_temperature_method`: formula or workflow used
- `emissivity_method`: NDVI-based, threshold-based, class-based, or not reported
- `emissivity_equation`: exact emissivity formula
- `wavelength_parameter`: wavelength value used in the LST formula
- `thermal_constants`: K1, K2, metadata constants, or source reference
- `ndvi_method`, `ndbi_method`, `ndwi_method`, `mndwi_method`: extraction logic
- `ndvi_equation`, `ndbi_equation`, `ndwi_equation`, `mndwi_equation`: exact formulas
- `ndvi_range`, `ndbi_range`, `ndwi_range`, `mndwi_range`: numeric ranges if reported
- `albedo_method`, `utfvi_method`, `other_indices`: note equation or logic used
- `albedo_range`, `utfvi_range`: reported ranges

## LULC Fields

- `lulc_source_imagery`: imagery used for classification
- `lulc_years`: years classified
- `lulc_classes`: exact class names used
- `lulc_algorithm`: Random Forest, Maximum Likelihood, K-means, etc.
- `training_sample_source`: Google Earth, field data, author interpretation, etc.
- `post_classification_refinement`: filtering, smoothing, recoding, not reported
- `accuracy_assessment`: confusion matrix, holdout, cross-validation, etc.
- `overall_accuracy`: numeric value
- `kappa`: numeric value
- `producer_accuracy`: class-wise producer's accuracy
- `user_accuracy`: class-wise user's accuracy

## Meteorological and Statistical Fields

- `meteorological_integration`: how station or climate data were used
- `correlation_analysis`: Pearson, Spearman, significance level, etc.
- `regression_model`: linear regression, MLR, spatial regression, etc.
- `spatial_statistics`: Moran's I or other spatial methods
- `hotspot_analysis`: hotspot or coldspot method
- `trend_analysis`: Mann-Kendall, Sen's slope, temporal comparison, etc.
- `machine_learning_workflow`: predictive workflow if used
- `feature_selection`: VIF, recursive elimination, importance ranking, etc.
- `explainability_method`: SHAP or other interpretation method
- `performance_metrics`: RMSE, MAE, R2, AUC, F1, accuracy, etc.

## Reported Value Fields

- `lst_range_c`: minimum and maximum LST in Celsius
- `lst_mean_c`: mean LST in Celsius
- `lst_max_c`: maximum LST
- `lst_min_c`: minimum LST
- `correlation_results`: all key correlation coefficients
- `regression_coefficients`: model coefficients if reported
- `class_fractions`: area percentages or shares by class
- `thresholds`: index thresholds, class thresholds, thermal thresholds
- `temperature_difference_c`: class-wise or zone-wise temperature difference
- `urban_rural_contrast_c`: urban-rural or built-up-reference contrast
- `bangladesh_specific_parameters`: local constants, thresholds, or assumptions

## Quality and Decision Fields

- `limitations`: author-stated or extracted limitations
- `validation_dataset`: source of validation points or observations
- `cross_validation`: k-fold or other design
- `train_test_split`: split percentage if used
- `sensitivity_analysis`: robustness test if reported
- `reproducibility_score`: integer 1 to 5
- `robustness_score`: integer 1 to 5
- `dhaka_suitability_score`: integer 1 to 5
- `bangladesh_suitability_score`: integer 1 to 5
- `validation_strength_score`: integer 1 to 5
- `numerical_extraction_richness_score`: integer 1 to 5
- `thesis_reuse_potential_score`: integer 1 to 5
- `key_findings`: short synthesis of main findings
- `thesis_use_notes`: what will be reused
- `evidence_status`: Extracted, Derived, Inferred, Thesis Decision
- `source_notes`: any note that should not be lost
