"""
Replenishment recommendation derived from a forecast.

Replaces the legacy "predicted inbound" output, which was attempting to
model a business decision (when to restock) as a temporal regression.

Reorder math (textbook continuous-review (s, S) approximation):

    safety_stock          = z * σ_d * sqrt(L)
    reorder_point         = μ_d * L + safety_stock
    recommended_order_qty = max(target_stock - current_stock, min_order_qty)

Where:
    μ_d  – mean daily outbound (forecast P50 average)
    σ_d  – standard deviation of daily outbound (recent rolling std)
    L    – lead_time_days
    z    – service-level Z (1.65 ≈ 95% service level)

The customer can override `safety_stock`, `reorder_point`, `max_stock_level`,
`lead_time_days`, `par_level` per product; we only fill in defaults when
they're zero.
"""

from __future__ import annotations

from datetime import date, timedelta
import math


SERVICE_LEVEL_Z = 1.65  # 95% service level


def compute_replenishment(
    *,
    product: dict,
    forecast_horizon_30: list[float],   # 30 daily P50 predictions
    rolling_std_28: float,              # σ from recent history
    current_stock: int,
) -> dict:
    """Compute reorder recommendation.

    Inputs:
      product:
        lead_time_days (int), safety_stock (int), reorder_point (int),
        max_stock_level (int), par_level (int)
      forecast_horizon_30: list of 30 P50 daily-outbound values
      rolling_std_28: σ of the last 28 days
      current_stock: stock_at_warehouse today

    Output dict has reorder_point, recommended_order_qty, recommended_reorder_date,
    safety_stock, total_forecast_30, days_of_cover, service_level.
    """
    lead = max(int(product.get("lead_time_days") or 0), 1)
    forecast = [max(0.0, float(v)) for v in forecast_horizon_30]

    avg_daily = (sum(forecast) / len(forecast)) if forecast else 0.0

    # Safety stock — honour explicit value if non-zero, else compute
    explicit_safety = int(product.get("safety_stock") or 0)
    derived_safety = SERVICE_LEVEL_Z * float(rolling_std_28) * math.sqrt(lead)
    safety_stock = float(explicit_safety) if explicit_safety > 0 else derived_safety

    # Reorder point
    explicit_rp = int(product.get("reorder_point") or 0)
    derived_rp = avg_daily * lead + safety_stock
    reorder_point = float(explicit_rp) if explicit_rp > 0 else derived_rp

    # Recommended order qty (one PAR/cycle of stock)
    target = int(product.get("max_stock_level") or 0)
    par = int(product.get("par_level") or 0)
    if target <= 0:
        # Default: cover one lead-time + 30d demand from above forecast.
        target = int(round(sum(forecast) + safety_stock))
    if par > 0 and target < par:
        target = par
    recommended_qty = max(int(round(target - current_stock)), 0)

    # Recommended reorder date — the day that projected stock crosses below RP
    # Walking forward day by day and applying the forecast.
    today = date.today()
    projected = float(current_stock)
    reorder_date: date | None = None
    for i, daily_demand in enumerate(forecast):
        projected -= daily_demand
        if projected <= reorder_point and reorder_date is None:
            reorder_date = today + timedelta(days=i)

    days_of_cover = int(projected / avg_daily) if avg_daily > 0 else None

    return {
        "current_stock": int(current_stock),
        "lead_time_days": lead,
        "avg_daily_forecast": round(avg_daily, 2),
        "rolling_std_28d": round(float(rolling_std_28), 2),
        "safety_stock": round(safety_stock, 2),
        "reorder_point": round(reorder_point, 2),
        "max_stock_level": target,
        "recommended_order_qty": int(recommended_qty),
        "recommended_reorder_date": str(reorder_date) if reorder_date else None,
        "days_of_cover": days_of_cover,
        "total_forecast_30d": round(sum(forecast), 2),
        "service_level": "95%",
    }
