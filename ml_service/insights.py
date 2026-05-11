"""
Portfolio insight engine.

Generates ranked, actionable alerts by combining:
  - current stock levels        (products.stock_at_warehouse)
  - cached forecast P50/P90     (ml_forecast_cache)
  - seller concentration        (Herfindahl on recent inbound)
  - buyer concentration         (Herfindahl on recent outbound)
  - model staleness             (ml_global_model_metadata.trained_at)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text

from db import (
    engine,
    get_portfolio_product_list,
    get_seller_product_series,
    get_buyer_product_series,
    get_forecast_cache,
    get_global_model_metadata,
)

STOCKOUT_HORIZON_DAYS = 14
CONCENTRATION_THRESHOLD = 0.65
SLOW_MOVER_WEEKS = 8
SLOW_MOVER_UNITS_PER_WEEK = 1.0
MODEL_STALE_DAYS = 30


def _herfindahl_shares(qty_by_entity: dict[int, float]) -> tuple[float, int | None, float]:
    """Returns (HHI, top_entity_id, top_share_pct)."""
    total = sum(qty_by_entity.values())
    if total <= 0 or not qty_by_entity:
        return 0.0, None, 0.0
    shares = {k: v / total for k, v in qty_by_entity.items()}
    top_id, top_share = max(shares.items(), key=lambda kv: kv[1])
    hhi = sum(s * s for s in shares.values())
    return hhi, top_id, top_share


def compute_portfolio_insights(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
) -> list[dict]:
    out: list[dict] = []

    products = get_portfolio_product_list(business_id, customer_id, warehouse_id)
    if not products:
        return []

    today = date.today()
    horizon_end = today + timedelta(days=STOCKOUT_HORIZON_DAYS * 3)

    cache = get_forecast_cache(
        business_id, customer_id, warehouse_id,
        aggregate_only=True,
        start_date=today,
        end_date=horizon_end,
    )

    # ── 1. Stockout risk per product ──────────────────────────────────────
    for p in products:
        stock = int(p.get("stock_at_warehouse") or 0)
        if stock <= 0:
            continue
        pid = int(p["id"])
        pforecast = cache[cache["product_id"] == pid].sort_values("forecast_date") if not cache.empty else pd.DataFrame()
        if pforecast.empty:
            continue
        cum = pforecast["p50"].cumsum()
        cover_days = None
        for d, c in zip(pforecast["forecast_date"], cum):
            if c >= stock:
                cover_days = (pd.Timestamp(d).date() - today).days + 1
                break
        if cover_days is None:
            continue
        if cover_days <= STOCKOUT_HORIZON_DAYS:
            avg_daily = float(pforecast["p50"].head(7).mean()) if len(pforecast) else 0
            out.append({
                "type": "STOCKOUT_RISK",
                "severity": "critical",
                "product_id": pid,
                "message": (
                    f"{p['name']} will run out in ~{cover_days} day(s) "
                    f"(est. {(today + timedelta(days=cover_days)).isoformat()})"
                ),
                "value": float(cover_days),
                "threshold": float(STOCKOUT_HORIZON_DAYS),
                "meta": {
                    "current_stock": stock,
                    "avg_daily_outbound": round(avg_daily, 2),
                    "product_name": p["name"],
                    "sku_code": p.get("sku_code"),
                },
            })

    # ── 2. Seller concentration per product (last 90d) ────────────────────
    seller_series = get_seller_product_series(business_id, customer_id, warehouse_id=warehouse_id)
    if not seller_series.empty:
        recent = seller_series[seller_series["date"] >= pd.Timestamp(today - timedelta(days=90))]
        for pid, grp in recent.groupby("product_id"):
            qty_by_seller = grp.groupby("seller_id")["inbound_qty"].sum().to_dict()
            hhi, top_id, top_share = _herfindahl_shares(
                {int(k): float(v) for k, v in qty_by_seller.items()}
            )
            if top_share >= CONCENTRATION_THRESHOLD and top_id is not None:
                pname = next((p["name"] for p in products if p["id"] == pid), str(pid))
                out.append({
                    "type": "SELLER_CONCENTRATION",
                    "severity": "warning",
                    "product_id": int(pid),
                    "entity_type": "seller",
                    "entity_id": int(top_id),
                    "message": (
                        f"{round(top_share * 100, 1)}% of {pname} inbound "
                        f"comes from a single supplier"
                    ),
                    "value": round(top_share * 100, 2),
                    "threshold": CONCENTRATION_THRESHOLD * 100,
                    "meta": {"hhi": round(hhi, 3), "product_name": pname},
                })

    # ── 3. Buyer concentration per product (last 90d) ─────────────────────
    buyer_series = get_buyer_product_series(business_id, customer_id, warehouse_id=warehouse_id)
    if not buyer_series.empty:
        recent = buyer_series[buyer_series["date"] >= pd.Timestamp(today - timedelta(days=90))]
        for pid, grp in recent.groupby("product_id"):
            qty_by_buyer = grp.groupby("buyer_id")["outbound_qty"].sum().to_dict()
            hhi, top_id, top_share = _herfindahl_shares(
                {int(k): float(v) for k, v in qty_by_buyer.items()}
            )
            if top_share >= CONCENTRATION_THRESHOLD and top_id is not None:
                pname = next((p["name"] for p in products if p["id"] == pid), str(pid))
                out.append({
                    "type": "BUYER_CONCENTRATION",
                    "severity": "warning",
                    "product_id": int(pid),
                    "entity_type": "buyer",
                    "entity_id": int(top_id),
                    "message": (
                        f"{round(top_share * 100, 1)}% of {pname} outbound "
                        f"goes to a single buyer"
                    ),
                    "value": round(top_share * 100, 2),
                    "threshold": CONCENTRATION_THRESHOLD * 100,
                    "meta": {"hhi": round(hhi, 3), "product_name": pname},
                })

        # ── 4. Slow movers ───────────────────────────────────────────────
        last_window = recent[recent["date"] >= pd.Timestamp(today - timedelta(days=SLOW_MOVER_WEEKS * 7))]
        if not last_window.empty:
            per_product = last_window.groupby("product_id")["outbound_qty"].sum()
            threshold = SLOW_MOVER_UNITS_PER_WEEK * SLOW_MOVER_WEEKS
            for pid, total in per_product.items():
                if total < threshold:
                    pname = next((p["name"] for p in products if p["id"] == pid), str(pid))
                    out.append({
                        "type": "SLOW_MOVER",
                        "severity": "info",
                        "product_id": int(pid),
                        "message": (
                            f"{pname}: only {int(total)} units sold in {SLOW_MOVER_WEEKS} weeks"
                        ),
                        "value": float(total),
                        "threshold": float(threshold),
                        "meta": {"product_name": pname},
                    })

    # ── 5. Model staleness ────────────────────────────────────────────────
    meta = get_global_model_metadata(business_id, customer_id, warehouse_id)
    if meta and meta.get("trained_at"):
        trained_at = meta["trained_at"]
        if isinstance(trained_at, datetime):
            age = datetime.now(timezone.utc) - (
                trained_at if trained_at.tzinfo else trained_at.replace(tzinfo=timezone.utc)
            )
            age_days = age.days
            if age_days >= MODEL_STALE_DAYS:
                out.append({
                    "type": "MODEL_STALE",
                    "severity": "info",
                    "product_id": None,
                    "message": f"Global model not retrained in {age_days} days",
                    "value": float(age_days),
                    "threshold": float(MODEL_STALE_DAYS),
                    "meta": {},
                })

    # Order: critical first, then warning, then info, then by value desc
    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda x: (sev_rank.get(x.get("severity", "info"), 3), -(x.get("value") or 0)))
    return out
