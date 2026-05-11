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
