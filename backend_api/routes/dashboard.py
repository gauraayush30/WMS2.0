"""
Dashboard routes – stats & notifications, tenant-scoped.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import (
    UserContext,
    get_current_user_id,
    get_user_context,
    require_warehouse,
)
from db import (
    get_user_by_id,
    get_dashboard_stats,
    get_products_without_location,
    get_customer_breakdown_stats,
    get_warehouse_dashboard_stats,
    get_customer_dashboard_stats,
    get_outbound_trend_daily,
    get_reorder_now_list,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _get_user_business_id(user_id: int) -> int:
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


@router.get("/stats")
def dashboard_stats(user_id: int = Depends(get_current_user_id)):
    """Legacy aggregate dashboard statistics (kept for backwards compat)."""
    biz_id = _get_user_business_id(user_id)
    return get_dashboard_stats(biz_id)


@router.get("/products-without-location")
def products_without_location(user_id: int = Depends(get_current_user_id)):
    """Return all products that have no warehouse location assigned."""
    biz_id = _get_user_business_id(user_id)
    products = get_products_without_location(biz_id)
    return {"products": products, "count": len(products)}


# ── Phase 4: tenant-aware dashboards ─────────────────────────────────────────

@router.get("/warehouse-stats")
def warehouse_stats(ctx: UserContext = Depends(require_warehouse)):
    """Top-line stats across the warehouse business (warehouse role only)."""
    return {
        "stats": get_warehouse_dashboard_stats(ctx.business_id),
        "customer_breakdown": get_customer_breakdown_stats(ctx.business_id),
    }


@router.get("/customer-stats")
def customer_stats(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """KPIs for a single customer.

    - Customer roles: forced to own customer.
    - Warehouse roles: pass `customer_id` query param. If omitted, returns
      a 400 (warehouse users should call /warehouse-stats for the cross-customer view).
    """
    cust = ctx.resolve_customer_filter(customer_id)
    if cust is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id query param is required for warehouse roles",
        )
    return {
        "customer_id": cust,
        "stats": get_customer_dashboard_stats(ctx.business_id, cust),
        "outbound_trend": get_outbound_trend_daily(ctx.business_id, cust, days=90),
    }


@router.get("/replenishment-now")
def replenishment_now(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Products at or below their reorder_point — i.e. action items."""
    cust = ctx.resolve_customer_filter(customer_id)
    return {"items": get_reorder_now_list(ctx.business_id, cust)}


@router.get("/outbound-trend")
def outbound_trend(
    days: int = Query(90, ge=7, le=365),
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Daily outbound time series for charts."""
    cust = ctx.resolve_customer_filter(customer_id)
    return {"series": get_outbound_trend_daily(ctx.business_id, cust, days)}
