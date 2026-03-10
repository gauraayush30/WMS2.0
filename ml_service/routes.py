"""
ML Service API routes.

All endpoints receive ``business_id`` and optionally ``user_id`` as query
parameters – the main backend API proxy is responsible for resolving these
from the auth token before forwarding.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from db import (
    get_product_info,
    get_daily_aggregated_transactions,
    get_uploaded_history,
    get_model_metadata,
    save_uploaded_history,
    delete_model_metadata,
    delete_uploaded_history,
)
from csv_handler import generate_csv_template, parse_and_validate_csv
from trainer import train_model, delete_model as delete_model_file
from predictor import predict_demand

from fastapi.responses import StreamingResponse
import io

router = APIRouter(tags=["ML"])


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

    n_rows = save_uploaded_history(product_id, business_id, user_id, df)

    return {
        "message": f"Successfully uploaded {n_rows} rows of historical data",
        "rows_uploaded": n_rows,
        "date_range": {
            "start": str(df["date"].min()),
            "end": str(df["date"].max()),
        },
    }


# ── Train Model ──────────────────────────────────────────────────────────────

@router.post("/train/{product_id}")
def train_product_model(
    product_id: int,
    business_id: int = Query(...),
):
    """Trigger on-demand model training for a product."""
    product = get_product_info(product_id, business_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        result = train_model(product_id, business_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    auto_df = get_daily_aggregated_transactions(product_id, business_id)
    uploaded_df = get_uploaded_history(product_id, business_id)

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
            "start": str(auto_df["date"].min()) if not auto_df.empty else None,
            "end": str(auto_df["date"].max()) if not auto_df.empty else None,
        },
        "uploaded_date_range": {
            "start": str(uploaded_df["date"].min()) if not uploaded_df.empty else None,
            "end": str(uploaded_df["date"].max()) if not uploaded_df.empty else None,
        },
        "ready_to_train": len(all_dates) >= 30,
    }


# ── Delete Model ─────────────────────────────────────────────────────────────

@router.delete("/model/{product_id}")
def delete_model_endpoint(
    product_id: int,
    business_id: int = Query(...),
):
    """Delete a trained model (to retrain from scratch)."""
    file_deleted = delete_model_file(product_id, business_id)
    meta_deleted = delete_model_metadata(product_id, business_id)

    if not file_deleted and not meta_deleted:
        raise HTTPException(status_code=404, detail="No model found for this product")

    return {"message": "Model deleted successfully", "product_id": product_id}
