print("THIS FILE IS RUNNING")

from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import joblib
import pandas as pd
from datetime import date, timedelta
from typing import Optional

import migrations
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)

# Legacy imports (prediction-related – kept but deferred)
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
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_alert_settings as db_get_alert_settings,
    set_alert_settings as db_set_alert_settings,
    get_at_risk_skus,
    # WMS 2.0 imports
    create_business,
    get_business_by_id,
    update_business,
    create_product,
    get_products_by_business,
    get_product_by_id,
    update_product,
    delete_product,
    check_skus_exist,
    get_inventory_overview,
    get_inventory_summary,
    create_inventory_transaction,
    get_inventory_transactions,
    create_inventory_batch,
    get_inventory_batches,
    get_inventory_batch_detail,
    create_user_v2,
    get_users_by_business,
    update_user_business,
    update_user_role,
)
from replenishment import ReplenishmentRecommendationEngine
from scheduler import create_scheduler, run_stock_alert_job


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks (migrations) before the app begins serving requests."""
    migrations.run_all()
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TransactionRequest(BaseModel):
    """Request body for recording a sales/purchase transaction."""
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



# REPLENISHMENT MODELS - Pydantic models for replenishment feature


class ReplenishmentSettings(BaseModel):
    """Replenishment settings for a SKU."""
    sku_id: str = Field(..., description="Stock Keeping Unit ID")
    lead_time_days: int = Field(..., ge=1, description="Days until supplier delivers order")
    min_order_qty: int = Field(..., ge=1, description="Minimum order quantity from supplier")
    reorder_point: int = Field(..., ge=0, description="Stock level that triggers reorder")
    safety_stock: int = Field(..., ge=0, description="Minimum buffer stock to maintain")
    target_stock_level: int = Field(..., ge=0, description="Desired inventory level")

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
    """Request body for updating replenishment settings."""
    lead_time_days: int = Field(..., ge=1, description="Days until supplier delivers order")
    min_order_qty: int = Field(..., ge=1, description="Minimum order quantity from supplier")
    reorder_point: int = Field(..., ge=0, description="Stock level that triggers reorder")
    safety_stock: int = Field(..., ge=0, description="Minimum buffer stock to maintain")
    target_stock_level: int = Field(..., ge=0, description="Desired inventory level")

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
    """Response model for replenishment recommendation."""
    sku_id: str
    reorder_needed: bool
    order_quantity: int
    urgency: str  # CRITICAL, HIGH, MEDIUM, LOW
    projected_stock_at_lead_time: int
    current_stock: int
    demand_during_lead_time: float
    reorder_point: int
    safety_stock: int
    target_stock_level: int
    suggested_order_date: str = None
    expected_arrival_date: str = None
    message: str


models = joblib.load("../backend/models.pkl")

FEATURES = [
    "day_of_week", "month", "day_of_month",
    "day_of_year", "is_weekend", "week_of_year",
]


def compute_at_risk_skus() -> list[dict]:
    """
    Compute at-risk SKUs using the forecast model – mirrors the
    replenishment-recommendation logic but runs across *all* SKUs.

    Steps for each SKU:
    1. Fetch current stock and replenishment settings (defaults if none).
    2. Generate a demand forecast over (lead_time + 7) days.
    3. Use ReplenishmentRecommendationEngine to decide if reorder is needed.
    4. Return only SKUs where reorder_needed is True.
    """
    all_skus = get_at_risk_skus()       # returns every SKU with settings
    today = date.today()
    at_risk: list[dict] = []

    for sku in all_skus:
        sku_id = sku["sku_id"]

        # Skip SKUs that have no trained model
        if sku_id not in models:
            continue

        model = models[sku_id]
        lead_time = sku["lead_time_days"]
        forecast_days = lead_time + 7

        # Build feature rows for the forecast window
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

        # Use the same engine as the replenishment-recommendation endpoint
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
                # Fields the frontend already expects
                "sku_id":              sku["sku_id"],
                "sku_name":            sku["sku_name"],
                "current_stock":       sku["current_stock"],
                "reorder_point":       sku["reorder_point"],
                "safety_stock":        sku["safety_stock"],
                "lead_time_days":      lead_time,
                "target_stock_level":  sku["target_stock_level"],
                # Extra forecast-driven data
                "projected_stock":     rec["projected_stock_at_lead_time"],
                "demand_during_lead_time": rec["demand_during_lead_time"],
                "order_quantity":      rec["order_quantity"],
                "urgency":             rec["urgency"],
                "message":             rec["message"],
            })

    # Sort by urgency: CRITICAL > HIGH > MEDIUM > LOW
    urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    at_risk.sort(key=lambda x: (urgency_order.get(x["urgency"], 99), x["current_stock"]))
    return at_risk


@app.get("/")
def home():
    return {"message": "Inventory Forecast API Running"}


@app.get("/skus")
def skus():
    return {"skus": get_all_skus()}


@app.get("/history")
def history(sku_id: str = Query(...), days: int = Query(7)):
    rows = db_get_history(sku_id, days)
    current_stock = get_current_stock(sku_id)
    return {"sku_id": sku_id, "days": days, "history": rows, "current_stock": current_stock}


@app.get("/forecast")
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


@app.post("/record-transaction", status_code=status.HTTP_201_CREATED)
def record_sale_purchase(transaction: TransactionRequest):
    """
    Record a sales or purchase transaction for an SKU.
    
    Updates inventory stock level based on sales and purchases.
    Returns the transaction details and updated stock information.
    
    Parameters:
    - sku_id: Stock Keeping Unit ID
    - sales_qty: Quantity sold (reduces inventory)
    - purchase_qty: Quantity purchased (increases inventory)
    - transaction_date: Date of transaction (default: today)
    """
    try:
        # Validate that at least one operation is being performed
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording transaction: {str(e)}"
        )


# ============================================================================
# REPLENISHMENT ENDPOINTS - NEW functionality for stock replenishment recommendations
# ============================================================================

@app.get("/replenishment-settings/{sku_id}")
def get_replenishment_settings_endpoint(sku_id: str):
    """
    Get replenishment settings for a SKU.
    
    Returns custom settings if configured, otherwise returns sensible defaults.
    
    Parameters:
    - sku_id: Stock Keeping Unit ID
    """
    try:
        settings = get_replenishment_settings(sku_id)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving replenishment settings: {str(e)}"
        )


@app.post("/replenishment-settings/{sku_id}", status_code=status.HTTP_201_CREATED)
def set_replenishment_settings_endpoint(sku_id: str, settings: ReplenishmentSettingsUpdate):
    """
    Set or update replenishment settings for a SKU.
    
    Parameters:
    - sku_id: Stock Keeping Unit ID
    - settings: Replenishment settings (lead_time_days, min_order_qty, reorder_point, safety_stock, target_stock_level)
    """
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving replenishment settings: {str(e)}"
        )


@app.get("/replenishment-recommendation", response_model=ReplenishmentRecommendation)
def replenishment_recommendation(sku_id: str = Query(...), days: int = Query(14)):
    """
    Generate a stock replenishment recommendation for a SKU.
    
    Analyzes current stock and forecasted demand to recommend when and how much to order.
    Takes into account supplier lead time to ensure stock availability.
    
    Parameters:
    - sku_id: Stock Keeping Unit ID
    - days: Number of days to forecast (default: 14, should be >= lead_time_days)
    
    Returns:
    - Recommendation with order quantity, urgency, and projected stock levels
    """
    try:
        # Validate SKU has a model
        if sku_id not in models:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No forecast model found for SKU '{sku_id}'"
            )
        
        # Get current stock
        current_stock = get_current_stock(sku_id)
        
        # Get replenishment settings
        rep_settings = get_replenishment_settings(sku_id)
        
        # Generate forecast (ensure we forecast far enough ahead)
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
        
        # Extract forecasted sales for the lead time period
        forecasted_demand = [max(0, float(pred)) for pred in predictions]
        
        # Calculate recommendation
        recommendation = ReplenishmentRecommendationEngine.calculate_recommendation(
            current_stock=current_stock,
            forecasted_demand_days=forecasted_demand,
            lead_time_days=rep_settings["lead_time_days"],
            min_order_qty=rep_settings["min_order_qty"],
            reorder_point=rep_settings["reorder_point"],
            safety_stock=rep_settings["safety_stock"],
            target_stock_level=rep_settings["target_stock_level"],
        )
        
        return {
            "sku_id": sku_id,
            **recommendation,
        }
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recommendation: {str(e)}"
        )
    

@app.get("/product-metrics")
def product_metrics_endpoint(start_date: str = Query(...), end_date: str = Query(...)):
    try:
        metrics = db_get_product_metrics(start_date, end_date)
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching product metrics: {str(e)}"
        )


@app.get("/reports/purchases")
def purchase_report(start_date: str = Query(...), end_date: str = Query(...)):
    """Return purchase transactions between two dates."""
    try:
        rows = db_get_purchase_report(start_date, end_date)
        return {"report": rows}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching purchase report: {str(e)}"
        )


@app.get("/reports/sales")
def sales_report(start_date: str = Query(...), end_date: str = Query(...)):
    """Return sales transactions between two dates."""
    try:
        rows = db_get_sales_report(start_date, end_date)
        return {"report": rows}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sales report: {str(e)}"
        )


@app.get("/forecast-accuracy")
def forecast_accuracy(start_date: str = Query(...), end_date: str = Query(...)):
    """
    Compare actual vs predicted sales for all SKUs in a date range.
    Uses the trained model to generate predictions for each date,
    then compares with actual sales from the database.

    Accuracy is computed using WMAPE (Weighted Mean Absolute Percentage Error):
        WMAPE = sum(|actual_i - predicted_i|) / sum(actual_i) * 100
    This is the industry-standard metric for demand forecasting.
    """
    try:
        # Get actual daily sales (aggregated per day per SKU)
        actuals = db_get_daily_actual_sales(start_date, end_date)

        # Also get the number of transactions per day per SKU so we can
        # scale the model's per-row prediction to a daily total.
        from db import get_daily_transaction_counts as db_get_daily_tx_counts

        tx_counts = db_get_daily_tx_counts(start_date, end_date)
        # tx_counts: list of {date, sku_id, tx_count}
        tx_lookup: dict[str, dict[str, int]] = {}
        for row in tx_counts:
            tx_lookup.setdefault(row["sku_id"], {})[row["date"]] = row["tx_count"]

        # Group actuals by SKU
        sku_actuals: dict[str, dict] = {}
        for row in actuals:
            sid = row["sku_id"]
            if sid not in sku_actuals:
                sku_actuals[sid] = {"sku_name": row["sku_name"], "days": {}}
            sku_actuals[sid]["days"][row["date"]] = row["actual_sales"]

        # Build date list
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

        # Build feature matrix once for all dates
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
                # The model predicts per-transaction sales. Multiply by
                # the number of transactions that day to get a daily total.
                raw_pred = max(0, float(predictions[i]))
                n_tx = sku_tx.get(date_str, 1)  # fallback to 1 if no data
                predicted = round(raw_pred * n_tx, 2)

                total_actual += actual
                total_predicted += predicted
                sum_abs_error += abs(actual - predicted)

            n_days = len(all_dates)
            mae = round(sum_abs_error / n_days, 2) if n_days else 0

            # WMAPE = sum(|actual - predicted|) / sum(actual) * 100
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing forecast accuracy: {str(e)}"
        )


# ============================================================================
# AUTH MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    business_name: str = Field(default="", description="Business name (creates new business if provided)")
    business_location: str = Field(default="", description="Business location")


class LoginRequest(BaseModel):
    email: str
    password: str


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    """Register a new user. Optionally creates a business and assigns the user to it."""
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    hashed = hash_password(req.password)

    # Create business if name provided
    business_id = None
    if req.business_name.strip():
        try:
            biz = create_business(req.business_name.strip(), req.business_location.strip() or None)
            business_id = biz["id"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating business: {str(e)}",
            )

    try:
        user = create_user_v2(
            username=req.username,
            name=req.name,
            email=req.email,
            hashed_password=hashed,
            business_id=business_id,
            role="admin" if business_id else "employee",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating account: {str(e)}",
        )
    token = create_access_token({"sub": str(user["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "email": user["email"],
            "business_id": user["business_id"],
            "role": user["role"],
        },
    }


@app.post("/auth/login")
def login(req: LoginRequest):
    """Authenticate a user. Returns a JWT token on success."""
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    token = create_access_token({"sub": str(user["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user.get("username", ""),
            "name": user["name"],
            "email": user["email"],
            "business_id": user.get("business_id"),
            "role": user.get("role", "employee"),
        },
    }


@app.get("/auth/me")
def me(user_id: int = Depends(get_current_user_id)):
    """Return the currently authenticated user's profile."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ============================================================================
