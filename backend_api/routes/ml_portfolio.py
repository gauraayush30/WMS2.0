"""
Portfolio + global-model proxy routes.

All endpoints sit at /forecast/portfolio/* and require auth. Tenancy is
resolved server-side from the UserContext — customer roles can only see
their own customer's data.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import UserContext, get_user_context

router = APIRouter(prefix="/forecast/portfolio", tags=["ML Portfolio"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8100")
_TIMEOUT = httpx.Timeout(timeout=120.0, connect=10.0)


def _resolve_scope(
    ctx: UserContext,
    customer_id: int | None,
    warehouse_id: int | None,
) -> tuple[int, int, int]:
    """Return (business_id, customer_id, warehouse_id) or raise 400.

    Customer roles have their customer_id auto-filled; warehouse roles must
    pass it explicitly.
    """
    effective_customer = ctx.resolve_customer_filter(customer_id)
    if effective_customer is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id is required",
        )
    if warehouse_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="warehouse_id is required",
        )
    return ctx.business_id, int(effective_customer), int(warehouse_id)


def _params(business_id: int, customer_id: int, warehouse_id: int, **extra) -> dict:
    p = {
        "business_id": business_id,
        "customer_id": customer_id,
        "warehouse_id": warehouse_id,
        **{k: v for k, v in extra.items() if v is not None},
    }
    return p


def _raise_from_resp(resp: httpx.Response, fallback: str):
    detail = fallback
    try:
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("detail"):
            detail = payload["detail"]
    except Exception:
        if resp.text:
            detail = resp.text
    raise HTTPException(status_code=resp.status_code, detail=detail)


def _service_unavailable(exc: Exception):
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"ML service unavailable at {ML_SERVICE_URL}. ({type(exc).__name__})",
    )


async def _ml_get(path: str, params: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_from_resp(resp, "ML service request failed")
    return resp.json()


async def _ml_post(path: str, params: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_from_resp(resp, "ML service request failed")
    return resp.json()


async def _ml_delete(path: str, params: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_from_resp(resp, "ML service request failed")
    return resp.json()


# ── Global model ─────────────────────────────────────────────────────────────

@router.post("/train")
async def train(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_post("/portfolio/train", _params(biz, cust, wh))


@router.get("/train-progress")
async def train_progress(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/train-progress", _params(biz, cust, wh))


@router.get("/status")
async def model_status(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/status", _params(biz, cust, wh))


@router.delete("/model")
async def delete_model(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_delete("/portfolio/model", _params(biz, cust, wh))


# ── Portfolio reads ──────────────────────────────────────────────────────────

@router.get("/summary")
async def summary(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/summary", _params(biz, cust, wh, period_days=period_days))


@router.get("/insights")
async def insights(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/insights", _params(biz, cust, wh))


@router.get("/seller/{seller_id}")
async def seller_detail(
    seller_id: int,
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(f"/portfolio/seller/{seller_id}", _params(biz, cust, wh, period_days=period_days))


@router.get("/buyer/{buyer_id}")
async def buyer_detail(
    buyer_id: int,
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(f"/portfolio/buyer/{buyer_id}", _params(biz, cust, wh, period_days=period_days))


@router.get("/location-heatmap")
async def location_heatmap(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    mode: str = Query("buyer", pattern="^(buyer|seller)$"),
    period_days: int = Query(90, ge=7, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(
        "/portfolio/location-heatmap",
        _params(biz, cust, wh, mode=mode, period_days=period_days),
    )


@router.get("/sellers/metrics")
async def seller_metrics(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(
        "/portfolio/sellers/metrics",
        _params(biz, cust, wh, period_days=period_days),
    )


@router.get("/outbound-forecast")
async def outbound_forecast(
    customer_id:  int  = Query(...),
    warehouse_id: int  = Query(...),
    start_date:   date = Query(...),
    end_date:     date = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    """Day-wise, buyer-wise, location-wise, and product×buyer outbound forecast with valuations."""
    today = date.today()
    if start_date < today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="start_date must be >= today")
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="end_date must be >= start_date")
    if end_date > start_date + timedelta(days=60):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="end_date must be <= start_date + 60 days")
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(
        "/portfolio/outbound-forecast",
        _params(biz, cust, wh,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()),
    )


@router.get("/inbound-forecast")
async def inbound_forecast(
    customer_id:  int  = Query(...),
    warehouse_id: int  = Query(...),
    start_date:   date = Query(...),
    end_date:     date = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    """Inbound forecast projection per seller."""
    today = date.today()
    if start_date < today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="start_date must be >= today")
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="end_date must be >= start_date")
    if end_date > start_date + timedelta(days=60):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="end_date must be <= start_date + 60 days")
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get(
        "/portfolio/inbound-forecast",
        _params(biz, cust, wh,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()),
    )


@router.post("/cache/refresh")
async def cache_refresh(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    days_ahead: int = Query(30, ge=7, le=90),
    ctx: UserContext = Depends(get_user_context),
):
    """Trigger an immediate forecast cache + insight refresh for this scope."""
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_post(
        "/portfolio/cache/refresh",
        _params(biz, cust, wh, days_ahead=days_ahead),
    )


# ── Inbound model ─────────────────────────────────────────────────────────────

@router.post("/inbound/train")
async def inbound_train(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_post("/portfolio/inbound/train", _params(biz, cust, wh))


@router.get("/inbound/train-progress")
async def inbound_train_progress(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/inbound/train-progress", _params(biz, cust, wh))


@router.get("/inbound/status")
async def inbound_model_status(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_get("/portfolio/inbound/status", _params(biz, cust, wh))


@router.delete("/inbound/model")
async def inbound_delete_model(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    ctx: UserContext = Depends(get_user_context),
):
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_delete("/portfolio/inbound/model", _params(biz, cust, wh))


@router.post("/inbound/cache/refresh")
async def inbound_cache_refresh(
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    days_ahead: int = Query(30, ge=7, le=90),
    ctx: UserContext = Depends(get_user_context),
):
    """Trigger an immediate inbound forecast cache refresh for this scope."""
    biz, cust, wh = _resolve_scope(ctx, customer_id, warehouse_id)
    return await _ml_post(
        "/portfolio/inbound/cache/refresh",
        _params(biz, cust, wh, days_ahead=days_ahead),
    )
