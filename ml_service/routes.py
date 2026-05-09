"""
ML Service API routes.

All endpoints receive ``business_id`` and optionally ``user_id`` as query
parameters – the main backend API proxy is responsible for resolving these
from the auth token before forwarding.
"""

from __future__ import annotations

import threading
import time

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from db import (
    get_product_info,
    get_daily_aggregated_transactions,
    get_uploaded_history,
    get_model_metadata,
    get_product_tenant_ids,
    save_uploaded_history,
    delete_model_metadata,
    delete_uploaded_history,
    get_current_stock,
    get_product_replenishment_inputs,
    get_customer_outbound_history,
)
from csv_handler import generate_csv_template, parse_and_validate_csv
from trainer import train_model, delete_model as delete_model_file
from predictor import predict_demand
from replenishment import compute_replenishment

from fastapi.responses import StreamingResponse
import io

router = APIRouter(tags=["ML"])

# ── In-memory training state ─────────────────────────────────────────────────
# key: f"{product_id}_{business_id}"
_training_state: dict[str, dict] = {}
_training_lock = threading.Lock()


def _run_training_bg(product_id: int, business_id: int, key: str) -> None:
    """Background thread target: runs train_model and updates _training_state."""
    started_at = time.time()
    with _training_lock:
        _training_state[key] = {
            "status": "training",
            "phase": "initializing",
            "phase_detail": "",
            "cv_done": 0,
            "cv_total": 0,
            "started_at": started_at,
            "result": None,
            "error": None,
        }

    def _progress(phase: str, cv_done: int = 0, cv_total: int = 0, detail: str = "") -> None:
        with _training_lock:
            if key in _training_state:
                _training_state[key].update({
                    "phase": phase,
                    "phase_detail": detail,
                    "cv_done": cv_done,
                    "cv_total": cv_total,
                })

    try:
        result = train_model(product_id, business_id, progress_callback=_progress)
        with _training_lock:
            _training_state[key] = {
                "status": "ready",
                "phase": "done",
                "phase_detail": "",
                "cv_done": 0,
                "cv_total": 0,
                "started_at": started_at,
                "elapsed_seconds": round(time.time() - started_at, 1),
                "result": result,
                "error": None,
            }
    except Exception as exc:
        with _training_lock:
            _training_state[key] = {
                "status": "failed",
                "phase": "failed",
                "phase_detail": str(exc),
                "cv_done": 0,
                "cv_total": 0,
                "started_at": started_at,
                "elapsed_seconds": round(time.time() - started_at, 1),
                "result": None,
                "error": str(exc),
            }


# ── CSV Template Download ────────────────────────────────────────────────────

@router.get("/template/{product_id}")
def download_template(
    product_id: int,
    business_id: int = Query(...),
):
    """Download a pre-filled CSV template for historical data upload."""
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    csv_bytes = generate_csv_template(product["name"], product["sku_code"])

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="history_template_{product["sku_code"]}.csv"'
            )
        },
    )


# ── CSV Upload ───────────────────────────────────────────────────────────────

@router.post("/upload/{product_id}")
async def upload_history(
    product_id: int,
    file: UploadFile = File(...),
    business_id: int = Query(...),
    user_id: int = Query(0),
):
    """Upload and validate a CSV of historical inventory data."""
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    df, errors = parse_and_validate_csv(contents)

    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    # Resolve customer_id from the product (authoritative source)
    tenant = get_product_tenant_ids(product_id, business_id)
    n_rows = save_uploaded_history(
        product_id, business_id, user_id, df,
        customer_id=tenant["customer_id"],
    )

    return {
        "message": f"Successfully uploaded {n_rows} rows of historical data",
        "rows_uploaded": n_rows,
        "date_range": {
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
        },
    }


# ── Train Model ──────────────────────────────────────────────────────────────

