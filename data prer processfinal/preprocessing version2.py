"""
preprocessing_pipeline.py  —  v2.6  (fully fixed)
====================================================
Task 1 — LST/SUHI Preprocessing Pipeline

Designed for: National-scale Bangladesh modelling, 2015-2024 (8 divisions)
Current data: Single-division (Barisal), single-year (2025) — pilot mode.
              Temporal features (year, lag4) are structurally present but
              carry no information until multi-year data is provided.
              All reported metrics from pilot data are inflated (random spatial split).

All 11 bugs from the v1 review are fixed:
  BUG-1  validate_no_leakage broken for temporal splits        → fixed
  BUG-2  MAD back-conversion wrong (quantile round-trip)       → fixed
  BUG-3  Step-9 called after step-8 (wrong order)             → fixed
  BUG-4  Spatial/temporal lags missing entirely                → implemented
  BUG-5  VIF/Spearman pruning absent                           → implemented
  BUG-6  dist_to_any_water not gated on VIF                   → gated
  BUG-7  Dead-code SUHI passthrough guard                      → fixed
  BUG-8  impervious_pct unit fix fragile (single outlier)      → fixed (median)
  BUG-9  Pilot split not spatially blocked (no comment)        → documented
  BUG-10 _step6 return value unused / naming confusing         → renamed
  BUG-11 SUHI derivation does not exclude water pixels         → fixed

Correct order-of-operations (spec §1.1):
  1  Physical-range filtering           — stateless
  2  Artefact / unit fixes              — stateless
  3  Water-pixel flagging               — stateless
  4  Hard-drop redundant columns        — stateless
  5  Train / val / test split           — SPLIT FIRST
  6  Outlier thresholds                 — fit on train
  7  Log1p transforms                   — fit on train (which cols present)
  8  Cyclic season + year encoding      — stateless transform
  9  Drop rows with null target         — after split, before feature matrix
  10 Temporal lags                      — within panel, train boundary respected
  11 Spatial lags                       — within fold, documented
  12 Collinearity pruning (Spearman → VIF) — fit on train
  13 Config A / Config B feature matrices — derived from pruned set
  14 StandardScaler                     — fit on train Config-A features

Usage
-----
    from preprocessing_pipeline import PreprocessingPipeline, derive_suhi_per_division
    pipe = PreprocessingPipeline()
    train, val, test, meta = pipe.fit_transform("path/to/data.csv")
    # or pass a DataFrame directly
    train, val, test, meta = pipe.fit_transform(df)

    # Apply to new data at inference time (uses fitted state, no re-fitting)
    new_processed = pipe.transform(new_df)

    # Add scaled columns for DL / linear models
    train_scaled = pipe.apply_scaler(train)

    # Derive per-division SUHI (replaces raw export's national reference)
    train = derive_suhi_per_division(train)

Requirements
------------
    pip install pandas numpy scipy scikit-learn statsmodels
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor

# statsmodels for VIF
try:
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    import statsmodels.api as _sm
    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False
    warnings.warn(
        "statsmodels not installed — VIF pruning will be skipped. "
        "Install with: pip install statsmodels",
        RuntimeWarning,
    )

PIPELINE_NAME = "preprocessing version2.py"
PIPELINE_VERSION = "2.4"
CONFIG_A_DESCRIPTION = (
    "Config A is the driver/causal feature set: non-thermal environmental and "
    "built-environment predictors only. It excludes same-season thermal products, "
    "emissivity, targets, passthrough SUHI/reference columns, IDs, and target lags."
)
CONFIG_B_DESCRIPTION = (
    "Config B is the predictive/forecasting feature set: Config A plus target "
    "history and same-season thermal/emissivity predictors where available. Use it "
    "for accuracy benchmarks, not causal interpretation."
)
INVALID_ZERO_LST_COLS = [
    "lst_c_mean",
    "lst_c_max",
    "modis_lst_day_mean",
    "modis_lst_night_mean",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Physical bounds — values outside these are retrieval/digitisation errors
PHYSICAL_BOUNDS = {
    "lst_c_mean":              (0.01,  60.0),   # strict > 0: exactly-zero rows are retrieval failures
    "lst_c_max":               (0.01,  65.0),   # strict > 0: same reason
    "lst_c_min":               (-5.0,  55.0),
    "lst_k_mean":              (273.0, 333.0),
    "modis_lst_day_mean":      (0.0,   60.0),
    "modis_lst_night_mean":    (0.0,   55.0),
    "modis_lst_diurnal_range": (0.0,   30.0),
    "ndvi_mean":               (-0.2,  0.95),
    "ndvi_max":                (-0.2,  1.0),
    "ndbi_mean":               (-1.0,  1.0),
    "ndwi_mean":               (-1.0,  1.0),
    "mndwi_mean":              (-1.0,  1.0),
    "ndmi_mean":               (-1.0,  1.0),
    "evi_mean":                (-1.0,  1.0),
    "savi_mean":               (-1.0,  1.0),
    "ibi_mean":                (-1.0,  1.0),
    "ui_mean":                 (-1.0,  1.0),
    "bsi_mean":                (-1.0,  1.0),
    "albedo_mean":             (0.0,   1.0),
    "fvc_mean":                (0.0,   1.0),
    "building_area_ratio":     (0.0,   1.0),
    "water_occurrence_pct":    (0.0,   100.0),
    "slope_deg_mean":          (0.0,   90.0),
    "elevation_m_mean":        (-10.0, 1500.0),
}

# Columns where 0 is a TRUE observation value — never impute, never coerce to NaN
TRUE_ZERO_COLS = [
    "building_count", "building_area_m2", "building_area_ratio",
    "building_density_km2", "mean_building_size_m2", "builtup_surface_m2",
    "impervious_pct", "impervious_frac_ghsl", "lc_builtup_pct",
    "ntl_avg_radiance_mean", "ntl_avg_radiance_sum",
    "population_count", "population_density",
    "no2_tropospheric_mean", "co_column_mean",
]

# Log1p-transform columns (contain true zeros; log(0) = -inf is a real bug)
# BUG-6 FIX: dist_to_any_water_m is marked conditional — included here for
# the transform step, but gated by VIF in the collinearity pruning step.
LOG1P_COLS = [
    "building_area_m2",
    "population_density",
    "ntl_avg_radiance_mean",
    "building_count",
    "dist_to_perm_water_m",
    "dist_to_city_centre_m",
    "dist_to_any_water_m",          # BUG-6: conditional on VIF; pruned if VIF > 5
    "mean_building_size_m2",        # heavy upper tail; log1p + 99th-pct clip
]

# Definitional/hard drops — redundant by construction, not data-driven
HARD_DROP_COLS = [
    "lst_k_mean",                  # duplicate of lst_c_mean in different units
    "lst_c_min",                   # too noisy per spec; excluded from all models
    "no2_tropospheric_mean",       # coarse, weak LST link (spec §1.4)
    "co_column_mean",
    "aerosol_index_mean",
    "sar_vv_vh_ratio",             # derived from sar_vv + sar_vh (redundant DOF)
    "ndwi_mean",                   # mndwi_mean is superior for urban water detection
    "ibi_mean",                    # definitionally collinear with impervious_pct
    "ui_mean",                     # definitionally collinear with impervious_pct
    "impervious_frac_ghsl",        # exact duplicate construct of impervious_pct
    "lc_builtup_pct",              # collinear with impervious_pct/building_area_ratio
    "building_count",              # extensive/scale-dependent; ratio covers intensity
    "building_area_m2",            # extensive; building_area_ratio covers it
    "builtup_surface_m2",          # extensive; collinear with building_area_ratio
    "dewpoint_temp_K_mean",        # encoded by RH + temp_2m together
    "temp_2m_K_mean",              # coarse ERA5; only as regional covariate (dropped)
    "wind_u_ms_mean",              # directional components → keep scalar wind_speed_ms
    "wind_v_ms_mean",
    "lc_shrub_pct",                # minimal area in Bangladesh lowlands
    "lc_grass_pct",                # minimal; captured by lc_cropland / ndvi
    "lc_bare_pct",                 # sparse; correlated with bsi_mean
    "lc_wetland_pct",              # captured by water_occurrence_pct
    "dw_built_pct",                # DW built-up = collinear with impervious_pct
    "dw_veg_pct",                  # DW veg = collinear with ndvi / lc_trees
    "dw_water_pct",                # DW water = collinear with lc_water_pct
    "dw_dominant_class",           # categorical version of the above
    "cell_area_m2",                # constant at 1 km²; zero variance
    "ntl_avg_radiance_sum",        # extensive; keep mean
    "chirps_precip_mm_mean",       # collinear with chirps_precip_mm_total
    "chirps_rainy_days",           # correlated with total precip
    "total_precip_m",              # ERA5 precip duplicate of CHIRPS; keep CHIRPS
    "elevation_m_max",             # keep mean; max is collinear
    "aspect_deg_mean",             # weak LST signal; collinear with hillshade
    "hillshade_mean",              # derived from elevation + aspect + slope
    "water_recurrence_pct",        # collinear with water_occurrence_pct
    "water_seasonality_months",    # collinear with water_occurrence_pct
    "s5p_available",               # data-quality flag, not a predictor
    "s1_available",
    "landsat_scene_count",
    "population_count",            # extensive; use density
]

# Primary and secondary targets — excluded from all feature matrices
TARGET_COLS = [
    "lst_c_mean",         # PRIMARY regression target
    "lst_c_max",          # secondary (optional)
    "reference_lst_mean", # carry-through for SUHI re-derivation
]

# BUG-7 FIX: PASSTHROUGH_COLS are excluded from feature matrices via the exclude
# set, not via a post-hoc guard that can never fire. The guard is removed.
PASSTHROUGH_COLS = ["suhi_mean", "suhi_max"]

# Thermal features — Config B only (accuracy/forecasting)
# Config A (driver/causal) must NEVER include these — kill-shot #1 in the spec.
THERMAL_FEATURES_CONFIG_B_ONLY = [
    "modis_lst_day_mean",
    "modis_lst_night_mean",
    "modis_lst_diurnal_range",
    "emissivity_mean",
]

# ID / spatial columns — kept for joining and spatial analysis, never fed to models
# FIX-14: "year" is intentionally NOT in ID_COLS — it is a predictor (linear
# trend term). Putting it in ID_COLS silently excluded it from Config A, which
# contradicted the docstring comment "year as linear trend term." Year is added
# to candidates in fit_transform and survives VIF as a low-collinearity feature.
ID_COLS = ["grid_id", "grid_x", "grid_y", "district", "division", "year", "season"]

# Season ordering for cyclic encoding
SEASON_MAP = {"winter": 1, "pre_monsoon": 2, "monsoon": 3, "post_monsoon": 4}

# Columns to compute spatial neighbourhood lags for (queen contiguity, ~1 km)
SPATIAL_LAG_COLS = [
    "ndvi_mean",
    "impervious_pct",
    "building_area_ratio",
    "elevation_m_mean",
]

# Temporal lag steps (in seasonal units: 1 = previous season, 4 = same season last year)
TEMPORAL_LAG_STEPS = [1, 4]
TEMPORAL_LAG_COLS  = ["lst_c_mean", "ndvi_mean", "impervious_pct"]
TARGET_LAG_COLS = [f"lst_c_mean_lag{lag}" for lag in TEMPORAL_LAG_STEPS]

# Engineered features that are collinear-by-construction with their parent:
# temporal lags, spatial lags, and target lags.  Generic collinearity pruning
# would systematically remove exactly these — they exist to carry engineered
# signal that the raw column cannot express in a single row.  They are
# exempted from Spearman/VIF and added to configs unconditionally.
_ENGINEERED_LAG_PREFIXES = (
    "lst_c_mean_lag",   # target lags  → Config B only
    "lst_c_max_lag",    # target lags  → Config B only
    "ndvi_mean_lag",    # predictor lags → Config A
    "impervious_pct_lag",  # predictor lags → Config A
    "_spatial_lag",     # spatial lags (suffix)  → Config A
)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PIPELINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class PreprocessingPipeline:
    """
    Full Task-1 preprocessing pipeline for the Bangladesh national LST/SUHI study.

    Public API
    ----------
    fit_transform(path_or_df) → (train, val, test, meta)
        Runs the full pipeline. All fitting (outlier bounds, scaler, VIF pruning)
        is performed on `train` only and then applied to val and test.

    transform(df) → df
        Applies the fitted pipeline to new/inference data without re-fitting.

    apply_scaler(df) → df
        Adds *_scaled columns for DL / linear models.

    Notes
    -----
    - Config A (driver / causal): no concurrent thermal features, no emissivity.
      Use for SHAP, ALE, DoWhy/EconML causal analysis.
    - Config B (accuracy / forecasting): Config A + modis_lst_day/night/diurnal.
      Use for best-accuracy benchmarks and ConvLSTM.
    - The same algorithm should be run twice (once per config) so that:
      (a) Config A answers 'what drives LST?'
      (b) Config B answers 'how well can we predict/forecast LST?'
      Showing both pre-empts reviewer kill-shots #1 and #6.
    """

    def __init__(
        self,
        train_years: list = None,
        val_years:   list = None,
        test_years:  list = None,
        mad_threshold: float = 3.5,
        vif_threshold: float = 5.0,
        spearman_threshold: float = 0.8,
        water_pct_threshold: float = 50.0,
        mean_building_size_clip_pct: float = 99.0,
        max_feature_missingness: float = 0.50,
        expected_divisions: list = None,
        expected_years: list = None,
        expected_seasons: list = None,
        spatial_lag_radius_km: float = 3.0,
        grid_scale_km: float = 1.0,
    ):
        self.train_years   = train_years
        self.val_years     = val_years
        self.test_years    = test_years
        self.mad_threshold = mad_threshold
        self.vif_threshold = vif_threshold
        self.spearman_threshold = spearman_threshold
        self.water_pct_threshold = water_pct_threshold
        self.mean_building_size_clip_pct = mean_building_size_clip_pct
        self.max_feature_missingness = max_feature_missingness
        self.expected_divisions = expected_divisions
        self.expected_years = expected_years
        self.expected_seasons = expected_seasons
        self.spatial_lag_radius_km = spatial_lag_radius_km
        self.grid_scale_km = grid_scale_km

        # Fitted state (populated in fit_transform, used in transform/apply_scaler)
        self._outlier_bounds: dict = {}
        self._log1p_cols_used: list = []
        self._mean_bld_clip: float = np.inf
        self._scaler = StandardScaler()
        self._scaler_b = StandardScaler()
        self._scale_cols: list = []
        self._scale_cols_b: list = []
        self._pruned_config_a: list = []
        self._pruned_config_b: list = []
        self._dropped_by_spearman: list = []
        self._dropped_by_vif: list = []
        self._dropped_unusable: list = []
        self._dropped_high_missing: list = []
        self._scale_medians: dict = {}
        self._scale_medians_b: dict = {}
        self._impervious_divisor: float = 1.0
        self._water_occurrence_multiplier: float = 1.0
        self._raw_panel_audit: dict = {}
        self._dataset_identity_audit: dict = {}
        self._fitted: bool = False

    # ──────────────────────────────────────────────────────────────────────────
    # STATELESS STEPS (1–4): no data-driven fitting; safe to run before split
    # ──────────────────────────────────────────────────────────────────────────

    def _step1_physical_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 1: Physical-range filtering.
        Clip-only columns (albedo, fvc, building_area_ratio): clip rather than drop.
        All other out-of-range values are nulled; rows with null targets are dropped
        later (step 9) so we don't lose test rows with bad predictors but valid targets.
        """
        df = df.copy()

        # Clip-only columns (small floating-point overruns are expected)
        clip_only = {
            "albedo_mean":         (0.0, 1.0),
            "fvc_mean":            (0.0, 1.0),
            "building_area_ratio": (0.0, 1.0),
        }
        for col, (lo, hi) in clip_only.items():
            if col in df.columns:
                df[col] = df[col].clip(lo, hi)

        # BUG-8 / FIX-7: use the 99th percentile to detect the unit scale of
        # impervious_pct and water_occurrence_pct.
        # - median > 1 fails on rural-dominated grids where median ≈ 0 even in
        #   0-100 scale data.
        # - max > 1.5 is tripped by a single stray outlier in genuinely 0-1 data.
        # - p99 > 1.5 is robust to both: a real 0-100 column has p99 >> 1.5,
        #   while a real 0-1 column cannot have p99 > 1.5 except for data errors.
        if "impervious_pct" in df.columns:
            p99 = df["impervious_pct"].quantile(0.99)
            if p99 > 1.5:
                df["impervious_pct"] = df["impervious_pct"] / 100.0
                print(f"[Step 1] impervious_pct divided by 100 (p99={p99:.1f} > 1.5 → was 0-100 scale)")
        if "water_occurrence_pct" in df.columns:
            p99_w = df["water_occurrence_pct"].quantile(0.99)
            if p99_w <= 1.5:
                # Data is in 0-1 fraction scale; multiply to 0-100 for threshold checks
                df["water_occurrence_pct"] = df["water_occurrence_pct"] * 100.0
                print(f"[Step 1] water_occurrence_pct ×100 (p99={p99_w:.3f} ≤ 1.5 → was 0-1 scale)")

        # Null out-of-range values for all other bounded columns
        for col, (lo, hi) in PHYSICAL_BOUNDS.items():
            if col in df.columns and col not in clip_only:
                bad = (df[col] < lo) | (df[col] > hi)
                n_bad = bad.sum()
                if n_bad:
                    df.loc[bad, col] = np.nan
                    print(f"[Step 1] {col}: nulled {n_bad} out-of-range values ({lo}–{hi})")

        return df

    def _step1_physical_range(
        self,
        df: pd.DataFrame,
        process_impervious: bool = True,
        process_water: bool = True,
    ) -> pd.DataFrame:
        """
        Step 1: Physical-range filtering.

        Called before split with unit conversion disabled, then after the
        train-only unit fit for impervious/water. Exact-zero LST values are
        retrieval failures and are nulled before target-null rows are dropped.
        """
        df = df.copy()
        clip_only = {
            "albedo_mean": (0.0, 1.0),
            "fvc_mean": (0.0, 1.0),
            "building_area_ratio": (0.0, 1.0),
        }
        for col, (lo, hi) in clip_only.items():
            if col in df.columns:
                df[col] = df[col].clip(lo, hi)

        for col in INVALID_ZERO_LST_COLS:
            if col in df.columns:
                zero_mask = df[col] == 0
                n_zero = int(zero_mask.sum())
                if n_zero:
                    df.loc[zero_mask, col] = np.nan
                    print(f"[Step 1] {col}: nulled {n_zero:,} exact-zero retrieval failures")

        if process_impervious:
            df = self._apply_impervious_units(df)
        if process_water:
            df = self._apply_water_occurrence_units(df)

        for col, (lo, hi) in PHYSICAL_BOUNDS.items():
            if col in df.columns and col not in clip_only:
                bad = (df[col] < lo) | (df[col] > hi)
                n_bad = int(bad.sum())
                if n_bad:
                    df.loc[bad, col] = np.nan
                    print(f"[Step 1] {col}: nulled {n_bad:,} out-of-range values ({lo}-{hi})")

        return df

    def _fit_impervious_units(self, train: pd.DataFrame) -> float:
        self._impervious_divisor = 1.0
        if "impervious_pct" in train.columns:
            p99 = train["impervious_pct"].dropna().quantile(0.99)
            if pd.notna(p99) and p99 > 1.5:
                self._impervious_divisor = 100.0
        print(f"[Units] impervious_pct divisor fit on train: {self._impervious_divisor}")
        return self._impervious_divisor

    def _apply_impervious_units(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "impervious_pct" in df.columns and self._impervious_divisor not in (0, 1.0):
            df["impervious_pct"] = df["impervious_pct"] / self._impervious_divisor
        return df

    def _fit_water_occurrence_units(self, train: pd.DataFrame) -> float:
        self._water_occurrence_multiplier = 1.0
        if "water_occurrence_pct" in train.columns:
            p99 = train["water_occurrence_pct"].dropna().quantile(0.99)
            if pd.notna(p99) and p99 <= 1.5:
                self._water_occurrence_multiplier = 100.0
        print(f"[Units] water_occurrence_pct multiplier fit on train: {self._water_occurrence_multiplier}")
        return self._water_occurrence_multiplier

    def _apply_water_occurrence_units(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "water_occurrence_pct" in df.columns and self._water_occurrence_multiplier != 1.0:
            df["water_occurrence_pct"] = df["water_occurrence_pct"] * self._water_occurrence_multiplier
        return df

    def _step2_water_flag(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 2: Flag water-dominant pixels.
        Retained in all splits but tracked so they can be excluded from the
        SUHI rural-reference derivation (BUG-11 fix).

        FIX-2: If 'is_water' already exists (e.g., loaded from a pre-processed
        CSV), preserve it rather than recomputing — the column may have been
        correctly set externally. If 'water_occurrence_pct' is absent (was hard-
        dropped or never exported), fall back to is_water=0 with a warning
        rather than silently flagging zero pixels.
        """
        df = df.copy()

        # FIX-5: If is_water already exists AND water_occurrence_pct is also
        # present, cross-check them. If they disagree substantially (>5% of rows),
        # recompute is_water from water_occurrence_pct and warn — the saved flag
        # may have used a different threshold or have been computed before physical
        # range filtering corrected water_occurrence_pct outliers.
        if "is_water" in df.columns:
            if "water_occurrence_pct" in df.columns:
                recomputed = (df["water_occurrence_pct"] > self.water_pct_threshold).astype(int)
                disagreement = (recomputed != df["is_water"]).mean()
                if disagreement > 0.05:
                    print(f"[Step 2] WARNING: Existing 'is_water' disagrees with "
                          f"water_occurrence_pct on {disagreement:.1%} of rows — "
                          f"recomputing from water_occurrence_pct.")
                    df = df.copy()
                    df["is_water"] = recomputed
                else:
                    n_water = int(df["is_water"].sum())
                    print(f"[Step 2] Existing 'is_water' preserved (cross-checked OK): "
                          f"{n_water:,} ({100 * n_water / len(df):.1f}%)")
                    return df
            else:
                n_water = int(df["is_water"].sum())
                print(f"[Step 2] Existing 'is_water' preserved (no occ_pct to cross-check): "
                      f"{n_water:,} ({100 * n_water / len(df):.1f}%)")
                return df

        if "water_occurrence_pct" not in df.columns:
            print("[Step 2] WARNING: 'water_occurrence_pct' not found — "
                  "is_water set to 0 for all pixels. "
                  "SUHI rural reference will not exclude water pixels.")
            df["is_water"] = 0
            return df

        occ = df["water_occurrence_pct"]
        df["is_water"] = (occ > self.water_pct_threshold).astype(int)
        n_water = df["is_water"].sum()
        print(f"[Step 2] Water-dominant pixels flagged: {n_water:,} "
              f"({100 * n_water / len(df):.1f}%) — threshold: {self.water_pct_threshold}%")
        return df

    def _step3_hard_drop_and_rename(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 3: Drop definitionally redundant columns and normalise names.
        These drops are not data-driven; they encode domain knowledge.
        """
        df = df.copy()
        present = [c for c in HARD_DROP_COLS if c in df.columns]
        df = df.drop(columns=present)
        print(f"[Step 3] Hard-dropped {len(present)} redundant columns")

        renames = {
            "wind_speed_ms_mean":     "wind_speed_ms",
            "solar_radiation_Jm2":    "solar_radiation",
            "chirps_precip_mm_total": "chirps_precip_mm",
        }
        df = df.rename(columns={k: v for k, v in renames.items() if k in df.columns})
        return df

    # ──────────────────────────────────────────────────────────────────────────
    # SPLIT (Step 4) — must precede all fitting
    # ──────────────────────────────────────────────────────────────────────────

    def _step4_split(self, df: pd.DataFrame):
        """
        Step 4: Split into train / val / test.

        Priority order:
        1. If the DataFrame already has a 'split' column (values: 'train','val','test'),
           honour it exactly — no reshuffling. This respects externally computed
           spatial-block or temporal splits saved with the data.
        2. If no 'split' column and >2 years: temporal split by year.
        3. Otherwise: random 60/20/20 spatial pilot split (for pipeline testing only).

        BUG-9 FIX: The pilot spatial split is documented as producing inflated
        metrics and must not be used for any reported results.
        """
        # ── Priority 1: honour existing split column ──────────────────────
        if "split" in df.columns:
            valid = {"train", "val", "test"}
            found = set(df["split"].dropna().unique())
            # FIX-4: require EXACTLY {"train","val","test"} — no partial splits,
            # no extra labels. Partial splits (e.g. only "train"+"val") would
            # silently create an empty test set. Extra labels are unrecognised rows.
            if found == valid:
                train = df[df["split"] == "train"].drop(columns=["split"]).copy()
                val   = df[df["split"] == "val"].drop(columns=["split"]).copy()
                test  = df[df["split"] == "test"].drop(columns=["split"]).copy()
                print(f"[Step 4] Existing 'split' column honoured — "
                      f"train: {len(train):,}, val: {len(val):,}, test: {len(test):,}")
                # Record year assignments so meta is populated correctly
                self.train_years = sorted(train["year"].unique().tolist()) if "year" in train.columns else []
                self.val_years   = sorted(val["year"].unique().tolist())   if "year" in val.columns   else []
                self.test_years  = sorted(test["year"].unique().tolist())  if "year" in test.columns  else []
                return train, val, test
            else:
                print(f"[Step 4] WARNING: 'split' column found but values {found} are not "
                      "{{train,val,test}} — falling through to automatic split.")

        # ── Priority 2: temporal split by year ────────────────────────────
        years = sorted(df["year"].unique())
        print(f"[Step 4] Years in data: {years}")

        if len(years) > 2:
            if self.train_years is None:
                self.test_years  = [years[-1]]
                self.val_years   = [years[-2]]
                self.train_years = years[:-2]

            train = df[df["year"].isin(self.train_years)].copy()
            val   = df[df["year"].isin(self.val_years)].copy()
            test  = df[df["year"].isin(self.test_years)].copy()
            print(f"[Step 4] Temporal split — "
                  f"train: {self.train_years}, val: {self.val_years}, test: {self.test_years}")
            print(f"         Rows — train: {len(train):,}, val: {len(val):,}, test: {len(test):,}")
        else:
            # ── Priority 3: random pilot spatial split ────────────────────
            print("[Step 4] WARNING: ≤2 years detected — using random spatial "
                  "split for pipeline testing ONLY. Do not report these metrics.")
            np.random.seed(42)
            ids = df["grid_id"].unique()
            np.random.shuffle(ids)
            n = len(ids)
            train = df[df["grid_id"].isin(ids[:int(0.6 * n)])].copy()
            val   = df[df["grid_id"].isin(ids[int(0.6 * n):int(0.8 * n)])].copy()
            test  = df[df["grid_id"].isin(ids[int(0.8 * n):])].copy()
            print(f"[Step 4] Pilot spatial split — "
                  f"train: {len(train):,}, val: {len(val):,}, test: {len(test):,}")

        return train, val, test

    # ──────────────────────────────────────────────────────────────────────────
    # FIT-ON-TRAIN STEPS (5–12)
    # ──────────────────────────────────────────────────────────────────────────

    def _step5_fit_outlier_bounds(self, train: pd.DataFrame) -> dict:
        """
        Step 5 (FIT on train): MAD-based modified z-score outlier bounds.

        BUG-2 FIX: The correct MAD formula is:
            lo = median - (threshold / 0.6745) * MAD
            hi = median + (threshold / 0.6745) * MAD
        The old code did a round-trip through quantiles of the z-score
        distribution, which is equivalent to extreme percentile clipping
        and adds no robustness.

        Applied to PREDICTOR columns only. The target (lst_c_mean) is
        deliberately excluded — extreme urban LST values (industrial zones,
        Barind dry tract) are real and clipping them biases the model toward
        the mean, suppressing the hotspots this study aims to characterise.
        Physical-range filtering (Step 1) already removed retrieval errors.
        """
        non_pred = set(
            TARGET_COLS + PASSTHROUGH_COLS + ID_COLS
            + ["is_water", "season"]
        )
        # FIX-6: Exclude LOG1P_COLS from MAD clipping.
        # population_density and ntl_avg_radiance_mean are right-skewed; the
        # MAD bound (median + 5.19*MAD on raw scale) is very small for such
        # distributions and pulls the dense-urban tail toward the median before
        # logging, suppressing the UHI signal. We log-transform first (step 6)
        # and MAD-clip never fires on them because they are in LOG1P_COLS.
        _mad_skip = set(LOG1P_COLS)
        pred_cols = [
            c for c in train.columns
            if c not in non_pred
            and c not in _mad_skip
            and train[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]
        ]

        bounds = {}
        for col in pred_cols:
            vals = train[col].dropna()
            if len(vals) < 10:
                continue
            median = vals.median()
            mad = np.median(np.abs(vals - median))
            if mad == 0:
                continue  # constant column; no bounds needed

            # BUG-2 FIXED: direct formula, no quantile round-trip
            scale = self.mad_threshold / 0.6745
            lo = median - scale * mad
            hi = median + scale * mad

            # Hard physical bounds as outer limits
            if col in PHYSICAL_BOUNDS:
                lo = max(lo, PHYSICAL_BOUNDS[col][0])
                hi = min(hi, PHYSICAL_BOUNDS[col][1])

            bounds[col] = (lo, hi)

        print(f"[Step 5] MAD outlier bounds computed for {len(bounds)} predictor "
              f"columns (fit on train, threshold={self.mad_threshold})")
        return bounds

    def _apply_outlier_clip(self, df: pd.DataFrame, bounds: dict) -> pd.DataFrame:
        """Apply fitted outlier bounds (clip, not drop)."""
        df = df.copy()
        for col, (lo, hi) in bounds.items():
            if col in df.columns:
                df[col] = df[col].clip(lo, hi)
        return df

    def _step6_fit_log1p_transforms(self, train: pd.DataFrame) -> tuple:
        """
        Step 6 (FIT on train): Determine which log1p columns are present
        and compute the 99th-percentile clip for mean_building_size_m2.

        BUG-10 FIX: Renamed from _step6_log1p_transform to make the
        fit/apply separation explicit. Returns values used by _apply_log1p.
        """
        present = [c for c in LOG1P_COLS if c in train.columns]

        # 99th-percentile upper clip for mean_building_size_m2 (heavy upper tail)
        clip_val = np.inf
        if "mean_building_size_m2" in train.columns:
            clip_val = train["mean_building_size_m2"].quantile(
                self.mean_building_size_clip_pct / 100.0
            )

        print(f"[Step 6] log1p cols identified: {present}")
        if clip_val < np.inf:
            print(f"[Step 6] mean_building_size_m2 upper clip: {clip_val:.1f} m² "
                  f"({self.mean_building_size_clip_pct}th pct of train)")
        return present, clip_val

    def _apply_log1p(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted log1p transforms."""
        df = df.copy()
        if "mean_building_size_m2" in df.columns and self._mean_bld_clip < np.inf:
            df["mean_building_size_m2"] = df["mean_building_size_m2"].clip(
                upper=self._mean_bld_clip
            )
        for col in self._log1p_cols_used:
            if col in df.columns:
                df[col] = np.log1p(df[col].clip(lower=0))
        return df

    def _step7_cyclic_season(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 7: Cyclic season encoding (sin/cos) and year as linear trend term.
        Stateless transform — same formula applied to all splits.
        """
        df = df.copy()
        s_ord = df["season"].map(SEASON_MAP)
        bad = sorted(df.loc[s_ord.isna(), "season"].dropna().unique().tolist())
        if bad:
            raise ValueError(f"Unknown season labels: {bad}. Expected one of {sorted(SEASON_MAP)}")
        df["sin_season"] = np.sin(2 * np.pi * s_ord / 4)
        df["cos_season"] = np.cos(2 * np.pi * s_ord / 4)
        return df

    def _step8_drop_target_nulls(self, df: pd.DataFrame, label: str = "") -> pd.DataFrame:
        """
        Step 8 (BUG-3 FIX): Drop rows where the primary target is null.
        Now called BEFORE _step9_build_feature_matrices, matching the spec §1.1.
        """
        before = len(df)
        df = df.dropna(subset=["lst_c_mean"])
        after = len(df)
        if before != after:
            print(f"[Step 8{' ' + label if label else ''}] "
                  f"Dropped {before - after:,} rows with null lst_c_mean")
        return df

    def _step9_temporal_lags(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Step 9: Add temporal lag columns within the panel.

        Design principles (kill-shot #5 guard):
        - Lags are computed using the panel's sort order (grid_id, year, season).
        - Lag values that would cross the train/val/test boundary are left as NaN;
          the caller is responsible for not using NaN lag rows as training targets
          (or for imputing them with the column median — acceptable for a few steps).
        - lst_lag1 = LST from the previous seasonal step (e.g. winter → previous post-monsoon)
        - lst_lag4 = LST from the same season one year prior (the physically most
          meaningful lag for seasonal modelling)
        - These lags are TEMPORAL FEATURES for tabular models. The ConvLSTM handles
          temporal dependencies structurally through its sequence input — do not add
          lags as extra channels to the ConvLSTM input tensor.

        Multi-year data required: single-year pilots will produce all-NaN lag columns
        (documented; downstream models handle NaN natively for tree models).
        """
        df = df.copy()
        years_present = df["year"].nunique()
        if years_present < 2:
            print("[Step 9] WARNING: ≤1 year in split — temporal lags will be all-NaN. "
                  "This is expected for pilot data; tree models handle NaN natively.")

        # N-1/N-3 FIX: Sort by a numeric season ordinal, NOT the string name.
        # Alphabetical order is: monsoon < post_monsoon < pre_monsoon < winter,
        # which is physically wrong. shift(1) on that order produces lags like
        # "pre_monsoon lag = monsoon" instead of "pre_monsoon lag = winter".
        df["_season_ord"] = df["season"].map(SEASON_MAP).fillna(0).astype(int)
        df = df.sort_values(["grid_id", "year", "_season_ord"]).reset_index(drop=True)

        for col in TEMPORAL_LAG_COLS:
            if col not in df.columns:
                continue
            for lag in TEMPORAL_LAG_STEPS:
                lag_col = f"{col}_lag{lag}"
                df[lag_col] = (
                    df.groupby("grid_id")[col]
                    .shift(lag)
                )
                n_nan = df[lag_col].isna().sum()
                print(f"[Step 9] {lag_col}: created ({n_nan:,} NaN at panel boundaries)")

        df = df.drop(columns=["_season_ord"])
        return df

    def _step9_temporal_lags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add exact seasonal-period temporal lags within each division/grid panel."""
        df = df.copy()
        if "year" not in df.columns or "season" not in df.columns or "grid_id" not in df.columns:
            print("[Step 9] year/season/grid_id not found; temporal lags skipped.")
            return df

        s_ord = df["season"].map(SEASON_MAP)
        bad = sorted(df.loc[s_ord.isna(), "season"].dropna().unique().tolist())
        if bad:
            raise ValueError(f"Unknown season labels: {bad}. Expected one of {sorted(SEASON_MAP)}")

        df["_season_ord"] = s_ord.astype(int)
        df["_period"] = df["year"].astype(int) * 4 + df["_season_ord"] - 1
        key_cols = _panel_key_cols(df, include_period=True)
        duplicates = int(df.duplicated(key_cols).sum())
        if duplicates:
            raise ValueError(
                f"Duplicate panel period rows detected for {key_cols}: {duplicates:,}. "
                "Temporal lag joins require one row per division/grid_id/year/season."
            )

        for col in TEMPORAL_LAG_COLS:
            if col not in df.columns:
                continue
            base = df[key_cols + [col]].copy()
            for lag in TEMPORAL_LAG_STEPS:
                lag_col = f"{col}_lag{lag}"
                previous = base.copy()
                previous["_period"] = previous["_period"] + lag
                previous = previous.rename(columns={col: lag_col})
                df = df.merge(previous, on=key_cols, how="left", validate="one_to_one")
                n_nan = int(df[lag_col].isna().sum())
                print(f"[Step 9] {lag_col}: created ({n_nan:,} NaN at missing/panel boundaries)")

        df = df.sort_values([c for c in key_cols if c in df.columns]).reset_index(drop=True)
        return df.drop(columns=["_season_ord", "_period"])

    def _step10_spatial_lags(
        self,
        df: pd.DataFrame,
        x_col: str = "grid_x",
        y_col: str = "grid_y",
        radius_km: float = 3.0,
    ) -> pd.DataFrame:
        """
        Step 10: Add spatial neighbourhood lag columns (focal mean within radius).

        LEAKAGE NOTE (spec §1.3):
        Spatial lags must be computed WITHIN each split, not on the combined
        dataset.  This method is safe because it is called on train, val, and
        test separately after the split (see fit_transform).  For spatial-block
        CV folds, also enforce a buffer zone between train and test blocks
        so that the lag of a test-adjacent train cell cannot leak the answer.
        This buffer is implemented in the spatial-block CV utility (see below).

        Parameters
        ----------
        radius_km : float
            Neighbourhood radius in km. At 1 km grid spacing, radius=3 km
            captures a 7×7 focal window, which is a reasonable approximation
            of coarse ERA5 (~9 km) footprints.
        """
        df = df.copy()

        if x_col not in df.columns or y_col not in df.columns:
            print(f"[Step 10] WARNING: {x_col}/{y_col} not found — "
                  "spatial lags skipped. Add grid coordinates to enable this step.")
            return df

        # Approximate degree-to-km conversion at Bangladesh latitude (~23° N)
        # 1° lat ≈ 111 km; 1° lon ≈ 111 * cos(23°) ≈ 102 km
        # If coordinates are in metres (UTM) this threshold needs adjusting.
        radius = radius_km * 1000.0  # assume coordinates are in metres (UTM 46N)

        # Group by (year, season) — same reason as the fast variant: lags
        # should reflect the same seasonal state, not mix time periods.
        period_cols = [c for c in ["year", "season"] if c in df.columns]
        if period_cols:
            period_groups = df.groupby(period_cols, sort=False, dropna=False).indices.values()
        else:
            period_groups = [np.arange(len(df))]

        for col in SPATIAL_LAG_COLS:
            if col not in df.columns:
                continue
            lag_col = f"{col}_spatial_lag"
            vals = df[col].values.astype(float)
            lag_vals = np.full(len(df), np.nan)

            for positions in period_groups:
                positions = np.asarray(positions)
                coords = df.iloc[positions][[x_col, y_col]].values.astype(float)
                period_vals = vals[positions]

                for local_i, position in enumerate(positions):
                    dist = np.sqrt(
                        (coords[:, 0] - coords[local_i, 0]) ** 2
                        + (coords[:, 1] - coords[local_i, 1]) ** 2
                    )
                    neighbours = (dist > 0) & (dist <= radius) & ~np.isnan(period_vals)
                    if neighbours.sum() > 0:
                        lag_vals[position] = np.nanmean(period_vals[neighbours])

            df[lag_col] = lag_vals
            n_nan = np.isnan(lag_vals).sum()
            print(f"[Step 10] {lag_col}: created (r={radius_km} km, "
                  f"{n_nan:,} NaN at edges)")

        return df

    def _step10_spatial_lags_fast(
        self,
        df: pd.DataFrame,
        x_col: str = "grid_x",
        y_col: str = "grid_y",
        n_neighbours: int = 8,
    ) -> pd.DataFrame:
        """
        Faster spatial lag using k-nearest neighbours, computed per year/season snapshot.

        Grouping by (year, season) is physically correct: spatial neighbourhood
        averages should reflect the same seasonal state, not mix winter NDVI
        with monsoon NDVI from a different time period. This also means the
        number of neighbours is bounded by the snapshot size, not the full
        split — the k<=1 guard handles small snapshots gracefully.

        Self-exclusion uses local_i index matching rather than assuming position 0
        is always the query point (which breaks when coords are not unique).
        """
        from sklearn.neighbors import NearestNeighbors
        df = df.copy()

        if x_col not in df.columns or y_col not in df.columns:
            print(f"[Step 10-fast] WARNING: {x_col}/{y_col} not found — spatial lags skipped.")
            return df

        # Group by (year, season) so lags are computed within the same snapshot
        period_cols = [c for c in ["year", "season"] if c in df.columns]
        if period_cols:
            period_groups = df.groupby(period_cols, sort=False, dropna=False).indices.values()
        else:
            period_groups = [np.arange(len(df))]

        for col in SPATIAL_LAG_COLS:
            if col not in df.columns:
                continue
            lag_col = f"{col}_spatial_lag"
            vals = df[col].values.astype(float)
            lag_vals = np.full(len(df), np.nan)

            for positions in period_groups:
                positions = np.asarray(positions)
                coords = df.iloc[positions][[x_col, y_col]].values.astype(float)
                # N-6 FIX: cap k per snapshot size, not global row count
                k = min(n_neighbours + 1, len(positions))
                if k <= 1:
                    continue  # snapshot too small for any neighbours
                nbrs = NearestNeighbors(n_neighbors=k, algorithm="ball_tree").fit(coords)
                _, indices = nbrs.kneighbors(coords)

                for local_i, position in enumerate(positions):
                    # Exclude self by local index match (safer than assuming index 0 = self)
                    neighbour_local = indices[local_i]
                    neighbour_local = neighbour_local[neighbour_local != local_i]
                    neighbour_vals = vals[positions[neighbour_local[:n_neighbours]]]
                    if np.any(~np.isnan(neighbour_vals)):
                        lag_vals[position] = np.nanmean(neighbour_vals)

            df[lag_col] = lag_vals
            n_nan = np.isnan(lag_vals).sum()
            print(f"[Step 10-fast] {lag_col}: created within year/season snapshots "
                  f"(k={n_neighbours} neighbours, {n_nan:,} NaN)")

        return df

    def _step10_spatial_lags(
        self,
        df: pd.DataFrame,
        x_col: str = "grid_x",
        y_col: str = "grid_y",
        radius_km: float = None,
        grid_scale_km: float = None,
    ) -> pd.DataFrame:
        return self._step10_spatial_lags_fast(
            df,
            x_col=x_col,
            y_col=y_col,
            radius_km=radius_km,
            grid_scale_km=grid_scale_km,
        )

    def _step10_spatial_lags_fast(
        self,
        df: pd.DataFrame,
        x_col: str = "grid_x",
        y_col: str = "grid_y",
        radius_km: float = None,
        grid_scale_km: float = None,
        n_neighbours: int = None,
    ) -> pd.DataFrame:
        """Add radius-based same-snapshot spatial lag means.

        grid_x/grid_y are grid indices in this dataset, not degrees. radius_km is
        converted to index units via grid_scale_km before querying neighbours.
        """
        from sklearn.neighbors import NearestNeighbors

        df = df.copy()
        if x_col not in df.columns or y_col not in df.columns:
            print(f"[Step 10-fast] WARNING: {x_col}/{y_col} not found; spatial lags skipped.")
            return df

        radius_km = self.spatial_lag_radius_km if radius_km is None else radius_km
        grid_scale_km = self.grid_scale_km if grid_scale_km is None else grid_scale_km
        if grid_scale_km <= 0:
            raise ValueError("grid_scale_km must be > 0 for index-coordinate spatial lags")
        radius_grid_units = radius_km / grid_scale_km

        group_cols = _spatial_group_cols(df)
        if group_cols:
            period_groups = df.groupby(group_cols, sort=False, dropna=False).indices.values()
        else:
            period_groups = [np.arange(len(df))]

        for col in SPATIAL_LAG_COLS:
            if col not in df.columns:
                continue
            lag_col = f"{col}_spatial_lag"
            vals = df[col].to_numpy(dtype=float)
            lag_vals = np.full(len(df), np.nan)
            neighbour_counts = []

            for positions in period_groups:
                positions = np.asarray(positions)
                if len(positions) <= 1:
                    continue
                coords = df.iloc[positions][[x_col, y_col]].to_numpy(dtype=float)
                nbrs = NearestNeighbors(radius=radius_grid_units, algorithm="ball_tree")
                nbrs.fit(coords)
                indices = nbrs.radius_neighbors(coords, return_distance=False)

                for local_i, position in enumerate(positions):
                    neighbour_local = indices[local_i]
                    neighbour_local = neighbour_local[neighbour_local != local_i]
                    neighbour_vals = vals[positions[neighbour_local]]
                    neighbour_vals = neighbour_vals[~np.isnan(neighbour_vals)]
                    neighbour_counts.append(int(len(neighbour_vals)))
                    if len(neighbour_vals):
                        lag_vals[position] = float(np.mean(neighbour_vals))

            df[lag_col] = lag_vals
            n_nan = int(np.isnan(lag_vals).sum())
            mean_neighbours = float(np.mean(neighbour_counts)) if neighbour_counts else 0.0
            print(
                f"[Step 10-fast] {lag_col}: radius={radius_km} km, "
                f"grid_scale={grid_scale_km} km/index, "
                f"mean_neighbours={mean_neighbours:.1f}, NaN={n_nan:,}"
            )

        return df

    def _step11_collinearity_prune(
        self,
        train: pd.DataFrame,
        candidate_cols: list,
    ) -> list:
        """
        Step 11 (FIT on train): Spearman-cluster → iterative VIF pruning.

        Procedure (spec §1.4):
        1. Compute Spearman |ρ| matrix on train candidates.
        2. Hierarchical-cluster at |ρ| >= spearman_threshold.
           Within each cluster, keep the most physically interpretable feature
           (preference order encoded in PRIORITY_WITHIN_CLUSTER).
        3. Iterative VIF on survivors: drop the highest-VIF feature, recompute,
           repeat until all VIF < vif_threshold (default 5.0).

        Why prune even for tree models?
        --------------------------------
        Collinearity does NOT hurt tree prediction skill, but it does:
        (a) Corrupt SHAP attribution — importance is split arbitrarily among
            correlated features, masking the true driver.
        (b) Destabilise causal ATEs — correlated treatments produce biased
            standard errors and ATEs in DoWhy/EconML.
        This pruning is for interpretability and causal validity, not accuracy.

        BUG-5 FIX: Previously this step was absent, meaning fvc_mean, evi_mean,
        savi_mean, ndbi_mean, building_density_km2, dist_to_any_water_m and others
        survived into the feature matrix with unchecked collinearity.

        BUG-6 FIX: dist_to_any_water_m is now subject to VIF; it will be dropped
        if VIF > vif_threshold (which is expected given its correlation with
        dist_to_perm_water_m and water_occurrence_pct).
        """
        if not _HAS_STATSMODELS:
            print("[Step 11] WARNING: statsmodels unavailable — VIF pruning skipped. "
                  "Spearman-only pruning applied.")
            cols = [
                c for c in candidate_cols
                if c in train.columns
                and pd.api.types.is_numeric_dtype(train[c])
                and train[c].notna().any()
                and train[c].nunique(dropna=True) > 1
            ]
            dropped_spearman = []
            kept = []
            if cols:
                corr = train[cols].fillna(train[cols].median()).corr(method="spearman").abs()
                for col in cols:
                    if any(corr.loc[col, prev] >= self.spearman_threshold for prev in kept):
                        dropped_spearman.append(col)
                    else:
                        kept.append(col)
            self._dropped_unusable = [
                c for c in candidate_cols
                if c in train.columns and (
                    not pd.api.types.is_numeric_dtype(train[c])
                    or not train[c].notna().any()
                    or train[c].nunique(dropna=True) <= 1
                )
            ]
            self._dropped_by_spearman = dropped_spearman
            self._dropped_by_vif = []
            return kept

        # Only numeric, non-target columns
        non_pred = set(TARGET_COLS + PASSTHROUGH_COLS + ID_COLS + ["is_water", "season"])
        cols = [
            c for c in candidate_cols
            if c in train.columns
            and c not in non_pred
            and train[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]
        ]
        self._dropped_unusable = [
            c for c in cols
            if not train[c].notna().any() or train[c].nunique(dropna=True) <= 1
        ]
        self._dropped_high_missing = [
            c for c in cols
            if c not in self._dropped_unusable
            and train[c].isna().mean() > self.max_feature_missingness
        ]
        cols = [
            c for c in cols
            if c not in self._dropped_unusable and c not in self._dropped_high_missing
        ]
        if self._dropped_unusable:
            print(f"[Step 11] Dropped unusable all-null/constant features: {self._dropped_unusable}")
        if self._dropped_high_missing:
            print(
                f"[Step 11] Dropped high-missing features "
                f"(>{self.max_feature_missingness:.0%} missing): {self._dropped_high_missing}"
            )

        if len(cols) < 2:
            return cols

        # FIX-1+2: Separate engineered lag/spatial-lag features from core features.
        # Engineered features are collinear-by-construction with their parent column
        # (ndvi_mean_spatial_lag ~ ndvi_mean, lst_c_mean_lag1 ~ lst_c_mean, etc.).
        # Running them through Spearman/VIF will systematically drop them even though
        # they carry *different* information (neighbourhood context, trend, history).
        # Solution: exempt all engineered lag features; bypass Spearman+VIF for them
        # and re-attach them after pruning.
        def _is_engineered(c):
            return (
                any(c.startswith(p) for p in _ENGINEERED_LAG_PREFIXES if not p.startswith("_"))
                or any(c.endswith(p) for p in _ENGINEERED_LAG_PREFIXES if p.startswith("_"))
            )

        engineered_cols = [c for c in cols if _is_engineered(c)]
        core_cols       = [c for c in cols if not _is_engineered(c)]
        if engineered_cols:
            print(f"[Step 11] Engineered lag/spatial-lag features exempted from "
                  f"Spearman+VIF ({len(engineered_cols)}): {engineered_cols}")

        # Only run Spearman+VIF on core (non-engineered) features
        cols = core_cols
        if len(cols) < 2:
            self._dropped_by_spearman = []
            self._dropped_by_vif = []
            remaining = cols + engineered_cols
            return remaining

        # Fill NaN with column median for the correlation / VIF calculation only
        X = train[cols].fillna(train[cols].median())

        # ── Phase 1: Spearman clustering ──────────────────────────────────
        corr = X.corr(method="spearman").abs()

        # N-2 FIX: Use scipy hierarchical clustering (complete linkage on 1-|ρ|)
        # instead of a greedy pairwise loop. Greedy loops are not transitive:
        # if A~B and B~C but not A~C, a greedy pass may keep all three depending
        # on iteration order. Hierarchical clustering correctly identifies the
        # full cluster and keeps exactly one representative per cluster.
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform

        # Priority: which feature to KEEP within a correlated cluster.
        # Lower number = higher priority (keep me). Unknown columns default to 10.
        # FIX-4: Give the two most theory-central UHI drivers numerically lower
        # priority values than other PRIORITY-1 features so they always survive when
        # they land in the same Spearman cluster (e.g. with building_area_ratio).
        # Previously all three had priority=1 and the tiebreak was alphabetical,
        # so "building_area_ratio" beat "impervious_pct" and "ndvi_mean" purely on
        # name, silently dropping the canonical UHI driver variables.
        PRIORITY = {
            # Core built-environment drivers (must survive)
            "impervious_pct": 1,
            "ndvi_mean": 2,
            # Secondary vegetation/spectral
            "ndvi_max": 3, "ndmi_mean": 4,
            # Built form
            "building_area_ratio": 5, "mean_building_size_m2": 6,
            # Water indices
            "mndwi_mean": 5, "water_occurrence_pct": 6,
            "dist_to_perm_water_m": 7, "dist_to_any_water_m": 8,
            # Terrain
            "elevation_m_mean": 5, "slope_deg_mean": 6, "tpi_mean": 7,
        }
        default_priority = 10

        # Convert Spearman |ρ| to a distance matrix (0 = identical, 1 = uncorrelated)
        dist_matrix = 1.0 - corr.values
        np.fill_diagonal(dist_matrix, 0.0)
        dist_matrix = np.clip(dist_matrix, 0.0, None)  # numerical safety

        try:
            condensed = squareform(dist_matrix, checks=False)
            # Safety: non-finite values in Spearman corr (near-constant cols after
            # physical-range nulling) produce inf/nan in the distance matrix.
            # nan_to_num replaces them with 1.0 (= maximum distance = uncorrelated),
            # which is conservative: the pair will NOT be clustered together.
            condensed = np.nan_to_num(condensed, nan=1.0, posinf=1.0, neginf=0.0)
            Z = linkage(condensed, method="complete")
            # Cut at distance threshold = 1 - spearman_threshold
            cluster_labels = fcluster(Z, t=1.0 - self.spearman_threshold, criterion="distance")
        except Exception as e:
            print(f"[Step 11] Hierarchical clustering failed ({e}) — falling back to greedy")
            cluster_labels = np.arange(len(cols)) + 1  # each feature its own cluster

        # Within each cluster, keep the highest-priority feature
        from collections import defaultdict
        clusters = defaultdict(list)
        for feat, label in zip(cols, cluster_labels):
            clusters[label].append(feat)

        kept = []
        dropped_spearman = []
        for label, members in clusters.items():
            # Sort by priority (ascending = keep first); unknown cols get priority 10
            members_sorted = sorted(members, key=lambda c: (PRIORITY.get(c, default_priority), c))
            kept.append(members_sorted[0])
            dropped_spearman.extend(members_sorted[1:])
        self._dropped_by_spearman = dropped_spearman
        print(f"[Step 11] Spearman pruning (|ρ| ≥ {self.spearman_threshold}): "
              f"dropped {len(dropped_spearman)}: {dropped_spearman}")

        # ── Phase 2: Iterative VIF ────────────────────────────────────────
        # N-4 FIX: Exclude columns that are >50% NaN from the VIF matrix.
        # High-NaN columns (e.g. lag4 at ~97% NaN on pilot data) get filled with
        # their median, creating near-zero variance, which drives VIF → ∞ and
        # causes them to be dropped first — even before genuinely collinear features.
        # These columns are kept in the feature list but exempted from VIF.
        # FIX-5: threshold is >= 0.5 (not strictly > 0.5).
        # With exactly 2 balanced training years, lag4 has exactly 50% NaN.
        # These columns are not VIF-testable and should be treated as VIF-exempt.
        # FIX-14: protect structural trend/encoding features from VIF.
        # 'year' encodes a monotone warming trend. Its high VIF with seasonal features
        # is expected and does NOT mean year is redundant — it captures a different
        # direction of variance. sin/cos season similarly encode a known fixed cycle.
        # Dropping them via VIF silently removes the trend term from Config A.
        _VIF_PROTECTED = {"year", "sin_season", "cos_season"}

        nan_thresh = 0.5
        vif_exempt = [
            c for c in kept
            if c in train.columns
            and (train[c].isna().mean() >= nan_thresh or c in _VIF_PROTECTED)
        ]
        if vif_exempt:
            nan_ex   = [c for c in vif_exempt if c not in _VIF_PROTECTED]
            prot_ex  = [c for c in vif_exempt if c in _VIF_PROTECTED]
            if nan_ex:
                print(f"[Step 11] VIF-exempt (>={int(nan_thresh*100)}% NaN): {nan_ex}")
            if prot_ex:
                print(f"[Step 11] VIF-protected (structural trend/encoding): {prot_ex}")
        remaining = [c for c in kept if c not in vif_exempt]
        dropped_vif = []
        max_iters = len(remaining)

        # FIX-7: sample up to 10k rows for VIF. On 40k+ row datasets the full
        # matrix makes each VIF iteration slow (statsmodels uses OLS internally).
        # VIF is a property of the feature correlation structure, not sample size —
        # a 10k random sample from train gives the same pruning decisions.
        _VIF_MAX_ROWS = 10_000
        if len(train) > _VIF_MAX_ROWS:
            vif_sample = train.sample(_VIF_MAX_ROWS, random_state=42)
            print(f"[Step 11] VIF sampled to {_VIF_MAX_ROWS:,} rows from {len(train):,} train rows for speed")
        else:
            vif_sample = train

        for _ in range(max_iters):
            if len(remaining) < 2:
                break
            X_core = vif_sample[remaining].fillna(vif_sample[remaining].median())
            # FIX-3: Add a constant column so each regression has an intercept.
            # Without a constant, every regression is forced through the origin,
            # which inflates all VIFs and causes over-pruning of real features.
            X_vif = _sm.add_constant(X_core, has_constant="add").values
            # The constant column is index 0 after add_constant; skip it when
            # recording VIFs so the column index matches `remaining`.
            n_feat = X_vif.shape[1]
            try:
                # col 0 = constant — compute VIF for all cols then slice off const
                all_vifs = [variance_inflation_factor(X_vif, i) for i in range(n_feat)]
                vifs = all_vifs[1:]   # drop the constant's VIF
            except Exception as e:
                print(f"[Step 11] VIF computation error: {e} — stopping VIF pruning")
                break

            max_vif = max(vifs)
            if max_vif <= self.vif_threshold:
                break  # all VIFs acceptable

            worst_col = remaining[vifs.index(max_vif)]
            dropped_vif.append((worst_col, round(max_vif, 2)))
            remaining.remove(worst_col)

        # VIF-exempt (high-NaN) columns ARE intentionally kept.
        remaining = remaining + vif_exempt
        self._dropped_by_vif = dropped_vif
        print(f"[Step 11] VIF pruning (threshold={self.vif_threshold}): "
              f"dropped {len(dropped_vif)}: {dropped_vif}")

        # FIX-1+2: Re-attach engineered lag/spatial-lag features that were bypassed.
        # These are appended AFTER the Spearman/VIF survivors, not before, so the
        # pruning summary above reflects only core-feature decisions.
        final = remaining + [c for c in engineered_cols if c not in remaining]
        print(f"[Step 11] Survivors after both phases: {len(final)} features "
              f"(core: {len(remaining)}, engineered lags re-attached: {len(engineered_cols)})")
        return final

    def _step12_build_feature_matrices(
        self, df: pd.DataFrame, pruned_cols: list
    ) -> tuple:
        """
        Step 12: Build Config A and Config B feature matrices from the
        VIF/Spearman-pruned column list.

        BUG-7 FIX: PASSTHROUGH_COLS are excluded from the candidate list
        before calling this method, so the dead-code post-hoc guard is removed.

        Config A (driver / causal / SHAP):
            Pruned core + regional/seasonal covariates + spatial/temporal lags
            NO concurrent thermal features, NO emissivity.

        Config B (accuracy / forecasting / ConvLSTM):
            Config A + modis_lst_day/night/diurnal + emissivity (if present).
        """
        # FIX-4: lst_c_mean lag columns are target-derived and must NOT appear
        # in Config A (driver/causal/SHAP). They encode the target's own past
        # values, which would dominate SHAP and bias causal ATEs.
        # They ARE allowed in Config B (forecasting), where predicting future LST
        # from past LST is the explicit goal.
        target_lag_cols = [
            c for c in df.columns
            if c.startswith("lst_c_mean_lag") or c.startswith("lst_c_max_lag")
        ]

        exclude = set(
            TARGET_COLS
            + PASSTHROUGH_COLS
            + ID_COLS
            + THERMAL_FEATURES_CONFIG_B_ONLY
            + HARD_DROP_COLS
            + target_lag_cols       # excluded from Config A only (FIX-4)
            + ["is_water", "season"]
        )

        config_a = [
            c for c in pruned_cols
            if c in df.columns
            and c not in exclude
            and df[c].dtype != object
        ]

        # Config B = Config A + target lags (unconditional) + thermal features.
        # Target lags are DEFINED as the forecasting features; VIF collinearity with
        # the target is expected and is NOT a reason to exclude them from Config B.
        # We add every target-lag column that exists in df regardless of pruning.
        thermal_present = [c for c in THERMAL_FEATURES_CONFIG_B_ONLY if c in df.columns]
        # Pull from df directly — not from pruned_cols — so VIF cannot drop them
        target_lags_present = [c for c in target_lag_cols if c in df.columns]
        config_b = config_a + [c for c in target_lags_present if c not in config_a] + [
            c for c in thermal_present if c not in config_a
        ]

        print(f"[Step 12] Config A: {len(config_a)} features (driver/causal, no thermal)")
        print(f"[Step 12] Config B: {len(config_b)} features "
              f"(accuracy/forecast, +{len(target_lags_present)} target lags, "
              f"+{len(thermal_present)} thermal)")
        return config_a, config_b

    def _step13_fit_scaler(self, train: pd.DataFrame, config_a_cols: list):
        """
        Step 13 (FIT on train): StandardScaler on Config A numeric features.
        Scaling is not needed for tree models but is required for:
        - Linear baselines (Ridge, Lasso)
        - ConvLSTM input tensor (per-channel standardisation)
        Fit on Config A only; Config B features can be scaled separately if needed.

        FIX-9: NaN values are filled with the per-column TRAIN MEDIAN before
        fitting and applying the scaler, not with 0. Zero is not a neutral value
        for distance columns, vegetation indices, or lag features — filling with 0
        creates spurious outliers in the scaled space. Median is always safe.
        The fill value is stored so apply_scaler() uses the same fill at inference.
        """
        num_cols = [
            c for c in config_a_cols
            if c in train.columns
            and pd.api.types.is_numeric_dtype(train[c])
        ]
        self._scale_cols = num_cols
        if not num_cols:
            print("[Step 13] No Config-A numeric features available for scaling")
            return
        # Store train medians for consistent NaN fill at inference time
        self._scale_medians = train[num_cols].median().to_dict()
        fill_df = train[num_cols].fillna(pd.Series(self._scale_medians))
        self._scaler.fit(fill_df)
        print(f"[Step 13] StandardScaler fit on {len(num_cols)} Config-A numeric "
              f"features (NaN filled with train median, not 0)")

    def _step13_fit_config_b_scaler(self, train: pd.DataFrame, config_b_cols: list):
        """Fit a separate StandardScaler on train Config-B numeric features."""
        num_cols = [
            c for c in config_b_cols
            if c in train.columns and pd.api.types.is_numeric_dtype(train[c])
        ]
        self._scale_cols_b = num_cols
        if not num_cols:
            print("[Step 13] No Config-B numeric features available for scaling")
            return
        self._scale_medians_b = train[num_cols].median().to_dict()
        fill_df = train[num_cols].fillna(pd.Series(self._scale_medians_b))
        self._scaler_b.fit(fill_df)
        print(f"[Step 13] StandardScaler fit on {len(num_cols)} Config-B numeric features")

    # ──────────────────────────────────────────────────────────────────────────
    # APPLY TRANSFORMS (stateless application of fitted state)
    # ──────────────────────────────────────────────────────────────────────────

    def apply_scaler(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add *_scaled columns for DL / linear models.
        Call after fit_transform / transform. Does NOT modify original columns.
        NaN values are filled with the TRAIN median stored during fit_transform,
        not with 0 (FIX-9).
        """
        assert self._fitted, "Call fit_transform() before apply_scaler()"
        df = df.copy()
        missing = [c for c in self._scale_cols if c not in df.columns]
        if missing:
            raise ValueError(f"apply_scaler missing fitted columns: {missing}")
        present = [c for c in self._scale_cols if c in df.columns]
        if not present:
            return df
        # Use train medians (not 0) for NaN fill at inference time
        medians = {c: self._scale_medians.get(c, 0) for c in present}
        fill_df = df[present].fillna(pd.Series(medians))
        scaled = self._scaler.transform(fill_df)
        for i, col in enumerate(present):
            df[col + "_scaled"] = scaled[:, i]
        return df

    def apply_scaler_config_b(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add *_scaled_b columns using the fitted Config-B scaler."""
        assert self._fitted, "Call fit_transform() before apply_scaler_config_b()"
        df = df.copy()
        missing = [c for c in self._scale_cols_b if c not in df.columns]
        if missing:
            raise ValueError(f"apply_scaler_config_b missing fitted columns: {missing}")
        present = [c for c in self._scale_cols_b if c in df.columns]
        if not present:
            return df
        medians = {c: self._scale_medians_b.get(c, 0) for c in present}
        fill_df = df[present].fillna(pd.Series(medians))
        scaled = self._scaler_b.transform(fill_df)
        for i, col in enumerate(present):
            df[col + "_scaled_b"] = scaled[:, i]
        return df

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINTS
    # ──────────────────────────────────────────────────────────────────────────

    def fit_transform(self, path_or_df, use_fast_spatial_lags: bool = True):
        """
        Full pipeline. All fitting is performed on train only.

        Parameters
        ----------
        path_or_df : str or pd.DataFrame
        use_fast_spatial_lags : bool
            True (default) → k-NN spatial lags (recommended for > 5k rows)
            False → exact-radius spatial lags (slower, more precise)

        Returns
        -------
        train, val, test : pd.DataFrame  (with all engineered features)
        meta : dict  (fitted objects and column lists for downstream use)
        """
        # ── Load ──────────────────────────────────────────────────────────
        if isinstance(path_or_df, str):
            df = pd.read_csv(path_or_df)
            self._raw_panel_audit = audit_panel_integrity(df)
            self._dataset_identity_audit = validate_dataset_identity(
                df,
                expected_divisions=self.expected_divisions,
                expected_years=self.expected_years,
                expected_seasons=self.expected_seasons,
            )
            print(f"[Load] {len(df):,} rows × {df.shape[1]} columns")
        else:
            df = path_or_df.copy()
            self._raw_panel_audit = audit_panel_integrity(df)
            self._dataset_identity_audit = validate_dataset_identity(
                df,
                expected_divisions=self.expected_divisions,
                expected_years=self.expected_years,
                expected_seasons=self.expected_seasons,
            )
            print(f"[Load] DataFrame: {len(df):,} rows × {df.shape[1]} columns")

        # ── Stateless steps 1–3 ──────────────────────────────────────────
        df = self._step1_physical_range(df, process_impervious=False, process_water=False)
        df = self._step3_hard_drop_and_rename(df)

        # ── Step 4: SPLIT (must precede all fitting) ──────────────────────
        train, val, test = self._step4_split(df)

        self._fit_impervious_units(train)
        self._fit_water_occurrence_units(train)
        train = self._step1_physical_range(train)
        val   = self._step1_physical_range(val)
        test  = self._step1_physical_range(test)
        train = self._step2_water_flag(train)
        val   = self._step2_water_flag(val)
        test  = self._step2_water_flag(test)

        # ── Step 5: Outlier bounds (fit on train) ─────────────────────────
        self._outlier_bounds = self._step5_fit_outlier_bounds(train)
        train = self._apply_outlier_clip(train, self._outlier_bounds)
        val   = self._apply_outlier_clip(val,   self._outlier_bounds)
        test  = self._apply_outlier_clip(test,  self._outlier_bounds)

        # ── Step 6: Log1p transform (fit on train to determine cols + clip) ─
        self._log1p_cols_used, self._mean_bld_clip = \
            self._step6_fit_log1p_transforms(train)
        train = self._apply_log1p(train)
        val   = self._apply_log1p(val)
        test  = self._apply_log1p(test)

        # ── Step 7: Cyclic season encoding ────────────────────────────────
        train = self._step7_cyclic_season(train)
        val   = self._step7_cyclic_season(val)
        test  = self._step7_cyclic_season(test)

        # ── Step 8 (BUG-3 FIX): Drop null-target rows BEFORE feature matrix ─
        train = self._step8_drop_target_nulls(train, "TRAIN")
        val   = self._step8_drop_target_nulls(val,   "VAL")
        test  = self._step8_drop_target_nulls(test,  "TEST")
        validate_no_leakage(train, val, test)

        # ── Step 9: Temporal lags on the FULL panel before reassigning splits ─
        # Temporal lags are deterministic backward shifts — a 2024 row reading
        # 2023 / 2020 is legitimate, not leakage.  Calling _step9 per-split
        # makes val (single year) and test (single year) produce all-NaN lag4
        # because there is no prior history inside each isolated split.
        # Rule: "fit on train only" applies to data-driven transforms (MAD bounds,
        # log-clip percentile, VIF, scaler).  Deterministic backward lags must run
        # on the combined panel so every row can see its own history.
        # Spatial lags stay per-split (they must not cross train/val/test boundaries).
        train["_split_label"] = "train"
        val["_split_label"]   = "val"
        test["_split_label"]  = "test"
        _full_panel = pd.concat([train, val, test], ignore_index=True)
        _full_panel = self._step9_temporal_lags(_full_panel)
        train = _full_panel[_full_panel["_split_label"] == "train"].drop(columns=["_split_label"]).reset_index(drop=True)
        val   = _full_panel[_full_panel["_split_label"] == "val"].drop(columns=["_split_label"]).reset_index(drop=True)
        test  = _full_panel[_full_panel["_split_label"] == "test"].drop(columns=["_split_label"]).reset_index(drop=True)
        del _full_panel

        # ── Step 10: Spatial lags (within-split, documented leakage guard) ─
        _lag_fn = (self._step10_spatial_lags_fast if use_fast_spatial_lags
                   else self._step10_spatial_lags)
        train = _lag_fn(train)
        val   = _lag_fn(val)
        test  = _lag_fn(test)

        # ── Step 11: Collinearity pruning (fit on train) ──────────────────
        # Build candidate list: everything numeric that isn't an ID/target/passthrough
        exclude_from_candidates = set(
            TARGET_COLS + PASSTHROUGH_COLS + ID_COLS
            + THERMAL_FEATURES_CONFIG_B_ONLY
            + ["is_water", "season"]
        )
        all_candidates = [
            c for c in train.columns
            if c not in exclude_from_candidates
            and train[c].dtype != object
        ]
        pruned_cols = self._step11_collinearity_prune(train, all_candidates)

        # ── Step 12: Config A / Config B feature matrices ─────────────────
        config_a, config_b = self._step12_build_feature_matrices(train, pruned_cols)
        self._pruned_config_a = config_a
        self._pruned_config_b = config_b

        # ── Step 13: Scaler (fit on train) ───────────────────────────────
        self._step13_fit_scaler(train, config_a)
        self._step13_fit_config_b_scaler(train, config_b)

        self._fitted = True

        # ── Metadata dict ────────────────────────────────────────────────
        meta = {
            "pipeline_name":          PIPELINE_NAME,
            "pipeline_version":       PIPELINE_VERSION,
            "config_a_description":   CONFIG_A_DESCRIPTION,
            "config_b_description":   CONFIG_B_DESCRIPTION,
            "config_a_claim":         "Driver/causal feature set; excludes target lags and same-season thermal products.",
            "config_b_claim":         "Predictive/forecasting feature set; includes target lags and thermal products where available.",
            "config_a_cols":          config_a,
            "config_b_cols":          config_b,
            "target":                 "lst_c_mean",
            "secondary_target":       "suhi_mean (re-derive via derive_suhi_per_division)",
            "id_cols":                ID_COLS,
            "outlier_bounds":         self._outlier_bounds,
            "log1p_cols":             self._log1p_cols_used,
            "mean_building_size_clip": self._mean_bld_clip,
            "scale_cols":             self._scale_cols,
            "scaler":                 self._scaler,
            "scale_cols_b":           self._scale_cols_b,
            "scaler_b":               self._scaler_b,
            "scale_fill_values":      self._scale_medians,
            "scale_fill_values_b":    self._scale_medians_b,
            "dropped_by_spearman":    self._dropped_by_spearman,
            "dropped_by_vif":         self._dropped_by_vif,
            "dropped_unusable":       self._dropped_unusable,
            "dropped_high_missing":   self._dropped_high_missing,
            "train_years":            self.train_years,
            "val_years":              self.val_years,
            "test_years":             self.test_years,
            "thermal_features":       THERMAL_FEATURES_CONFIG_B_ONLY,
            "target_lag_features":    [c for c in config_b if c.startswith("lst_c_mean_lag")],
            "impervious_divisor":     self._impervious_divisor,
            "water_occurrence_multiplier": self._water_occurrence_multiplier,
            "invalid_zero_lst_cols":  INVALID_ZERO_LST_COLS,
            "spatial_lag_radius_km":  self.spatial_lag_radius_km,
            "grid_scale_km":          self.grid_scale_km,
            "raw_panel_audit":        self._raw_panel_audit,
            "dataset_identity_audit": self._dataset_identity_audit,
        }

        # FIX-2 / FIX-3: Warn about single-year data quality issues
        n_years = len(set(
            list(train["year"].unique()) + list(val["year"].unique()) + list(test["year"].unique())
        )) if "year" in train.columns else 0
        if n_years <= 1:
            print(f"[WARNING] Single-year data detected ({n_years} unique year):")
            print("  - All lag4 columns will be all-NaN — useless for modelling.")
            print("    Keep them in feature lists but exclude from training by")
            print("    using: X = train[meta['config_a_cols']].dropna(subset=lag4_cols, how='any')")
            print("    or letting tree models handle NaN natively.")
            print("  - 'year' is a constant feature — contributes no information.")
            print("    Consider dropping it manually: meta['config_a_cols'].remove('year')")
            print("  These warnings disappear automatically with multi-year data.")

        # Run feature-role audit to catch any config violations at fit time
        audit_feature_roles(meta)
        _print_summary(train, val, test, config_a, config_b)
        return train, val, test, meta

    def transform(self, df: pd.DataFrame, use_fast_spatial_lags: bool = True,
                  panel_history: pd.DataFrame = None) -> pd.DataFrame:
        """
        Apply the fitted pipeline to new/inference-time data.
        Does NOT re-fit anything. Use for model deployment or test-time transforms.

        N-5 FIX: Returns only the columns that the fitted model was trained on
        (config_a_cols + config_b_cols + id/target/passthrough cols), so that
        downstream model.predict(X[meta['config_a_cols']]) never sees extra columns
        that were present in the raw data but pruned during fit_transform.

        FIX-13 / KNOWN LIMITATION — temporal lags at inference:
        _step9_temporal_lags() computes lags within the passed df only.
        If you pass a single new season, lag1 and lag4 will be NaN because
        there is no prior history in the df. To get valid lags at inference,
        pass `panel_history` — the N most recent seasons from training data
        (at minimum lag4=4 seasons of history). The method will prepend the
        history, compute lags, then return only the new rows.

        Example:
            # FIX-7: tail() after sort_values is not grid-safe. Use groupby.
            recent = train.groupby("grid_id").tail(4)   # last 4 seasons per grid
            new_processed = pipe.transform(new_season_df, panel_history=recent)
        """
        assert self._fitted, "Call fit_transform() before transform()"
        df = self._step1_physical_range(df)
        df = self._step2_water_flag(df)
        df = self._step3_hard_drop_and_rename(df)
        df = self._apply_outlier_clip(df, self._outlier_bounds)
        df = self._apply_log1p(df)
        df = self._step7_cyclic_season(df)

        # FIX-13: prepend history rows so temporal lags are computable
        if panel_history is not None and len(panel_history) > 0:
            # FIX-6: panel_history may be either raw (from raw CSV) or already
            # processed (e.g. passing `train` from a prior fit_transform call).
            # If the history already has 'sin_season' or 'is_water', it was already
            # processed — skip the raw transforms to avoid double-transforming
            # log1p columns (distances, population, NTL) a second time.
            _already_processed = (
                "sin_season" in panel_history.columns
                or "is_water" in panel_history.columns
            )
            if _already_processed:
                hist = panel_history.copy()
                # Still apply outlier clip (idempotent) and cyclic season (idempotent)
                hist = self._apply_outlier_clip(hist, self._outlier_bounds)
                if "sin_season" not in hist.columns:
                    hist = self._step7_cyclic_season(hist)
                print("[panel_history] Detected as already-processed — "
                      "skipping raw transforms to avoid double-transformation.")
            else:
                hist = self._apply_log1p(
                    self._step7_cyclic_season(
                        self._apply_outlier_clip(
                            self._step3_hard_drop_and_rename(
                                self._step2_water_flag(
                                    self._step1_physical_range(panel_history.copy())
                                )
                            ), self._outlier_bounds
                        )
                    )
                )
            # FIX-13: tag new rows BEFORE combining, so we can recover them
            # safely after _step9 re-sorts by (grid_id, year, season_ord).
            # Also deduplicate: if history contains rows that overlap with df
            # (same grid_id + year + season), remove them from history to avoid
            # double-counting — only truly prior observations should be in history.
            df = df.copy(); df["_is_new_row"] = True
            hist = hist.copy(); hist["_is_new_row"] = False
            key_cols = [c for c in ["grid_id", "year", "season"] if c in df.columns and c in hist.columns]
            if key_cols:
                df_keys = set(map(tuple, df[key_cols].values.tolist()))
                hist = hist[~hist[key_cols].apply(tuple, axis=1).isin(df_keys)]
            combined = pd.concat([hist, df], ignore_index=True)
            combined = self._step9_temporal_lags(combined)
            df = (combined[combined["_is_new_row"] == True]
                  .drop(columns=["_is_new_row"])
                  .reset_index(drop=True))
        else:
            df = self._step9_temporal_lags(df)
        _lag_fn = (self._step10_spatial_lags_fast if use_fast_spatial_lags
                   else self._step10_spatial_lags)
        df = _lag_fn(df)

        # N-5 FIX: retain only cols the model was trained on + metadata cols
        keep_cols = set(
            self._pruned_config_b          # all model features (Config A ⊂ Config B)
            + TARGET_COLS
            + PASSTHROUGH_COLS
            + ID_COLS
            + THERMAL_FEATURES_CONFIG_B_ONLY
            + ["is_water", "sin_season", "cos_season"]
        )
        df = df[[c for c in df.columns if c in keep_cols]]
        return df


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SUHI RE-DERIVATION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def derive_suhi_per_division(
    df: pd.DataFrame,
    impervious_col: str = "impervious_pct",
    low_impervious_quantile: float = 0.10,
) -> pd.DataFrame:
    """
    Acceptable-fallback SUHI derivation (kill-shot #2 fix).

    For each (division, season, year) group:
      - Rural reference pixels = bottom `low_impervious_quantile` of impervious_pct
        AND is_water == 0 (BUG-11 FIX: exclude water pixels from reference)
      - reference_lst = median LST of those rural pixels
      - suhi_derived = lst_c_mean - reference_lst

    Replaces the raw GEE export's single national seasonal reference, which
    is meaningless at national scale because the natural background LST of
    the Chittagong Hill Tracts, Barind dry tract, coastal delta, and Sylhet
    wetlands differs by many degrees Celsius (spec §2.2).

    For the Du et al. 2024 preferred approach (RF background model trained on
    non-built pixels), see derive_suhi_du_style() below.
    """
    df = df.copy()
    df["suhi_derived"]          = np.nan
    df["reference_lst_derived"] = np.nan

    for keys, grp in df.groupby(["division", "season", "year"]):
        imp_thresh = grp[impervious_col].quantile(low_impervious_quantile)

        # BUG-11 FIX: exclude water-dominant pixels from rural reference
        rural_mask = (grp[impervious_col] <= imp_thresh)
        if "is_water" in grp.columns:
            rural_mask = rural_mask & (grp["is_water"] == 0)

        if rural_mask.sum() < 5:
            # Fallback: use bottom 20th percentile
            imp_thresh = grp[impervious_col].quantile(0.20)
            rural_mask = grp[impervious_col] <= imp_thresh
            if "is_water" in grp.columns:
                rural_mask = rural_mask & (grp["is_water"] == 0)

        if rural_mask.sum() == 0:
            continue  # skip groups with no valid rural pixels

        rural_lst = grp.loc[rural_mask, "lst_c_mean"].median()
        df.loc[grp.index, "suhi_derived"]          = grp["lst_c_mean"] - rural_lst
        df.loc[grp.index, "reference_lst_derived"] = rural_lst

    n = df["suhi_derived"].notna().sum()
    print(f"[SUHI] Per-division/season/year SUHI derived for {n:,} pixels "
          f"(water pixels excluded from rural reference)")
    return df


def derive_suhi_du_style(
    train: pd.DataFrame,
    target_df: pd.DataFrame,
    background_features: list = None,
    impervious_col: str = "impervious_pct",
    impervious_background_threshold: float = 0.10,
) -> pd.DataFrame:
    """
    Du et al. 2024 (Remote Sens. 16:599) RF-background SUHI derivation.

    Method:
    1. Identify non-built pixels in train (impervious_pct <= threshold, non-water).
    2. Train a RandomForest on those pixels to predict LST from terrain +
       meteorology + natural land cover (NO built-up predictors).
    3. SUHI_intensity = observed_LST - RF_predicted_background_LST at each pixel.

    This is the 'preferred construction' per spec §2.2 and is defensible at
    national scale because the background model adapts to local climate and terrain.
    The key difference from per-division reference: the background adjusts
    continuously across space rather than stepping at division boundaries.

    Parameters
    ----------
    train       : training DataFrame (background model fit on train's rural pixels)
    target_df   : DataFrame to which SUHI is applied (can be train/val/test)
    background_features : list of feature names for the background RF.
                  Default (None) uses terrain + meteorology + natural LC only.
    impervious_background_threshold : fraction; pixels below this are 'non-built'.
    """
    if background_features is None:
        background_features = [
            "elevation_m_mean", "slope_deg_mean", "tpi_mean",
            "relative_humidity_pct", "chirps_precip_mm", "wind_speed_ms",
            "solar_radiation", "sin_season", "cos_season", "year",
            "ndvi_mean", "mndwi_mean", "lc_cropland_pct", "lc_trees_pct",
            "lc_water_pct", "water_occurrence_pct",
            "dist_to_perm_water_m",
        ]

    # Select non-built, non-water training pixels
    non_built_mask = (
        (train[impervious_col] <= impervious_background_threshold)
        & (train.get("is_water", pd.Series(0, index=train.index)) == 0)
        & train["lst_c_mean"].notna()
    )
    bg_train = train.loc[non_built_mask]

    avail_feats = [c for c in background_features if c in bg_train.columns]
    if len(avail_feats) < 3 or len(bg_train) < 50:
        print("[SUHI-Du] WARNING: insufficient background training pixels or features — "
              "falling back to per-division derivation.")
        return derive_suhi_per_division(target_df)

    # FIX-11: compute train medians for all background features BEFORE fitting.
    # These same medians must be used to fill NaN in val/test target_df, not
    # the target split's own median — using the target median leaks val/test
    # distribution information into the prediction.
    train_bg_medians = bg_train[avail_feats].median()

    X_bg = bg_train[avail_feats].fillna(train_bg_medians)
    y_bg = bg_train["lst_c_mean"]

    rf_bg = RandomForestRegressor(
        n_estimators=200, max_depth=10, min_samples_leaf=5,
        n_jobs=-1, random_state=42
    )
    rf_bg.fit(X_bg, y_bg)
    print(f"[SUHI-Du] Background RF trained on {len(bg_train):,} non-built pixels, "
          f"{len(avail_feats)} features. "
          f"Train R²: {rf_bg.score(X_bg, y_bg):.3f}")

    # Predict background LST for all pixels in target_df
    target = target_df.copy()
    avail_in_target = [c for c in avail_feats if c in target.columns]
    # FIX-11: fill NaN with TRAIN medians, not target_df's own median
    X_target = target[avail_in_target].fillna(train_bg_medians[avail_in_target])
    target["lst_background_du"] = rf_bg.predict(X_target)
    target["suhi_du"]           = target["lst_c_mean"] - target["lst_background_du"]

    n = target["suhi_du"].notna().sum()
    print(f"[SUHI-Du] Du-style SUHI computed for {n:,} pixels")
    return target


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — VALIDATION UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def _panel_key_cols(df: pd.DataFrame, include_period: bool = False) -> list:
    cols = []
    if "division" in df.columns:
        cols.append("division")
    if "district" in df.columns:
        cols.append("district")
    if "grid_id" in df.columns:
        cols.append("grid_id")
    if include_period:
        if "_period" in df.columns:
            cols.append("_period")
    else:
        for col in ["year", "season"]:
            if col in df.columns:
                cols.append(col)
    return cols


def _spatial_group_cols(df: pd.DataFrame) -> list:
    return [col for col in ["division", "district", "year", "season"] if col in df.columns]


def audit_panel_integrity(df: pd.DataFrame) -> dict:
    key_cols = _panel_key_cols(df)
    duplicate_panel_keys = int(df.duplicated(key_cols).sum()) if key_cols else None
    report = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "panel_key_cols": key_cols,
        "duplicate_panel_keys": duplicate_panel_keys,
        "divisions": sorted(df["division"].dropna().unique().tolist()) if "division" in df.columns else [],
        "years": sorted(int(y) for y in df["year"].dropna().unique()) if "year" in df.columns else [],
        "seasons": sorted(df["season"].dropna().unique().tolist()) if "season" in df.columns else [],
    }
    print(
        f"[Audit] rows={report['rows']:,}, divisions={report['divisions']}, "
        f"years={report['years']}, seasons={report['seasons']}, "
        f"duplicate_panel_keys={report['duplicate_panel_keys']}"
    )
    return report


def validate_dataset_identity(
    df: pd.DataFrame,
    expected_divisions: list = None,
    expected_years: list = None,
    expected_seasons: list = None,
) -> dict:
    report = audit_panel_integrity(df)
    errors = []

    if expected_divisions is not None:
        expected = sorted(str(x) for x in expected_divisions)
        observed = sorted(str(x) for x in report["divisions"])
        if observed != expected:
            errors.append(f"divisions expected {expected}, observed {observed}")
    if expected_years is not None:
        expected = sorted(int(x) for x in expected_years)
        observed = sorted(int(x) for x in report["years"])
        if observed != expected:
            errors.append(f"years expected {expected}, observed {observed}")
    if expected_seasons is not None:
        expected = sorted(str(x) for x in expected_seasons)
        observed = sorted(str(x) for x in report["seasons"])
        if observed != expected:
            errors.append(f"seasons expected {expected}, observed {observed}")

    unknown_seasons = sorted(set(report["seasons"]) - set(SEASON_MAP))
    if unknown_seasons:
        errors.append(f"Unknown season labels: {unknown_seasons}")

    if report["duplicate_panel_keys"]:
        errors.append(
            f"duplicate division/grid_id/year/season keys: {report['duplicate_panel_keys']:,}"
        )

    if errors:
        raise ValueError("Dataset identity validation failed: " + "; ".join(errors))
    print("[Identity] PASSED expected dataset identity checks")
    return report


def audit_feature_roles(meta: dict) -> None:
    """
    Verify target/passthrough/leakage columns are not in model feature lists,
    AND that Config B contains the target-lag forecasting features.
    FIX-5: Added positive check so the audit catches Config B with zero lags.
    """
    config_a = set(meta.get("config_a_cols", []))
    config_b = set(meta.get("config_b_cols", []))
    forbidden_any = set(TARGET_COLS + PASSTHROUGH_COLS)
    config_a_forbidden = forbidden_any | set(THERMAL_FEATURES_CONFIG_B_ONLY)

    bad_a = sorted(config_a & config_a_forbidden)
    bad_b = sorted(config_b & forbidden_any)
    errors = []
    if bad_a:
        errors.append(f"Config A contains forbidden cols: {bad_a}")
    if bad_b:
        errors.append(f"Config B contains forbidden cols: {bad_b}")

    # Positive check: Config B must contain at least one target-lag feature
    target_lag_present = [
        c for c in config_b
        if c.startswith("lst_c_mean_lag") or c.startswith("lst_c_max_lag")
    ]
    if not target_lag_present:
        errors.append(
            "Config B contains NO target-lag features (lst_c_mean_lag*). "
            "The forecasting config is missing its defining autoregressive features."
        )

    if errors:
        raise ValueError("Feature role audit FAILED:\n  " + "\n  ".join(errors))
    print(f"[Feature audit] PASSED — Config A ({len(config_a)} features), "
          f"Config B ({len(config_b)} features, "
          f"{len(target_lag_present)} target lags confirmed)")


def validate_no_leakage(
    train: pd.DataFrame,
    val:   pd.DataFrame,
    test:  pd.DataFrame,
    id_col: str = "grid_id",
) -> None:
    """
    BUG-1 FIX: Leakage check adapted for temporal vs. spatial splits.

    Temporal split: same grid_id appears in all splits (same location, different
    years) → check that year ranges are strictly ordered, not that grid_ids are
    disjoint (disjoint grid_ids would be wrong for a temporal split).

    Spatial split (pilot): grid_ids must be disjoint across splits.
    """
    train_years = set(train["year"].unique()) if "year" in train.columns else set()
    val_years   = set(val["year"].unique())   if "year" in val.columns   else set()
    test_years  = set(test["year"].unique())  if "year" in test.columns  else set()

    is_temporal = len(train_years | val_years | test_years) > 1

    if is_temporal:
        # Temporal split: verify strict ordering of year ranges
        ok = True
        if train_years and val_years and max(train_years) >= min(val_years):
            print(f"[Leakage] FAIL: train years {sorted(train_years)} overlap "
                  f"with val years {sorted(val_years)}")
            ok = False
        if val_years and test_years and max(val_years) >= min(test_years):
            print(f"[Leakage] FAIL: val years {sorted(val_years)} overlap "
                  f"with test years {sorted(test_years)}")
            ok = False
        if ok:
            print(f"[Leakage] PASSED (temporal) — "
                  f"train:{sorted(train_years)}, "
                  f"val:{sorted(val_years)}, "
                  f"test:{sorted(test_years)}")
    else:
        # Spatial split (pilot): grid_ids must be disjoint
        train_ids = set(train[id_col].unique())
        val_ids   = set(val[id_col].unique())
        test_ids  = set(test[id_col].unique())
        tv = train_ids & val_ids
        tt = train_ids & test_ids
        vt = val_ids   & test_ids
        if tv or tt or vt:
            print(f"[Leakage] FAIL — train∩val={len(tv)}, "
                  f"train∩test={len(tt)}, val∩test={len(vt)}")
        else:
            print("[Leakage] PASSED (spatial) — train/val/test grid_ids are fully disjoint")


def validate_no_leakage(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    id_col: str = "grid_id",
) -> None:
    """Raise if split boundaries allow target leakage."""
    splits = {"train": train, "val": val, "test": test}
    year_sets = {
        name: set(frame["year"].dropna().astype(int).unique()) if "year" in frame.columns else set()
        for name, frame in splits.items()
    }
    id_sets = {
        name: set(frame[id_col].dropna().unique()) if id_col in frame.columns else set()
        for name, frame in splits.items()
    }

    year_overlap = (
        (year_sets["train"] & year_sets["val"])
        or (year_sets["train"] & year_sets["test"])
        or (year_sets["val"] & year_sets["test"])
    )
    errors = []

    if year_overlap:
        overlaps = {
            "train_val": len(id_sets["train"] & id_sets["val"]),
            "train_test": len(id_sets["train"] & id_sets["test"]),
            "val_test": len(id_sets["val"] & id_sets["test"]),
        }
        if any(overlaps.values()):
            errors.append(f"spatial split has overlapping {id_col}s: {overlaps}")
        else:
            print("[Leakage] PASSED (spatial/block) - overlapping years, disjoint grid_ids")
    else:
        if year_sets["train"] and year_sets["val"] and max(year_sets["train"]) >= min(year_sets["val"]):
            errors.append(f"train years {sorted(year_sets['train'])} overlap val {sorted(year_sets['val'])}")
        if year_sets["val"] and year_sets["test"] and max(year_sets["val"]) >= min(year_sets["test"]):
            errors.append(f"val years {sorted(year_sets['val'])} overlap test {sorted(year_sets['test'])}")
        if not errors:
            print(
                f"[Leakage] PASSED (temporal) - train:{sorted(year_sets['train'])}, "
                f"val:{sorted(year_sets['val'])}, test:{sorted(year_sets['test'])}"
            )

    if errors:
        raise ValueError("Leakage validation failed: " + "; ".join(errors))


def audit_missingness(df: pd.DataFrame, split_label: str = "") -> None:
    """Print a compact missingness report. Call on each split separately."""
    miss = df.isnull().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    total = len(df)
    if len(miss) == 0:
        print(f"[Missingness {split_label}] No missing values.")
        return
    print(f"\n[Missingness {split_label}] {len(miss)} columns with nulls "
          f"(total rows={total:,}):")
    for col, n in miss.items():
        print(f"  {col}: {n:,} ({100 * n / total:.1f}%)")


def check_target_stats(
    train: pd.DataFrame,
    val:   pd.DataFrame,
    test:  pd.DataFrame,
    target: str = "lst_c_mean",
) -> None:
    """Compare target distribution across splits — flag large drift."""
    print(f"\n[Target stats: {target}]")
    for name, split in [("train", train), ("val", val), ("test", test)]:
        if target in split.columns and len(split) > 0:
            s = split[target].dropna()
            print(f"  {name:6s}: mean={s.mean():.2f}  std={s.std():.2f}  "
                  f"min={s.min():.2f}  max={s.max():.2f}  n={len(s):,}")


def _print_summary(
    train, val, test,
    config_a_cols, config_b_cols,
) -> None:
    """Human-readable pipeline summary."""
    sep = "=" * 65
    print(f"\n{sep}")
    print("PREPROCESSING PIPELINE — COMPLETE SUMMARY")
    print(sep)
    print(f"  Train rows : {len(train):,}")
    print(f"  Val rows   : {len(val):,}")
    print(f"  Test rows  : {len(test):,}")
    print(f"\n  Config A (driver/causal)   : {len(config_a_cols)} features")
    print(f"  Config B (accuracy/fcst)   : {len(config_b_cols)} features "
          f"(+{len(config_b_cols) - len(config_a_cols)} thermal)")

    print(f"\n  Config A features ({len(config_a_cols)}):")
    for c in sorted(config_a_cols):
        print(f"    {c}")

    added = [c for c in config_b_cols if c not in config_a_cols]
    if added:
        print(f"\n  Config B adds ({len(added)}):")
        for c in added:
            print(f"    {c}")

    print(f"\n  Target: lst_c_mean (primary)")
    print(f"  SUHI:   suhi_mean to be re-derived via derive_suhi_per_division()")
    print(f"          or derive_suhi_du_style() for the preferred Du et al. approach")
    print(sep + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — MAIN (demo run on sample data)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # FIX-9: Update DATA_PATH to match your actual working file.
    # Options:
    #   Raw single-division export:
    #     DATA_PATH = "/mnt/user-data/uploads/barisal_uhi_2025_all_districts_seasons_1000m.csv"
    #   Pre-processed combined file:
    #     DATA_PATH = "/mnt/user-data/outputs/preprocessed_combined_fixed.csv"
    #   Multi-year national file (when available):
    #     DATA_PATH = "/path/to/bangladesh_uhi_2015_2024_all_divisions.csv"
    DATA_PATH = "/mnt/user-data/outputs/preprocessed_combined_fixed.csv"

    print("\n" + "=" * 65)
    print("Running fixed preprocessing pipeline v2.6")
    print("=" * 65 + "\n")

    pipe = PreprocessingPipeline(
        train_years=None,      # auto-assign: last 2 years → val + test
        val_years=None,
        test_years=None,
        mad_threshold=3.5,
        vif_threshold=5.0,
        spearman_threshold=0.80,
        water_pct_threshold=50.0,
    )

    train, val, test, meta = pipe.fit_transform(DATA_PATH)

    # ── Validation checks ────────────────────────────────────────────────────
    validate_no_leakage(train, val, test)
    check_target_stats(train, val, test)
    audit_missingness(train, "TRAIN")
    audit_missingness(val,   "VAL")
    audit_missingness(test,  "TEST")

    # ── SUHI re-derivation ───────────────────────────────────────────────────
    # FIX-10 / FIX-8: SUHI derivation design choice — two valid approaches:
    #
    # Option A (below, default): combine all splits, derive once.
    #   PRO: every split gets the same rural reference for a given (division,season,year).
    #        Makes SUHI values comparable across train/val/test.
    #   CON: the rural reference for val/test uses some val/test LST pixels, which
    #        is mild label leakage if you use suhi_derived as a SUPERVISED TARGET.
    #        It is NOT leakage if you use lst_c_mean as the target and suhi_derived
    #        only for descriptive/spatial analysis (the recommended use here).
    #
    # Option B (commented): derive on train only, apply reference to val/test.
    #   Use this if suhi_derived is your regression target.
    #   # train = derive_suhi_per_division(train)
    #   # val = derive_suhi_per_division(val)    # each gets its own ref — less consistent
    #   # test = derive_suhi_per_division(test)

    # Default: Option A — combined, consistent reference (suitable for lst_c_mean target)
    full_df = pd.concat([train, val, test], ignore_index=True)
    full_df = derive_suhi_per_division(full_df)
    n_tr = len(train)
    n_va = len(val)
    train = full_df.iloc[:n_tr].reset_index(drop=True)
    val   = full_df.iloc[n_tr:n_tr+n_va].reset_index(drop=True)
    test  = full_df.iloc[n_tr+n_va:].reset_index(drop=True)

    # For Du-style (RF background — preferred, fit on train only):
    # train = derive_suhi_du_style(train, train)
    # val   = derive_suhi_du_style(train, val)   # ← train passed as first arg always
    # test  = derive_suhi_du_style(train, test)  # ← train passed as first arg always

    # ── Scaler (for DL / linear models) ─────────────────────────────────────
    train_scaled = pipe.apply_scaler(train)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"Config A feature count : {len(meta['config_a_cols'])}")
    print(f"Config B feature count : {len(meta['config_b_cols'])}")
    print(f"\nDropped by Spearman    : {meta['dropped_by_spearman']}")
    print(f"Dropped by VIF         : {meta['dropped_by_vif']}")
    print(f"\nSample Config A features (first 12):")
    for c in sorted(meta['config_a_cols'])[:12]:
        print(f"  {c}")
    if len(meta['config_a_cols']) > 12:
        print(f"  ... and {len(meta['config_a_cols']) - 12} more")

    print("\nPipeline complete. Outputs: train, val, test DataFrames + meta dict.")
    print("Next step: pass train[meta['config_a_cols']] and train['lst_c_mean']")
    print("           to OLS → Lasso → RF → LightGBM → CatBoost → XGBoost")
