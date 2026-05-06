"""
Customer routes — CRUD for the 3PL business's customers (tenants whose
inventory is stored at the warehouse).

- Warehouse roles can create/edit customers; customer roles can view their
  own customer record only.
- /customers/{id}/users lists users attached to that customer.
- /customers/{id}/users/invite creates a customer_admin / customer_staff user
  directly with a temporary password (simple Phase-1 onboarding; the existing
  invites table is left for warehouse-staff invites and can be unified later).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from auth import (
    UserContext,
    get_user_context,
    require_warehouse_admin,
    hash_password,
)
from db import (
    list_customers,
    get_customer_by_id,
    create_customer,
    update_customer,
    list_users_for_customer,
    create_user_for_customer,
    get_user_by_email,
)


router = APIRouter(prefix="/customers", tags=["Customers"])


# ── Models ───────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    contact_name: str = Field(default="", max_length=255)
    contact_email: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)


class CustomerUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    contact_name: str = Field(default="", max_length=255)
    contact_email: str = Field(default="", max_length=255)
    contact_phone: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)


class CustomerUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="customer_staff", description="customer_admin | customer_staff")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_customer_for_ctx(customer_id: int, ctx: UserContext) -> dict:
    """Fetch a customer enforcing tenant isolation:
    - warehouse roles → any customer in their business
    - customer roles  → only their own customer
    """
    if ctx.is_customer and ctx.customer_id != customer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    cust = get_customer_by_id(customer_id, ctx.business_id)
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return cust


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_endpoint(ctx: UserContext = Depends(get_user_context)):
    """List customers visible to the user.

    - Warehouse user: all customers in the business.
    - Customer user: a single-element list with their own customer.
    """
    if ctx.is_customer:
        own = get_customer_by_id(ctx.customer_id, ctx.business_id) if ctx.customer_id else None
        return {"customers": [own] if own else []}
    return {"customers": list_customers(ctx.business_id)}


@router.get("/{customer_id}")
def get_endpoint(customer_id: int, ctx: UserContext = Depends(get_user_context)):
    return _resolve_customer_for_ctx(customer_id, ctx)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_endpoint(
    body: CustomerCreate,
    ctx: UserContext = Depends(require_warehouse_admin),
):
    """Create a new customer (tenant). warehouse_admin only."""
    try:
        return create_customer(
            business_id=ctx.business_id,
            name=body.name, code=body.code,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
        )
    except Exception as e:
        msg = str(e)
        if "customers_business_id_code_key" in msg or "duplicate key" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer code '{body.code}' already exists",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)


@router.patch("/{customer_id}")
def update_endpoint(
    customer_id: int,
    body: CustomerUpdate,
    ctx: UserContext = Depends(require_warehouse_admin),
):
    cust = update_customer(
        customer_id, ctx.business_id,
        name=body.name, code=body.code,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        is_active=body.is_active,
    )
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return cust


# ── Users for a customer ─────────────────────────────────────────────────────

@router.get("/{customer_id}/users")
def list_customer_users(customer_id: int, ctx: UserContext = Depends(get_user_context)):
    """List users belonging to a customer.

    Visible to: warehouse_admin / customer_admin (of the same customer).
    """
    cust = _resolve_customer_for_ctx(customer_id, ctx)
    if ctx.is_customer and not ctx.is_customer_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer admin required")
    if ctx.is_warehouse and not ctx.is_warehouse_admin:
        # warehouse_staff can see the list but not invite — read-only
        pass
    users = list_users_for_customer(ctx.business_id, customer_id)
    return {"customer_id": customer_id, "users": users}


@router.post("/{customer_id}/users", status_code=status.HTTP_201_CREATED)
def create_customer_user(
    customer_id: int,
    body: CustomerUserCreate,
    ctx: UserContext = Depends(get_user_context),
):
    """Create a new user attached to a customer.

    Allowed for warehouse_admin and customer_admin (of the same customer).
    """
    cust = _resolve_customer_for_ctx(customer_id, ctx)
    is_allowed = ctx.is_warehouse_admin or (
        ctx.is_customer_admin and ctx.customer_id == customer_id
    )
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only warehouse_admin or customer_admin can add users",
        )
    if body.role not in ("customer_admin", "customer_staff"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be customer_admin or customer_staff",
        )

    if get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    return create_user_for_customer(
        username=body.username, name=body.name, email=body.email,
        hashed_password=hash_password(body.password),
        business_id=ctx.business_id, customer_id=customer_id,
        role=body.role,
    )
