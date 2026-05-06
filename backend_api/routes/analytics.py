"""
Analytics routes (Phase 5):
  - FIFO/FEFO compliance + aging + expiry-risk
  - Complete Analysis (single-SKU 360)
  - Behavior Analysis (ABC × XYZ + lifecycle)

All endpoints are tenant-scoped via UserContext.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import UserContext, get_user_context
from db import (
    get_aging_buckets,
    get_behavior_analysis,
    get_complete_analysis,
    get_expiry_risk,
    get_fifo_fefo_compliance,
)


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/fifo-fefo")
def fifo_fefo(
    customer_id: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    return get_fifo_fefo_compliance(ctx.business_id, cust, from_date, to_date)


@router.get("/aging")
def aging(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    return {"buckets": get_aging_buckets(ctx.business_id, cust)}


@router.get("/expiry-risk")
def expiry_risk(
    customer_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    return {"items": get_expiry_risk(ctx.business_id, cust, days)}


@router.get("/complete-analysis/{product_id}")
def complete_analysis(
    product_id: int,
    days: int = Query(90, ge=7, le=365),
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    data = get_complete_analysis(product_id, ctx.business_id, cust, days)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return data


@router.get("/behavior")
def behavior(
    days: int = Query(90, ge=14, le=365),
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    return get_behavior_analysis(ctx.business_id, cust, days)
