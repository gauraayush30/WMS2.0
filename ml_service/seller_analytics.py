"""
Seller reliability metrics — pure SQL + stats, no ML.

Reasoning: supplier performance is governed by PO cycles and contract lead
times, not temporal demand patterns. Forecasting it with an ML model is
spurious. Instead we surface measurable behaviour:
    - fill rate              SUM(received_qty) / SUM(expected_qty)
    - avg lead time          mean(received_at - PO created_at) per order
    - delivery regularity    1 - coefficient_of_variation(restock interval)
    - concentration index    Herfindahl across products this seller supplies
    - products supplied      distinct product count in window
    - last delivery date     MAX(received_at)
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from db import engine


def _herfindahl(shares: list[float]) -> float:
    if not shares:
        return 0.0
    total = sum(shares) or 1.0
    norm = [s / total for s in shares]
    return float(sum(s * s for s in norm))


def compute_seller_metrics(
    business_id: int,
    customer_id: int,
    seller_id: int | None = None,
    days_lookback: int = 90,
) -> list[dict]:
    """Per-supplier metrics over the lookback window."""
    start = (date.today() - timedelta(days=days_lookback))
    params: dict = {
        "biz": business_id, "cust": customer_id, "start": start,
    }
    seller_filter = ""
    if seller_id is not None:
        seller_filter = " AND io.supplier_id = :sid"
        params["sid"] = seller_id

    # Aggregate inbound order behaviour
    line_sql = text(f"""
        SELECT io.supplier_id,
               s.name AS supplier_name,
               COUNT(DISTINCT io.id)                              AS order_count,
               COUNT(DISTINCT il.product_id)                      AS product_count,
               SUM(il.expected_qty)                               AS expected_total,
               SUM(il.received_qty)                               AS received_total,
               MAX(io.received_at)                                AS last_delivery,
               EXTRACT(EPOCH FROM AVG(io.received_at - io.created_at))/86400 AS avg_lead_time_days
        FROM inbound_orders io
        JOIN inbound_lines  il ON il.inbound_id = io.id
        JOIN suppliers      s  ON s.id = io.supplier_id
        WHERE io.business_id = :biz AND io.customer_id = :cust
          AND io.received_at >= :start
          AND io.status = 'received'
          AND io.supplier_id IS NOT NULL
          {seller_filter}
        GROUP BY io.supplier_id, s.name
        ORDER BY received_total DESC NULLS LAST
    """)

    # Restock-interval timestamps for delivery regularity
    interval_sql = text(f"""
        SELECT io.supplier_id, io.received_at
        FROM inbound_orders io
        WHERE io.business_id = :biz AND io.customer_id = :cust
          AND io.received_at >= :start
          AND io.status = 'received'
          AND io.supplier_id IS NOT NULL
          {seller_filter}
        ORDER BY io.supplier_id, io.received_at
    """)

    # Per-(seller, product) qty for concentration
    prod_sql = text(f"""
        SELECT io.supplier_id, il.product_id,
               SUM(il.received_qty)::FLOAT AS qty
        FROM inbound_orders io
        JOIN inbound_lines  il ON il.inbound_id = io.id
        WHERE io.business_id = :biz AND io.customer_id = :cust
          AND io.received_at >= :start
          AND io.status = 'received'
          AND io.supplier_id IS NOT NULL
          {seller_filter}
        GROUP BY io.supplier_id, il.product_id
    """)

    with engine.connect() as conn:
        rows = conn.execute(line_sql, params).mappings().all()
        intervals = conn.execute(interval_sql, params).mappings().all()
        prod_rows = conn.execute(prod_sql, params).mappings().all()

    # Group intervals by supplier
    int_df = pd.DataFrame(intervals)
    regularity: dict[int, float] = {}
    if not int_df.empty:
        int_df["received_at"] = pd.to_datetime(int_df["received_at"])
        for sid, grp in int_df.groupby("supplier_id"):
            ts = grp["received_at"].sort_values()
            gaps = ts.diff().dt.total_seconds().dropna() / 86400.0
            if len(gaps) >= 2 and gaps.mean() > 0:
                cv = float(gaps.std() / gaps.mean())
                regularity[int(sid)] = round(max(0.0, 1.0 - cv), 3)
            else:
                regularity[int(sid)] = None

    # Group product shares by supplier
    prod_df = pd.DataFrame(prod_rows)
    conc: dict[int, float] = {}
    if not prod_df.empty:
        for sid, grp in prod_df.groupby("supplier_id"):
            conc[int(sid)] = round(_herfindahl(grp["qty"].tolist()), 3)

    out: list[dict] = []
    for r in rows:
        sid = int(r["supplier_id"])
        expected = float(r["expected_total"] or 0)
        received = float(r["received_total"] or 0)
        fill_rate = round(received / expected, 3) if expected > 0 else None
        out.append({
            "seller_id": sid,
            "name": r["supplier_name"],
            "order_count": int(r["order_count"] or 0),
            "product_count": int(r["product_count"] or 0),
            "received_total": int(received),
            "expected_total": int(expected),
            "fill_rate": fill_rate,
            "avg_lead_time_days": (
                round(float(r["avg_lead_time_days"]), 2)
                if r["avg_lead_time_days"] is not None else None
            ),
            "delivery_regularity": regularity.get(sid),
            "concentration_index": conc.get(sid),
            "last_delivery": (
                r["last_delivery"].isoformat() if r["last_delivery"] is not None else None
            ),
        })
    return out
