"""
Authentication utilities – password hashing and JWT token management.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ── Configuration ────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "wms-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

bearer_scheme = HTTPBearer()


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    """Extract and validate the user_id from the Bearer token."""
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    return int(user_id)


# ── Multi-tenant context (Phase 1 of revamp) ─────────────────────────────────

WAREHOUSE_ROLES = {"warehouse_admin", "warehouse_staff"}
CUSTOMER_ROLES  = {"customer_admin",  "customer_staff"}


class UserContext:
    """Authenticated user context with tenant scoping.

    - business_id: the 3PL company (deployment-level tenant)
    - role:        warehouse_admin | warehouse_staff | customer_admin | customer_staff
    - customer_id: NULL for warehouse roles; set for customer roles. When set,
                   the DB layer hard-filters every owned-record query to this
                   customer (preventing cross-customer leaks).
    """

    __slots__ = ("user_id", "business_id", "role", "customer_id", "name", "email")

    def __init__(self, user_id: int, business_id: int, role: str,
                 customer_id: int | None, name: str = "", email: str = ""):
        self.user_id = user_id
        self.business_id = business_id
        self.role = role
        self.customer_id = customer_id
        self.name = name
        self.email = email

    @property
    def is_warehouse(self) -> bool:
        return self.role in WAREHOUSE_ROLES

    @property
    def is_customer(self) -> bool:
        return self.role in CUSTOMER_ROLES

    @property
    def is_warehouse_admin(self) -> bool:
        return self.role == "warehouse_admin"

    @property
    def is_customer_admin(self) -> bool:
        return self.role == "customer_admin"

    def resolve_customer_filter(self, requested_customer_id: int | None) -> int | None:
        """Return the effective customer_id filter to apply in queries.

        - For customer roles: ignore client-supplied filter, always force own.
        - For warehouse roles: pass through whatever the caller asked for
          (None means "all customers under this business").
        """
        if self.is_customer:
            return self.customer_id
        return requested_customer_id


def get_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserContext:
    """Resolve the authenticated user's full tenant context.

    Imported lazily to avoid a circular import (db.py loads auth-free).
    """
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )
    from db import get_user_by_id  # noqa: WPS433  (deliberate lazy import)
    user = get_user_by_id(int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    if not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return UserContext(
        user_id=int(user_id),
        business_id=user["business_id"],
        role=user.get("role", "warehouse_staff"),
        customer_id=user.get("customer_id"),
        name=user.get("name", ""),
        email=user.get("email", ""),
    )


def require_warehouse(ctx: UserContext = Depends(get_user_context)) -> UserContext:
    """Allow only warehouse_admin / warehouse_staff."""
    if not ctx.is_warehouse:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Warehouse role required",
        )
    return ctx


def require_warehouse_admin(ctx: UserContext = Depends(get_user_context)) -> UserContext:
    """Allow only warehouse_admin."""
    if not ctx.is_warehouse_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Warehouse admin role required",
        )
    return ctx


def require_customer(ctx: UserContext = Depends(get_user_context)) -> UserContext:
    """Allow only customer_admin / customer_staff."""
    if not ctx.is_customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer role required",
        )
    return ctx
