"""
Dashboard routes – stats & notifications for the authenticated user's business.
"""

from fastapi import APIRouter, HTTPException, status, Depends

from auth import get_current_user_id
from db import (
    get_user_by_id,
    get_dashboard_stats,
    get_products_without_location,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _get_user_business_id(user_id: int) -> int:
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


@router.get("/stats")
def dashboard_stats(user_id: int = Depends(get_current_user_id)):
    """Aggregate dashboard statistics for the user's business."""
    biz_id = _get_user_business_id(user_id)
    return get_dashboard_stats(biz_id)


@router.get("/products-without-location")
def products_without_location(user_id: int = Depends(get_current_user_id)):
    """Return all products that have no warehouse location assigned."""
    biz_id = _get_user_business_id(user_id)
    products = get_products_without_location(biz_id)
    return {"products": products, "count": len(products)}
