"""
Portfolio + global-model HTTP endpoints.

All endpoints expect (business_id, customer_id, warehouse_id) as query params
— the backend_api proxy resolves these from the authenticated user before
forwarding.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Query

from db import (
    get_global_model_metadata,
    get_insights,
    get_forecast_cache,
    save_forecast_cache,
    save_insights,
)
from global_trainer import train_global_model, delete_global_model
from global_predictor import predict_global
from portfolio import (
    get_portfolio_summary,
    get_seller_detail,
    get_buyer_detail,
    get_location_heatmap,
)
from insights import compute_portfolio_insights
from seller_analytics import compute_seller_metrics

router = APIRouter(prefix="/portfolio", tags=["ML Portfolio"])

# ── In-memory training state (per customer-warehouse) ───────────────────────
_g_state: dict[str, dict] = {}
_g_lock = threading.Lock()


def _key(biz: int, cust: int, wh: int) -> str:
    return f"{biz}:{cust}:{wh}"


def _run_global_training_bg(biz: int, cust: int, wh: int, key: str) -> None:
    started = time.time()
    with _g_lock:
        _g_state[key] = {
            "status": "training", "phase": "initializing",
            "phase_detail": "", "started_at": started,
            "result": None, "error": None,
        }

    def _p(phase, done=0, total=0, detail=""):
        with _g_lock:
            if key in _g_state:
                _g_state[key].update({
                    "phase": phase, "phase_detail": detail,
                    "cv_done": done, "cv_total": total,
                })

    try:
        result = train_global_model(biz, cust, wh, progress_callback=_p)
        with _g_lock:
            _g_state[key] = {
                "status": "ready", "phase": "done", "phase_detail": "",
                "started_at": started,
                "elapsed_seconds": round(time.time() - started, 1),
                "result": result, "error": None,
            }
    except Exception as exc:
        with _g_lock:
            _g_state[key] = {
                "status": "failed", "phase": "failed",
                "phase_detail": str(exc), "started_at": started,
                "elapsed_seconds": round(time.time() - started, 1),
                "result": None, "error": str(exc),
            }


# ── Global model train / status ─────────────────────────────────────────────

@router.post("/train")
def train(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
):
    """Start async training of the global model for this customer-warehouse."""
    key = _key(business_id, customer_id, warehouse_id)
    with _g_lock:
        current = _g_state.get(key, {})
        if current.get("status") == "training":
            return {
                "status": "training",
                "message": "Training already in progress",
                "elapsed_seconds": round(time.time() - current["started_at"], 1),
            }
    t = threading.Thread(
        target=_run_global_training_bg,
        args=(business_id, customer_id, warehouse_id, key),
        daemon=True,
    )
    t.start()
    return {"status": "training", "message": "Global model training started"}


@router.get("/train-progress")
def train_progress(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
):
    key = _key(business_id, customer_id, warehouse_id)
    with _g_lock:
        state = dict(_g_state.get(key, {}))
    if not state:
        meta = get_global_model_metadata(business_id, customer_id, warehouse_id)
        return {
            "status": meta.get("status", "idle") if meta else "idle",
            "phase": "idle", "phase_detail": "",
            "cv_done": 0, "cv_total": 0, "elapsed_seconds": 0.0,
            "result": None, "error": None,
        }
    elapsed = (
        round(time.time() - state["started_at"], 1)
        if state.get("status") == "training"
        else state.get("elapsed_seconds", 0.0)
    )
    return {
        "status": state["status"],
        "phase": state.get("phase", ""),
        "phase_detail": state.get("phase_detail", ""),
        "cv_done": state.get("cv_done", 0),
        "cv_total": state.get("cv_total", 0),
        "elapsed_seconds": elapsed,
        "result": state.get("result"),
        "error": state.get("error"),
    }


@router.get("/status")
def model_status(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
):
    meta = get_global_model_metadata(business_id, customer_id, warehouse_id)
    if not meta:
        return {"has_model": False, "status": "no_model"}
    return {
        "has_model": True,
        "status": meta.get("status", "ready"),
        "trained_at": meta["trained_at"].isoformat() if meta.get("trained_at") else None,
        "data_start": meta["data_start_date"].isoformat() if meta.get("data_start_date") else None,
        "data_end": meta["data_end_date"].isoformat() if meta.get("data_end_date") else None,
        "n_products": meta.get("n_products"),
        "n_buyers": meta.get("n_buyers"),
        "cv_mae": float(meta["cv_mae"]) if meta.get("cv_mae") is not None else None,
        "cv_mape": float(meta["cv_mape"]) if meta.get("cv_mape") is not None else None,
    }


@router.delete("/model")
def delete_model(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
):
    existed = delete_global_model(business_id, customer_id, warehouse_id)
    return {"deleted": existed}


# ── Portfolio reads (cache-backed) ──────────────────────────────────────────

@router.get("/summary")
def summary(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
):
    try:
        return get_portfolio_summary(business_id, customer_id, warehouse_id, period_days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"summary failed: {exc}")


@router.get("/insights")
def insights(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
):
    return {"insights": get_insights(business_id, customer_id, warehouse_id)}


@router.get("/seller/{seller_id}")
def seller_detail(
    seller_id: int,
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
):
    return get_seller_detail(business_id, customer_id, warehouse_id, seller_id, period_days)


@router.get("/buyer/{buyer_id}")
def buyer_detail(
    buyer_id: int,
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
):
    return get_buyer_detail(business_id, customer_id, warehouse_id, buyer_id, period_days)


@router.get("/location-heatmap")
def location_heatmap(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    mode: str = Query("buyer", pattern="^(buyer|seller)$"),
    period_days: int = Query(90, ge=7, le=365),
):
    return get_location_heatmap(business_id, customer_id, warehouse_id, mode, period_days)


@router.get("/sellers/metrics")
def seller_metrics(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    period_days: int = Query(90, ge=7, le=365),
):
    return {"sellers": compute_seller_metrics(
        business_id, customer_id, days_lookback=period_days,
    )}


# ── Cache refresh (manual trigger; also called by nightly job) ──────────────

@router.post("/cache/refresh")
def cache_refresh(
    business_id: int = Query(...),
    customer_id: int = Query(...),
    warehouse_id: int = Query(...),
    days_ahead: int = Query(30, ge=7, le=90),
):
    """Run inference and re-populate the forecast cache + insights for this scope.

    Cheaper than retraining; suitable for daily refresh. Returns cache row count.
    """
    try:
        result = predict_global(
            business_id, customer_id, warehouse_id,
            days_ahead=days_ahead, include_aggregate=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rows = []
    for _, r in result.iterrows():
        bid = r.get("buyer_id")
        rows.append({
            "product_id": int(r["product_id"]),
            "buyer_id": (None if (bid is None or (isinstance(bid, float) and __import__("math").isnan(bid))) else int(bid)),
            "forecast_date": r["date"],
            "p10": float(r["p10"]),
            "p50": float(r["p50"]),
            "p90": float(r["p90"]),
        })
    saved = save_forecast_cache(business_id, customer_id, warehouse_id, rows)

    # Recompute insights now that fresh forecasts are in cache
    insights_list = compute_portfolio_insights(business_id, customer_id, warehouse_id)
    save_insights(business_id, customer_id, warehouse_id, insights_list)

    return {
        "rows_cached": saved,
        "insights": len(insights_list),
        "days_ahead": days_ahead,
    }
