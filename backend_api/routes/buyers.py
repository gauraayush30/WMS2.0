"""
Buyer routes — CRUD for buyers (customers' downstream recipients)
and their locations.

Buyers belong to a customer (tenant). When a warehouse role accesses
these endpoints, a customer_id must be provided or resolved from the
default customer.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth import UserContext, get_user_context
from db import (
    list_buyers,
    create_buyer,
    get_buyer_by_id,
    update_buyer,
    list_buyer_locations,
    create_buyer_location,
    update_buyer_location,
    delete_buyer_location,
    get_default_customer_id,
)


router = APIRouter(prefix="/buyers", tags=["Buyers"])


# ── Models ───────────────────────────────────────────────────────────────────

class BuyerCreate(BaseModel):
    customer_id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    contact_name: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)


class BuyerUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    contact_name: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)


class BuyerLocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=1000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    contact_person: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)


class BuyerLocationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=1000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    contact_person: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)


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


# ── Buyer CRUD ───────────────────────────────────────────────────────────────

@router.get("")
def list_buyers_endpoint(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = _resolve_customer(ctx, customer_id)
    return {"buyers": list_buyers(ctx.business_id, cust)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_buyer_endpoint(body: BuyerCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    return create_buyer(
        business_id=ctx.business_id, customer_id=cust,
        name=body.name, gstin=body.gstin,
        contact_name=body.contact_name, contact_phone=body.contact_phone,
    )


@router.get("/{buyer_id}")
def get_buyer_endpoint(buyer_id: int, ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    # Enforce customer isolation
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return buyer


@router.patch("/{buyer_id}")
def update_buyer_endpoint(buyer_id: int, body: BuyerUpdate, ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = update_buyer(
        buyer_id, ctx.business_id,
        name=body.name, gstin=body.gstin,
        contact_name=body.contact_name, contact_phone=body.contact_phone,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    return result


# ── Buyer Locations ──────────────────────────────────────────────────────────

@router.get("/{buyer_id}/locations")
def list_locations_endpoint(buyer_id: int, ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"locations": list_buyer_locations(buyer_id, ctx.business_id)}


@router.post("/{buyer_id}/locations", status_code=status.HTTP_201_CREATED)
def create_location_endpoint(buyer_id: int, body: BuyerLocationCreate,
                              ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return create_buyer_location(
        buyer_id=buyer_id, business_id=ctx.business_id,
        name=body.name, address=body.address, city=body.city,
        state=body.state, zip_code=body.zip_code,
        contact_person=body.contact_person, contact_phone=body.contact_phone,
    )


@router.patch("/{buyer_id}/locations/{location_id}")
def update_location_endpoint(buyer_id: int, location_id: int,
                              body: BuyerLocationUpdate,
                              ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = update_buyer_location(
        location_id, ctx.business_id,
        name=body.name, address=body.address, city=body.city,
        state=body.state, zip_code=body.zip_code,
        contact_person=body.contact_person, contact_phone=body.contact_phone,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return result


@router.delete("/{buyer_id}/locations/{location_id}")
def delete_location_endpoint(buyer_id: int, location_id: int,
                              ctx: UserContext = Depends(get_user_context)):
    buyer = get_buyer_by_id(buyer_id, ctx.business_id)
    if not buyer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")
    if ctx.is_customer and buyer.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if not delete_buyer_location(location_id, ctx.business_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {"message": "Location deleted"}
