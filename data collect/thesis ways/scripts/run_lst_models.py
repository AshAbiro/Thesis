from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


ROOT = Path(__file__).resolve().parents[1]
MODELING_DIR = ROOT / "modeling"
DEMO_DIR = MODELING_DIR / "demo"
RESULTS_DIR = MODELING_DIR / "results"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pbias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denominator = float(np.sum(y_true))
    if denominator == 0:
        return float("nan")
    return float(100.0 * np.sum(y_pred - y_true) / denominator)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(math.sqrt(mean_squared_error(y_true, y_pred)))


def bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(y_pred - y_true))


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": rmse(y_true, y_pred),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "pbias": pbias(y_true, y_pred),
        "bias": bias(y_true, y_pred),
    }


def ensure_dirs() -> None:
    for directory in [MODELING_DIR, DEMO_DIR, RESULTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_preprocessor(feature_columns: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, feature_columns),
        ],
        remainder="drop",
    )


def build_models(feature_columns: list[str], cv_folds: int, random_state: int) -> dict[str, GridSearchCV | Pipeline]:
    preprocessor = build_preprocessor(feature_columns)

    linear = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", LinearRegression()),
        ]
    )

    svr = GridSearchCV(
        estimator=Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("model", SVR(kernel="rbf")),
            ]
        ),
        param_grid={
            "model__C": [1.0, 10.0, 100.0],
            "model__gamma": ["scale", 0.1, 0.01],
            "model__epsilon": [0.1, 0.2],
        },
        cv=KFold(n_splits=cv_folds, shuffle=True, random_state=random_state),
        scoring="neg_root_mean_squared_error",
        n_jobs=1,
        refit=True,
    )

    random_forest = GridSearchCV(
        estimator=Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "model",
                    RandomForestRegressor(
                        random_state=random_state,
                        n_estimators=300,
                    ),
                ),
            ]
        ),
        param_grid={
            "model__max_depth": [None, 10, 20],
            "model__min_samples_split": [2, 4],
            "model__min_samples_leaf": [1, 2],
        },
        cv=KFold(n_splits=cv_folds, shuffle=True, random_state=random_state),
        scoring="neg_root_mean_squared_error",
        n_jobs=1,
        refit=True,
    )

    ann = GridSearchCV(
        estimator=Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "model",
                    MLPRegressor(
                        random_state=random_state,
                        max_iter=4000,
                        early_stopping=True,
                    ),
                ),
            ]
        ),
        param_grid={
            "model__hidden_layer_sizes": [(64,), (64, 32), (128, 64)],
            "model__alpha": [0.0001, 0.001],
            "model__learning_rate_init": [0.001, 0.01],
        },
        cv=KFold(n_splits=cv_folds, shuffle=True, random_state=random_state),
        scoring="neg_root_mean_squared_error",
        n_jobs=1,
        refit=True,
    )

    return {
        "LinearRegression": linear,
        "SVM": svr,
        "RandomForest": random_forest,
        "ANN": ann,
    }


