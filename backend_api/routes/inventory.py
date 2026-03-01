"""
Inventory routes – overview, summary, transactions, batches.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

from auth import get_current_user_id
from db import (
    get_user_by_id,
    get_inventory_overview,
    get_inventory_summary,
    create_inventory_transaction,
    get_inventory_transactions,
    create_inventory_batch,
    get_inventory_batches,
    get_inventory_batch_detail,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_business_id(user_id: int) -> int:
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


# ── Models ───────────────────────────────────────────────────────────────────

class InventoryTransactionCreate(BaseModel):
    product_id: int = Field(..., description="Product ID")
    stock_adjusted: int = Field(..., description="Stock change (+stock_in / -stock_out)")
    reason: str = Field(..., min_length=1, max_length=100, description="stock_in, stock_out, adjustment, return, damage")
    reference_no: str = Field(default="", max_length=255)
    transaction_at: str = Field(default="", description="ISO datetime (defaults to now)")


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


# ── Overview & Summary ───────────────────────────────────────────────────────

@router.get("/overview")
def inventory_overview(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    user_id: int = Depends(get_current_user_id),
):
    """Inventory overview – all products with current stock (paginated)."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_overview(biz_id, page, per_page, search)


@router.get("/summary")
def inventory_summary(user_id: int = Depends(get_current_user_id)):
    """Dashboard summary: total products, total stock, out-of-stock count, low-stock count."""
    biz_id = _get_user_business_id(user_id)
    return get_inventory_summary(biz_id)


# ── Transactions ─────────────────────────────────────────────────────────────

@router.post("/transactions", status_code=status.HTTP_201_CREATED)
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


@router.get("/transactions")
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


# ── Batches ──────────────────────────────────────────────────────────────────

@router.post("/batches", status_code=status.HTTP_201_CREATED)
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


@router.get("/batches")
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


@router.get("/batches/{batch_id}")
def get_batch_detail_endpoint(batch_id: int, user_id: int = Depends(get_current_user_id)):
    """Get a single batch with its line items."""
    biz_id = _get_user_business_id(user_id)
    batch = get_inventory_batch_detail(batch_id, biz_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch
