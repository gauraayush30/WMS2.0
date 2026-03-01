"""
Legacy routes – forecast, replenishment, reports, alerts.
These endpoints predate the WMS 2.0 schema and work with the legacy
inventory_sales table.
"""

import asyncio
from datetime import date, timedelta

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_all_skus,
    get_history as db_get_history,
    get_current_stock,
    record_transaction,
    get_replenishment_settings,
    set_replenishment_settings,
    get_product_metrics as db_get_product_metrics,
    get_purchase_report as db_get_purchase_report,
    get_sales_report as db_get_sales_report,
    get_daily_actual_sales as db_get_daily_actual_sales,
    get_alert_settings as db_get_alert_settings,
    set_alert_settings as db_set_alert_settings,
    get_at_risk_skus,
)
from replenishment import ReplenishmentRecommendationEngine
from scheduler import run_stock_alert_job

router = APIRouter(tags=["Legacy"])


# ── Load ML models ───────────────────────────────────────────────────────────

models = joblib.load("../backend/models.pkl")

FEATURES = [
    "day_of_week", "month", "day_of_month",
    "day_of_year", "is_weekend", "week_of_year",
]


# ── Pydantic models ─────────────────────────────────────────────────────────

class TransactionRequest(BaseModel):
    sku_id: str = Field(..., description="Stock Keeping Unit ID")
    sales_qty: int = Field(default=0, ge=0, description="Quantity sold")
    purchase_qty: int = Field(default=0, ge=0, description="Quantity purchased")
    transaction_date: str = Field(default_factory=lambda: str(date.today()), description="Transaction date (YYYY-MM-DD)")

    class Config:
        schema_extra = {
            "example": {
                "sku_id": "SKU001",
                "sales_qty": 5,
                "purchase_qty": 10,
                "transaction_date": "2026-02-14"
            }
        }


class ReplenishmentSettings(BaseModel):
    sku_id: str = Field(...)
    lead_time_days: int = Field(..., ge=1)
    min_order_qty: int = Field(..., ge=1)
    reorder_point: int = Field(..., ge=0)
    safety_stock: int = Field(..., ge=0)
    target_stock_level: int = Field(..., ge=0)

    class Config:
        schema_extra = {
            "example": {
                "sku_id": "SKU001",
                "lead_time_days": 7,
                "min_order_qty": 10,
                "reorder_point": 50,
                "safety_stock": 25,
                "target_stock_level": 150,
            }
        }


class ReplenishmentSettingsUpdate(BaseModel):
    lead_time_days: int = Field(..., ge=1)
    min_order_qty: int = Field(..., ge=1)
    reorder_point: int = Field(..., ge=0)
    safety_stock: int = Field(..., ge=0)
    target_stock_level: int = Field(..., ge=0)

    class Config:
        schema_extra = {
            "example": {
                "lead_time_days": 7,
                "min_order_qty": 10,
                "reorder_point": 50,
                "safety_stock": 25,
                "target_stock_level": 150,
            }
        }


class ReplenishmentRecommendation(BaseModel):
    sku_id: str
    reorder_needed: bool
    order_quantity: int
    urgency: str
    projected_stock_at_lead_time: int
    current_stock: int
    demand_during_lead_time: float
    reorder_point: int
    safety_stock: int
    target_stock_level: int
    suggested_order_date: str = None
    expected_arrival_date: str = None
    message: str


