"""
Inbound (GRN) routes — header + line items, draft → received commit.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth import UserContext, get_user_context
from db import (
    create_inbound_order,
    create_supplier,
    get_inbound_order,
    list_inbound_orders,
    list_suppliers,
    receive_inbound_order,
    get_default_warehouse_id,
    get_default_customer_id,
)


router = APIRouter(prefix="/inbounds", tags=["Inbound"])


# ── Models ───────────────────────────────────────────────────────────────────

class InboundLineCreate(BaseModel):
    product_id: int
    expected_qty: int = Field(..., gt=0)
    unit_cost: float = Field(default=0, ge=0)
    tax_pct: float = Field(default=0, ge=0)
    discount_pct: float = Field(default=0, ge=0)
    batch_code: str = Field(default="", max_length=64)
    manufactured_at: str | None = None
    expires_at: str | None = None
    notes: str = Field(default="", max_length=1000)


class InboundCreate(BaseModel):
    customer_id: int | None = None  # required for warehouse roles
    warehouse_id: int | None = None
    supplier_id: int | None = None
    po_number: str = Field(default="", max_length=255)
    invoice_number: str = Field(default="", max_length=255)
    invoice_date: str | None = None
    received_at: str | None = None
    notes: str = Field(default="", max_length=2000)
    lines: list[InboundLineCreate] = Field(..., min_length=1)


class SupplierCreate(BaseModel):
    customer_id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    contact_name: str = Field(default="", max_length=255)
    contact_email: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    address: str = Field(default="", max_length=2000)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_customer(ctx: UserContext, requested: int | None) -> int:
    if ctx.is_customer:
        return ctx.customer_id  # forced
    if requested:
        return requested
    fallback = get_default_customer_id(ctx.business_id)
    if not fallback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id is required",
        )
    return fallback


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_endpoint(
    customer_id: int | None = Query(None),
    warehouse_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ctx: UserContext = Depends(get_user_context),
):
    cust = ctx.resolve_customer_filter(customer_id)
    return list_inbound_orders(
        ctx.business_id, cust, warehouse_id, status_filter, page, per_page,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_endpoint(body: InboundCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    wh = body.warehouse_id or get_default_warehouse_id(ctx.business_id)
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No warehouse available; create one first",
        )
    try:
        return create_inbound_order(
            business_id=ctx.business_id, customer_id=cust, warehouse_id=wh,
            created_by=ctx.user_id,
            supplier_id=body.supplier_id,
            po_number=body.po_number, invoice_number=body.invoice_number,
            invoice_date=body.invoice_date, received_at=body.received_at,
            notes=body.notes,
            lines=[l.dict() for l in body.lines],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{inbound_id}")
def get_endpoint(inbound_id: int, ctx: UserContext = Depends(get_user_context)):
    cust = ctx.resolve_customer_filter(None)
    head = get_inbound_order(inbound_id, ctx.business_id, cust)
    if not head:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbound not found")
    return head


@router.post("/{inbound_id}/receive")
def receive_endpoint(inbound_id: int, ctx: UserContext = Depends(get_user_context)):
    """Commit the inbound: write ledger + batches, advance status to 'received'."""
    cust = ctx.resolve_customer_filter(None)
    try:
        return receive_inbound_order(inbound_id, ctx.business_id, cust)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Suppliers (nested under inbounds for now) ────────────────────────────────

@router.get("/suppliers")
def list_suppliers_endpoint(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = _resolve_customer(ctx, customer_id)
    return {"suppliers": list_suppliers(ctx.business_id, cust)}


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier_endpoint(body: SupplierCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    return create_supplier(
        business_id=ctx.business_id, customer_id=cust,
        name=body.name, gstin=body.gstin,
        contact_name=body.contact_name, contact_email=body.contact_email,
        contact_phone=body.contact_phone, address=body.address,
    )
