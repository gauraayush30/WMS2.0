"""
Warehouse routes — CRUD for the business's physical warehouses.

Only warehouse_admin can create or modify warehouses (per Decision §12.1).
Any authenticated warehouse user can list them; customer users can see
the warehouses where their inventory is stored.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import (
    UserContext,
    get_user_context,
    require_warehouse_admin,
)
from db import (
    list_warehouses,
    get_warehouse_by_id,
    create_warehouse,
    update_warehouse,
)


router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


# ── Models ───────────────────────────────────────────────────────────────────

class WarehouseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    address: str = Field(default="", max_length=2000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)


class WarehouseUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    address: str = Field(default="", max_length=2000)
    city: str = Field(default="", max_length=255)
    state: str = Field(default="", max_length=255)
    zip_code: str = Field(default="", max_length=50)
    is_active: bool = Field(default=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_endpoint(ctx: UserContext = Depends(get_user_context)):
    """List warehouses in the user's business (active by default)."""
    return {"warehouses": list_warehouses(ctx.business_id)}


@router.get("/{warehouse_id}")
def get_endpoint(warehouse_id: int, ctx: UserContext = Depends(get_user_context)):
    wh = get_warehouse_by_id(warehouse_id, ctx.business_id)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return wh


@router.post("", status_code=status.HTTP_201_CREATED)
def create_endpoint(
    body: WarehouseCreate,
    ctx: UserContext = Depends(require_warehouse_admin),
):
    """Create a new warehouse. warehouse_admin only."""
    try:
        return create_warehouse(
            business_id=ctx.business_id,
            name=body.name, code=body.code,
            address=body.address, city=body.city, state=body.state,
            zip_code=body.zip_code,
        )
    except Exception as e:  # IntegrityError → duplicate code, etc.
        msg = str(e)
        if "warehouses_business_id_code_key" in msg or "duplicate key" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Warehouse code '{body.code}' already exists",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)


@router.patch("/{warehouse_id}")
def update_endpoint(
    warehouse_id: int,
    body: WarehouseUpdate,
    ctx: UserContext = Depends(require_warehouse_admin),
):
    """Edit a warehouse. warehouse_admin only."""
    wh = update_warehouse(
        warehouse_id, ctx.business_id,
        name=body.name, code=body.code,
        address=body.address, city=body.city, state=body.state,
        zip_code=body.zip_code, is_active=body.is_active,
    )
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return wh
