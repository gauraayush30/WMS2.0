"""
Product routes – CRUD + bulk upload + SKU check + audit log.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_user_by_id,
    create_product,
    get_products_by_business,
    get_product_by_id,
    update_product,
    delete_product,
    check_skus_exist,
    create_product_audit_entries,
    get_product_audit_log,
)

router = APIRouter(prefix="/products", tags=["Products"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_business_id(user_id: int) -> int:
    """Helper: get the business_id for a user, raise 403 if none."""
    user = get_user_by_id(user_id)
    if not user or not user.get("business_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must belong to a business to access this resource",
        )
    return user["business_id"]


# ── Models ───────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_code: str = Field(..., min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)
    stock_at_warehouse: int = Field(default=0, ge=0)
    uom: str = Field(default="pcs", max_length=50)
    par_level: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=0, ge=0)
    max_stock_level: int = Field(default=0, ge=0)
    location_zone: str = Field(default="", max_length=50)
    location_aisle: str = Field(default="", max_length=50)
    location_rack: str = Field(default="", max_length=50)
    location_shelf: str = Field(default="", max_length=50)
    location_level: str = Field(default="", max_length=50)
    location_bin: str = Field(default="", max_length=50)


class ProductUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_code: str = Field(..., min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)
    uom: str = Field(default="pcs", max_length=50)
    par_level: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=0, ge=0)
    max_stock_level: int = Field(default=0, ge=0)
    location_zone: str = Field(default="", max_length=50)
    location_aisle: str = Field(default="", max_length=50)
    location_rack: str = Field(default="", max_length=50)
    location_shelf: str = Field(default="", max_length=50)
    location_level: str = Field(default="", max_length=50)
    location_bin: str = Field(default="", max_length=50)


class SkuCheckRequest(BaseModel):
    sku_codes: list[str] = Field(..., min_length=1, max_length=500)


class BulkProductItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sku_code: str = Field(..., min_length=1, max_length=100)
    price: float = Field(default=0, ge=0)
    stock_at_warehouse: int = Field(default=0, ge=0)
    uom: str = Field(default="pcs", max_length=50)
    par_level: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=0, ge=0)
    safety_stock: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=0, ge=0)
    max_stock_level: int = Field(default=0, ge=0)
    location_zone: str = Field(default="", max_length=50)
    location_aisle: str = Field(default="", max_length=50)
    location_rack: str = Field(default="", max_length=50)
    location_shelf: str = Field(default="", max_length=50)
    location_level: str = Field(default="", max_length=50)
    location_bin: str = Field(default="", max_length=50)


class BulkProductRequest(BaseModel):
    products: list[BulkProductItem] = Field(..., min_length=1)


# ── CRUD Endpoints ───────────────────────────────────────────────────────────

@router.get("")
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    user_id: int = Depends(get_current_user_id),
):
    """List products for the user's business (paginated, searchable)."""
    biz_id = _get_user_business_id(user_id)
    return get_products_by_business(biz_id, page, per_page, search)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product_endpoint(body: ProductCreate, user_id: int = Depends(get_current_user_id)):
    """Create a new product for the user's business."""
    biz_id = _get_user_business_id(user_id)
    try:
        product = create_product(
            body.name, body.sku_code, biz_id, body.price, body.stock_at_warehouse, body.uom,
            body.par_level, body.reorder_point, body.safety_stock, body.lead_time_days, body.max_stock_level,
            body.location_zone, body.location_aisle, body.location_rack,
            body.location_shelf, body.location_level, body.location_bin,
        )
        return product
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU code already exists")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{product_id}")
def get_product_endpoint(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Get a single product by ID."""
    biz_id = _get_user_business_id(user_id)
    product = get_product_by_id(product_id, biz_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.put("/{product_id}")
def update_product_endpoint(product_id: int, body: ProductUpdate, user_id: int = Depends(get_current_user_id)):
    """Update a product. Automatically logs which fields were changed and by whom."""
    biz_id = _get_user_business_id(user_id)

    # Fetch the current product state before updating
    existing = get_product_by_id(product_id, biz_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    try:
        result = update_product(
            product_id, biz_id, body.name, body.sku_code, body.price, body.uom,
            body.par_level, body.reorder_point, body.safety_stock, body.lead_time_days, body.max_stock_level,
            body.location_zone, body.location_aisle, body.location_rack,
            body.location_shelf, body.location_level, body.location_bin,
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Compute field-level diffs and create audit entries
        changes: list[dict] = []
        if existing["name"] != body.name:
            changes.append({"field_name": "name", "old_value": existing["name"], "new_value": body.name})
        if existing["sku_code"] != body.sku_code:
            changes.append({"field_name": "sku_code", "old_value": existing["sku_code"], "new_value": body.sku_code})
        if float(existing["price"]) != body.price:
            changes.append({"field_name": "price", "old_value": str(existing["price"]), "new_value": str(body.price)})
        if existing.get("uom", "pcs") != body.uom:
            changes.append({"field_name": "uom", "old_value": existing.get("uom", "pcs"), "new_value": body.uom})
        for field in ("par_level", "reorder_point", "safety_stock", "lead_time_days", "max_stock_level"):
            if int(existing.get(field, 0)) != getattr(body, field):
                changes.append({"field_name": field, "old_value": str(existing.get(field, 0)), "new_value": str(getattr(body, field))})
        for field in ("location_zone", "location_aisle", "location_rack", "location_shelf", "location_level", "location_bin"):
            if existing.get(field, "") != getattr(body, field):
                changes.append({"field_name": field, "old_value": existing.get(field, ""), "new_value": getattr(body, field)})

        if changes:
            create_product_audit_entries(product_id, biz_id, user_id, changes)

        return result
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU code already exists")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{product_id}")
def delete_product_endpoint(product_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete a product."""
    biz_id = _get_user_business_id(user_id)
    deleted = delete_product(product_id, biz_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {"message": "Product deleted"}


@router.post("/check-skus")
def check_skus_endpoint(body: SkuCheckRequest, user_id: int = Depends(get_current_user_id)):
    """Check which SKU codes already exist for the user's business."""
    biz_id = _get_user_business_id(user_id)
    existing = check_skus_exist(biz_id, body.sku_codes)
    return {"existing": existing}


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_products(body: BulkProductRequest, user_id: int = Depends(get_current_user_id)):
    """Create multiple products at once. Returns per-row results."""
    biz_id = _get_user_business_id(user_id)
    results = []
    for item in body.products:
        try:
            product = create_product(
                item.name, item.sku_code, biz_id, item.price, item.stock_at_warehouse, item.uom,
                item.par_level, item.reorder_point, item.safety_stock, item.lead_time_days, item.max_stock_level,
                item.location_zone, item.location_aisle, item.location_rack,
                item.location_shelf, item.location_level, item.location_bin,
            )
            results.append({
                "name": item.name,
                "sku_code": item.sku_code,
                "status": "created",
                "id": product["id"],
            })
        except Exception as e:
            msg = "A product with this SKU code already exists" if ("unique" in str(e).lower() or "duplicate" in str(e).lower()) else str(e)
            results.append({
                "name": item.name,
                "sku_code": item.sku_code,
                "status": "error",
                "message": msg,
            })
    return {"results": results}


# ── Audit Log Endpoint ──────────────────────────────────────────────────────

@router.get("/{product_id}/audit-log")
def get_product_audit_log_endpoint(
    product_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
):
    """Get the edit history (audit log) for a product."""
    biz_id = _get_user_business_id(user_id)
    # Verify product exists and belongs to this business
    product = get_product_by_id(product_id, biz_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return get_product_audit_log(product_id, biz_id, page, per_page)