@router.post("/train/{product_id}")
def train_product_model(
    product_id: int,
    business_id: int = Query(...),
):
    """Start async model training in a background thread. Returns 202 immediately."""
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    key = f"{product_id}_{business_id}"
    with _training_lock:
        current = _training_state.get(key, {})
        if current.get("status") == "training":
            elapsed = round(time.time() - current.get("started_at", time.time()), 1)
            return {
                "status": "training",
                "message": "Training already in progress",
                "elapsed_seconds": elapsed,
            }

    t = threading.Thread(
        target=_run_training_bg,
        args=(product_id, business_id, key),
        daemon=True,
    )
    t.start()
    return {"status": "training", "message": "Training started"}


# ── Training Progress ────────────────────────────────────────────────────────

@router.get("/train-progress/{product_id}")
def train_progress(
    product_id: int,
    business_id: int = Query(...),
):
    """Poll training progress. Returns phase, cv steps, elapsed time."""
    key = f"{product_id}_{business_id}"
    with _training_lock:
        state = dict(_training_state.get(key, {}))

    if not state:
        # No in-memory record — check the DB for a persisted status
        meta = get_model_metadata(product_id, business_id)
        return {
            "status": meta.get("status", "idle") if meta else "idle",
            "phase": "idle",
            "phase_detail": "",
            "cv_done": 0,
            "cv_total": 0,
            "elapsed_seconds": 0.0,
            "result": None,
            "error": None,
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


# ── Predict ──────────────────────────────────────────────────────────────────

@router.get("/predict/{product_id}")
def get_prediction(
    product_id: int,
    business_id: int = Query(...),
    days: int = Query(30, ge=7, le=90),
):
    """Get demand forecast for the next N days."""
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        return predict_demand(product_id, business_id, days_ahead=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Model Status ─────────────────────────────────────────────────────────────

@router.get("/status/{product_id}")
def model_status(
    product_id: int,
    business_id: int = Query(...),
):
    """Check whether a trained model exists and its metrics."""
    meta = get_model_metadata(product_id, business_id)

    if not meta:
        return {
            "has_model": False,
            "status": "no_model",
            "product_id": product_id,
        }

    return {
        "has_model": True,
        "status": meta.get("status", "ready"),
        "product_id": product_id,
        "trained_at": str(meta.get("trained_at", "")),
        "data_start": str(meta.get("data_start_date", "")),
        "data_end": str(meta.get("data_end_date", "")),
        "data_points": meta.get("total_data_points"),
        "cv_mae": float(meta["cv_mae"]) if meta.get("cv_mae") is not None else None,
        "cv_mape": float(meta["cv_mape"]) if meta.get("cv_mape") is not None else None,
        "features_used": meta.get("features_used", []),
    }


# ── Training Data Preview ───────────────────────────────────────────────────

@router.get("/training-data/{product_id}")
def training_data_preview(
    product_id: int,
    business_id: int = Query(...),
):
    """Preview available training data (auto-aggregated + uploaded counts)."""
    # Resolve customer_id for tenant-scoped queries
    tenant = get_product_tenant_ids(product_id, business_id)
    customer_id = tenant["customer_id"]

    auto_df = get_daily_aggregated_transactions(
        product_id, business_id, customer_id=customer_id,
    )
    uploaded_df = get_uploaded_history(
        product_id, business_id, customer_id=customer_id,
    )

    auto_days = len(auto_df)
    uploaded_days = len(uploaded_df)

    # Estimate combined unique days
    all_dates: set = set()
    if not auto_df.empty:
        all_dates.update(auto_df["date"].tolist())
    if not uploaded_df.empty:
        all_dates.update(uploaded_df["date"].tolist())

    return {
        "product_id": product_id,
        "auto_aggregated_days": auto_days,
        "uploaded_days": uploaded_days,
        "combined_unique_days": len(all_dates),
        "auto_date_range": {
            "start": str(auto_df["date"].min().date()) if not auto_df.empty else None,
            "end": str(auto_df["date"].max().date()) if not auto_df.empty else None,
        },
        "uploaded_date_range": {
            "start": str(uploaded_df["date"].min().date()) if not uploaded_df.empty else None,
            "end": str(uploaded_df["date"].max().date()) if not uploaded_df.empty else None,
        },
        "ready_to_train": len(all_dates) >= 30,
    }


# ── Delete Model ─────────────────────────────────────────────────────────────

# ── v2: Forecast (7d + 30d) + Replenishment ────────────────────────────────

@router.get("/forecast/v2/{product_id}")
def forecast_v2(
    product_id: int,
    business_id: int = Query(...),
    customer_id: int | None = Query(None),
):
    """v2 forecast: returns 7-day and 30-day P50 series + replenishment.

    The model itself is the existing per-product trainer (XGBoost/GBR with
    holiday + lag features). When no model exists or the product has too
    little data, we fall back to a customer-level rolling-mean heuristic
    so the customer still gets a usable recommendation.
    """
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    rep_inputs = get_product_replenishment_inputs(product_id, business_id)
    current_stock = int(rep_inputs.get("stock_at_warehouse", 0) or 0)

    # Try the trained model first.
    forecast_30: list[float] = []
    forecast_7: list[float] = []
    rolling_std_28 = 0.0
    source = "trained_model"

    try:
        pred = predict_demand(product_id, business_id, days_ahead=30)
        # predict_demand returns {predictions: [{date, predicted_outbound, ...}]}
        preds = pred.get("predictions", []) if isinstance(pred, dict) else []
        forecast_30 = [float(p.get("predicted_outbound", 0)) for p in preds[:30]]
        forecast_7 = forecast_30[:7]
    except Exception:
        forecast_30 = []
        forecast_7 = []

    if not forecast_30:
        # Fallback: use the customer's recent average daily outbound.
        if customer_id is not None:
            cdf = get_customer_outbound_history(business_id, customer_id, days=120)
            if not cdf.empty:
                # Distribute customer-level demand by product's share of recent outbound
                auto = get_daily_aggregated_transactions(product_id, business_id, customer_id)
                share = 0.0
                if not auto.empty:
                    cust_total = float(cdf["outbound_qty"].sum()) or 1.0
                    share = float(auto["outbound_qty"].sum()) / cust_total
                avg = float(cdf["outbound_qty"].mean())
                forecast_30 = [round(avg * share, 2)] * 30
                forecast_7 = forecast_30[:7]
                rolling_std_28 = float(cdf["outbound_qty"].tail(28).std() or 0)
                source = "customer_rolling_mean"

        if not forecast_30:
            # Final fallback: own product rolling mean (if anything)
            auto = get_daily_aggregated_transactions(product_id, business_id, customer_id)
            avg = float(auto["outbound_qty"].mean()) if not auto.empty else 0.0
            std = float(auto["outbound_qty"].tail(28).std() or 0) if not auto.empty else 0.0
            forecast_30 = [round(avg, 2)] * 30
            forecast_7 = forecast_30[:7]
            rolling_std_28 = std
            source = "product_rolling_mean"

    if rolling_std_28 == 0.0:
        # Use rolling std from the trained data window if available
        auto = get_daily_aggregated_transactions(product_id, business_id, customer_id)
        if not auto.empty:
            rolling_std_28 = float(auto["outbound_qty"].tail(28).std() or 0)

    repl = compute_replenishment(
        product=rep_inputs,
        forecast_horizon_30=forecast_30,
        rolling_std_28=rolling_std_28,
        current_stock=current_stock,
    )

    return {
        "product_id": product_id,
        "customer_id": customer_id,
        "source": source,
        "forecast_7d": {
            "daily": forecast_7,
            "total": round(sum(forecast_7), 2),
        },
        "forecast_30d": {
            "daily": forecast_30,
            "total": round(sum(forecast_30), 2),
        },
        "replenishment": repl,
    }


@router.delete("/model/{product_id}")
def delete_model_endpoint(
    product_id: int,
    business_id: int = Query(...),
):
    """Delete a trained model (to retrain from scratch)."""
    # Resolve customer_id for tenant-scoped operations
    tenant = get_product_tenant_ids(product_id, business_id)
    customer_id = tenant["customer_id"]

    file_deleted = delete_model_file(product_id, business_id)
    meta_deleted = delete_model_metadata(
        product_id, business_id, customer_id=customer_id,
    )

    if not file_deleted and not meta_deleted:
        raise HTTPException(status_code=404, detail="No model found for this product")

    return {"message": "Model deleted successfully", "product_id": product_id}