class AlertSettingsUpdate(BaseModel):
    alerts_enabled: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def compute_at_risk_skus() -> list[dict]:
    """Compute at-risk SKUs using the forecast model."""
    all_skus = get_at_risk_skus()
    today = date.today()
    at_risk: list[dict] = []

    for sku in all_skus:
        sku_id = sku["sku_id"]
        if sku_id not in models:
            continue

        model = models[sku_id]
        lead_time = sku["lead_time_days"]
        forecast_days = lead_time + 7

        future_dates = [today + timedelta(days=i) for i in range(1, forecast_days + 1)]
        rows = []
        for d in future_dates:
            rows.append({
                "day_of_week":  d.weekday(),
                "month":        d.month,
                "day_of_month": d.day,
                "day_of_year":  d.timetuple().tm_yday,
                "is_weekend":   1 if d.weekday() >= 5 else 0,
                "week_of_year": d.isocalendar()[1],
            })

        X_future = pd.DataFrame(rows)[FEATURES]
        predictions = model.predict(X_future)
        forecasted_demand = [max(0, float(p)) for p in predictions]

        rec = ReplenishmentRecommendationEngine.calculate_recommendation(
            current_stock=sku["current_stock"],
            forecasted_demand_days=forecasted_demand,
            lead_time_days=lead_time,
            min_order_qty=sku["min_order_qty"],
            reorder_point=sku["reorder_point"],
            safety_stock=sku["safety_stock"],
            target_stock_level=sku["target_stock_level"],
        )

        if rec["reorder_needed"]:
            at_risk.append({
                "sku_id":              sku["sku_id"],
                "sku_name":            sku["sku_name"],
                "current_stock":       sku["current_stock"],
                "reorder_point":       sku["reorder_point"],
                "safety_stock":        sku["safety_stock"],
                "lead_time_days":      lead_time,
                "target_stock_level":  sku["target_stock_level"],
                "projected_stock":     rec["projected_stock_at_lead_time"],
                "demand_during_lead_time": rec["demand_during_lead_time"],
                "order_quantity":      rec["order_quantity"],
                "urgency":             rec["urgency"],
                "message":             rec["message"],
            })

    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    at_risk.sort(key=lambda x: (urgency_order.get(x["urgency"], 99), x["current_stock"]))
    return at_risk


# ── Root ─────────────────────────────────────────────────────────────────────

@router.get("/")
def home():
    return {"message": "Inventory Forecast API Running"}


# ── SKU & History ────────────────────────────────────────────────────────────

@router.get("/skus")
def skus():
    return {"skus": get_all_skus()}


@router.get("/history")
def history(sku_id: str = Query(...), days: int = Query(7)):
    rows = db_get_history(sku_id, days)
    current_stock = get_current_stock(sku_id)
    return {"sku_id": sku_id, "days": days, "history": rows, "current_stock": current_stock}


# ── Forecast ─────────────────────────────────────────────────────────────────

@router.get("/forecast")
def forecast(sku_id: str = Query(...), days: int = Query(7)):
    if sku_id not in models:
        return {"error": f"No model found for {sku_id}"}

    model = models[sku_id]
    today = date.today()

    future_dates = [today + timedelta(days=i) for i in range(1, days + 1)]
    rows = []
    for d in future_dates:
        rows.append({
            "day_of_week":  d.weekday(),
            "month":        d.month,
            "day_of_month": d.day,
            "day_of_year":  d.timetuple().tm_yday,
            "is_weekend":   1 if d.weekday() >= 5 else 0,
            "week_of_year": d.isocalendar()[1],
        })

    X_future = pd.DataFrame(rows)[FEATURES]
    predictions = model.predict(X_future)

    result = []
    total_demand = 0
    for i, d in enumerate(future_dates):
        sales = max(0, round(float(predictions[i]), 2))
        total_demand += sales
        result.append({
            "date": d.strftime("%Y-%m-%d"),
            "predicted_sales": sales,
        })

    current_stock = get_current_stock(sku_id)
    if current_stock < total_demand:
        stock_status = "REORDER NOW"
    elif current_stock < total_demand * 1.2:
        stock_status = "LOW STOCK"
    else:
        stock_status = "STOCK OK"

    return {
        "sku_id": sku_id,
        "current_stock": current_stock,
        "total_forecast_demand": round(total_demand, 2),
        "stock_status": stock_status,
        "forecast": result,
    }


