"""
Reports routes – analytical reports for the authenticated user's business.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from auth import get_current_user_id
from db import get_user_by_id, engine
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


@router.get("/fast-slow-moving")
def fast_slow_moving_report(
    days: int = Query(30, ge=7, le=365, description="Look-back period in days"),
    user_id: int = Depends(get_current_user_id),
):
    """
    Classify every product as Fast / Medium / Slow / Non-Moving
    based on total outbound quantity over the given period.

    Classification thresholds are computed using percentiles of the
    movement distribution within the business (top 25% = fast, bottom
    25% = slow, zero movement = non-moving).
    """
    biz_id = _get_user_business_id(user_id)

    query = text("""
        WITH movement AS (
            -- Outbound from inventory_transactions
            SELECT
                t.product_id,
                SUM(CASE WHEN t.stock_adjusted < 0 THEN ABS(t.stock_adjusted) ELSE 0 END)::int AS total_outbound,
                SUM(CASE WHEN t.stock_adjusted > 0 THEN t.stock_adjusted ELSE 0 END)::int       AS total_inbound,
                COUNT(*)::int                                                                     AS tx_count
            FROM inventory_transactions t
            WHERE t.business_id = :biz
              AND t.transaction_at >= NOW() - MAKE_INTERVAL(days => :days)
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
            WHERE m.business_id = :biz
              AND m.date >= (CURRENT_DATE - MAKE_INTERVAL(days => :days))
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
            WHERE p.business_id = :biz AND p.is_active = true
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
        rows = conn.execute(query, {"biz": biz_id, "days": days}).mappings().all()

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