# WMS 2.0 – BUSINESS ENDPOINTS
# ============================================================================

class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(default="", max_length=500)


class BusinessUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(default="", max_length=500)


@app.get("/business")
def get_business(user_id: int = Depends(get_current_user_id)):
    """Get the current user's business."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    biz = get_business_by_id(user["business_id"])
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return biz


@app.post("/business", status_code=status.HTTP_201_CREATED)
def create_business_endpoint(body: BusinessCreate, user_id: int = Depends(get_current_user_id)):
    """Create a new business and assign the user to it."""
    user = get_user_by_id(user_id)
    if user and user.get("business_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to a business")
    try:
        biz = create_business(body.name, body.location or None)
        update_user_business(user_id, biz["id"])
        return biz
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.put("/business")
def update_business_endpoint(body: BusinessUpdate, user_id: int = Depends(get_current_user_id)):
    """Update the current user's business."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    result = update_business(user["business_id"], body.name, body.location or None)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return result


# ============================================================================
# WMS 2.0 – PRODUCT ENDPOINTS
# ============================================================================

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_code: str = Field(..., min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)
    stock_at_warehouse: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_code: str = Field(..., min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)


def _get_user_business_id(user_id: int) -> int:
    """Helper: get the business_id for a user, raise 403 if none."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


@app.get("/products")
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    user_id: int = Depends(get_current_user_id),
):
    """List products for the user's business (paginated, searchable)."""
    biz_id = _get_user_business_id(user_id)
    return get_products_by_business(biz_id, page, per_page, search)


