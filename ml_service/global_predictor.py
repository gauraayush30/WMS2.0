"""
Multi-day quantile rollout for the global per-customer-warehouse model.

Inference is iterative: each day's P50 prediction is appended to the
(product, buyer) history buffer so the next day's lag/rolling features
remain coherent. P10/P90 are computed alongside but don't feed back into
the recursion (we use P50 as the "expected" trajectory).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from db import get_buyer_product_series
from global_features import (
    ALL_FEATURES, CATEGORICAL_FEATURES,
    build_panel_dataframe, add_panel_features, to_model_frame,
)
from global_trainer import load_global_model, _encode_categoricals_numeric

logger = logging.getLogger(__name__)


def _align_categories(X: pd.DataFrame, categories: dict) -> pd.DataFrame:
    X = X.copy()
    X["product_id_cat"] = X["product_id_cat"].astype(
        pd.CategoricalDtype(categories=categories["product_id"])
    )
    X["buyer_id_cat"] = X["buyer_id_cat"].astype(
        pd.CategoricalDtype(categories=categories["buyer_id"])
    )
    return X


def _predict_one(model_artifact: dict, X: pd.DataFrame) -> dict:
    """Return {'p10','p50','p90'} np.ndarrays for one feature batch."""
    X_aligned = _align_categories(X, model_artifact["categories"])
    if model_artifact["fit_kind"] != "xgb_quantile":
        X_aligned = _encode_categoricals_numeric(X_aligned)
    return {
        "p10": np.maximum(model_artifact["p10"].predict(X_aligned), 0),
        "p50": np.maximum(model_artifact["p50"].predict(X_aligned), 0),
        "p90": np.maximum(model_artifact["p90"].predict(X_aligned), 0),
    }


def predict_global(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
    days_ahead: int = 30,
    product_ids: list[int] | None = None,
    buyer_ids: list[int] | None = None,
    include_aggregate: bool = True,
) -> pd.DataFrame:
    """Roll out predictions for the next N days.

    Returns a DataFrame: product_id, buyer_id (NaN for aggregate), date, p10/p50/p90.
    """
    art = load_global_model(business_id, customer_id, warehouse_id)
    if not art:
        raise ValueError("No global model trained for this customer-warehouse")

    history = get_buyer_product_series(
        business_id=business_id, customer_id=customer_id, warehouse_id=warehouse_id,
    )
    if history.empty:
        return pd.DataFrame(columns=["product_id", "buyer_id", "date", "p10", "p50", "p90"])

    panel = build_panel_dataframe(history)

    if product_ids:
        panel = panel[panel["product_id"].isin(product_ids)]
    if buyer_ids:
        panel = panel[panel["buyer_id"].isin(buyer_ids)]
    if panel.empty:
        return pd.DataFrame(columns=["product_id", "buyer_id", "date", "p10", "p50", "p90"])

    last_date = panel["date"].max()
    rollout_rows: list[dict] = []

    # working buffer keeps appending predicted rows so lag features remain valid
    work = panel.copy()

    for step in range(1, days_ahead + 1):
        target_date = last_date + pd.Timedelta(days=step)

        # one row per (buyer, product) at target_date with zero outbound (placeholder
        # so the feature builder treats it like a real day)
        seed = (
            work.groupby(["product_id", "buyer_id"])
                .head(1)[["product_id", "buyer_id"]]
                .drop_duplicates()
                .reset_index(drop=True)
        )
        seed["date"] = target_date
        seed["outbound_qty"] = 0

        combined = pd.concat([work, seed], ignore_index=True).sort_values(
            ["product_id", "buyer_id", "date"]
        ).reset_index(drop=True)

        feats = add_panel_features(combined)
        today_feats = feats[feats["date"] == target_date].copy()
        if today_feats.empty:
            continue
        X = to_model_frame(today_feats)
        preds = _predict_one(art, X)

        today_feats["p10"] = preds["p10"]
        today_feats["p50"] = preds["p50"]
        today_feats["p90"] = preds["p90"]

        rollout_rows.append(today_feats[[
            "product_id", "buyer_id", "date", "p10", "p50", "p90"
        ]].copy())

        # Append predicted p50 to work buffer for next step's lags
        next_work = seed.copy()
        next_work["outbound_qty"] = preds["p50"].round().astype(int)
        work = pd.concat([work, next_work], ignore_index=True)

    if not rollout_rows:
        return pd.DataFrame(columns=["product_id", "buyer_id", "date", "p10", "p50", "p90"])

    result = pd.concat(rollout_rows, ignore_index=True)

    if include_aggregate:
        # Per-product aggregate (sum across buyers) — captures total demand
        agg = result.groupby(["product_id", "date"], as_index=False)[["p10", "p50", "p90"]].sum()
        agg["buyer_id"] = np.nan
        result = pd.concat([result, agg], ignore_index=True)

    result["date"] = pd.to_datetime(result["date"]).dt.date
    return result
