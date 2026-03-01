"""
Users / Employees routes – list users, update roles.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import get_user_by_id, get_users_by_business, update_user_role

router = APIRouter(prefix="/users", tags=["Users"])


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

class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="admin, manager, or employee")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_users(user_id: int = Depends(get_current_user_id)):
    """List all users in the same business."""
    biz_id = _get_user_business_id(user_id)
    return {"users": get_users_by_business(biz_id)}


@router.put("/{target_user_id}/role")
def update_user_role_endpoint(target_user_id: int, body: UserRoleUpdate, user_id: int = Depends(get_current_user_id)):
    """Update role of a user in the same business."""
    biz_id = _get_user_business_id(user_id)
    if body.role not in ("admin", "manager", "employee"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    result = update_user_role(target_user_id, body.role, biz_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this business")
    return result