@app.post("/products", status_code=status.HTTP_201_CREATED)
def create_product_endpoint(body: ProductCreate, user_id: int = Depends(get_current_user_id)):
    """Create a new product for the user's business."""
    biz_id = _get_user_business_id(user_id)
    try:
        product = create_product(body.name, body.sku_code, biz_id, body.price, body.stock_at_warehouse)
        return product
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU code already exists")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/products/{product_id}")
def get_product_endpoint(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Get a single product by ID."""
    biz_id = _get_user_business_id(user_id)
    product = get_product_by_id(product_id, biz_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@app.put("/products/{product_id}")
def update_product_endpoint(product_id: int, body: ProductUpdate, user_id: int = Depends(get_current_user_id)):
    """Update a product."""
    biz_id = _get_user_business_id(user_id)
    try:
        result = update_product(product_id, biz_id, body.name, body.sku_code, body.price)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU code already exists")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.delete("/products/{product_id}")
def delete_product_endpoint(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete a product."""
    biz_id = _get_user_business_id(user_id)
    deleted = delete_product(product_id, biz_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"message": "Product deleted"}


class SkuCheckRequest(BaseModel):
    sku_codes: list[str] = Field(..., min_length=1, max_length=500)


@app.post("/products/check-skus")
def check_skus_endpoint(body: SkuCheckRequest, user_id: int = Depends(get_current_user_id)):
    """Check which SKU codes already exist for the user's business."""
    biz_id = _get_user_business_id(user_id)
    existing = check_skus_exist(biz_id, body.sku_codes)
    return {"existing": existing}


# ============================================================================
# WMS 2.0 – INVENTORY ENDPOINTS
# ============================================================================

class InventoryTransactionCreate(BaseModel):
    product_id: int = Field(..., description="Product ID")
    stock_adjusted: int = Field(..., description="Stock change (+stock_in / -stock_out)")
    reason: str = Field(..., min_length=1, max_length=100, description="stock_in, stock_out, adjustment, return, damage")
    reference_no: str = Field(default="", max_length=255)
    transaction_at: str = Field(default="", description="ISO datetime (defaults to now)")


@app.get("/inventory/overview")
def inventory_overview(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    user_id: int = Depends(get_current_user_id),
):
    """Inventory overview – all products with current stock (paginated)."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_overview(biz_id, page, per_page, search)


@app.get("/inventory/summary")
def inventory_summary(user_id: int = Depends(get_current_user_id)):
    """Dashboard summary: total products, total stock, out-of-stock count, low-stock count."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_summary(biz_id)


@app.post("/inventory/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction_endpoint(body: InventoryTransactionCreate, user_id: int = Depends(get_current_user_id)):
    """Record a new inventory transaction (stock in, stock out, etc.)."""
    biz_id = _get_user_business_id(user_id)
    try:
        result = create_inventory_transaction(
            product_id=body.product_id,
            business_id=biz_id,
            created_by=user_id,
            stock_adjusted=body.stock_adjusted,
            reason=body.reason,
            reference_no=body.reference_no or None,
            transaction_at=body.transaction_at or None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/inventory/transactions")
def list_transactions(
    product_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    """List inventory transactions (paginated, filterable by product & date range)."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_transactions(biz_id, product_id, page, per_page, start_date, end_date)


# ── Inventory Batches ────────────────────────────────────────────────────────

class BatchLineItem(BaseModel):
    product_id: int = Field(..., description="Product ID")
    stock_adjusted: int = Field(..., description="Stock change (+in / -out)")


class InventoryBatchCreate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=100,
                        description="delivery, shipment, adjustment, return, damage, transfer")
    reference_no: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=1000)
    items: list[BatchLineItem] = Field(..., min_length=1, description="Line items")
    transaction_at: str = Field(default="", description="ISO datetime (defaults to now)")


@app.post("/inventory/batches", status_code=status.HTTP_201_CREATED)
def create_batch_endpoint(body: InventoryBatchCreate, user_id: int = Depends(get_current_user_id)):
    """Create a batch inventory transaction grouping multiple product adjustments."""
    biz_id = _get_user_business_id(user_id)
    try:
        result = create_inventory_batch(
            business_id=biz_id,
            created_by=user_id,
            reason=body.reason,
            items=[item.dict() for item in body.items],
            reference_no=body.reference_no or None,
            notes=body.notes,
            transaction_at=body.transaction_at or None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/inventory/batches")
def list_batches(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    reason: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    """List inventory batches (paginated, filterable)."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_batches(biz_id, page, per_page, start_date, end_date, reason)


@app.get("/inventory/batches/{batch_id}")
def get_batch_detail_endpoint(batch_id: int, user_id: int = Depends(get_current_user_id)):
    """Get a single batch with its line items."""
    biz_id = _get_user_business_id(user_id)
    batch = get_inventory_batch_detail(batch_id, biz_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


# ============================================================================
# WMS 2.0 – USERS / EMPLOYEES ENDPOINTS
# ============================================================================

class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="admin, manager, or employee")


@app.get("/users")
def list_users(user_id: int = Depends(get_current_user_id)):
    """List all users in the same business."""
    biz_id = _get_user_business_id(user_id)
    return {"users": get_users_by_business(biz_id)}


@app.put("/users/{target_user_id}/role")
def update_user_role_endpoint(target_user_id: int, body: UserRoleUpdate, user_id: int = Depends(get_current_user_id)):
    """Update role of a user in the same business."""
    biz_id = _get_user_business_id(user_id)
    if body.role not in ("admin", "manager", "employee"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    result = update_user_role(target_user_id, body.role, biz_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this business")
    return result


# ============================================================================
# ALERT ENDPOINTS (legacy)
# ============================================================================

@app.get("/alerts/settings")
def get_alert_settings_endpoint(user_id: int = Depends(get_current_user_id)):
    """Get the current user's alert settings."""
    try:
        return db_get_alert_settings(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching alert settings: {str(e)}",
        )


class AlertSettingsUpdate(BaseModel):
    alerts_enabled: bool


@app.post("/alerts/settings")
def set_alert_settings_endpoint(
    body: AlertSettingsUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Enable or disable stock alerts for the current user."""
    try:
        return db_set_alert_settings(user_id, body.alerts_enabled)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving alert settings: {str(e)}",
        )


@app.get("/alerts/at-risk")
def at_risk_skus(user_id: int = Depends(get_current_user_id)):
    """Return SKUs that are at risk based on forecasted demand."""
    try:
        return {"at_risk": compute_at_risk_skus()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching at-risk SKUs: {str(e)}",
        )


@app.post("/alerts/send-now", status_code=status.HTTP_202_ACCEPTED)
async def send_alerts_now(user_id: int = Depends(get_current_user_id)):
    """Manually trigger the alert job immediately (useful for testing)."""
    import asyncio
    asyncio.create_task(run_stock_alert_job())
    return {"message": "Alert job triggered"}
