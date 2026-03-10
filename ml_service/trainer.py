"""
On-demand model training pipeline.

Flow:
  1. Fetch auto-aggregated data from inventory_transactions
  2. Merge with CSV-uploaded historical data (if any)
  3. De-duplicate by date (uploaded data takes precedence for overlapping dates)
  4. Build feature matrix
  5. Train GradientBoostingRegressor (or RandomForest for small datasets)
  6. Cross-validate with TimeSeriesSplit
  7. Persist model + metadata
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error

from config import MODEL_STORAGE_PATH, MIN_TRAINING_DAYS
from db import (
    get_daily_aggregated_transactions,
    get_uploaded_history,
    save_model_metadata,
    update_model_status,
)
from features import build_feature_matrix, ALL_FEATURES


def _merge_data_sources(
    auto_df: pd.DataFrame,
    uploaded_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine auto-aggregated and uploaded data into a single daily series.

    If both sources have data for the same date, uploaded data takes precedence
    (assumption: user-provided historical data is more accurate for pre-WMS period).
    """
    frames = []

    if not uploaded_df.empty:
        upl = uploaded_df[["date", "inbound_qty", "outbound_qty"]].copy()
        upl["source"] = "uploaded"
        frames.append(upl)

    if not auto_df.empty:
        auto = auto_df[["date", "inbound_qty", "outbound_qty"]].copy()
        auto["source"] = "auto"
        frames.append(auto)

    if not frames:
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty"])

    combined = pd.concat(frames, ignore_index=True)

    # Keep uploaded rows over auto rows for the same date
    combined = combined.sort_values(
        ["date", "source"], ascending=[True, True]  # 'auto' < 'uploaded'
    ).drop_duplicates(subset=["date"], keep="last")

    return (
        combined[["date", "inbound_qty", "outbound_qty"]]
        .sort_values("date")
        .reset_index(drop=True)
    )


def _fill_missing_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill gaps in the date sequence with zero inbound/outbound rows.
    Ensures a contiguous daily series for lag/trend feature computation.
    """
    if df.empty:
        return df

    full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    full_df = pd.DataFrame({"date": full_range.date})

    merged = full_df.merge(df, on="date", how="left")
    merged["inbound_qty"] = merged["inbound_qty"].fillna(0).astype(int)
    merged["outbound_qty"] = merged["outbound_qty"].fillna(0).astype(int)
    return merged


def _get_model_path(product_id: int, business_id: int) -> Path:
    return MODEL_STORAGE_PATH / f"product_{product_id}_biz_{business_id}.joblib"


def train_model(product_id: int, business_id: int) -> dict:
    """
    Train (or re-train) a demand prediction model for a single product.

    Returns a dict with training metrics and metadata.
    Raises ValueError if insufficient data.
    """
    # Mark status as training
    update_model_status(product_id, business_id, "training")

    try:
        # ── 1. Gather data ───────────────────────────────────────────
        auto_df = get_daily_aggregated_transactions(product_id, business_id)
        uploaded_df = get_uploaded_history(product_id, business_id)
        combined = _merge_data_sources(auto_df, uploaded_df)

        if combined.empty:
            raise ValueError(
                "No training data available. Upload historical data or "
                "record inventory transactions first."
            )

        combined = _fill_missing_dates(combined)
        n_days = len(combined)

        if n_days < MIN_TRAINING_DAYS:
            raise ValueError(
                f"Need at least {MIN_TRAINING_DAYS} days of data to train a model. "
                f"Currently have {n_days} days."
            )

        # ── 2. Build features ────────────────────────────────────────
        X, y = build_feature_matrix(combined)

        # ── 3. Choose model ──────────────────────────────────────────
        if n_days >= 60:
            model = GradientBoostingRegressor(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
            )
        else:
            # Small dataset – simpler model to avoid overfitting
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                random_state=42,
            )

        # ── 4. Cross-validate with TimeSeriesSplit ───────────────────
        n_splits = min(5, max(2, n_days // 30))
        tscv = TimeSeriesSplit(n_splits=n_splits)

        cv_maes: list[float] = []
        cv_mapes: list[float] = []

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            preds = np.maximum(preds, 0)  # demand can't be negative

            mae = mean_absolute_error(y_test, preds)
            cv_maes.append(mae)

            # MAPE – avoid division by zero
            mask = y_test > 0
            if mask.sum() > 0:
                mape = float(np.mean(np.abs((y_test[mask] - preds[mask]) / y_test[mask])) * 100)
            else:
                mape = 0.0
            cv_mapes.append(mape)

        avg_mae = float(np.mean(cv_maes))
        avg_mape = float(np.mean(cv_mapes))

        # ── 5. Retrain on full data ──────────────────────────────────
        model.fit(X, y)

        # ── 6. Persist model ─────────────────────────────────────────
        model_path = _get_model_path(product_id, business_id)
        artifact = {
            "model": model,
            "features": ALL_FEATURES,
            "data_start": combined["date"].min(),
            "data_end": combined["date"].max(),
            "n_days": n_days,
        }
        joblib.dump(artifact, model_path)

        # ── 7. Save metadata to DB ───────────────────────────────────
        meta = save_model_metadata(
            product_id=product_id,
            business_id=business_id,
            model_path=str(model_path),
            data_start=combined["date"].min(),
            data_end=combined["date"].max(),
            total_points=n_days,
            cv_mae=avg_mae,
            cv_mape=avg_mape,
            features_used=ALL_FEATURES,
        )

        return {
            "status": "ready",
            "product_id": product_id,
            "business_id": business_id,
            "data_points": n_days,
            "data_start": str(combined["date"].min()),
            "data_end": str(combined["date"].max()),
            "model_type": type(model).__name__,
            "cv_mae": round(avg_mae, 2),
            "cv_mape": round(avg_mape, 2),
            "cv_splits": n_splits,
            "features_used": ALL_FEATURES,
            "message": "Model trained successfully",
        }

    except ValueError:
        update_model_status(product_id, business_id, "failed")
        raise
    except Exception as e:
        update_model_status(product_id, business_id, "failed")
        raise ValueError(f"Training failed: {str(e)}")


def load_model(product_id: int, business_id: int) -> dict | None:
    """
    Load a trained model artifact from disk.

    Returns a dict with keys: model, features, data_start, data_end, n_days
    or None if no model exists.
    """
    model_path = _get_model_path(product_id, business_id)
    if not model_path.exists():
        return None
    return joblib.load(model_path)


def delete_model(product_id: int, business_id: int) -> bool:
    """Delete the model file from disk. Returns True if file existed."""
    model_path = _get_model_path(product_id, business_id)
    if model_path.exists():
        model_path.unlink()
        return True
    return False
