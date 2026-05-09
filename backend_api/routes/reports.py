"""
Reports routes – analytical reports for the authenticated user's business.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from auth import get_user_context, UserContext
from db import (
    get_user_by_id, 
    engine,
    get_inbound_report_details,
    get_outbound_report_details
)
from sqlalchemy import text

router = APIRouter(prefix="/reports", tags=["Reports"])


def _get_user_business_id(user_id: int) -> int:
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


def fast_slow_moving_report(
    days: int = Query(30, ge=7, le=365, description="Look-back period in days"),
    customer_id: int | None = Query(None, description="Optional customer filter"),
    ctx: UserContext = Depends(get_user_context),
):
    """
    Classify every product as Fast / Medium / Slow / Non-Moving
    based on total outbound quantity over the given period.

    Classification thresholds are computed using percentiles of the
    movement distribution within the business (top 25% = fast, bottom
    25% = slow, zero movement = non-moving).
    """
    """
    cust = ctx.resolve_customer_filter(customer_id)
    where_t = ["t.business_id = :biz", "t.transaction_at >= NOW() - MAKE_INTERVAL(days => :days)"]
    where_m = ["m.business_id = :biz", "m.date >= (CURRENT_DATE - MAKE_INTERVAL(days => :days))"]
    where_p = ["p.business_id = :biz"]
    params: dict = {"biz": ctx.business_id, "days": days}
    
    if cust is not None:
        where_t.append("t.customer_id = :cust")
        where_m.append("m.customer_id = :cust")
        where_p.append("p.customer_id = :cust")
        params["cust"] = cust

    query = text(f"""
        WITH movement AS (
            -- Outbound from inventory_transactions
            SELECT
                t.product_id,
                SUM(CASE WHEN t.stock_adjusted < 0 THEN ABS(t.stock_adjusted) ELSE 0 END)::int AS total_outbound,
                SUM(CASE WHEN t.stock_adjusted > 0 THEN t.stock_adjusted ELSE 0 END)::int       AS total_inbound,
                COUNT(*)::int                                                                     AS tx_count
            FROM inventory_transactions t
            WHERE {' AND '.join(where_t)}
            GROUP BY t.product_id
        ),
        ml_movement AS (
            -- Outbound from uploaded history
            SELECT
                m.product_id,
                SUM(m.outbound_qty)::int AS total_outbound,
                SUM(m.inbound_qty)::int  AS total_inbound,
                COUNT(*)::int            AS tx_count
            FROM ml_uploaded_history m
            WHERE {' AND '.join(where_m)}
            GROUP BY m.product_id
        ),
        combined AS (
            SELECT
                p.id            AS product_id,
                p.name          AS product_name,
                p.sku_code,
                p.price,
                p.stock_at_warehouse AS current_stock,
                COALESCE(mv.total_outbound, 0) + COALESCE(ml.total_outbound, 0) AS total_outbound,
                COALESCE(mv.total_inbound, 0)  + COALESCE(ml.total_inbound, 0)  AS total_inbound,
                COALESCE(mv.tx_count, 0)       + COALESCE(ml.tx_count, 0)       AS tx_count
            FROM products p
            LEFT JOIN movement    mv ON mv.product_id = p.id
            LEFT JOIN ml_movement ml ON ml.product_id = p.id
            WHERE {' AND '.join(where_p)}
        ),
        thresholds AS (
            SELECT
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_outbound) AS p75,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total_outbound) AS p25,
                AVG(total_outbound)                                           AS avg_outbound
            FROM combined
            WHERE total_outbound > 0
        )
        SELECT
            c.*,
            ROUND(c.total_outbound::numeric / NULLIF(:days, 0), 2) AS avg_daily_outbound,
            CASE
                WHEN c.total_outbound = 0          THEN 'non_moving'
                WHEN c.total_outbound >= t.p75     THEN 'fast'
                WHEN c.total_outbound <= t.p25     THEN 'slow'
                ELSE 'medium'
            END AS category,
            ROUND(t.p75::numeric, 0) AS threshold_fast,
            ROUND(t.p25::numeric, 0) AS threshold_slow,
            ROUND(t.avg_outbound::numeric, 1) AS avg_outbound_all
        FROM combined c
        CROSS JOIN thresholds t
        ORDER BY c.total_outbound DESC
    """)

    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    items = [dict(r) for r in rows]

    # Build summary
    summary = {"fast": 0, "medium": 0, "slow": 0, "non_moving": 0, "total": len(items)}
    for item in items:
        cat = item.get("category", "non_moving")
        summary[cat] = summary.get(cat, 0) + 1

    return {
        "days": days,
        "summary": summary,
        "thresholds": {
            "fast_min": items[0]["threshold_fast"] if items else 0,
            "slow_max": items[0]["threshold_slow"] if items else 0,
            "avg_outbound": items[0]["avg_outbound_all"] if items else 0,
        },
        "items": items,
    }