def choose_feature_columns(df: pd.DataFrame, target: str, explicit_features: list[str] | None) -> list[str]:
    if explicit_features:
        missing = [column for column in explicit_features if column not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {', '.join(missing)}")
        return explicit_features

    numeric_columns = [column for column in df.columns if pd.api.types.is_numeric_dtype(df[column])]
    return [column for column in numeric_columns if column != target]


def create_demo_dataset(output_path: Path, rows: int, random_state: int) -> None:
    rng = np.random.default_rng(random_state)

    df = pd.DataFrame(
        {
            "ndvi": rng.uniform(0.05, 0.75, rows),
            "ndbi": rng.uniform(-0.2, 0.65, rows),
            "ndwi": rng.uniform(-0.35, 0.45, rows),
            "albedo": rng.uniform(0.08, 0.35, rows),
            "ui": rng.uniform(-0.1, 0.8, rows),
            "water_pct": rng.uniform(0, 45, rows),
            "tree_cover_gt2m_pct": rng.uniform(0, 55, rows),
            "built_area_ratio": rng.uniform(0.05, 0.95, rows),
            "x_coord": rng.uniform(0, 1, rows),
            "y_coord": rng.uniform(0, 1, rows),
        }
    )

    noise = rng.normal(0, 0.7, rows)
    df["lst_c"] = (
        31.5
        - 6.0 * df["ndvi"]
        + 5.4 * df["ndbi"]
        - 2.8 * df["ndwi"]
        - 4.2 * df["albedo"]
        + 3.6 * df["ui"]
        - 0.035 * df["water_pct"]
        - 0.025 * df["tree_cover_gt2m_pct"]
        + 4.1 * df["built_area_ratio"]
        + 1.6 * df["x_coord"]
        - 1.1 * df["y_coord"]
        + noise
    )

    df.to_csv(output_path, index=False)


def model_report_text(
    dataset_path: Path,
    target: str,
    feature_columns: list[str],
    metrics_rows: list[dict[str, object]],
    best_model: str,
    train_rows: int,
    test_rows: int,
) -> str:
    headers = ["Model", "RMSE", "MAE", "R2", "PBIAS", "Bias"]
    rows = []
    for item in metrics_rows:
        rows.append(
            [
                str(item["model"]),
                f"{item['rmse']:.4f}",
                f"{item['mae']:.4f}",
                f"{item['r2']:.4f}",
                f"{item['pbias']:.4f}",
                f"{item['bias']:.4f}",
            ]
        )

    lines = [
        "# LST Model Run",
        "",
        f"Generated: {timestamp()}",
        "",
        f"- Dataset: {dataset_path}",
        f"- Target: {target}",
        f"- Feature count: {len(feature_columns)}",
        f"- Features: {', '.join(feature_columns)}",
        f"- Train rows: {train_rows}",
        f"- Test rows: {test_rows}",
        f"- Best model by RMSE: {best_model}",
        "",
        markdown_table(headers, rows),
        "",
    ]
    return "\n".join(lines)


def run_models(
    dataset_path: Path,
    target: str,
    feature_columns: list[str] | None,
    test_size: float,
    cv_folds: int,
    random_state: int,
    run_name: str | None,
) -> Path:
    ensure_dirs()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    df = pd.read_csv(dataset_path)
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found in {dataset_path.name}")

    chosen_features = choose_feature_columns(df, target, feature_columns)
    if not chosen_features:
        raise ValueError("No numeric feature columns were found to train models.")

    modeling_df = df[chosen_features + [target]].copy()
    modeling_df = modeling_df.dropna(subset=[target])

    x = modeling_df[chosen_features]
    y = modeling_df[target].astype(float)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=test_size,
        random_state=random_state,
    )

    models = build_models(chosen_features, cv_folds=cv_folds, random_state=random_state)

    metrics_rows: list[dict[str, object]] = []
    prediction_frame = pd.DataFrame({"observed": y_test.reset_index(drop=True)})
    best_model_name = ""
    best_rmse = float("inf")

    for model_name, model in models.items():
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics = regression_metrics(y_test.to_numpy(), predictions)

        metrics_rows.append({"model": model_name, **metrics})
        prediction_frame[model_name] = predictions

        if metrics["rmse"] < best_rmse:
            best_rmse = metrics["rmse"]
            best_model_name = model_name

    metrics_rows.sort(key=lambda item: item["rmse"])

    run_slug = run_name or dataset_path.stem
    output_dir = RESULTS_DIR / run_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "metrics.json"
    predictions_path = output_dir / "predictions.csv"
    report_path = output_dir / "report.md"

    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated": timestamp(),
                "dataset": str(dataset_path),
                "target": target,
                "features": chosen_features,
                "train_rows": int(len(x_train)),
                "test_rows": int(len(x_test)),
                "best_model": best_model_name,
                "metrics": metrics_rows,
            },
            handle,
            indent=2,
        )

    prediction_frame.to_csv(predictions_path, index=False)
    report_path.write_text(
        model_report_text(
            dataset_path=dataset_path,
            target=target,
            feature_columns=chosen_features,
            metrics_rows=metrics_rows,
            best_model=best_model_name,
            train_rows=int(len(x_train)),
            test_rows=int(len(x_test)),
        ),
        encoding="utf-8",
    )

    print(f"Model run completed: {run_slug}")
    print(f"- Report: {report_path}")
    print(f"- Metrics: {metrics_path}")
    print(f"- Predictions: {predictions_path}")
    print(f"- Best model: {best_model_name}")
    return output_dir


def command_demo_data(args: argparse.Namespace) -> int:
    ensure_dirs()
    output_path = Path(args.output) if args.output else DEMO_DIR / "synthetic_lst_demo.csv"
    create_demo_dataset(output_path=output_path, rows=args.rows, random_state=args.random_state)
    print(f"Created demo dataset: {output_path}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset)
    feature_columns = args.features.split(",") if args.features else None
    run_models(
        dataset_path=dataset_path,
        target=args.target,
        feature_columns=feature_columns,
        test_size=args.test_size,
        cv_folds=args.cv_folds,
        random_state=args.random_state,
        run_name=args.run_name,
    )
    return 0


def command_demo_run(args: argparse.Namespace) -> int:
    ensure_dirs()
    dataset_path = DEMO_DIR / "synthetic_lst_demo.csv"
    create_demo_dataset(output_path=dataset_path, rows=args.rows, random_state=args.random_state)
    run_models(
        dataset_path=dataset_path,
        target="lst_c",
        feature_columns=None,
        test_size=0.2,
        cv_folds=5,
        random_state=args.random_state,
        run_name="synthetic_demo_run",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run thesis-style LST regression models on a CSV feature table.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_data = subparsers.add_parser("demo-data", help="Create a synthetic LST regression dataset for smoke testing.")
    demo_data.add_argument("--output", help="Output CSV path. Defaults to modeling/demo/synthetic_lst_demo.csv")
    demo_data.add_argument("--rows", type=int, default=500, help="Number of synthetic rows to create.")
    demo_data.add_argument("--random-state", type=int, default=42)
    demo_data.set_defaults(func=command_demo_data)

    run = subparsers.add_parser("run", help="Run regression models on a real CSV dataset.")
    run.add_argument("--dataset", required=True, help="Path to the input CSV.")
    run.add_argument("--target", required=True, help="Target column name, e.g. lst_c.")
    run.add_argument("--features", help="Comma-separated feature columns. Defaults to all numeric columns except target.")
    run.add_argument("--test-size", type=float, default=0.2)
    run.add_argument("--cv-folds", type=int, default=5)
    run.add_argument("--random-state", type=int, default=42)
    run.add_argument("--run-name", help="Optional output folder name under modeling/results/.")
    run.set_defaults(func=command_run)

    demo_run = subparsers.add_parser("demo-run", help="Create a synthetic dataset and run the full model pipeline.")
    demo_run.add_argument("--rows", type=int, default=500)
    demo_run.add_argument("--random-state", type=int, default=42)
    demo_run.set_defaults(func=command_demo_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
