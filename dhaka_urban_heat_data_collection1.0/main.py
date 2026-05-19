"""CLI driver for Dhaka urban heat data collection."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import ee

from config import (
    DEFAULT_GRID_SIZE_M,
    DEFAULT_LANDSAT_SCALE_M,
    DEFAULT_MAX_CLOUD_COVER,
    DEFAULT_REFERENCE_BUFFER_KM,
    GOOGLE_OPEN_BUILDINGS,
    LOG_OUTPUT_DIR,
    LULC_PERCENT_FIELDS,
    PROCESSED_OUTPUT_DIR,
    SEASONS,
)
from src.aggregation import add_run_metadata, aggregate_image_to_grid, join_feature_collections
from src.distance_features import aggregate_distance_to_grid, calculate_distance_to_water
from src.ee_auth import initialize_earth_engine
from src.export import export_table_to_drive, feature_collection_to_local_csv
from src.grid import create_grid
from src.landsat_lst import get_landsat_lst_composite
from src.lulc6 import calculate_lulc_percentages, get_lulc6_image
from src.morphology import calculate_morphology_features
from src.spectral_indices import add_spectral_indices
from src.study_area import create_analysis_region, create_reference_zone, get_dhaka_boundary
from src.suhi import add_suhi_band, calculate_reference_lst_mean
from src.validation import build_validation_report


def _configure_logging() -> None:
    LOG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_OUTPUT_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")],
    )


def _merge_feature_collections(collections: list[ee.FeatureCollection]) -> ee.FeatureCollection:
    if not collections:
        return ee.FeatureCollection([])
    merged = collections[0]
    for collection in collections[1:]:
        merged = merged.merge(collection)
    return merged


def build_year_table(
    year: int,
    season: str,
    aoi: ee.FeatureCollection,
    analysis_region: ee.FeatureCollection,
    reference_zone: ee.FeatureCollection,
    grid: ee.FeatureCollection,
    morphology_fc: ee.FeatureCollection,
    max_cloud_cover: float,
) -> tuple[ee.FeatureCollection, ee.FeatureCollection]:
    """Build one year-season machine-learning-ready grid table."""
    logging.info("Building Landsat LST composite for %s %s", year, season)
    landsat = get_landsat_lst_composite(
        analysis_region,
        year=year,
        season=season,
        max_cloud_cover=max_cloud_cover,
    )
    indexed = add_spectral_indices(landsat)

    logging.info("Calculating reference LST and SUHI for %s %s", year, season)
    reference_mean = calculate_reference_lst_mean(indexed, reference_zone, scale=DEFAULT_LANDSAT_SCALE_M)

    logging.info("Calculating distance-to-water for %s %s", year, season)
    distance_image = calculate_distance_to_water(aoi, year, season, spectral_image=indexed)
    analysis_image = add_suhi_band(indexed.addBands(distance_image, overwrite=True), reference_mean)

    logging.info("Aggregating raster variables to grid for %s %s", year, season)
    raster_grid = aggregate_image_to_grid(analysis_image, grid, scale=DEFAULT_LANDSAT_SCALE_M)
    distance_grid = aggregate_distance_to_grid(distance_image, grid, scale=DEFAULT_LANDSAT_SCALE_M)

    logging.info("Calculating LULC6 percentages for %s", year)
    lulc = get_lulc6_image(year, aoi)
    lulc_grid = calculate_lulc_percentages(lulc, grid)

    table = join_feature_collections(
        raster_grid,
        lulc_grid,
        right_properties=[*LULC_PERCENT_FIELDS, "dominant_lulc6", "lulc_total_area_m2", "lulc_year"],
    )
    table = join_feature_collections(
        table,
        morphology_fc,
        right_properties=[
            "building_area_m2",
            "building_area_ratio",
            "building_count",
            "road_density_m_per_km2",
            "road_density_available",
            "road_density_note",
        ],
    )
    table = join_feature_collections(
        table,
        distance_grid,
        right_properties=["mean_distance_to_water_m", "min_distance_to_water_m", "distance_to_water"],
    )
    table = add_run_metadata(table, year, season, reference_mean)

    validation = build_validation_report(table, analysis_image, aoi, year, season)
    return table, validation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dhaka urban heat data collection pipeline.")
    parser.add_argument("--project", type=str, default=None, help="Google Cloud project for Earth Engine.")
    parser.add_argument("--start-year", type=int, required=True, help="First observation year.")
    parser.add_argument("--end-year", type=int, required=True, help="Last observation year.")
    parser.add_argument("--season", choices=sorted(SEASONS), required=True, help="Dhaka season to process.")
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE_M, choices=[500, 1000])
    parser.add_argument("--export-folder", type=str, required=True, help="Google Drive folder for CSV exports.")
    parser.add_argument("--boundary-asset", type=str, default=None, help="Optional user-uploaded Dhaka boundary asset.")
    parser.add_argument("--roads-asset", type=str, default=None, help="Optional road line vector asset for road density.")
    parser.add_argument("--no-open-buildings", action="store_true", help="Skip Google Open Buildings morphology.")
    parser.add_argument("--max-cloud-cover", type=float, default=DEFAULT_MAX_CLOUD_COVER)
    parser.add_argument("--local-small-csv", action="store_true", help="Also attempt local CSV export for small grids.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _configure_logging()

    if args.start_year > args.end_year:
        raise ValueError("--start-year must be less than or equal to --end-year.")

    logging.info("Initializing Earth Engine")
    initialize_earth_engine(args.project)

    logging.info("Loading Dhaka boundary")
    aoi = get_dhaka_boundary(args.boundary_asset)
    reference_zone = create_reference_zone(aoi, buffer_km=DEFAULT_REFERENCE_BUFFER_KM)
    analysis_region = create_analysis_region(aoi, reference_zone)

    logging.info("Creating %s m grid", args.grid_size)
    grid = create_grid(aoi, grid_size_m=args.grid_size)

    logging.info("Calculating static morphology features")
    buildings_asset = None if args.no_open_buildings else GOOGLE_OPEN_BUILDINGS
    morphology_fc = calculate_morphology_features(
        grid,
        aoi,
        buildings_asset_id=buildings_asset,
        roads_asset_id=args.roads_asset,
    )

    yearly_tables: list[ee.FeatureCollection] = []
    validation_reports: list[ee.FeatureCollection] = []

    for year in range(args.start_year, args.end_year + 1):
        table, validation = build_year_table(
            year=year,
            season=args.season,
            aoi=aoi,
            analysis_region=analysis_region,
            reference_zone=reference_zone,
            grid=grid,
            morphology_fc=morphology_fc,
            max_cloud_cover=args.max_cloud_cover,
        )

        yearly_name = f"dhaka_urban_heat_grid_{year}_{args.season}_{args.grid_size}m"
        validation_name = f"dhaka_urban_heat_validation_{year}_{args.season}_{args.grid_size}m"

        task = export_table_to_drive(table, yearly_name, args.export_folder, yearly_name)
        validation_task = export_table_to_drive(validation, validation_name, args.export_folder, validation_name)
        logging.info("Started Drive export %s: %s", yearly_name, task.id)
        logging.info("Started validation export %s: %s", validation_name, validation_task.id)

        if args.local_small_csv:
            local_path = PROCESSED_OUTPUT_DIR / f"{yearly_name}.csv"
            try:
                feature_collection_to_local_csv(table, local_path)
                logging.info("Wrote local small CSV to %s", local_path)
            except Exception as exc:
                logging.warning("Local CSV export skipped: %s", exc)

        yearly_tables.append(table)
        validation_reports.append(validation)

    final_table = _merge_feature_collections(yearly_tables)
    final_validation = _merge_feature_collections(validation_reports)

    final_name = f"dhaka_urban_heat_grid_{args.start_year}_{args.end_year}_{args.season}_{args.grid_size}m"
    final_validation_name = (
        f"dhaka_urban_heat_validation_{args.start_year}_{args.end_year}_{args.season}_{args.grid_size}m"
    )
    final_task = export_table_to_drive(final_table, final_name, args.export_folder, final_name)
    final_validation_task = export_table_to_drive(
        final_validation,
        final_validation_name,
        args.export_folder,
        final_validation_name,
    )
    logging.info("Started final joined table export %s: %s", final_name, final_task.id)
    logging.info("Started final validation export %s: %s", final_validation_name, final_validation_task.id)
    logging.info("Earth Engine exports are asynchronous. Check the Earth Engine Tasks tab or Drive folder.")


if __name__ == "__main__":
    main()