@router.get("/inbound-outbound")
def inbound_outbound_report(
    days: int = Query(30, ge=7, le=365, description="Look-back period in days"),
    product_id: int | None = Query(None, description="Optional product ID to get daily time-series for"),
    customer_id: int | None = Query(None, description="Optional customer filter"),
    ctx: UserContext = Depends(get_user_context),
):
    """
    Inbound vs Outbound report:
      - Top 5 products by total inbound
      - Top 5 products by total outbound
      - Product list (for search dropdown)
      - Daily inbound/outbound time-series (all products or a specific one)
    """
    """
    cust = ctx.resolve_customer_filter(customer_id)
    where_t = ["t.business_id = :biz", "t.transaction_at >= NOW() - MAKE_INTERVAL(days => :days)"]
    where_p = ["p.business_id = :biz"]
    params: dict = {"biz": ctx.business_id, "days": days}
    
    if cust is not None:
        where_t.append("t.customer_id = :cust")
        where_p.append("p.customer_id = :cust")
        params["cust"] = cust

    # ── Top 5 rankings ──────────────────────────────────────────
    ranking_query = text(f"""
        WITH movement AS (
            SELECT
                t.product_id,
                SUM(CASE WHEN t.stock_adjusted > 0
                         THEN t.stock_adjusted ELSE 0 END)::int AS total_inbound,
                SUM(CASE WHEN t.stock_adjusted < 0
                         THEN ABS(t.stock_adjusted) ELSE 0 END)::int AS total_outbound
            FROM inventory_transactions t
            WHERE {' AND '.join(where_t)}
            GROUP BY t.product_id
        )
        SELECT
            p.id   AS product_id,
            p.name AS product_name,
            p.sku_code,
            COALESCE(m.total_inbound, 0)  AS total_inbound,
            COALESCE(m.total_outbound, 0) AS total_outbound,
            p.stock_at_warehouse AS current_stock
        FROM products p
        LEFT JOIN movement m ON m.product_id = p.id
        WHERE {' AND '.join(where_p)}
        ORDER BY COALESCE(m.total_outbound, 0) + COALESCE(m.total_inbound, 0) DESC
    """)

    with engine.connect() as conn:
        rows = conn.execute(ranking_query, params).mappings().all()

    all_products = [dict(r) for r in rows]

    # Top 5 by inbound
    top_inbound = sorted(all_products, key=lambda x: x["total_inbound"], reverse=True)[:5]
    # Top 5 by outbound
    top_outbound = sorted(all_products, key=lambda x: x["total_outbound"], reverse=True)[:5]

    # Product list for dropdown (only products with any movement)
    product_list = [
        {"id": p["product_id"], "name": p["product_name"], "sku_code": p["sku_code"]}
        for p in all_products
    ]

    # ── Daily time-series ────────────────────────────────────────
    if product_id:
        tl_where = where_t + ["t.product_id = :pid"]
        tl_params = {**params, "pid": product_id}
        timeline_query = text(f"""
            SELECT
                DATE(t.transaction_at) AS date,
                SUM(CASE WHEN t.stock_adjusted > 0
                         THEN t.stock_adjusted ELSE 0 END)::int AS inbound,
                SUM(CASE WHEN t.stock_adjusted < 0
                         THEN ABS(t.stock_adjusted) ELSE 0 END)::int AS outbound
            FROM inventory_transactions t
            WHERE {' AND '.join(tl_where)}
            GROUP BY DATE(t.transaction_at)
            ORDER BY date
        """)
        with engine.connect() as conn:
            tl_rows = conn.execute(timeline_query, tl_params).mappings().all()
    else:
        timeline_query = text(f"""
            SELECT
                DATE(t.transaction_at) AS date,
                SUM(CASE WHEN t.stock_adjusted > 0
                         THEN t.stock_adjusted ELSE 0 END)::int AS inbound,
                SUM(CASE WHEN t.stock_adjusted < 0
                         THEN ABS(t.stock_adjusted) ELSE 0 END)::int AS outbound
            FROM inventory_transactions t
            WHERE {' AND '.join(where_t)}
            GROUP BY DATE(t.transaction_at)
            ORDER BY date
        """)
        with engine.connect() as conn:
            tl_rows = conn.execute(timeline_query, params).mappings().all()

    timeline = [dict(r) for r in tl_rows]
    # Convert date objects to strings for JSON serialization
    for row in timeline:
        row["date"] = str(row["date"])

    # Summary totals
    total_inbound = sum(p["total_inbound"] for p in all_products)
    total_outbound = sum(p["total_outbound"] for p in all_products)

    return {
        "days": days,
        "summary": {
            "total_inbound": total_inbound,
            "total_outbound": total_outbound,
            "total_products": len(all_products),
            "net_flow": total_inbound - total_outbound,
        },
        "top_inbound": top_inbound,
        "top_outbound": top_outbound,
        "product_list": product_list,
        "timeline": timeline,
        "selected_product_id": product_id,
    }


@router.get("/inbound-details")
def inbound_details_report(
    days: int = Query(30, ge=1, le=365, description="Look-back period in days"),
    customer_id: int | None = Query(None, description="Optional customer filter"),
    ctx: UserContext = Depends(get_user_context),
):
    """
    Shows stock in / inbound details: seller, location, product, qty, price, batchno.
    """
    """
    cust = ctx.resolve_customer_filter(customer_id)
    return {"days": days, "items": get_inbound_report_details(ctx.business_id, days, cust)}


@router.get("/outbound-details")
def outbound_details_report(
    days: int = Query(30, ge=1, le=365, description="Look-back period in days"),
    customer_id: int | None = Query(None, description="Optional customer filter"),
    ctx: UserContext = Depends(get_user_context),
):
    """
    Shows stock out / outbound details: buyer, location, product, qty, price, batchno.
    """
    """
    cust = ctx.resolve_customer_filter(customer_id)
    return {"days": days, "items": get_outbound_report_details(ctx.business_id, days, cust)}
