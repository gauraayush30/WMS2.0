"""
Business routes – CRUD for the current user's business.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_user_by_id,
    get_business_by_id,
    create_business,
    update_business,
    update_user_business,
)

router = APIRouter(prefix="/business", tags=["Business"])


# ── Models ───────────────────────────────────────────────────────────────────

class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(default="", max_length=500)


class BusinessUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(default="", max_length=500)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def get_business(user_id: int = Depends(get_current_user_id)):
    """Get the current user's business."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    biz = get_business_by_id(user["business_id"])
    if not biz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return biz


@router.post("", status_code=status.HTTP_201_CREATED)
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


@router.put("")
def update_business_endpoint(body: BusinessUpdate, user_id: int = Depends(get_current_user_id)):
    """Update the current user's business."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No business found")
    result = update_business(user["business_id"], body.name, body.location or None)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return result
