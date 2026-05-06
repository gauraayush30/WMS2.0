"""
Outbound (Shipment) routes — header + line items, draft → pick-plan preview → ship.

FEFO is the default for products with expiry_days > 0; FIFO otherwise.
Users can override per-outbound via `pick_strategy`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth import UserContext, get_user_context
from db import (
    create_outbound_order,
    create_buyer,
    get_outbound_order,
    list_outbound_orders,
    list_buyers,
    preview_outbound_pick_plan,
    ship_outbound_order,
    get_default_warehouse_id,
    get_default_customer_id,
    get_product_by_id,
)


router = APIRouter(prefix="/outbounds", tags=["Outbound"])


# ── Models ───────────────────────────────────────────────────────────────────

class OutboundLineCreate(BaseModel):
    product_id: int
    requested_qty: int = Field(..., gt=0)
    unit_price: float = Field(default=0, ge=0)
    tax_pct: float = Field(default=0, ge=0)
    discount_pct: float = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=1000)


class OutboundCreate(BaseModel):
    customer_id: int | None = None
    warehouse_id: int | None = None
    buyer_id: int | None = None
    delivery_location_id: int | None = None
    so_number: str = Field(default="", max_length=255)
    invoice_number: str = Field(default="", max_length=255)
    invoice_date: str | None = None
    shipped_at: str | None = None
    pick_strategy: str | None = Field(
        default=None,
        description="FIFO | FEFO | manual. When omitted, FEFO is used if any "
                    "line product has expiry_days>0, else FIFO.",
    )
    notes: str = Field(default="", max_length=2000)
    lines: list[OutboundLineCreate] = Field(..., min_length=1)


class BuyerCreate(BaseModel):
    customer_id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    delivery_location_id: int | None = None
    contact_name: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_customer(ctx: UserContext, requested: int | None) -> int:
    if ctx.is_customer:
        return ctx.customer_id
    if requested:
        return requested
    fallback = get_default_customer_id(ctx.business_id)
    if not fallback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id is required",
        )
    return fallback


def _default_pick_strategy(business_id: int, lines: list[OutboundLineCreate]) -> str:
    """Per Decision §12.3: FEFO if any line product has expiry_days > 0, else FIFO."""
    for ln in lines:
        prod = get_product_by_id(ln.product_id, business_id)
        if prod and int(prod.get("expiry_days") or 0) > 0:
            return "FEFO"
    return "FIFO"


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
    return list_outbound_orders(
        ctx.business_id, cust, warehouse_id, status_filter, page, per_page,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_endpoint(body: OutboundCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    wh = body.warehouse_id or get_default_warehouse_id(ctx.business_id)
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No warehouse available; create one first",
        )
    strategy = body.pick_strategy or _default_pick_strategy(ctx.business_id, body.lines)

    try:
        return create_outbound_order(
            business_id=ctx.business_id, customer_id=cust, warehouse_id=wh,
            created_by=ctx.user_id,
            buyer_id=body.buyer_id,
            delivery_location_id=body.delivery_location_id,
            so_number=body.so_number, invoice_number=body.invoice_number,
            invoice_date=body.invoice_date, shipped_at=body.shipped_at,
            pick_strategy=strategy, notes=body.notes,
            lines=[l.dict() for l in body.lines],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{outbound_id}")
def get_endpoint(outbound_id: int, ctx: UserContext = Depends(get_user_context)):
    cust = ctx.resolve_customer_filter(None)
    head = get_outbound_order(outbound_id, ctx.business_id, cust)
    if not head:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbound not found")
    return head


@router.post("/{outbound_id}/pick-plan")
def pick_plan_endpoint(outbound_id: int, ctx: UserContext = Depends(get_user_context)):
    """Preview the FIFO/FEFO consumption plan without committing."""
    cust = ctx.resolve_customer_filter(None)
    try:
        return preview_outbound_pick_plan(outbound_id, ctx.business_id, cust)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{outbound_id}/ship")
def ship_endpoint(outbound_id: int, ctx: UserContext = Depends(get_user_context)):
    """Commit the shipment: consume batches, write picks + ledger."""
    cust = ctx.resolve_customer_filter(None)
    try:
        return ship_outbound_order(outbound_id, ctx.business_id, cust)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Buyers (nested under outbounds for now) ──────────────────────────────────

@router.get("/buyers")
def list_buyers_endpoint(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = _resolve_customer(ctx, customer_id)
    return {"buyers": list_buyers(ctx.business_id, cust)}


@router.post("/buyers", status_code=status.HTTP_201_CREATED)
def create_buyer_endpoint(body: BuyerCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    return create_buyer(
        business_id=ctx.business_id, customer_id=cust,
        name=body.name, gstin=body.gstin,
        delivery_location_id=body.delivery_location_id,
        contact_name=body.contact_name, contact_phone=body.contact_phone,
    )
