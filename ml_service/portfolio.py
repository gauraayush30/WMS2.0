"""
Portfolio summary aggregator.

Reads from the forecast cache + transactional DB to assemble the dashboard
payload the frontend renders. Never invokes live inference.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from db import (
    get_portfolio_product_list,
    get_all_sellers, get_all_buyers,
    get_seller_product_series, get_buyer_product_series,
    get_forecast_cache,
    get_global_model_metadata,
    get_insights,
)
from seller_analytics import compute_seller_metrics


def _safe_float(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    return float(x)


def _date_window(days: int) -> tuple[date, date]:
    today = date.today()
    return (today - timedelta(days=days), today)


def get_portfolio_summary(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
    period_days: int = 90,
) -> dict:
    start, end = _date_window(period_days)
    products = get_portfolio_product_list(business_id, customer_id, warehouse_id)
    sellers = get_all_sellers(business_id, customer_id)
    buyers = get_all_buyers(business_id, customer_id)

    # Pull forecasts for the whole scope (aggregate / no buyer_id rows).
    today = date.today()
    fc = get_forecast_cache(
        business_id, customer_id, warehouse_id,
        aggregate_only=True,
        start_date=today,
        end_date=today + timedelta(days=30),
    )

    seller_series = get_seller_product_series(
        business_id, customer_id, warehouse_id=warehouse_id,
        start_date=start, end_date=end,
    )
    buyer_series = get_buyer_product_series(
        business_id, customer_id, warehouse_id=warehouse_id,
        start_date=start, end_date=end,
    )

    # ── Per-product summary ───────────────────────────────────────────────
    product_rows = []
    products_with_model = 0
    stockout_count = 0
    total_outbound = 0
    total_inbound = 0

    seller_top_for_product = {}
    if not seller_series.empty:
        for pid, grp in seller_series.groupby("product_id"):
            top = grp.groupby("seller_id")["inbound_qty"].sum().idxmax()
            seller_top_for_product[int(pid)] = int(top)

    buyer_top_for_product = {}
    if not buyer_series.empty:
        for pid, grp in buyer_series.groupby("product_id"):
            top = grp.groupby("buyer_id")["outbound_qty"].sum().idxmax()
            buyer_top_for_product[int(pid)] = int(top)

    seller_name_by_id = {s["id"]: s["name"] for s in sellers}
    buyer_name_by_id = {b["id"]: b["name"] for b in buyers}

    for p in products:
        pid = int(p["id"])
        has_model = p.get("model_status") == "ready"
        if has_model:
            products_with_model += 1
        pfc = fc[fc["product_id"] == pid].sort_values("forecast_date") if not fc.empty else pd.DataFrame()
        forecast_7d = float(pfc["p50"].head(7).sum()) if not pfc.empty else 0.0
        forecast_30d = float(pfc["p50"].head(30).sum()) if not pfc.empty else 0.0
        stock = int(p.get("stock_at_warehouse") or 0)
        stockout_date = None
        days_of_supply = None
        if not pfc.empty and stock > 0:
            cum = pfc["p50"].cumsum()
            for d, c in zip(pfc["forecast_date"], cum):
                if c >= stock:
                    stockout_date = pd.Timestamp(d).date().isoformat()
                    days_of_supply = (pd.Timestamp(d).date() - today).days + 1
                    break
            if stockout_date and days_of_supply is not None and days_of_supply <= 14:
                stockout_count += 1

        product_outbound = int(
            buyer_series[buyer_series["product_id"] == pid]["outbound_qty"].sum()
        ) if not buyer_series.empty else 0
        product_inbound = int(
            seller_series[seller_series["product_id"] == pid]["inbound_qty"].sum()
        ) if not seller_series.empty else 0
        total_outbound += product_outbound
        total_inbound += product_inbound

        top_s = seller_top_for_product.get(pid)
        top_b = buyer_top_for_product.get(pid)

        product_rows.append({
            "id": pid,
            "name": p["name"],
            "sku_code": p.get("sku_code"),
            "stock_at_warehouse": stock,
            "lead_time_days": int(p.get("lead_time_days") or 0),
            "has_model": has_model,
            "model_status": p.get("model_status"),
            "trained_at": p["trained_at"].isoformat() if p.get("trained_at") else None,
            "cv_mae": _safe_float(p.get("cv_mae")),
            "cv_mape": _safe_float(p.get("cv_mape")),
            "forecast_7d": round(forecast_7d, 2),
            "forecast_30d": round(forecast_30d, 2),
            "stockout_date": stockout_date,
            "days_of_supply": days_of_supply,
            "period_outbound": product_outbound,
            "period_inbound": product_inbound,
            "top_seller_id": top_s,
            "top_seller_name": seller_name_by_id.get(top_s) if top_s else None,
            "top_buyer_id": top_b,
            "top_buyer_name": buyer_name_by_id.get(top_b) if top_b else None,
        })

    # ── Per-seller summary ────────────────────────────────────────────────
    seller_rows = []
    seller_total_inbound = (
        seller_series.groupby("seller_id")["inbound_qty"].sum().to_dict()
        if not seller_series.empty else {}
    )
    grand_inbound = sum(seller_total_inbound.values()) or 1
    for s in sellers:
        sid = int(s["id"])
        qty = int(seller_total_inbound.get(sid, 0))
        sub = seller_series[seller_series["seller_id"] == sid] if not seller_series.empty else pd.DataFrame()
        product_count = int(sub["product_id"].nunique()) if not sub.empty else 0
        # Per-product share for concentration
        per_prod = sub.groupby("product_id")["inbound_qty"].sum() if not sub.empty else pd.Series(dtype=float)
        conc = float((per_prod / per_prod.sum()).pow(2).sum()) if per_prod.sum() > 0 else 0.0
        last_delivery = sub["date"].max() if not sub.empty else None
        seller_rows.append({
            "id": sid,
            "name": s["name"],
            "city": s.get("city"),
            "state": s.get("state"),
            "inbound_qty_period": qty,
            "share_pct": round(qty / grand_inbound * 100, 2),
            "product_count": product_count,
            "concentration_index": round(conc, 3),
            "last_delivery": last_delivery.date().isoformat() if last_delivery is not None else None,
        })
    seller_rows.sort(key=lambda r: r["inbound_qty_period"], reverse=True)

    # ── Per-buyer summary ─────────────────────────────────────────────────
    buyer_rows = []
    buyer_total_outbound = (
        buyer_series.groupby("buyer_id")["outbound_qty"].sum().to_dict()
        if not buyer_series.empty else {}
    )
    grand_outbound = sum(buyer_total_outbound.values()) or 1
    for b in buyers:
        bid = int(b["id"])
        qty = int(buyer_total_outbound.get(bid, 0))
        sub = buyer_series[buyer_series["buyer_id"] == bid] if not buyer_series.empty else pd.DataFrame()
        product_count = int(sub["product_id"].nunique()) if not sub.empty else 0
        per_prod = sub.groupby("product_id")["outbound_qty"].sum() if not sub.empty else pd.Series(dtype=float)
        conc = float((per_prod / per_prod.sum()).pow(2).sum()) if per_prod.sum() > 0 else 0.0
        last_order = sub["date"].max() if not sub.empty else None
        buyer_rows.append({
            "id": bid,
            "name": b["name"],
            "city": b.get("city"),
            "state": b.get("state"),
            "outbound_qty_period": qty,
            "share_pct": round(qty / grand_outbound * 100, 2),
            "product_count": product_count,
            "concentration_index": round(conc, 3),
            "last_order": last_order.date().isoformat() if last_order is not None else None,
        })
    buyer_rows.sort(key=lambda r: r["outbound_qty_period"], reverse=True)

    insights_count = len(get_insights(business_id, customer_id, warehouse_id))
    model_meta = get_global_model_metadata(business_id, customer_id, warehouse_id)

    return {
        "business_id": business_id,
        "customer_id": customer_id,
        "warehouse_id": warehouse_id,
        "period_days": period_days,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "global_model": {
            "trained": bool(model_meta),
            "status": model_meta.get("status") if model_meta else None,
            "trained_at": model_meta["trained_at"].isoformat() if model_meta and model_meta.get("trained_at") else None,
            "cv_mae": _safe_float(model_meta.get("cv_mae")) if model_meta else None,
            "cv_mape": _safe_float(model_meta.get("cv_mape")) if model_meta else None,
            "n_products": int(model_meta["n_products"]) if model_meta and model_meta.get("n_products") else 0,
            "n_buyers": int(model_meta["n_buyers"]) if model_meta and model_meta.get("n_buyers") else 0,
        },
        "kpis": {
            "total_products": len(products),
            "products_with_model": products_with_model,
            "active_sellers": len([s for s in seller_rows if s["inbound_qty_period"] > 0]),
            "active_buyers": len([b for b in buyer_rows if b["outbound_qty_period"] > 0]),
            "stockout_risk_count": stockout_count,
            "total_inbound_qty": total_inbound,
            "total_outbound_qty": total_outbound,
            "insights_count": insights_count,
        },
        "products": product_rows,
        "sellers": seller_rows,
        "buyers": buyer_rows,
    }


def get_seller_detail(
    business_id: int, customer_id: int, warehouse_id: int,
    seller_id: int, period_days: int = 90,
) -> dict:
    start, end = _date_window(period_days)
    series = get_seller_product_series(
        business_id, customer_id, warehouse_id=warehouse_id,
        seller_id=seller_id, start_date=start, end_date=end,
    )
    metrics = compute_seller_metrics(
        business_id, customer_id, seller_id=seller_id, days_lookback=period_days,
    )
    per_product = []
    if not series.empty:
        prods = series.groupby("product_id")["inbound_qty"].agg(["sum", "count"]).reset_index()
        for _, r in prods.iterrows():
            per_product.append({
                "product_id": int(r["product_id"]),
                "inbound_qty": int(r["sum"]),
                "delivery_days": int(r["count"]),
            })
    daily = []
    if not series.empty:
        agg = series.groupby("date")["inbound_qty"].sum().reset_index()
        daily = [
            {"date": pd.Timestamp(r["date"]).date().isoformat(), "inbound_qty": int(r["inbound_qty"])}
            for _, r in agg.iterrows()
        ]
    return {
        "seller_id": seller_id,
        "metrics": metrics[0] if metrics else None,
        "per_product": per_product,
        "daily": daily,
    }


def get_buyer_detail(
    business_id: int, customer_id: int, warehouse_id: int,
    buyer_id: int, period_days: int = 90,
) -> dict:
    start, end = _date_window(period_days)
    series = get_buyer_product_series(
        business_id, customer_id, warehouse_id=warehouse_id,
        buyer_id=buyer_id, start_date=start, end_date=end,
    )
    per_product = []
    if not series.empty:
        prods = series.groupby("product_id")["outbound_qty"].agg(["sum", "count"]).reset_index()
        for _, r in prods.iterrows():
            per_product.append({
                "product_id": int(r["product_id"]),
                "outbound_qty": int(r["sum"]),
                "order_days": int(r["count"]),
            })
    daily = []
    if not series.empty:
        agg = series.groupby("date")["outbound_qty"].sum().reset_index()
        daily = [
            {"date": pd.Timestamp(r["date"]).date().isoformat(), "outbound_qty": int(r["outbound_qty"])}
            for _, r in agg.iterrows()
        ]
    forecast = get_forecast_cache(
        business_id, customer_id, warehouse_id, buyer_id=buyer_id,
        start_date=date.today(), end_date=date.today() + timedelta(days=30),
    )
    forecast_rows = []
    if not forecast.empty:
        for _, r in forecast.iterrows():
            forecast_rows.append({
                "product_id": int(r["product_id"]),
                "date": pd.Timestamp(r["forecast_date"]).date().isoformat(),
                "p10": round(float(r["p10"]), 2),
                "p50": round(float(r["p50"]), 2),
                "p90": round(float(r["p90"]), 2),
            })
    return {
        "buyer_id": buyer_id,
        "per_product": per_product,
        "daily": daily,
        "forecast": forecast_rows,
    }


def get_location_heatmap(
    business_id: int, customer_id: int, warehouse_id: int,
    mode: str = "buyer",  # 'buyer' or 'seller'
    period_days: int = 90,
) -> dict:
    """Aggregate volume by city/state for sellers (origins) or buyers (destinations)."""
    from sqlalchemy import text
    from db import engine
    start, _ = _date_window(period_days)
    if mode == "seller":
        sql = text("""
            SELECT COALESCE(sl.city, '')  AS city,
                   COALESCE(sl.state, '') AS state,
                   s.id AS entity_id, s.name AS entity_name,
                   SUM(il.received_qty)::INT AS qty,
                   COUNT(DISTINCT il.product_id) AS product_count
            FROM inbound_lines il
            JOIN inbound_orders io ON io.id = il.inbound_id
            JOIN suppliers s ON s.id = io.supplier_id
            LEFT JOIN seller_locations sl ON sl.supplier_id = s.id AND sl.is_active
            WHERE io.business_id = :biz AND io.customer_id = :cust
              AND io.warehouse_id = :wh
              AND io.status = 'received'
              AND io.received_at >= :start
            GROUP BY sl.city, sl.state, s.id, s.name
        """)
    else:
        sql = text("""
            SELECT COALESCE(bl.city, '')  AS city,
                   COALESCE(bl.state, '') AS state,
                   b.id AS entity_id, b.name AS entity_name,
                   SUM(op.qty)::INT AS qty,
                   COUNT(DISTINCT ol.product_id) AS product_count
            FROM outbound_picks op
            JOIN outbound_lines ol  ON ol.id = op.outbound_line_id
            JOIN outbound_orders oo ON oo.id = ol.outbound_id
            JOIN buyers b ON b.id = oo.buyer_id
            LEFT JOIN buyer_locations bl ON bl.buyer_id = b.id AND bl.is_active
            WHERE oo.business_id = :biz AND oo.customer_id = :cust
              AND oo.warehouse_id = :wh
              AND oo.status = 'shipped'
              AND oo.shipped_at >= :start
            GROUP BY bl.city, bl.state, b.id, b.name
        """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {
            "biz": business_id, "cust": customer_id, "wh": warehouse_id, "start": start,
        }).mappings().all()

    # Aggregate by city
    city_map: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r["city"] or "Unknown", r["state"] or "")
        slot = city_map.setdefault(key, {
            "city": key[0], "state": key[1],
            "qty": 0, "entities": set(), "products": set(),
        })
        slot["qty"] += int(r["qty"] or 0)
        slot["entities"].add(int(r["entity_id"]))
        slot["products"].add(int(r["product_count"] or 0))

    locations = [
        {
            "city": v["city"], "state": v["state"],
            "qty": v["qty"], "entity_count": len(v["entities"]),
            "product_count": sum(v["products"]) if v["products"] else 0,
        }
        for v in city_map.values()
    ]
    locations.sort(key=lambda x: x["qty"], reverse=True)
    return {"mode": mode, "period_days": period_days, "locations": locations}


def get_outbound_forecast(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Return structured outbound forecast for the given date range.

    Uses the pre-computed ml_forecast_cache (populated by cache/refresh).
    Valuation = price × p50_qty, computed at read time from the products table.

    Returns:
      daily_total      – day-wise P10/P50/P90 (qty) + value_p50 (₹) summed across products
      by_buyer         – per-buyer day-wise P50 qty + value, ordered by total_value desc
      by_location      – per-city/state day-wise P50 qty + value aggregated from buyers
      by_product_buyer – per-product per-buyer breakdown with qty + value (the main view)
    """
    empty = {
        "start_date": start_date.isoformat(),
        "end_date":   end_date.isoformat(),
        "daily_total":      [],
        "by_buyer":         [],
        "by_location":      [],
        "by_product_buyer": [],
    }

    all_fc = get_forecast_cache(
        business_id, customer_id, warehouse_id,
        start_date=start_date, end_date=end_date,
    )
    if all_fc.empty:
        return empty

    all_fc["forecast_date"] = pd.to_datetime(all_fc["forecast_date"]).dt.date

    # Product lookup (includes price now)
    products = get_portfolio_product_list(business_id, customer_id, warehouse_id)
    price_by_product = {int(p["id"]): float(p.get("price") or 0) for p in products}
    name_by_product  = {int(p["id"]): p["name"] for p in products}
    sku_by_product   = {int(p["id"]): p.get("sku_code") for p in products}
    uom_by_product   = {int(p["id"]): p.get("uom") or "pcs" for p in products}

    buyers_info = get_all_buyers(business_id, customer_id)
    buyer_map = {b["id"]: b for b in buyers_info}

    # ── 1. Daily totals: aggregate rows (buyer_id IS NULL) ────────────────────
    agg_fc = all_fc[all_fc["buyer_id"].isna()].copy()
    if agg_fc.empty:
        daily_total = []
    else:
        agg_fc["value_p50"] = agg_fc["p50"] * agg_fc["product_id"].map(price_by_product).fillna(0)
        dt = (
            agg_fc.groupby("forecast_date")[["p10", "p50", "p90", "value_p50"]]
            .sum()
            .reset_index()
            .sort_values("forecast_date")
        )
        daily_total = [
            {
                "date":      str(r["forecast_date"]),
                "p10":       round(float(r["p10"]),       1),
                "p50":       round(float(r["p50"]),       1),
                "p90":       round(float(r["p90"]),       1),
                "value_p50": round(float(r["value_p50"]), 2),
            }
            for _, r in dt.iterrows()
        ]

    # ── 2. Per-buyer rows ──────────────────────────────────────────────────────
    buyer_fc = all_fc[all_fc["buyer_id"].notna()].copy()
    buyer_fc["buyer_id"]   = buyer_fc["buyer_id"].astype(int)
    buyer_fc["price"]      = buyer_fc["product_id"].map(price_by_product).fillna(0)
    buyer_fc["value_p50"]  = buyer_fc["p50"] * buyer_fc["price"]

    by_buyer: dict[int, dict] = {}
    if not buyer_fc.empty:
        bd = (
            buyer_fc.groupby(["buyer_id", "forecast_date"])[["p50", "value_p50"]]
            .sum()
            .reset_index()
        )
        for _, r in bd.iterrows():
            bid   = int(r["buyer_id"])
            binfo = buyer_map.get(bid, {})
            p50   = round(float(r["p50"]), 1)
            val   = round(float(r["value_p50"]), 2)
            if bid not in by_buyer:
                by_buyer[bid] = {
                    "buyer_id":    bid,
                    "buyer_name":  binfo.get("name")  or f"Buyer {bid}",
                    "city":        binfo.get("city")   or "",
                    "state":       binfo.get("state")  or "",
                    "total_p50":   0.0,
                    "total_value": 0.0,
                    "daily":       [],
                }
            by_buyer[bid]["total_p50"]   += p50
            by_buyer[bid]["total_value"] += val
            by_buyer[bid]["daily"].append({"date": str(r["forecast_date"]), "p50": p50, "value": val})

    for b in by_buyer.values():
        b["total_p50"]   = round(b["total_p50"],   1)
        b["total_value"] = round(b["total_value"],  2)
        b["daily"].sort(key=lambda x: x["date"])

    by_buyer_list = sorted(by_buyer.values(), key=lambda x: -x["total_value"])

    # ── 3. By location ────────────────────────────────────────────────────────
    loc_map: dict[str, dict] = {}
    for b in by_buyer_list:
        city  = b["city"]  or "Unknown"
        state = b["state"] or "Unknown"
        key   = f"{city}||{state}"
        if key not in loc_map:
            loc_map[key] = {
                "city":        city,
                "state":       state,
                "buyer_ids":   set(),
                "total_p50":   0.0,
                "total_value": 0.0,
                "daily":       {},
            }
        loc = loc_map[key]
        loc["buyer_ids"].add(b["buyer_id"])
        loc["total_p50"]   += b["total_p50"]
        loc["total_value"] += b["total_value"]
        for day in b["daily"]:
            slot = loc["daily"].setdefault(day["date"], {"p50": 0.0, "value": 0.0})
            slot["p50"]   += day["p50"]
            slot["value"] += day["value"]

    by_location = [
        {
            "city":        v["city"],
            "state":       v["state"],
            "buyer_count": len(v["buyer_ids"]),
            "total_p50":   round(v["total_p50"],   1),
            "total_value": round(v["total_value"],  2),
            "daily": [
                {"date": d, "p50": round(s["p50"], 1), "value": round(s["value"], 2)}
                for d, s in sorted(v["daily"].items())
            ],
        }
        for v in sorted(loc_map.values(), key=lambda x: -x["total_value"])
    ]

    # ── 4. By product × buyer ─────────────────────────────────────────────────
    by_product: dict[int, dict] = {}
    if not buyer_fc.empty:
        for pid, prod_grp in buyer_fc.groupby("product_id"):
            pid   = int(pid)
            price = price_by_product.get(pid, 0.0)
            buyers_in_prod: dict[int, dict] = {}
            for _, row in prod_grp.iterrows():
                bid   = int(row["buyer_id"])
                binfo = buyer_map.get(bid, {})
                qty   = float(row["p50"])
                val   = qty * price
                if bid not in buyers_in_prod:
                    buyers_in_prod[bid] = {
                        "buyer_id":    bid,
                        "buyer_name":  binfo.get("name")  or f"Buyer {bid}",
                        "city":        binfo.get("city")   or "",
                        "state":       binfo.get("state")  or "",
                        "total_qty":   0.0,
                        "total_value": 0.0,
                        "daily":       [],
                    }
                buyers_in_prod[bid]["total_qty"]   += qty
                buyers_in_prod[bid]["total_value"] += val
                buyers_in_prod[bid]["daily"].append({
                    "date":  str(row["forecast_date"]),
                    "qty":   round(qty, 1),
                    "value": round(val, 2),
                })
            for b in buyers_in_prod.values():
                b["total_qty"]   = round(b["total_qty"],   1)
                b["total_value"] = round(b["total_value"],  2)
                b["daily"].sort(key=lambda x: x["date"])

            by_product[pid] = {
                "product_id":   pid,
                "product_name": name_by_product.get(pid, f"Product {pid}"),
                "sku_code":     sku_by_product.get(pid),
                "uom":          uom_by_product.get(pid, "pcs"),
                "price":        price,
                "total_qty":    round(float(prod_grp["p50"].sum()),       1),
                "total_value":  round(float(prod_grp["value_p50"].sum()), 2),
                "buyers":       sorted(buyers_in_prod.values(), key=lambda x: -x["total_value"]),
            }

    by_product_buyer = sorted(by_product.values(), key=lambda x: -x["total_value"])

    return {
        "start_date":       start_date.isoformat(),
        "end_date":         end_date.isoformat(),
        "daily_total":      daily_total,
        "by_buyer":         by_buyer_list,
        "by_location":      by_location,
        "by_product_buyer": by_product_buyer,
    }


