"""
Auth routes – register, login, me.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)
from db import (
    get_user_by_email,
    get_user_by_id,
    create_business,
    create_user_v2,
    update_user_business,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Models ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    business_name: str = Field(default="", description="Business name (creates new business if provided)")
    business_location: str = Field(default="", description="Business location")


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    """Register a new user. Optionally creates a business and assigns the user to it."""
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    hashed = hash_password(req.password)

    # Create business if name provided
    business_id = None
    if req.business_name.strip():
        try:
            biz = create_business(req.business_name.strip(), req.business_location.strip() or None)
            business_id = biz["id"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating business: {str(e)}",
            )

    try:
        user = create_user_v2(
            username=req.username,
            name=req.name,
            email=req.email,
            hashed_password=hashed,
            business_id=business_id,
            role="admin" if business_id else "employee",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating account: {str(e)}",
        )
    token = create_access_token({"sub": str(user["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "email": user["email"],
            "business_id": user["business_id"],
            "role": user["role"],
        },
    }


@router.post("/login")
def login(req: LoginRequest):
    """Authenticate a user. Returns a JWT token on success."""
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    token = create_access_token({"sub": str(user["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user.get("username", ""),
            "name": user["name"],
            "email": user["email"],
            "business_id": user.get("business_id"),
            "role": user.get("role", "employee"),
        },
    }


@router.get("/me")
def me(user_id: int = Depends(get_current_user_id)):
    """Return the currently authenticated user's profile."""
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "id": user["id"],
        "username": user.get("username", ""),
        "name": user["name"],
        "email": user["email"],
        "business_id": user.get("business_id"),
        "role": user.get("role", "employee"),
    }
