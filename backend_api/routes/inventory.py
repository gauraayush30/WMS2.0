"""
Inventory routes – overview, summary, transactions, batches.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional

from auth import get_current_user_id, get_user_context, UserContext
from db import (
    get_user_by_id,
    get_inventory_overview,
    get_inventory_summary,
    create_inventory_transaction,
    get_inventory_transactions,
    create_inventory_batch,
    get_inventory_batches,
    get_inventory_batch_detail,
    get_product_by_id,
    create_stock_batch,
    consume_stock_batches,
)

from datetime import datetime, timedelta

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ── Helpers ──────────────────────────────────────────────────────────────────

# _get_user_business_id is no longer needed here as we use UserContext


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
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Inventory overview – all products with current stock (paginated)."""
    cust = ctx.resolve_customer_filter(customer_id)
    return get_inventory_overview(ctx.business_id, cust, page, per_page, search)


@router.get("/summary")
def inventory_summary(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Dashboard summary: total products, total stock, out-of-stock count, low-stock count."""
    cust = ctx.resolve_customer_filter(customer_id)
    return get_inventory_summary(ctx.business_id, cust)


# ── Transactions ─────────────────────────────────────────────────────────────

@router.post("/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction_endpoint(
    body: InventoryTransactionCreate,
    ctx: UserContext = Depends(get_user_context),
):
    """Record a new inventory transaction (stock in, stock out, etc.)."""
    biz_id = ctx.business_id
    user_id = ctx.user_id
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
        # Auto-create stock batch for stock-in when product has expiry tracking
        if body.stock_adjusted > 0 and body.reason in ("stock_in", "delivery"):
            product = get_product_by_id(body.product_id, biz_id)
            if product and product.get("expiry_days", 0) > 0:
                tx_date = body.transaction_at or datetime.now().isoformat()
                try:
                    purchased_dt = datetime.fromisoformat(tx_date.replace("Z", "+00:00"))
                except ValueError:
                    purchased_dt = datetime.now()
                expires_dt = (purchased_dt + timedelta(days=product["expiry_days"])).strftime("%Y-%m-%d")
                create_stock_batch(
                    product_id=body.product_id,
                    business_id=biz_id,
                    quantity=body.stock_adjusted,
                    purchased_at=tx_date or None,
                    expires_at=expires_dt,
                    transaction_id=result.get("id"),
                )
        # FIFO consume from batches for stock-out
        elif body.stock_adjusted < 0 and body.reason in ("stock_out", "shipment"):
            consume_stock_batches(body.product_id, biz_id, abs(body.stock_adjusted))
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
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """List inventory transactions (paginated, filterable by product & date range)."""
    cust = ctx.resolve_customer_filter(customer_id)
    return get_inventory_transactions(ctx.business_id, product_id, page, per_page, start_date, end_date, cust)


# ── Batches ──────────────────────────────────────────────────────────────────

@router.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch_endpoint(
    body: InventoryBatchCreate,
    ctx: UserContext = Depends(get_user_context),
):
    """Create a batch inventory transaction grouping multiple product adjustments."""
    biz_id = ctx.business_id
    user_id = ctx.user_id
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
        # Auto-create stock batches for stock-in items when product has expiry tracking
        if body.reason in ("delivery", "stock_in"):
            for item in body.items:
                if item.stock_adjusted > 0:
                    product = get_product_by_id(item.product_id, biz_id)
                    if product and product.get("expiry_days", 0) > 0:
                        tx_date = body.transaction_at or datetime.now().isoformat()
                        try:
                            purchased_dt = datetime.fromisoformat(tx_date.replace("Z", "+00:00"))
                        except ValueError:
                            purchased_dt = datetime.now()
                        expires_dt = (purchased_dt + timedelta(days=product["expiry_days"])).strftime("%Y-%m-%d")
                        create_stock_batch(
                            product_id=item.product_id,
                            business_id=biz_id,
                            quantity=item.stock_adjusted,
                            purchased_at=tx_date or None,
                            expires_at=expires_dt,
                        )
        elif body.reason in ("shipment", "stock_out"):
            for item in body.items:
                if item.stock_adjusted < 0:
                    consume_stock_batches(item.product_id, biz_id, abs(item.stock_adjusted))
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
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """List inventory batches (paginated, filterable)."""
    cust = ctx.resolve_customer_filter(customer_id)
    return get_inventory_batches(ctx.business_id, page, per_page, start_date, end_date, reason, cust)


@router.get("/batches/{batch_id}")
def get_batch_detail_endpoint(
    batch_id: int,
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    """Get a single batch with its line items."""
    cust = ctx.resolve_customer_filter(customer_id)
    batch = get_inventory_batch_detail(batch_id, ctx.business_id, cust)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch
