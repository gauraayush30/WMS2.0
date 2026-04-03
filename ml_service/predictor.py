"""
Prediction serving – loads a trained model and generates demand forecasts.

Uses iterative (step-by-step) prediction: each day's prediction feeds into
the next day's lag features for more accurate multi-step forecasting.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from db import (
    get_current_stock,
    get_daily_aggregated_transactions,
    get_uploaded_history,
    get_model_metadata,
)
from features import build_prediction_features, ALL_FEATURES
from indian_calendar import get_all_holiday_name
from trainer import load_model


def predict_demand(
    product_id: int,
    business_id: int,
    days_ahead: int = 30,
) -> dict:
    """
    Generate a demand forecast for ``days_ahead`` days into the future.

    Returns:
        {
          "product_id": int,
          "current_stock": int,
          "predictions": [
              {
                  "date": "YYYY-MM-DD",
                  "predicted_outbound": float,
                  "projected_stock": float,
                  "holiday_name": str | None,
              }, ...
          ],
          "model_info": { ... },
          "summary": {
              "total_predicted_outbound": float,
              "avg_daily_outbound": float,
              "stock_out_date": str | None,
              "days_until_stockout": int | None,
          }
        }

    Raises ValueError if no trained model exists.
    """
    # ── Load model ───────────────────────────────────────────────
    artifact = load_model(product_id, business_id)
    if artifact is None:
        raise ValueError(
            "No trained model found for this product. "
            "Please train a model first."
        )

    outbound_model = artifact["model"]
    inbound_model = artifact.get("inbound_model")
    log_target = artifact.get("log_target", False)
    meta = get_model_metadata(product_id, business_id)

    # ── Gather recent actuals for lag features ───────────────────
    auto_df = get_daily_aggregated_transactions(product_id, business_id)
    uploaded_df = get_uploaded_history(product_id, business_id)

    # Merge both sources (same logic as training) so uploaded history
    # is not silently discarded when auto data exists.
    frames = []
    if not uploaded_df.empty:
        frames.append(uploaded_df[["date", "inbound_qty", "outbound_qty"]].copy())
    if not auto_df.empty:
        frames.append(auto_df[["date", "inbound_qty", "outbound_qty"]].copy())

    last_outbound: list[float] = []
    last_inbound: list[float] = []
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values("date").drop_duplicates(
            subset=["date"], keep="last"
        )
        tail = combined.tail(60)  # keep 60 days for richer lag features
        last_outbound = tail["outbound_qty"].tolist()
        last_inbound = tail["inbound_qty"].tolist()

    # ── Build future dates ───────────────────────────────────────
    today = date.today()
    future_dates = [today + timedelta(days=i + 1) for i in range(days_ahead)]

    # ── Batch prediction (stable — no feedback loop) ─────────────
    # Predict all future days at once using actual history for lag
    # features.  Avoids the iterative death-spiral where small
    # under-predictions compound via lag features until demand → 0.
    X_all = build_prediction_features(
        future_dates,
        last_known_outbound=last_outbound or None,
        last_known_inbound=last_inbound or None,
    )

    raw_outbound = outbound_model.predict(X_all)
    if log_target:
        preds_outbound = [
            max(round(float(np.expm1(r)), 1), 0) for r in raw_outbound
        ]
    else:
        preds_outbound = [max(round(float(r), 1), 0) for r in raw_outbound]

    if inbound_model is not None:
        raw_inbound = inbound_model.predict(X_all)
        if log_target:
            preds_inbound = [
                max(round(float(np.expm1(r)), 1), 0) for r in raw_inbound
            ]
        else:
            preds_inbound = [max(round(float(r), 1), 0) for r in raw_inbound]
    else:
        avg_in = float(np.mean(last_inbound)) if last_inbound else 0.0
        preds_inbound = [round(avg_in, 1)] * days_ahead

    # ── Build projected stock curve ──────────────────────────────
    # Stock projection only subtracts predicted outbound (demand).
    # Inbound (restocking) is a business decision, not demand — including
    # it would always show "you'll never run out" which defeats the purpose.
    current_stock = get_current_stock(product_id, business_id)
    projected = float(current_stock)

    predictions = []
    stock_out_date = None
    days_until_stockout = None

    for i, (d, pred_out, pred_in) in enumerate(
        zip(future_dates, preds_outbound, preds_inbound)
    ):
        projected = max(projected - float(pred_out), 0)
        holiday_name = get_all_holiday_name(d)

        predictions.append({
            "date": str(d),
            "predicted_outbound": float(pred_out),
            "predicted_inbound": float(pred_in),
            "projected_stock": round(projected, 1),
            "holiday_name": holiday_name,
        })

        if stock_out_date is None and projected <= 0:
            stock_out_date = str(d)
            days_until_stockout = i + 1

    total_pred_out = float(sum(preds_outbound))
    total_pred_in = float(sum(preds_inbound))

    return {
        "product_id": product_id,
        "current_stock": current_stock,
        "days_ahead": days_ahead,
        "stockout_date": stock_out_date,
        "predictions": predictions,
        "model_info": {
            "model_type": type(outbound_model).__name__,
            "trained_at": str(meta["trained_at"]) if meta else None,
            "data_points": meta["total_data_points"] if meta else None,
            "cv_mae": float(meta["cv_mae"]) if meta else None,
            "cv_mape": float(meta["cv_mape"]) if meta else None,
        },
        "summary": {
            "total_predicted_outbound": round(total_pred_out, 1),
            "total_predicted_inbound": round(total_pred_in, 1),
            "avg_daily_outbound": round(total_pred_out / days_ahead, 1) if days_ahead else 0,
            "avg_daily_inbound": round(total_pred_in / days_ahead, 1) if days_ahead else 0,
            "stock_out_date": stock_out_date,
            "days_until_stockout": days_until_stockout,
        },
    }
