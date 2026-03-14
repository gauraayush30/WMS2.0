"""
ML Proxy routes – forwards forecast/ML requests to the ML microservice
while keeping authentication centralized in the main API.

All endpoints live under /products/{product_id}/forecast/…
"""

import io
import os

import httpx
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse

from auth import get_current_user_id
from db import get_user_by_id

router = APIRouter(prefix="/products/{product_id}/forecast", tags=["ML Forecast"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8100")

# Shared timeout config for ML service calls (training can be slow)
_TIMEOUT = httpx.Timeout(timeout=120.0, connect=10.0)

_TEMPLATE_HEADER = "date,inbound,outbound,stock_on_hand\n"
_TEMPLATE_SAMPLE = "2026-01-01,0,12,120\n"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_context(user_id: int) -> tuple[int, int]:
    """Return (user_id, business_id) or raise 403."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["id"], user["business_id"]


def _raise_proxy_http_error(resp: httpx.Response, fallback_message: str):
    """Raise an HTTPException by preserving upstream status/details when possible."""
    detail = fallback_message
    try:
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("detail"):
            detail = payload["detail"]
    except Exception:
        if resp.text:
            detail = resp.text
    raise HTTPException(status_code=resp.status_code, detail=detail)


def _raise_service_unavailable(exc: Exception):
    """Return a clear 503 error when the ML service is unreachable."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            f"ML service is unavailable at {ML_SERVICE_URL}. "
            f"Start/restart the ML service and retry. ({type(exc).__name__})"
        ),
    )


async def _proxy_get(path: str, business_id: int, extra_params: dict | None = None):
    """Forward a GET request to the ML service."""
    params = {"business_id": business_id, **(extra_params or {})}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _raise_service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_proxy_http_error(resp, "ML service request failed")
    return resp.json()


async def _proxy_post(path: str, business_id: int, user_id: int, extra_params: dict | None = None):
    """Forward a POST request to the ML service."""
    params = {"business_id": business_id, "user_id": user_id, **(extra_params or {})}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _raise_service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_proxy_http_error(resp, "ML service request failed")
    return resp.json()


async def _proxy_delete(path: str, business_id: int):
    """Forward a DELETE request to the ML service."""
    params = {"business_id": business_id}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(f"{ML_SERVICE_URL}{path}", params=params)
    except httpx.RequestError as exc:
        _raise_service_unavailable(exc)
    if resp.status_code >= 400:
        _raise_proxy_http_error(resp, "ML service request failed")
    return resp.json()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
async def forecast_status(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Check model status for a product."""
    _, biz_id = _get_user_context(user_id)
    return await _proxy_get(f"/status/{product_id}", biz_id)


@router.get("/training-data")
async def forecast_training_data(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Preview available training data."""
    _, biz_id = _get_user_context(user_id)
    return await _proxy_get(f"/training-data/{product_id}", biz_id)


@router.get("/template")
async def forecast_download_template(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Download CSV template for historical data upload."""
    _, biz_id = _get_user_context(user_id)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{ML_SERVICE_URL}/template/{product_id}",
                params={"business_id": biz_id},
            )
        if resp.status_code >= 400:
            _raise_proxy_http_error(resp, "Failed to generate template")

        return StreamingResponse(
            iter([resp.content]),
            media_type=resp.headers.get("content-type", "text/csv"),
            headers={
                "Content-Disposition": resp.headers.get(
                    "content-disposition",
                    f'attachment; filename="history_template_{product_id}.csv"',
                )
            },
        )
    except httpx.RequestError:
        # Fallback template keeps UX working even if the ML service is down.
        csv_content = _TEMPLATE_HEADER + _TEMPLATE_SAMPLE
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="history_template_{product_id}.csv"',
                "X-Template-Source": "backend-fallback",
            },
        )


@router.post("/upload")
async def forecast_upload_history(
    product_id: int,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    """Upload CSV historical data for a product."""
    uid, biz_id = _get_user_context(user_id)
    contents = await file.read()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{ML_SERVICE_URL}/upload/{product_id}",
                params={"business_id": biz_id, "user_id": uid},
                files={"file": (file.filename, contents, file.content_type or "text/csv")},
            )
    except httpx.RequestError as exc:
        _raise_service_unavailable(exc)

    if resp.status_code >= 400:
        _raise_proxy_http_error(resp, "ML upload failed")
    return resp.json()


@router.post("/train")
async def forecast_train(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Trigger on-demand model training for a product."""
    uid, biz_id = _get_user_context(user_id)
    return await _proxy_post(f"/train/{product_id}", biz_id, uid)


@router.get("/predict")
async def forecast_predict(
    product_id: int,
    days: int = Query(30, ge=7, le=90),
    user_id: int = Depends(get_current_user_id),
):
    """Get demand forecast predictions."""
    _, biz_id = _get_user_context(user_id)
    return await _proxy_get(f"/predict/{product_id}", biz_id, {"days": days})


@router.delete("/model")
async def forecast_delete_model(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete trained model to retrain from scratch."""
    _, biz_id = _get_user_context(user_id)
    return await _proxy_delete(f"/model/{product_id}", biz_id)