def get_inbound_forecast(
    business_id: int,
    customer_id: int,
    warehouse_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Statistical inbound forecast from historical delivery patterns.

    P10/P50/P90 are percentiles of historical daily inbound qty per
    (product, seller) over the 90 days before start_date. Valuation uses
    the historical average unit cost. Daily projections are flat (same
    value each day) — no seasonality, by design for V1.
    """
    from collections import defaultdict

    lookback_end   = start_date - timedelta(days=1)
    lookback_start = lookback_end - timedelta(days=89)

    df = get_seller_product_series(
        business_id, customer_id,
        warehouse_id=warehouse_id,
        start_date=lookback_start,
        end_date=lookback_end,
    )

    products    = get_portfolio_product_list(business_id, customer_id, warehouse_id)
    name_by_pid = {int(p["id"]): p["name"] for p in products}
    sku_by_pid  = {int(p["id"]): p.get("sku_code") for p in products}
    uom_by_pid  = {int(p["id"]): p.get("uom") or "pcs" for p in products}

    sellers    = get_all_sellers(business_id, customer_id)
    seller_map = {int(s["id"]): s for s in sellers}

    _empty = {
        "start_date": start_date.isoformat(),
        "end_date":   end_date.isoformat(),
        "note": "no_history",
        "daily_total": [], "by_seller": [], "by_location": [], "by_product_seller": [],
    }
    if df.empty:
        return _empty

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    all_hist_dates = pd.date_range(str(lookback_start), str(lookback_end), freq="D")
    forecast_dates = pd.date_range(str(start_date), str(end_date), freq="D")

    # Per-(product, seller): compute P10/P50/P90 from 90-day daily distribution
    stats_rows = []
    for (pid, sid), grp in df.groupby(["product_id", "seller_id"]):
        pid, sid = int(pid), int(sid)
        daily_qty = (
            grp.groupby("date")["inbound_qty"].sum()
            .reindex(all_hist_dates, fill_value=0)
        )
        avg_cost = float(grp["avg_unit_cost"].mean()) if "avg_unit_cost" in grp.columns else 0.0
        stats_rows.append({
            "product_id":    pid,
            "seller_id":     sid,
            "p10":           float(daily_qty.quantile(0.10)),
            "p50":           float(daily_qty.quantile(0.50)),
            "p90":           float(daily_qty.quantile(0.90)),
            "avg_unit_cost": avg_cost,
        })

    if not stats_rows:
        return _empty

    stats_df = pd.DataFrame(stats_rows)

    # Expand: same P10/P50/P90 for every forecast day
    fc_rows = [
        {
            "product_id":    int(s["product_id"]),
            "seller_id":     int(s["seller_id"]),
            "forecast_date": d.date(),
            "p10":           s["p10"],
            "p50":           s["p50"],
            "p90":           s["p90"],
            "avg_unit_cost": s["avg_unit_cost"],
        }
        for _, s in stats_df.iterrows()
        for d in forecast_dates
    ]
    fc_df = pd.DataFrame(fc_rows)
    fc_df["value_p50"] = fc_df["p50"] * fc_df["avg_unit_cost"]

    # ── daily_total ───────────────────────────────────────────────────────────
    agg_daily = (
        fc_df.groupby("forecast_date")[["p10", "p50", "p90", "value_p50"]]
        .sum().reset_index().sort_values("forecast_date")
    )
    daily_total = [
        {
            "date":      str(r["forecast_date"]),
            "p10":       round(float(r["p10"]),       1),
            "p50":       round(float(r["p50"]),       1),
            "p90":       round(float(r["p90"]),       1),
            "value_p50": round(float(r["value_p50"]), 2),
        }
        for _, r in agg_daily.iterrows()
    ]

    # ── by_seller ─────────────────────────────────────────────────────────────
    by_seller: dict[int, dict] = {}
    seller_daily_agg: dict[tuple, dict] = {}

    for _, row in fc_df.iterrows():
        sid   = int(row["seller_id"])
        d     = str(row["forecast_date"])
        qty   = float(row["p50"])
        val   = float(row["value_p50"])
        sinfo = seller_map.get(sid, {})

        if sid not in by_seller:
            by_seller[sid] = {
                "seller_id":   sid,
                "seller_name": sinfo.get("name")  or f"Seller {sid}",
                "city":        sinfo.get("city")   or "",
                "state":       sinfo.get("state")  or "",
                "total_p50":   0.0,
                "total_value": 0.0,
            }
        by_seller[sid]["total_p50"]   += qty
        by_seller[sid]["total_value"] += val

        k = (sid, d)
        if k not in seller_daily_agg:
            seller_daily_agg[k] = {"date": d, "p50": 0.0, "value": 0.0}
        seller_daily_agg[k]["p50"]   += qty
        seller_daily_agg[k]["value"] += val

    # Group daily entries by seller for O(1) lookup
    daily_by_sid: dict[int, list] = defaultdict(list)
    for (sid, _), v in seller_daily_agg.items():
        daily_by_sid[sid].append(v)

    for sid, entry in by_seller.items():
        entry["total_p50"]   = round(entry["total_p50"],   1)
        entry["total_value"] = round(entry["total_value"],  2)
        entry["daily"] = sorted(
            [{"date": d["date"], "p50": round(d["p50"], 1), "value": round(d["value"], 2)}
             for d in daily_by_sid[sid]],
            key=lambda x: x["date"],
        )

    by_seller_list = sorted(by_seller.values(), key=lambda x: -x["total_value"])

    # ── by_location ───────────────────────────────────────────────────────────
    loc_map: dict[tuple, dict] = {}
    for entry in by_seller_list:
        key = (entry["city"], entry["state"])
        if key not in loc_map:
            loc_map[key] = {
                "city":         entry["city"],
                "state":        entry["state"],
                "seller_count": 0,
                "total_p50":    0.0,
                "total_value":  0.0,
                "daily":        {},
            }
        loc_map[key]["seller_count"] += 1
        loc_map[key]["total_p50"]    += entry["total_p50"]
        loc_map[key]["total_value"]  += entry["total_value"]
        for d in entry["daily"]:
            ld = loc_map[key]["daily"].setdefault(d["date"], {"date": d["date"], "p50": 0.0, "value": 0.0})
            ld["p50"]   += d["p50"]
            ld["value"] += d["value"]

    by_location = []
    for entry in sorted(loc_map.values(), key=lambda x: -x["total_value"]):
        entry["total_p50"]   = round(entry["total_p50"],  1)
        entry["total_value"] = round(entry["total_value"], 2)
        entry["daily"] = sorted(entry.pop("daily").values(), key=lambda x: x["date"])
        by_location.append(entry)

    # ── by_product_seller ─────────────────────────────────────────────────────
    by_product: dict[int, dict] = {}
    for _, row in fc_df.iterrows():
        pid   = int(row["product_id"])
        sid   = int(row["seller_id"])
        d     = str(row["forecast_date"])
        qty   = float(row["p50"])
        val   = float(row["value_p50"])
        sinfo = seller_map.get(sid, {})

        if pid not in by_product:
            prod_stats = stats_df[stats_df["product_id"] == pid]
            avg_cost   = float(prod_stats["avg_unit_cost"].mean()) if not prod_stats.empty else 0.0
            by_product[pid] = {
                "product_id":    pid,
                "product_name":  name_by_pid.get(pid, f"Product {pid}"),
                "sku_code":      sku_by_pid.get(pid),
                "uom":           uom_by_pid.get(pid, "pcs"),
                "avg_unit_cost": avg_cost,
                "total_qty":     0.0,
                "total_value":   0.0,
                "sellers":       {},
            }
        by_product[pid]["total_qty"]   += qty
        by_product[pid]["total_value"] += val

        sellers_in_prod = by_product[pid]["sellers"]
        if sid not in sellers_in_prod:
            sellers_in_prod[sid] = {
                "seller_id":   sid,
                "seller_name": sinfo.get("name")  or f"Seller {sid}",
                "city":        sinfo.get("city")   or "",
                "state":       sinfo.get("state")  or "",
                "total_qty":   0.0,
                "total_value": 0.0,
                "daily":       [],
            }
        sellers_in_prod[sid]["total_qty"]   += qty
        sellers_in_prod[sid]["total_value"] += val
        sellers_in_prod[sid]["daily"].append({"date": d, "qty": round(qty, 1), "value": round(val, 2)})

    by_product_seller = []
    for pid, entry in by_product.items():
        entry["total_qty"]   = round(entry["total_qty"],   1)
        entry["total_value"] = round(entry["total_value"],  2)
        sellers_list = sorted(entry.pop("sellers").values(), key=lambda x: -x["total_value"])
        for s in sellers_list:
            s["total_qty"]   = round(s["total_qty"],   1)
            s["total_value"] = round(s["total_value"],  2)
            s["daily"].sort(key=lambda x: x["date"])
        entry["sellers"] = sellers_list
        by_product_seller.append(entry)
    by_product_seller.sort(key=lambda x: -x["total_value"])

    return {
        "start_date":        start_date.isoformat(),
        "end_date":          end_date.isoformat(),
        "note":              "historical_projection",
        "daily_total":       daily_total,
        "by_seller":         by_seller_list,
        "by_location":       by_location,
        "by_product_seller": by_product_seller,
    }
