#!/usr/bin/env python
"""Train baseline heat-prediction models from a tabular dataset.

The input file must contain a numeric target column such as ``lst_c`` plus
numeric predictor columns. Non-numeric columns are ignored unless explicitly
listed in ``--keep-cols`` for prediction output.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


@dataclass(frozen=True)
class ModelSpec:
    name: str
    estimator: object


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="CSV or Parquet dataset with predictors and target")
    parser.add_argument("--target", default="lst_c", help="Numeric target column to predict")
    parser.add_argument(
        "--features",
        nargs="*",
        default=None,
        help="Optional explicit feature columns. Default: all numeric columns except target",
    )
    parser.add_argument(
        "--keep-cols",
        nargs="*",
        default=[],
        help="Optional columns to carry through into predictions output",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Holdout fraction for evaluation")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for metrics and predictions")
    return parser.parse_args()


def load_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported input format: {path}")


def choose_features(df: pd.DataFrame, target: str, requested: list[str] | None) -> list[str]:
    if target not in df.columns:
        raise ValueError(f"Target column not found: {target}")

    if requested:
        missing = [col for col in requested if col not in df.columns]
        if missing:
            raise ValueError(f"Requested feature columns not found: {missing}")
        return requested

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    features = [col for col in numeric_cols if col != target]
    if not features:
        raise ValueError("No numeric feature columns found")
    return features


def build_models(random_state: int) -> list[ModelSpec]:
    return [
        ModelSpec(
            "LinearRegression",
            Pipeline(
                steps=[
                    ("scale", StandardScaler()),
                    ("model", LinearRegression()),
                ]
            ),
        ),
        ModelSpec(
            "SVM",
            Pipeline(
                steps=[
                    ("scale", StandardScaler()),
                    ("model", SVR(kernel="rbf", C=10.0, epsilon=0.1)),
                ]
            ),
        ),
        ModelSpec(
            "ANN",
            Pipeline(
                steps=[
                    ("scale", StandardScaler()),
                    (
                        "model",
                        MLPRegressor(
                            hidden_layer_sizes=(64, 32),
                            activation="relu",
                            solver="adam",
                            alpha=0.0005,
                            learning_rate_init=0.001,
                            max_iter=2000,
                            early_stopping=True,
                            random_state=random_state,
                        ),
                    ),
                ]
            ),
        ),
        ModelSpec(
            "RandomForest",
            RandomForestRegressor(
                n_estimators=400,
                min_samples_leaf=2,
                random_state=random_state,
                n_jobs=-1,
            ),
        ),
    ]


def pbias(y_true: pd.Series, y_pred: Iterable[float]) -> float:
    denom = float(y_true.sum())
    if abs(denom) < 1e-12:
        return 0.0
    return float(100.0 * ((pd.Series(y_pred, index=y_true.index) - y_true).sum() / denom))


def to_builtin_types(data: object) -> object:
    if isinstance(data, dict):
        return {str(k): to_builtin_types(v) for k, v in data.items()}
    if isinstance(data, list):
        return [to_builtin_types(v) for v in data]
    if hasattr(data, "item"):
        return data.item()
    return data


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw = load_table(args.input)
    features = choose_features(raw, args.target, args.features)

    keep_cols = [col for col in args.keep_cols if col in raw.columns]
    model_df = raw[keep_cols + features + [args.target]].copy()

    before_rows = len(model_df)
    model_df = model_df.dropna(subset=features + [args.target]).reset_index(drop=True)
    dropped_rows = before_rows - len(model_df)

    if len(model_df) < 20:
        raise ValueError("Not enough rows after dropping missing values to train models")

    x = model_df[features]
    y = model_df[args.target]
    kept = model_df[keep_cols].copy()

    x_train, x_test, y_train, y_test, keep_train, keep_test = train_test_split(
        x,
        y,
        kept,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    metrics: list[dict[str, object]] = []
    predictions = keep_test.reset_index(drop=True).copy()
    predictions[args.target] = y_test.reset_index(drop=True)

    for spec in build_models(args.random_state):
        estimator = spec.estimator
        estimator.fit(x_train, y_train)
        y_pred = estimator.predict(x_test)

        metrics.append(
            {
                "model": spec.name,
                "rmse": float(root_mean_squared_error(y_test, y_pred)),
                "mae": float(mean_absolute_error(y_test, y_pred)),
                "r2": float(r2_score(y_test, y_pred)),
                "pbias": float(pbias(y_test, y_pred)),
                "bias": float((pd.Series(y_pred, index=y_test.index) - y_test).mean()),
            }
        )
        predictions[f"pred_{spec.name}"] = y_pred

    metrics = sorted(metrics, key=lambda item: item["rmse"])
    best_model = metrics[0]["model"]

    report = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": str(args.input.resolve()),
        "target": args.target,
        "features": features,
        "rows_total": int(len(raw)),
        "rows_used": int(len(model_df)),
        "rows_dropped_missing": int(dropped_rows),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "best_model": best_model,
        "metrics": metrics,
    }

    metrics_path = args.output_dir / "metrics.json"
    predictions_path = args.output_dir / "predictions.csv"
    report_path = args.output_dir / "report.md"

    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(to_builtin_types(report), handle, indent=2)

    predictions.to_csv(predictions_path, index=False)

    lines = [
        "# Heat Model Run",
        "",
        f"Generated: {report['generated']}",
        "",
        f"- Dataset: {report['dataset']}",
        f"- Target: {report['target']}",
        f"- Feature count: {len(features)}",
        f"- Features: {', '.join(features)}",
        f"- Total rows: {report['rows_total']}",
        f"- Rows used: {report['rows_used']}",
        f"- Rows dropped for missing values: {report['rows_dropped_missing']}",
        f"- Train rows: {report['train_rows']}",
        f"- Test rows: {report['test_rows']}",
        f"- Best model by RMSE: {best_model}",
        "",
        "| Model | RMSE | MAE | R2 | PBIAS | Bias |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in metrics:
        lines.append(
            "| {model} | {rmse:.4f} | {mae:.4f} | {r2:.4f} | {pbias:.4f} | {bias:.4f} |".format(**item)
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {predictions_path}")
    print(f"Wrote: {report_path}")


if __name__ == "__main__":
    main()
