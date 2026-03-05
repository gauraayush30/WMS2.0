"""
Delivery location routes – CRUD for business delivery locations.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_user_by_id,
    create_delivery_location,
    get_delivery_locations,
    get_delivery_location_by_id,
    update_delivery_location,
    delete_delivery_location,
)

router = APIRouter(prefix="/delivery-locations", tags=["Delivery Locations"])


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

class DeliveryLocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=1000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    contact_person: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    notes: str = Field(default="", max_length=2000)


class DeliveryLocationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=1000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    contact_person: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    notes: str = Field(default="", max_length=2000)
    is_active: bool = Field(default=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_delivery_locations(
    include_inactive: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
):
    """List delivery locations for the user's business."""
    biz_id = _get_user_business_id(user_id)
    locations = get_delivery_locations(biz_id, include_inactive)
    return {"locations": locations}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_delivery_location_endpoint(
    body: DeliveryLocationCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create a new delivery location."""
    biz_id = _get_user_business_id(user_id)
    try:
        loc = create_delivery_location(
            business_id=biz_id,
            name=body.name,
            address=body.address,
            city=body.city,
            state=body.state,
            zip_code=body.zip_code,
            contact_person=body.contact_person,
            contact_phone=body.contact_phone,
            notes=body.notes,
        )
        return loc
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{location_id}")
def get_delivery_location_endpoint(
    location_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Get a single delivery location by ID."""
    biz_id = _get_user_business_id(user_id)
    loc = get_delivery_location_by_id(location_id, biz_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery location not found")
    return loc


@router.put("/{location_id}")
def update_delivery_location_endpoint(
    location_id: int,
    body: DeliveryLocationUpdate,
    user_id: int = Depends(get_current_user_id),
):
    """Update a delivery location."""
    biz_id = _get_user_business_id(user_id)
    result = update_delivery_location(
        location_id=location_id,
        business_id=biz_id,
        name=body.name,
        address=body.address,
        city=body.city,
        state=body.state,
        zip_code=body.zip_code,
        contact_person=body.contact_person,
        contact_phone=body.contact_phone,
        notes=body.notes,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery location not found")
    return result


@router.delete("/{location_id}")
def delete_delivery_location_endpoint(
    location_id: int,
    user_id: int = Depends(get_current_user_id),
):
    """Delete a delivery location."""
    biz_id = _get_user_business_id(user_id)
    deleted = delete_delivery_location(location_id, biz_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery location not found")
    return {"message": "Delivery location deleted"}
