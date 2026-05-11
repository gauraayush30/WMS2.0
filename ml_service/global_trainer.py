"""
Global per-(customer, warehouse) demand model.

Trains ONE model that predicts daily outbound for every (product, buyer)
in the customer-warehouse, with product_id and buyer_id as categorical
features. Three quantile heads (P10 / P50 / P90) are trained on the same
feature matrix.

Inference is performed at cache-refresh time, not on user request — the
portfolio API reads from ml_forecast_cache.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from config import MODEL_STORAGE_PATH
from db import (
    get_buyer_product_series,
    save_global_model_metadata,
    update_global_model_status,
)
from global_features import (
    ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES,
    build_panel_dataframe, add_panel_features, to_model_frame,
)

logger = logging.getLogger(__name__)

try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    from sklearn.ensemble import GradientBoostingRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


MIN_PANEL_DAYS = 30
MIN_PAIRS = 3


def _global_model_path(business_id: int, customer_id: int, warehouse_id: int) -> Path:
    return MODEL_STORAGE_PATH / (
        f"global_customer_{customer_id}_warehouse_{warehouse_id}_biz_{business_id}.joblib"
    )


def _fit_quantile(X: pd.DataFrame, y: pd.Series, quantile: float, n_estimators: int = 400):
    """Fit a single quantile regressor. Prefers XGBoost native quantile loss."""
    if HAS_XGBOOST:
        try:
            m = XGBRegressor(
                objective="reg:quantileerror",
                quantile_alpha=quantile,
                n_estimators=n_estimators,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.85,
                colsample_bytree=0.85,
                tree_method="hist",
                enable_categorical=True,
                random_state=42,
                n_jobs=-1,
            )
            m.fit(X, y)
            return m, "xgb_quantile"
        except Exception as exc:
            logger.warning(f"XGBoost quantile failed ({exc}); falling back to GBR")

    if HAS_SKLEARN:
        # GBR doesn't support categoricals → one-hot small cardinality, else label encode
        Xn = _encode_categoricals_numeric(X)
        m = GradientBoostingRegressor(
            loss="quantile",
            alpha=quantile,
            n_estimators=min(n_estimators, 300),
            max_depth=5,
            learning_rate=0.05,
            subsample=0.85,
            random_state=42,
        )
        m.fit(Xn, y)
        return m, "gbr_quantile"

    raise RuntimeError("Neither XGBoost nor sklearn GBR is available")


def _encode_categoricals_numeric(X: pd.DataFrame) -> pd.DataFrame:
    """For models without native categorical support, label-encode."""
    out = X.copy()
    for c in CATEGORICAL_FEATURES:
        if c in out.columns:
            if isinstance(out[c].dtype, pd.CategoricalDtype):
                out[c] = out[c].cat.codes.astype(int)
            else:
                out[c] = pd.Categorical(out[c]).codes.astype(int)
    return out


def _compute_wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = float(np.sum(np.abs(y_true)))
    if denom <= 0:
        return 0.0
    return float(np.sum(np.abs(y_true - y_pred)) / denom * 100)


def train_global_model(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
    progress_callback=None,
) -> dict:
    """Train the global model for one (customer, warehouse)."""
    def _p(phase: str, detail: str = "", done: int = 0, total: int = 0) -> None:
        if progress_callback:
            try:
                progress_callback(phase, done, total, detail)
            except Exception:
                pass

    update_global_model_status(business_id, customer_id, warehouse_id, "training")

    try:
        _p("loading_data")
        buyer_df = get_buyer_product_series(
            business_id=business_id,
            customer_id=customer_id,
            warehouse_id=warehouse_id,
        )
        if buyer_df.empty:
            raise ValueError("No buyer-product outbound history for this scope")

        n_pairs = len(buyer_df.groupby(["buyer_id", "product_id"]))
        if n_pairs < MIN_PAIRS:
            raise ValueError(
                f"Need at least {MIN_PAIRS} buyer-product pairs to train; have {n_pairs}"
            )

        _p("building_panel", detail=f"{n_pairs} buyer-product pairs")
        panel = build_panel_dataframe(buyer_df)
        if len(panel) < MIN_PANEL_DAYS * MIN_PAIRS:
            raise ValueError("Panel data too small to train a useful model")

        _p("building_features", detail=f"{len(panel)} rows")
        feat_df = add_panel_features(panel)

        # Drop rows where lag features are still null (first ~30 days per pair)
        warm = 14
        feat_df = feat_df.groupby(["product_id", "buyer_id"], group_keys=False).apply(
            lambda g: g.iloc[warm:] if len(g) > warm * 2 else g
        )
        if feat_df.empty:
            raise ValueError("Not enough history per (product, buyer) after warmup")

        # Hold out the last 14 days for evaluation
        cutoff = feat_df["date"].max() - pd.Timedelta(days=14)
        train_df = feat_df[feat_df["date"] <= cutoff].copy()
        test_df = feat_df[feat_df["date"] > cutoff].copy()
        if len(train_df) < 200:
            train_df = feat_df.copy()
            test_df = feat_df.tail(min(200, len(feat_df) // 5)).copy()

        X_train = to_model_frame(train_df)
        y_train = train_df["outbound_qty"].astype(float)
        X_test = to_model_frame(test_df) if not test_df.empty else None
        y_test = test_df["outbound_qty"].astype(float) if not test_df.empty else None

        # Align categories between train/test so XGB doesn't see unseen categories
        if X_test is not None:
            for c in CATEGORICAL_FEATURES:
                if c in X_test.columns:
                    X_test[c] = X_test[c].astype(
                        pd.CategoricalDtype(categories=X_train[c].cat.categories)
                    )

        _p("fitting_p50")
        m_p50, fit_kind = _fit_quantile(X_train, y_train, 0.5)
        _p("fitting_p10")
        m_p10, _ = _fit_quantile(X_train, y_train, 0.1)
        _p("fitting_p90")
        m_p90, _ = _fit_quantile(X_train, y_train, 0.9)

        # Metrics on held-out
        mae = wape = 0.0
        if X_test is not None and not X_test.empty:
            _p("evaluating")
            X_eval = X_test if fit_kind == "xgb_quantile" else _encode_categoricals_numeric(X_test)
            preds = np.maximum(m_p50.predict(X_eval), 0)
            mae = float(np.mean(np.abs(y_test.values - preds)))
            wape = _compute_wape(y_test.values, preds)

        # Persist
        _p("saving")
        model_path = _global_model_path(business_id, customer_id, warehouse_id)
        artifact = {
            "p10": m_p10, "p50": m_p50, "p90": m_p90,
            "fit_kind": fit_kind,
            "categories": {
                "product_id": list(X_train["product_id_cat"].cat.categories),
                "buyer_id":   list(X_train["buyer_id_cat"].cat.categories),
            },
            "features": ALL_FEATURES,
            "data_start": feat_df["date"].min().date(),
            "data_end":   feat_df["date"].max().date(),
            "n_rows": int(len(feat_df)),
            "n_pairs": int(n_pairs),
        }
        joblib.dump(artifact, model_path)

        meta = save_global_model_metadata(
            business_id=business_id, customer_id=customer_id, warehouse_id=warehouse_id,
            model_path=str(model_path),
            data_start=feat_df["date"].min().date(),
            data_end=feat_df["date"].max().date(),
            total_points=int(len(feat_df)),
            n_products=int(feat_df["product_id"].nunique()),
            n_buyers=int(feat_df["buyer_id"].nunique()),
            n_sellers=0,
            cv_mae=mae, cv_mape=wape,
            features_used=ALL_FEATURES,
        )

        return {
            "status": "ready",
            "business_id": business_id,
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "data_start": str(feat_df["date"].min().date()),
            "data_end":   str(feat_df["date"].max().date()),
            "n_rows": int(len(feat_df)),
            "n_pairs": int(n_pairs),
            "n_products": int(feat_df["product_id"].nunique()),
            "n_buyers":   int(feat_df["buyer_id"].nunique()),
            "fit_kind": fit_kind,
            "cv_mae": round(mae, 3),
            "cv_wape": round(wape, 2),
        }

    except ValueError:
        update_global_model_status(business_id, customer_id, warehouse_id, "failed")
        raise
    except Exception as exc:
        logger.exception("Global model training failed")
        update_global_model_status(business_id, customer_id, warehouse_id, "failed")
        raise ValueError(f"Training failed: {exc}")


def load_global_model(business_id: int, customer_id: int, warehouse_id: int) -> dict | None:
    p = _global_model_path(business_id, customer_id, warehouse_id)
    if not p.exists():
        return None
    return joblib.load(p)


def delete_global_model(business_id: int, customer_id: int, warehouse_id: int) -> bool:
    p = _global_model_path(business_id, customer_id, warehouse_id)
    if p.exists():
        p.unlink()
        return True
    return False
