"""
Location Utilization routes – heatmap, velocity classification, smart placement suggestions, config.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from auth import get_current_user_id
from db import (
    get_user_by_id,
    get_product_velocity_classification,
    get_location_utilization,
    generate_placement_suggestions,
    get_warehouse_location_configs,
    upsert_warehouse_location_config,
    delete_warehouse_location_config,
    get_distinct_zones,
)

router = APIRouter(prefix="/location-utilization", tags=["Location Utilization"])


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

class LocationConfigCreate(BaseModel):
    zone: str = Field(..., min_length=1, max_length=50)
    aisle: str = Field(default="", max_length=50)
    priority: int = Field(default=3, ge=1, le=5)
    label: str = Field(default="", max_length=100)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/overview")
def location_overview(
    days: int = Query(90, ge=7, le=365),
    user_id: int = Depends(get_current_user_id),
):
    """Location heatmap data + summary stats."""
    biz_id = _get_user_business_id(user_id)
    utilization = get_location_utilization(biz_id, days)
    configs = get_warehouse_location_configs(biz_id)

    # Build priority lookup for enrichment
    priority_map = {}
    for c in configs:
        key = f"{c['zone']}|{c['aisle']}" if c["aisle"] else c["zone"]
        priority_map[key] = c

    # Enrich utilization data with priority info
    for loc in utilization:
        zone = loc["zone"] or ""
        aisle = loc["aisle"] or ""
        exact = f"{zone}|{aisle}" if aisle else zone
        cfg = priority_map.get(exact)
        if not cfg:
            # Try zone-level match
            for k, v in priority_map.items():
                if v["zone"] == zone and not v["aisle"]:
                    cfg = v
                    break
        loc["priority"] = cfg["priority"] if cfg else 3
        loc["priority_label"] = cfg.get("label", "") if cfg else ""

    # Summary
    total_zones = len(set(l["zone"] for l in utilization))
    total_outbound = sum(l["total_outbound"] for l in utilization)
    busiest = utilization[0] if utilization else None

    return {
        "locations": utilization,
        "summary": {
            "total_zones": total_zones,
            "total_locations": len(utilization),
            "total_outbound": total_outbound,
            "busiest_zone": busiest["zone"] if busiest else None,
        },
    }


@router.get("/velocity")
def product_velocity(
    days: int = Query(90, ge=7, le=365),
    user_id: int = Depends(get_current_user_id),
):
    """Product ABC velocity classification list."""
    biz_id = _get_user_business_id(user_id)
    products = get_product_velocity_classification(biz_id, days)
    counts = {"A": 0, "B": 0, "C": 0}
    for p in products:
        counts[p["velocity_class"]] = counts.get(p["velocity_class"], 0) + 1
    return {
        "products": products,
        "summary": counts,
        "total": len(products),
        "days": days,
    }


@router.get("/suggestions")
def placement_suggestions(
    days: int = Query(90, ge=7, le=365),
    user_id: int = Depends(get_current_user_id),
):
    """Smart placement suggestions."""
    biz_id = _get_user_business_id(user_id)
    suggestions = generate_placement_suggestions(biz_id, days)
    counts = {"high": 0, "medium": 0, "low": 0}
    for s in suggestions:
        counts[s["priority"]] = counts.get(s["priority"], 0) + 1
    return {
        "suggestions": suggestions,
        "summary": counts,
        "total": len(suggestions),
    }


@router.get("/config")
def get_config(user_id: int = Depends(get_current_user_id)):
    """Get all location priority configs + auto-detected zones."""
    biz_id = _get_user_business_id(user_id)
    configs = get_warehouse_location_configs(biz_id)
    zones = get_distinct_zones(biz_id)
    return {"configs": configs, "detected_zones": zones}


@router.post("/config", status_code=status.HTTP_201_CREATED)
def create_or_update_config(
    body: LocationConfigCreate,
    user_id: int = Depends(get_current_user_id),
):
    """Create or update a location priority config entry."""
    biz_id = _get_user_business_id(user_id)
    result = upsert_warehouse_location_config(
        biz_id, body.zone, body.aisle, body.priority, body.label,
    )
    return result


@router.delete("/config/{config_id}")
def delete_config(config_id: int, user_id: int = Depends(get_current_user_id)):
    """Delete a location config entry."""
    biz_id = _get_user_business_id(user_id)
    deleted = delete_warehouse_location_config(config_id, biz_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return {"message": "Deleted"}
