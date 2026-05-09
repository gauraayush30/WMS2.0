"""
Dashboard routes – stats & notifications, tenant-scoped.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import (
    UserContext,
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


# _get_user_business_id removed in favor of UserContext


@router.get("/stats")
def dashboard_stats(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Legacy aggregate dashboard statistics (kept for backwards compat)."""
    cust = ctx.resolve_customer_filter(customer_id)
    return get_dashboard_stats(ctx.business_id, cust)


@router.get("/products-without-location")
def products_without_location(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Return all products that have no warehouse location assigned."""
    cust = ctx.resolve_customer_filter(customer_id)
    products = get_products_without_location(ctx.business_id, cust)
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