# ── Record Transaction ──────────────────────────────────────────────────────

@router.post("/record-transaction", status_code=status.HTTP_201_CREATED)
def record_sale_purchase(transaction: TransactionRequest):
    try:
        if transaction.sales_qty == 0 and transaction.purchase_qty == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either sales_qty or purchase_qty must be greater than 0"
            )
        result = record_transaction(
            sku_id=transaction.sku_id,
            sales_qty=transaction.sales_qty,
            purchase_qty=transaction.purchase_qty,
            transaction_date=transaction.transaction_date
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error recording transaction: {str(e)}")


# ── Replenishment ────────────────────────────────────────────────────────────

@router.get("/replenishment-settings/{sku_id}")
def get_replenishment_settings_endpoint(sku_id: str):
    try:
        settings = get_replenishment_settings(sku_id)
        return settings
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving replenishment settings: {str(e)}")


@router.post("/replenishment-settings/{sku_id}", status_code=status.HTTP_201_CREATED)
def set_replenishment_settings_endpoint(sku_id: str, settings: ReplenishmentSettingsUpdate):
    try:
        settings_dict = {
            "lead_time_days": settings.lead_time_days,
            "min_order_qty": settings.min_order_qty,
            "reorder_point": settings.reorder_point,
            "safety_stock": settings.safety_stock,
            "target_stock_level": settings.target_stock_level,
        }
        result = set_replenishment_settings(sku_id, settings_dict)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving replenishment settings: {str(e)}")


@router.get("/replenishment-recommendation", response_model=ReplenishmentRecommendation)
def replenishment_recommendation(sku_id: str = Query(...), days: int = Query(14)):
    try:
        if sku_id not in models:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No forecast model found for SKU '{sku_id}'")

        current_stock = get_current_stock(sku_id)
        rep_settings = get_replenishment_settings(sku_id)

        forecast_days = max(days, rep_settings["lead_time_days"] + 7)
        model = models[sku_id]
        today = date.today()

        future_dates = [today + timedelta(days=i) for i in range(1, forecast_days + 1)]
        rows = []
        for d in future_dates:
            rows.append({
                "day_of_week": d.weekday(),
                "month": d.month,
                "day_of_month": d.day,
                "day_of_year": d.timetuple().tm_yday,
                "is_weekend": 1 if d.weekday() >= 5 else 0,
                "week_of_year": d.isocalendar()[1],
            })

        X_future = pd.DataFrame(rows)[FEATURES]
        predictions = model.predict(X_future)
        forecasted_demand = [max(0, float(pred)) for pred in predictions]

        recommendation = ReplenishmentRecommendationEngine.calculate_recommendation(
            current_stock=current_stock,
            forecasted_demand_days=forecasted_demand,
            lead_time_days=rep_settings["lead_time_days"],
            min_order_qty=rep_settings["min_order_qty"],
            reorder_point=rep_settings["reorder_point"],
            safety_stock=rep_settings["safety_stock"],
            target_stock_level=rep_settings["target_stock_level"],
        )

        return {"sku_id": sku_id, **recommendation}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating recommendation: {str(e)}")


# ── Reports / Metrics ────────────────────────────────────────────────────────

@router.get("/product-metrics")
def product_metrics_endpoint(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        metrics = db_get_product_metrics(start_date, end_date)
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching product metrics: {str(e)}")


@router.get("/reports/purchases")
def purchase_report(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        rows = db_get_purchase_report(start_date, end_date)
        return {"report": rows}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching purchase report: {str(e)}")


@router.get("/reports/sales")
def sales_report(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        rows = db_get_sales_report(start_date, end_date)
        return {"report": rows}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching sales report: {str(e)}")


@router.get("/forecast-accuracy")
def forecast_accuracy(start_date: str = Query(...), end_date: str = Query(...)):
    """Compare actual vs predicted sales for all SKUs in a date range."""
    try:
        actuals = db_get_daily_actual_sales(start_date, end_date)

        from db import get_daily_transaction_counts as db_get_daily_tx_counts

        tx_counts = db_get_daily_tx_counts(start_date, end_date)
        tx_lookup: dict[str, dict[str, int]] = {}
        for row in tx_counts:
            tx_lookup.setdefault(row["sku_id"], {})[row["date"]] = row["tx_count"]

        sku_actuals: dict[str, dict] = {}
        for row in actuals:
            sid = row["sku_id"]
            if sid not in sku_actuals:
                sku_actuals[sid] = {"sku_name": row["sku_name"], "days": {}}
            sku_actuals[sid]["days"][row["date"]] = row["actual_sales"]

        from datetime import datetime
        d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        all_dates = []
        d = d_start
        while d <= d_end:
            all_dates.append(d)
            d += timedelta(days=1)

        if not all_dates:
            return {"comparison": []}

        feature_rows = []
        for d in all_dates:
            feature_rows.append({
                "day_of_week":  d.weekday(),
                "month":        d.month,
                "day_of_month": d.day,
                "day_of_year":  d.timetuple().tm_yday,
                "is_weekend":   1 if d.weekday() >= 5 else 0,
                "week_of_year": d.isocalendar()[1],
            })
        X = pd.DataFrame(feature_rows)[FEATURES]

        results = []
        for sku_id, info in sku_actuals.items():
            if sku_id not in models:
                continue

            model = models[sku_id]
            predictions = model.predict(X)

            total_actual = 0
            total_predicted = 0
            sum_abs_error = 0

            sku_tx = tx_lookup.get(sku_id, {})

            for i, d in enumerate(all_dates):
                date_str = d.strftime("%Y-%m-%d")
                actual = info["days"].get(date_str, 0)
                raw_pred = max(0, float(predictions[i]))
                n_tx = sku_tx.get(date_str, 1)
                predicted = round(raw_pred * n_tx, 2)

                total_actual += actual
                total_predicted += predicted
                sum_abs_error += abs(actual - predicted)

            n_days = len(all_dates)
            mae = round(sum_abs_error / n_days, 2) if n_days else 0

            if total_actual > 0:
                wmape = round(sum_abs_error / total_actual * 100, 2)
            else:
                wmape = 0.0 if total_predicted == 0 else 100.0

            accuracy = round(max(0, 100 - wmape), 2)

            results.append({
                "sku_id": sku_id,
                "sku_name": info["sku_name"],
                "total_actual_sales": total_actual,
                "total_predicted_sales": round(total_predicted, 2),
                "mae": mae,
                "mape": wmape,
                "accuracy_pct": accuracy,
            })

        results.sort(key=lambda x: x["accuracy_pct"], reverse=True)
        return {"comparison": results}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error computing forecast accuracy: {str(e)}")


# ── Alerts ───────────────────────────────────────────────────────────────────

@router.get("/alerts/settings")
def get_alert_settings_endpoint(user_id: int = Depends(get_current_user_id)):
    try:
        return db_get_alert_settings(user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching alert settings: {str(e)}")


@router.post("/alerts/settings")
def set_alert_settings_endpoint(body: AlertSettingsUpdate, user_id: int = Depends(get_current_user_id)):
    try:
        return db_set_alert_settings(user_id, body.alerts_enabled)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving alert settings: {str(e)}")


@router.get("/alerts/at-risk")
def at_risk_skus(user_id: int = Depends(get_current_user_id)):
    try:
        return {"at_risk": compute_at_risk_skus()}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error fetching at-risk SKUs: {str(e)}")


@router.post("/alerts/send-now", status_code=status.HTTP_202_ACCEPTED)
async def send_alerts_now(user_id: int = Depends(get_current_user_id)):
    asyncio.create_task(run_stock_alert_job())
    return {"message": "Alert job triggered"}
