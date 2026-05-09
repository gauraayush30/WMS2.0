"""
Seller routes — CRUD for sellers (suppliers: entities that send goods
to the warehouse) and their locations.

Sellers belong to a customer (tenant). The backend table is called
'suppliers' for historical reasons; the UI labels them "Sellers".
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth import UserContext, get_user_context
from db import (
    list_suppliers,
    create_supplier,
    get_supplier_by_id,
    update_supplier,
    list_seller_locations,
    create_seller_location,
    update_seller_location,
    delete_seller_location,
    get_default_customer_id,
)


router = APIRouter(prefix="/sellers", tags=["Sellers"])


# ── Models ───────────────────────────────────────────────────────────────────

class SellerCreate(BaseModel):
    customer_id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    contact_name: str = Field(default="", max_length=255)
    contact_email: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    address: str = Field(default="", max_length=2000)


class SellerUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str = Field(default="", max_length=20)
    contact_name: str = Field(default="", max_length=255)
    contact_email: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    address: str = Field(default="", max_length=2000)
    is_active: bool = Field(default=True)


class SellerLocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=1000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    contact_person: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)


class SellerLocationUpdate(BaseModel):
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


# ── Seller CRUD ──────────────────────────────────────────────────────────────

@router.get("")
def list_sellers_endpoint(
    customer_id: int | None = Query(None),
    ctx: UserContext = Depends(get_user_context),
):
    cust = _resolve_customer(ctx, customer_id)
    return {"sellers": list_suppliers(ctx.business_id, cust)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_seller_endpoint(body: SellerCreate, ctx: UserContext = Depends(get_user_context)):
    cust = _resolve_customer(ctx, body.customer_id)
    return create_supplier(
        business_id=ctx.business_id, customer_id=cust,
        name=body.name, gstin=body.gstin,
        contact_name=body.contact_name, contact_email=body.contact_email,
        contact_phone=body.contact_phone, address=body.address,
    )


@router.get("/{seller_id}")
def get_seller_endpoint(seller_id: int, ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return seller


@router.patch("/{seller_id}")
def update_seller_endpoint(seller_id: int, body: SellerUpdate,
                            ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = update_supplier(
        seller_id, ctx.business_id,
        name=body.name, gstin=body.gstin,
        contact_name=body.contact_name, contact_email=body.contact_email,
        contact_phone=body.contact_phone, address=body.address,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return result


# ── Seller Locations ─────────────────────────────────────────────────────────

@router.get("/{seller_id}/locations")
def list_locations_endpoint(seller_id: int, ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"locations": list_seller_locations(seller_id, ctx.business_id)}


@router.post("/{seller_id}/locations", status_code=status.HTTP_201_CREATED)
def create_location_endpoint(seller_id: int, body: SellerLocationCreate,
                              ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return create_seller_location(
        supplier_id=seller_id, business_id=ctx.business_id,
        name=body.name, address=body.address, city=body.city,
        state=body.state, zip_code=body.zip_code,
        contact_person=body.contact_person, contact_phone=body.contact_phone,
    )


@router.patch("/{seller_id}/locations/{location_id}")
def update_location_endpoint(seller_id: int, location_id: int,
                              body: SellerLocationUpdate,
                              ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    result = update_seller_location(
        location_id, ctx.business_id,
        name=body.name, address=body.address, city=body.city,
        state=body.state, zip_code=body.zip_code,
        contact_person=body.contact_person, contact_phone=body.contact_phone,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return result


@router.delete("/{seller_id}/locations/{location_id}")
def delete_location_endpoint(seller_id: int, location_id: int,
                              ctx: UserContext = Depends(get_user_context)):
    seller = get_supplier_by_id(seller_id, ctx.business_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    if ctx.is_customer and seller.get("customer_id") != ctx.customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if not delete_seller_location(location_id, ctx.business_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return {"message": "Location deleted"}
