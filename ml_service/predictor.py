"""
Prediction serving – loads a trained model and generates demand forecasts.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from db import (
    get_current_stock,
    get_daily_aggregated_transactions,
    get_uploaded_history,
    get_model_metadata,
)
from features import build_prediction_features
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

    model = artifact["model"]
    meta = get_model_metadata(product_id, business_id)

    # ── Gather recent actuals for lag features ───────────────────
    auto_df = get_daily_aggregated_transactions(product_id, business_id)
    uploaded_df = get_uploaded_history(product_id, business_id)

    last_outbound: list[float] = []
    last_inbound: list[float] = []

    # Prefer auto data (more recent), fall back to uploaded
    for source_df in [uploaded_df, auto_df]:
        if not source_df.empty:
            tail = source_df.tail(30)
            last_outbound = tail["outbound_qty"].tolist()
            last_inbound = tail["inbound_qty"].tolist()

    # ── Build future dates ───────────────────────────────────────
    today = date.today()
    future_dates = [today + timedelta(days=i + 1) for i in range(days_ahead)]

    X_future = build_prediction_features(
        future_dates,
        last_known_outbound=last_outbound or None,
        last_known_inbound=last_inbound or None,
    )

    # ── Predict ──────────────────────────────────────────────────
    raw_preds = model.predict(X_future)
    preds = np.maximum(raw_preds, 0).round(1)

    # ── Build projected stock curve ──────────────────────────────
    current_stock = get_current_stock(product_id, business_id)
    projected = float(current_stock)

    predictions = []
    stock_out_date = None
    days_until_stockout = None

    for i, (d, pred) in enumerate(zip(future_dates, preds)):
        projected = max(projected - float(pred), 0)
        holiday_name = get_all_holiday_name(d)

        predictions.append({
            "date": str(d),
            "predicted_outbound": float(pred),
            "projected_stock": round(projected, 1),
            "holiday_name": holiday_name,
        })

        if stock_out_date is None and projected <= 0:
            stock_out_date = str(d)
            days_until_stockout = i + 1

    total_pred = float(sum(preds))

    return {
        "product_id": product_id,
        "current_stock": current_stock,
        "predictions": predictions,
        "model_info": {
            "model_type": type(model).__name__,
            "trained_at": str(meta["trained_at"]) if meta else None,
            "data_points": meta["total_data_points"] if meta else None,
            "cv_mae": float(meta["cv_mae"]) if meta else None,
            "cv_mape": float(meta["cv_mape"]) if meta else None,
        },
        "summary": {
            "total_predicted_outbound": round(total_pred, 1),
            "avg_daily_outbound": round(total_pred / days_ahead, 1) if days_ahead else 0,
            "stock_out_date": stock_out_date,
            "days_until_stockout": days_until_stockout,
        },
    }
