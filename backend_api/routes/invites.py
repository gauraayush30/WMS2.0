"""
Invites routes – send/manage invites to users without a business.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_user_by_id,
    get_users_without_business,
    create_invite,
    get_sent_invites,
    get_received_invites,
    accept_invite,
    reject_invite,
    check_pending_invite,
)

router = APIRouter(prefix="/invites", tags=["Invites"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_admin_business_id(user_id: int) -> int:
    """Helper: get the business_id for an admin user, raise 403 if not admin."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage invites",
        )
    return user["business_id"]


# ── Models ───────────────────────────────────────────────────────────────────

class SendInviteRequest(BaseModel):
    to_user_id: int = Field(..., description="ID of the user to invite")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/users-without-business")
def list_users_without_business(
    search: str = Query(""),
    user_id: int = Depends(get_current_user_id),
):
    """List users who don't belong to any business (for admin to invite)."""
    _get_admin_business_id(user_id)  # Only admins can search
    users = get_users_without_business(search)
    return {"users": users}


@router.post("", status_code=status.HTTP_201_CREATED)
def send_invite(body: SendInviteRequest, user_id: int = Depends(get_current_user_id)):
    """Send an invite to a user without a business."""
    biz_id = _get_admin_business_id(user_id)

    # Check target user exists and has no business
    target = get_user_by_id(body.to_user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.get("business_id"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to a business")

    # Check for existing pending invite
    if check_pending_invite(biz_id, body.to_user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending invite already exists for this user")

    try:
        invite = create_invite(biz_id, user_id, body.to_user_id)
        return invite
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/sent")
def list_sent_invites(user_id: int = Depends(get_current_user_id)):
    """List all invites sent by the admin's business."""
    biz_id = _get_admin_business_id(user_id)
    invites = get_sent_invites(biz_id)
    return {"invites": invites}


@router.get("/received")
def list_received_invites(user_id: int = Depends(get_current_user_id)):
    """List all invites received by the current user."""
    invites = get_received_invites(user_id)
    return {"invites": invites}


@router.post("/{invite_id}/accept")
def accept_invite_endpoint(invite_id: int, user_id: int = Depends(get_current_user_id)):
    """Accept an invite – joins the user to the business."""
    result = accept_invite(invite_id, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found or already handled")
    return result


@router.post("/{invite_id}/reject")
def reject_invite_endpoint(invite_id: int, user_id: int = Depends(get_current_user_id)):
    """Reject an invite."""
    result = reject_invite(invite_id, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found or already handled")
    return result
