"""
On-demand model training pipeline (enhanced).

Flow:
  1. Fetch auto-aggregated data from inventory_transactions
  2. Merge with CSV-uploaded historical data (if any)
  3. De-duplicate by date (uploaded data takes precedence for overlapping dates)
  4. Build feature matrix (52 features: temporal, cyclical, holiday, lag, rolling,
     ratio, trend)
  5. Search across multiple model configurations with TimeSeriesSplit CV
  6. Pick the best config (lowest MAE), retrain on full data
  7. Persist model + metadata

Supports XGBoost (preferred) with early stopping, falls back to sklearn GBR.
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# ── XGBoost availability ────────────────────────────────────────────────────

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
    logger.info("XGBoost available – will use XGBRegressor")
except ImportError:
    HAS_XGBOOST = False
    logger.info("XGBoost not installed – falling back to sklearn")


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
    full_df = pd.DataFrame({"date": full_range})

    merged = full_df.merge(df, on="date", how="left")
    merged["inbound_qty"] = merged["inbound_qty"].fillna(0).astype(int)
    merged["outbound_qty"] = merged["outbound_qty"].fillna(0).astype(int)
    return merged


def _get_model_path(product_id: int, business_id: int) -> Path:
    return MODEL_STORAGE_PATH / f"product_{product_id}_biz_{business_id}.joblib"


# ── Candidate model configurations ──────────────────────────────────────────

def _get_candidates(n_days: int) -> list[dict]:
    """Return model configurations to evaluate, ordered by expected quality."""
    if HAS_XGBOOST:
        if n_days >= 300:
            return [
                {
                    "name": "xgb_huber_deep",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 3000, "max_depth": 6,
                        "learning_rate": 0.01, "subsample": 0.8,
                        "colsample_bytree": 0.8, "min_child_weight": 3,
                        "reg_alpha": 0.01, "reg_lambda": 0.3,
                        "gamma": 0.1,
                        "objective": "reg:pseudohubererror",
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 100,
                },
                {
                    "name": "xgb_huber_balanced",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 2000, "max_depth": 5,
                        "learning_rate": 0.01, "subsample": 0.85,
                        "colsample_bytree": 0.8, "min_child_weight": 3,
                        "reg_alpha": 0.005, "reg_lambda": 0.2,
                        "gamma": 0.05,
                        "objective": "reg:pseudohubererror",
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 80,
                },
                {
                    "name": "xgb_sqe_deep",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 2500, "max_depth": 6,
                        "learning_rate": 0.008, "subsample": 0.8,
                        "colsample_bytree": 0.85, "min_child_weight": 3,
                        "reg_alpha": 0.01, "reg_lambda": 0.3,
                        "gamma": 0.05,
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 100,
                },
                {
                    "name": "xgb_sqe_shallow",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 2000, "max_depth": 4,
                        "learning_rate": 0.015, "subsample": 0.9,
                        "colsample_bytree": 0.9, "min_child_weight": 2,
                        "reg_alpha": 0.0, "reg_lambda": 0.1,
                        "gamma": 0.0,
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 80,
                },
            ]
        elif n_days >= 100:
            return [
                {
                    "name": "xgb_huber_med",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 2000, "max_depth": 5,
                        "learning_rate": 0.01, "subsample": 0.85,
                        "colsample_bytree": 0.8, "min_child_weight": 2,
                        "reg_alpha": 0.005, "reg_lambda": 0.2,
                        "gamma": 0.05,
                        "objective": "reg:pseudohubererror",
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 80,
                },
                {
                    "name": "xgb_sqe_med",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 2000, "max_depth": 5,
                        "learning_rate": 0.01, "subsample": 0.85,
                        "colsample_bytree": 0.85, "min_child_weight": 2,
                        "reg_alpha": 0.005, "reg_lambda": 0.2,
                        "gamma": 0.05,
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 80,
                },
                {
                    "name": "xgb_sqe_med_shallow",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 1500, "max_depth": 4,
                        "learning_rate": 0.02, "subsample": 0.9,
                        "colsample_bytree": 0.9, "min_child_weight": 2,
                        "reg_alpha": 0.0, "reg_lambda": 0.1,
                        "gamma": 0.0,
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 60,
                },
            ]
        else:
            return [
                {
                    "name": "xgb_small_huber",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 1000, "max_depth": 4,
                        "learning_rate": 0.02, "subsample": 0.9,
                        "colsample_bytree": 0.9, "min_child_weight": 2,
                        "reg_alpha": 0.0, "reg_lambda": 0.1,
                        "objective": "reg:pseudohubererror",
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 40,
                },
                {
                    "name": "xgb_small_sqe",
                    "type": "xgb",
                    "params": {
                        "n_estimators": 1000, "max_depth": 5,
                        "learning_rate": 0.02, "subsample": 0.85,
                        "colsample_bytree": 0.85, "min_child_weight": 2,
                        "reg_alpha": 0.0, "reg_lambda": 0.1,
                        "random_state": 42, "n_jobs": -1,
                    },
                    "early_stopping_rounds": 40,
                },
            ]
    else:
        # Sklearn fallback
        if n_days >= 100:
            return [
                {
                    "name": "gbr_huber",
                    "type": "gbr",
                    "params": {
                        "n_estimators": 1500, "max_depth": 5,
                        "learning_rate": 0.01, "subsample": 0.8,
                        "loss": "huber",
                        "min_samples_leaf": 5, "min_samples_split": 10,
                        "random_state": 42,
                    },
                    "early_stopping_rounds": None,
                },
                {
                    "name": "gbr_sqe",
                    "type": "gbr",
                    "params": {
                        "n_estimators": 2000, "max_depth": 4,
                        "learning_rate": 0.008, "subsample": 0.85,
                        "min_samples_leaf": 5, "min_samples_split": 10,
                        "random_state": 42,
                    },
                    "early_stopping_rounds": None,
                },
            ]
        else:
            return [
                {
                    "name": "rf_deep",
                    "type": "rf",
                    "params": {
                        "n_estimators": 500, "max_depth": 12,
                        "min_samples_leaf": 3, "random_state": 42,
                        "n_jobs": -1,
                    },
                    "early_stopping_rounds": None,
                },
                {
                    "name": "gbr_small",
                    "type": "gbr",
                    "params": {
                        "n_estimators": 500, "max_depth": 4,
                        "learning_rate": 0.05, "subsample": 0.9,
                        "loss": "huber",
                        "min_samples_leaf": 5, "random_state": 42,
                    },
                    "early_stopping_rounds": None,
                },
            ]


def _create_model(config: dict):
    """Instantiate a model from a configuration dict."""
    if config["type"] == "xgb":
        params = dict(config["params"])
        if config.get("early_stopping_rounds"):
            params["early_stopping_rounds"] = config["early_stopping_rounds"]
        return XGBRegressor(**params)
    elif config["type"] == "gbr":
        return GradientBoostingRegressor(**config["params"])
    else:
        return RandomForestRegressor(**config["params"])


def _compute_inbound_stats(daily_df: pd.DataFrame) -> dict:
    """
    Extract historical restocking behaviour from the training data.

    Returns a dict with:
        avg_batch_size          – mean inbound qty on restock days
        median_batch_size       – median inbound qty on restock days
        avg_restock_freq_days   – mean gap (days) between consecutive restocks
        avg_daily_outbound      – mean daily outbound across all days
        reorder_point_units     – stock level below which a restock is triggered
                                  (approximated as avg_daily_outbound × avg_freq)
    """
    restock_days = daily_df[daily_df["inbound_qty"] > 0].copy()

    avg_daily_outbound = float(daily_df["outbound_qty"].mean())

    if restock_days.empty:
        # No restocking history – use sensible defaults
        return {
            "avg_batch_size": round(avg_daily_outbound * 5, 0),
            "median_batch_size": round(avg_daily_outbound * 5, 0),
            "avg_restock_freq_days": 5.0,
            "avg_daily_outbound": round(avg_daily_outbound, 2),
            "reorder_point_units": round(avg_daily_outbound * 5, 0),
        }

    avg_batch = float(restock_days["inbound_qty"].mean())
    median_batch = float(restock_days["inbound_qty"].median())

    # Compute gaps between consecutive restock days
    restock_dates = pd.to_datetime(restock_days["date"]).sort_values()
    gaps = restock_dates.diff().dt.days.dropna()
    avg_freq = float(gaps.mean()) if len(gaps) > 0 else 5.0

    # Reorder point: roughly 1 restock-cycle worth of demand
    reorder_point = avg_daily_outbound * avg_freq

    return {
        "avg_batch_size": round(avg_batch, 0),
        "median_batch_size": round(median_batch, 0),
        "avg_restock_freq_days": round(avg_freq, 1),
        "avg_daily_outbound": round(avg_daily_outbound, 2),
        "reorder_point_units": round(reorder_point, 0),
    }


def train_model(product_id: int, business_id: int) -> dict:
    """
    Train (or re-train) a demand prediction model for a single product.

    Evaluates multiple model configurations via TimeSeriesSplit CV,
    picks the one with the lowest MAE, and retrains on the full dataset.

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
        X, y_outbound, y_inbound = build_feature_matrix(combined)
        n_samples = len(X)
        logger.info(
            f"Built feature matrix: {n_samples} samples, "
            f"{len(ALL_FEATURES)} features (from {n_days} raw days)"
        )

        # ── 3. Target transforms (log1p for skewed demand) ──────────
        y_out_log = np.log1p(y_outbound)
        y_in_log = np.log1p(y_inbound)

        # ── 4. Naive baseline (for comparison) ───────────────────────
        if "outbound_7d_avg" in X.columns:
            baseline_mae = mean_absolute_error(y_outbound, X["outbound_7d_avg"])
        else:
            baseline_mae = float(y_outbound.std())
        logger.info(f"Naive baseline MAE (7d avg): {baseline_mae:.3f}")

        # ── 5. Search across model configurations ────────────────────
        candidates = _get_candidates(n_days)
        n_splits = min(5, max(2, n_samples // 60))
        # Gap prevents lag-feature contamination between train/test folds
        cv_gap = min(7, n_samples // (n_splits * 4))
        tscv = TimeSeriesSplit(n_splits=n_splits, gap=cv_gap)

        best_overall_mae = float("inf")
        best_config_idx = 0
        all_results: list[dict] = []

        for ci, config in enumerate(candidates):
            logger.info(
                f"  Config {ci + 1}/{len(candidates)}: {config['name']}"
            )
            cv_maes: list[float] = []
            cv_mapes: list[float] = []
            best_iters: list[int] = []

            for fold_i, (train_idx, test_idx) in enumerate(tscv.split(X)):
                X_train = X.iloc[train_idx]
                X_test = X.iloc[test_idx]
                y_train_log = y_out_log.iloc[train_idx]
                y_test_actual = y_outbound.iloc[test_idx]

                model = _create_model(config)

                if config["type"] == "xgb" and config.get("early_stopping_rounds"):
                    y_test_log = y_out_log.iloc[test_idx]
                    model.fit(
                        X_train, y_train_log,
                        eval_set=[(X_test, y_test_log)],
                        verbose=False,
                    )
                    bi = getattr(model, "best_iteration", None)
                    best_iters.append(
                        bi if bi is not None else config["params"]["n_estimators"]
                    )
                else:
                    model.fit(X_train, y_train_log)

                # Predict in log space, convert back to original scale
                preds_log = model.predict(X_test)
                preds = np.maximum(np.expm1(preds_log), 0)

                mae = mean_absolute_error(y_test_actual, preds)
                cv_maes.append(mae)

                # Weighted MAPE (avoids zero-division blow-up)
                total_actual = y_test_actual.sum()
                if total_actual > 0:
                    mape = float(
                        np.sum(np.abs(y_test_actual - preds)) / total_actual * 100
                    )
                else:
                    mape = 0.0
                cv_mapes.append(mape)

            avg_mae = float(np.mean(cv_maes))
            avg_mape = float(np.mean(cv_mapes))
            logger.info(
                f"    → MAE={avg_mae:.3f}  MAPE={avg_mape:.1f}%  "
                f"(per-fold MAEs: {[round(m, 2) for m in cv_maes]})"
            )

            all_results.append({
                "name": config["name"],
                "avg_mae": avg_mae,
                "avg_mape": avg_mape,
                "cv_maes": cv_maes,
                "cv_mapes": cv_mapes,
                "best_iters": best_iters,
            })

            if avg_mae < best_overall_mae:
                best_overall_mae = avg_mae
                best_config_idx = ci

        best_config = candidates[best_config_idx]
        best_result = all_results[best_config_idx]
        avg_mae = best_result["avg_mae"]
        avg_mape = best_result["avg_mape"]

        logger.info(
            f"Best config: {best_config['name']} "
            f"(MAE={avg_mae:.3f}, MAPE={avg_mape:.1f}%)"
        )

        # ── 5. Retrain on full data with best config ─────────────────
        final_params = dict(best_config["params"])

        # Use averaged best iteration from CV (+10 % buffer) for XGBoost
        if best_result["best_iters"]:
            avg_iter = int(np.mean(best_result["best_iters"]) * 1.1)
            final_params["n_estimators"] = max(avg_iter, 100)

        # Remove early stopping for full retrain (no eval set)
        final_config = {
            "type": best_config["type"],
            "params": final_params,
            "early_stopping_rounds": None,
            "name": best_config["name"],
        }
        outbound_model = _create_model(final_config)
        inbound_model = _create_model(final_config)

        outbound_model.fit(X, y_out_log)
        inbound_model.fit(X, y_in_log)
        logger.info("Full retrain complete")

        # ── 6. Feature importance ────────────────────────────────────
        if hasattr(outbound_model, "feature_importances_"):
            importances = outbound_model.feature_importances_
            top_idx = np.argsort(importances)[::-1][:10]
            top_features = [
                (ALL_FEATURES[i], round(float(importances[i]), 4))
                for i in top_idx
            ]
            logger.info(f"Top-10 features: {top_features}")
        else:
            top_features = []

        # ── 7. Compute inbound restocking statistics ────────────────
        # Inbound (restocking) is a business decision driven by stock
        # levels, not a temporal demand pattern.  Instead of using the
        # ML inbound model (which predicts ~0 due to zero-inflated
        # targets), we extract historical restocking behaviour and
        # replay it as a reorder-point heuristic during prediction.
        inbound_stats = _compute_inbound_stats(combined)
        logger.info(
            f"Inbound stats: avg_batch={inbound_stats['avg_batch_size']:.0f}, "
            f"avg_freq={inbound_stats['avg_restock_freq_days']:.1f}d, "
            f"reorder_point={inbound_stats['reorder_point_units']:.0f}"
        )

        # ── 8. Persist model ─────────────────────────────────────────
        model_path = _get_model_path(product_id, business_id)
        artifact = {
            "model": outbound_model,
            "inbound_model": inbound_model,
            "features": ALL_FEATURES,
            "log_target": True,
            "data_start": combined["date"].min().date(),
            "data_end": combined["date"].max().date(),
            "n_days": n_days,
            "inbound_stats": inbound_stats,
        }
        joblib.dump(artifact, model_path)

        # ── 9. Save metadata to DB ───────────────────────────────────
        meta = save_model_metadata(
            product_id=product_id,
            business_id=business_id,
            model_path=str(model_path),
            data_start=combined["date"].min().date(),
            data_end=combined["date"].max().date(),
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
            "training_samples": n_samples,
            "data_start": str(combined["date"].min().date()),
            "data_end": str(combined["date"].max().date()),
            "model_type": type(outbound_model).__name__,
            "best_config": best_config["name"],
            "cv_mae": round(avg_mae, 2),
            "cv_mape": round(avg_mape, 2),
            "baseline_mae": round(baseline_mae, 2),
            "improvement_vs_baseline": round(
                (1 - avg_mae / baseline_mae) * 100, 1
            ) if baseline_mae > 0 else 0.0,
            "cv_splits": n_splits,
            "configs_evaluated": len(candidates),
            "top_features": top_features[:5] if top_features else [],
            "all_config_results": [
                {"name": r["name"], "mae": round(r["avg_mae"], 3)}
                for r in all_results
            ],
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
