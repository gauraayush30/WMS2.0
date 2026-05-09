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
    get_product_tenant_ids,
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
    # ── Resolve tenancy ───────────────────────────────────────────
    tenant = get_product_tenant_ids(product_id, business_id)
    customer_id = tenant["customer_id"]

    # ── Load model ───────────────────────────────────────────────
    artifact = load_model(product_id, business_id)
    if artifact is None:
        raise ValueError(
            "No trained model found for this product. "
            "Please train a model first."
        )

    outbound_model = artifact["model"]
    log_target = artifact.get("log_target", False)
    inbound_stats = artifact.get("inbound_stats")
    meta = get_model_metadata(product_id, business_id)

    # ── Gather recent actuals for lag features ───────────────────
    auto_df = get_daily_aggregated_transactions(
        product_id, business_id, customer_id=customer_id,
    )
    uploaded_df = get_uploaded_history(
        product_id, business_id, customer_id=customer_id,
    )

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

    # ── Iterative outbound prediction with dampened feedback ──────
    out_buffer = list(last_outbound)
    in_buffer = list(last_inbound)

    hist_mean_out = (
        float(np.mean(out_buffer[-30:])) if out_buffer else 0.0
    )

    preds_outbound: list[float] = []

    for i, d in enumerate(future_dates):
        X_day = build_prediction_features(
            target_date=d,
            outbound_history=out_buffer,
            inbound_history=in_buffer,
        )

        # ── Outbound prediction (ML model) ───────────────────────
        raw_out = outbound_model.predict(X_day)[0]
        if log_target:
            pred_out = max(round(float(np.expm1(raw_out)), 1), 0)
        else:
            pred_out = max(round(float(raw_out), 1), 0)
        preds_outbound.append(pred_out)

        # Dampened feedback into history buffer
        dampen = max(0.5, 1.0 - 0.5 * (i / max(days_ahead - 1, 1)))
        out_buffer.append(dampen * pred_out + (1 - dampen) * hist_mean_out)
        in_buffer.append(0.0)  # placeholder; inbound computed below

    # ── Inbound prediction via reorder-point heuristic ───────────
    # Restocking is a business decision driven by stock levels, not
    # a temporal demand pattern.  We replay historical restocking
    # behaviour: when projected stock drops below the reorder point
    # derived from training data, we insert a predicted restock.
    current_stock = get_current_stock(product_id, business_id)

    if inbound_stats:
        avg_batch = float(inbound_stats["avg_batch_size"])
        median_batch = float(inbound_stats.get("median_batch_size", avg_batch))
        avg_freq = float(inbound_stats["avg_restock_freq_days"])
        reorder_point = float(inbound_stats["reorder_point_units"])
        avg_daily_out = float(inbound_stats["avg_daily_outbound"])
    else:
        # Fallback: derive from recent history
        avg_daily_out = hist_mean_out if hist_mean_out > 0 else 50.0
        avg_freq = 4.0
        avg_batch = avg_daily_out * avg_freq * 1.5
        median_batch = avg_batch
        reorder_point = avg_daily_out * avg_freq

    preds_inbound: list[float] = []
    projected = float(current_stock)
    days_since_restock = 0

    for i, pred_out in enumerate(preds_outbound):
        projected -= float(pred_out)
        days_since_restock += 1

        # Trigger a restock when stock drops below the reorder point
        # OR when enough days have passed since last restock (regular
        # delivery schedule), whichever comes first.
        # Skip Sundays (weekday 6) to match the generator pattern.
        d = future_dates[i]
        need_restock = (
            projected < reorder_point
            or days_since_restock >= avg_freq + 1
        )
        is_sunday = d.weekday() == 6

        if need_restock and not is_sunday and projected < avg_batch * 2:
            # Order enough to bring stock up to ~2× reorder point
            shortfall = max(0, (reorder_point * 2.5) - projected)
            batch = max(avg_batch * 0.85, min(shortfall, avg_batch * 1.15))
            pred_in = round(batch, 0)
            projected += pred_in
            days_since_restock = 0
        else:
            pred_in = 0.0

        preds_inbound.append(pred_in)

    # ── Build projected stock curves ─────────────────────────────
    # Two projections:
    #   1. With restocking (realistic view)
    #   2. Without restocking (for stockout risk assessment)
    projected_with_restock = float(current_stock)
    projected_no_restock = float(current_stock)

    predictions = []
    stock_out_date = None
    days_until_stockout = None

    for i, (d, pred_out, pred_in) in enumerate(
        zip(future_dates, preds_outbound, preds_inbound)
    ):
        projected_with_restock = max(
            projected_with_restock - float(pred_out) + float(pred_in), 0
        )
        projected_no_restock = max(projected_no_restock - float(pred_out), 0)
        holiday_name = get_all_holiday_name(d)

        predictions.append({
            "date": str(d),
            "predicted_outbound": float(pred_out),
            "predicted_inbound": float(pred_in),
            "projected_stock": round(projected_with_restock, 1),
            "projected_stock_no_restock": round(projected_no_restock, 1),
            "holiday_name": holiday_name,
        })

        # Stockout date based on no-restock projection (risk indicator)
        if stock_out_date is None and projected_no_restock <= 0:
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
