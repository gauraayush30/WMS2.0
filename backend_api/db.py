"""
Database helper – all PostgreSQL queries live here.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL not found in environment variables")

engine = create_engine(DB_URL, pool_pre_ping=True)


def get_all_skus() -> list[dict]:
    """Return distinct SKUs with their latest stock level and row count."""
    query = text("""
        SELECT
            d.sku_id,
            d.sku_name,
            d.stock_level AS current_stock,
            cnt.total_records
        FROM (
            SELECT DISTINCT ON (sku_id)
                   sku_id, sku_name, stock_level
            FROM inventory_sales
            ORDER BY sku_id, sale_date DESC, id DESC
        ) d
        INNER JOIN (
            SELECT sku_id,
                   COUNT(*)::int AS total_records
            FROM inventory_sales
            GROUP BY sku_id
        ) cnt ON d.sku_id = cnt.sku_id
        ORDER BY d.sku_id
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(r) for r in rows]


#  Historical sales 
def get_history(sku_id: str, days: int) -> list[dict]:
    """Return the last N days of sales for a given SKU."""
    query = text("""
        SELECT sale_date, sales_qty, purchase_qty, stock_level
        FROM inventory_sales
        WHERE sku_id = :sku_id
        ORDER BY sale_date DESC, id DESC
        LIMIT :days
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"sku_id": sku_id, "days": days}).mappings().all()

    # Reverse so oldest-first
    return [
        {
            "date": str(r["sale_date"]),
            "sales_qty": int(r["sales_qty"]),
            "purchase_qty": int(r["purchase_qty"]),
            "stock_level": int(r["stock_level"]),
        }
        for r in reversed(rows)
    ]


#  Current stock for a single SKU 
def get_current_stock(sku_id: str) -> int:
    """Return the most recent stock_level for the SKU."""
    query = text("""
        SELECT stock_level
        FROM inventory_sales
        WHERE sku_id = :sku_id
        ORDER BY sale_date DESC, id DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"sku_id": sku_id}).fetchone()
    return int(row[0]) if row else 0


#  Record a transaction (sale/purchase) 
def record_transaction(sku_id: str, sales_qty: int, purchase_qty: int, transaction_date: str) -> dict:
    """Record a sales/purchase transaction and update stock level.
    
    Args:
        sku_id: The SKU identifier
        sales_qty: Quantity sold (reduces stock)
        purchase_qty: Quantity purchased (increases stock)
        transaction_date: Date of transaction (YYYY-MM-DD format)
    
    Returns:
        Dictionary with transaction details and updated stock level
    
    Raises:
        ValueError: If SKU not found or invalid data
    """
    # Get current stock and SKU info
    get_sku_query = text("""
        SELECT sku_id, sku_name, stock_level
        FROM inventory_sales
        WHERE sku_id = :sku_id
        ORDER BY sale_date DESC, id DESC
        LIMIT 1
    """)
    
    with engine.connect() as conn:
        sku_row = conn.execute(get_sku_query, {"sku_id": sku_id}).fetchone()
    
    if not sku_row:
        raise ValueError(f"SKU '{sku_id}' not found in database")
    
    current_stock = int(sku_row[2])
    sku_name = sku_row[1]
    
    # Calculate new stock level: current + purchases - sales
    new_stock_level = current_stock + purchase_qty - sales_qty
    
    # Ensure stock doesn't go negative
    if new_stock_level < 0:
        raise ValueError(f"Insufficient stock. Current: {current_stock}, Cannot sell: {sales_qty}")
    
    # Insert transaction record
    insert_query = text("""
        INSERT INTO inventory_sales (sku_id, sku_name, sale_date, sales_qty, purchase_qty, stock_level)
        VALUES (:sku_id, :sku_name, :sale_date, :sales_qty, :purchase_qty, :stock_level)
        RETURNING id
    """)
    
    with engine.begin() as conn:
        result = conn.execute(
            insert_query,
            {
                "sku_id": sku_id,
                "sku_name": sku_name,
                "sale_date": transaction_date,
                "sales_qty": sales_qty,
                "purchase_qty": purchase_qty,
                "stock_level": new_stock_level,
            }
        )
        transaction_id = result.scalar()
    
    return {
        "id": transaction_id,
        "sku_id": sku_id,
        "sku_name": sku_name,
        "sale_date": transaction_date,
        "sales_qty": sales_qty,
        "purchase_qty": purchase_qty,
        "previous_stock": current_stock,
        "new_stock_level": new_stock_level,
        "message": "Transaction recorded successfully"
    }



# REPLENISHMENT SETTINGS - New functionality for stock replenishment recommendations


# Default replenishment parameters (used if no custom settings exist)
DEFAULT_REPLENISHMENT_SETTINGS = {
    "lead_time_days": 7,
    "min_order_qty": 10,
    "reorder_point": 50,
    "safety_stock": 25,
    "target_stock_level": 150,
}


def get_replenishment_settings(sku_id: str) -> dict:
    """
    Get replenishment settings for a SKU.
    
    Returns custom settings if saved, otherwise returns sensible defaults.
    Ensures defaults are used gracefully without requiring pre-populated database entries.
    
    Args:
        sku_id: The SKU identifier
    
    Returns:
        Dictionary with replenishment settings
    """
    query = text("""
        SELECT 
            sku_id, 
            lead_time_days, 
            min_order_qty, 
            reorder_point, 
            safety_stock, 
            target_stock_level,
            created_at,
            updated_at
        FROM replenishment_settings
        WHERE sku_id = :sku_id
        LIMIT 1
    """)
    
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"sku_id": sku_id}).mappings().fetchone()
        
        if row:
            return {
                "sku_id": row["sku_id"],
                "lead_time_days": int(row["lead_time_days"]),
                "min_order_qty": int(row["min_order_qty"]),
                "reorder_point": int(row["reorder_point"]),
                "safety_stock": int(row["safety_stock"]),
                "target_stock_level": int(row["target_stock_level"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "is_custom": True,
            }
    except Exception as e:
        # Table might not exist yet; fall through to defaults
        pass
    
    # Return defaults with indication that these are defaults
    return {
        "sku_id": sku_id,
        **DEFAULT_REPLENISHMENT_SETTINGS,
        "is_custom": False,
    }


def set_replenishment_settings(sku_id: str, settings: dict) -> dict:
    """
    Set or update replenishment settings for a SKU.
    
    Args:
        sku_id: The SKU identifier
        settings: Dictionary with settings (lead_time_days, min_order_qty, reorder_point, safety_stock, target_stock_level)
    
    Returns:
        Updated settings dictionary
    
    Raises:
        ValueError: If SKU not found or invalid settings
    """
    # Validate SKU exists
    check_sku_query = text("""
        SELECT sku_id FROM inventory_sales 
        WHERE sku_id = :sku_id 
        LIMIT 1
    """)
    
    with engine.connect() as conn:
        sku_row = conn.execute(check_sku_query, {"sku_id": sku_id}).fetchone()
    
    if not sku_row:
        raise ValueError(f"SKU '{sku_id}' not found in inventory")
    
    # Validate settings
    required_fields = ["lead_time_days", "min_order_qty", "reorder_point", "safety_stock", "target_stock_level"]
    for field in required_fields:
        if field not in settings:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate numeric constraints
    if settings["lead_time_days"] < 1:
        raise ValueError("lead_time_days must be >= 1")
    if settings["min_order_qty"] < 1:
        raise ValueError("min_order_qty must be >= 1")
    if settings["reorder_point"] < 0:
        raise ValueError("reorder_point must be >= 0")
    if settings["safety_stock"] < 0:
        raise ValueError("safety_stock must be >= 0")
    if settings["target_stock_level"] < settings["safety_stock"]:
        raise ValueError("target_stock_level must be >= safety_stock")
    
    # Upsert into replenishment_settings table
    upsert_query = text("""
        INSERT INTO replenishment_settings 
            (sku_id, lead_time_days, min_order_qty, reorder_point, safety_stock, target_stock_level, created_at, updated_at)
        VALUES 
            (:sku_id, :lead_time_days, :min_order_qty, :reorder_point, :safety_stock, :target_stock_level, NOW(), NOW())
        ON CONFLICT (sku_id) 
        DO UPDATE SET 
            lead_time_days = EXCLUDED.lead_time_days,
            min_order_qty = EXCLUDED.min_order_qty,
            reorder_point = EXCLUDED.reorder_point,
            safety_stock = EXCLUDED.safety_stock,
            target_stock_level = EXCLUDED.target_stock_level,
            updated_at = NOW()
        RETURNING *
    """)
    
    try:
        with engine.begin() as conn:
            result = conn.execute(
                upsert_query,
                {
                    "sku_id": sku_id,
                    "lead_time_days": settings["lead_time_days"],
                    "min_order_qty": settings["min_order_qty"],
                    "reorder_point": settings["reorder_point"],
                    "safety_stock": settings["safety_stock"],
                    "target_stock_level": settings["target_stock_level"],
                }
            )
            row = result.mappings().first()
        
        return {
            "sku_id": row["sku_id"],
            "lead_time_days": int(row["lead_time_days"]),
            "min_order_qty": int(row["min_order_qty"]),
            "reorder_point": int(row["reorder_point"]),
            "safety_stock": int(row["safety_stock"]),
            "target_stock_level": int(row["target_stock_level"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "message": "Replenishment settings saved successfully",
        }
    except Exception as e:
        if "replenishment_settings" in str(e).lower() and "does not exist" in str(e).lower():
            raise ValueError(
                "Replenishment settings table not yet created. "
                "Please ensure the database has been properly initialized."
            )
        raise ValueError(f"Error saving replenishment settings: {str(e)}")


def get_product_metrics(start_date, end_date) -> list[dict]:
    
    query = text("""
                 SELECT sku_id, sku_name, SUM(sales_qty) AS total_sales, SUM(purchase_qty) AS total_purchases
                 FROM inventory_sales
                 WHERE sale_date BETWEEN :start_date AND :end_date
                 GROUP BY sku_id, sku_name
                 ORDER BY total_sales DESC
                 """)
    
    with engine.connect() as conn:
        rows = conn.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    return [dict(r) for r in rows]


def get_daily_actual_sales(start_date: str, end_date: str) -> list[dict]:
    """Return daily total sales per SKU between two dates."""
    query = text("""
        SELECT sale_date, sku_id, sku_name, SUM(sales_qty) AS actual_sales
        FROM inventory_sales
        WHERE sale_date BETWEEN :start_date AND :end_date
        GROUP BY sale_date, sku_id, sku_name
        ORDER BY sku_id, sale_date
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "date": str(r["sale_date"]),
            "sku_id": r["sku_id"],
            "sku_name": r["sku_name"],
            "actual_sales": int(r["actual_sales"]),
        }
        for r in rows
    ]


def get_daily_transaction_counts(start_date: str, end_date: str) -> list[dict]:
    """Return the number of transaction rows per day per SKU."""
    query = text("""
        SELECT sale_date, sku_id, COUNT(*)::int AS tx_count
        FROM inventory_sales
        WHERE sale_date BETWEEN :start_date AND :end_date
        GROUP BY sale_date, sku_id
        ORDER BY sku_id, sale_date
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "date": str(r["sale_date"]),
            "sku_id": r["sku_id"],
            "tx_count": int(r["tx_count"]),
        }
        for r in rows
    ]


def get_purchase_report(start_date: str, end_date: str) -> list[dict]:
    """Return purchase transactions (purchase_qty > 0) between two dates."""
    query = text("""
        SELECT sale_date AS transaction_date, sku_id, sku_name, purchase_qty AS stock_adjustment_qty
        FROM inventory_sales
        WHERE sale_date BETWEEN :start_date AND :end_date
          AND purchase_qty > 0
        ORDER BY sale_date, sku_id
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "transaction_date": str(r["transaction_date"]),
            "sku_id": r["sku_id"],
            "sku_name": r["sku_name"],
            "stock_adjustment_qty": int(r["stock_adjustment_qty"]),
        }
        for r in rows
    ]


def get_sales_report(start_date: str, end_date: str) -> list[dict]:
    """Return sales transactions (sales_qty > 0) between two dates."""
    query = text("""
        SELECT sale_date AS transaction_date, sku_id, sku_name, sales_qty AS stock_adjustment_qty
        FROM inventory_sales
        WHERE sale_date BETWEEN :start_date AND :end_date
          AND sales_qty > 0
        ORDER BY sale_date, sku_id
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "transaction_date": str(r["transaction_date"]),
            "sku_id": r["sku_id"],
            "sku_name": r["sku_name"],
            "stock_adjustment_qty": int(r["stock_adjustment_qty"]),
        }
        for r in rows
    ]


# ── User management ───────────────────────────────────────────────────────────

def create_user(name: str, email: str, hashed_password: str) -> dict:
    """Insert a new user and return the created record."""
    query = text("""
        INSERT INTO users (name, email, hashed_password)
        VALUES (:name, :email, :hashed_password)
        RETURNING id, name, email, is_active, created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "name": name,
            "email": email,
            "hashed_password": hashed_password,
        }).mappings().first()
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    """Return a user row by email, or None if not found."""
    query = text("""
        SELECT id, username, name, email, hashed_password, business_id, role, is_active, created_at
        FROM users
        WHERE email = :email
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"email": email}).mappings().fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """Return a user row by id, or None if not found."""
    query = text("""
        SELECT id, username, name, email, is_active, created_at, business_id, role
        FROM users
        WHERE id = :user_id
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"user_id": user_id}).mappings().fetchone()
    return dict(row) if row else None


# ── Alert settings ────────────────────────────────────────────────────────────

def get_alert_settings(user_id: int) -> dict:
    """Return alert settings for a user (creates defaults if missing)."""
    query = text("""
        SELECT user_id, alerts_enabled, last_alert_sent, updated_at
        FROM alert_settings
        WHERE user_id = :user_id
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"user_id": user_id}).mappings().fetchone()
    if row:
        return {
            "user_id": row["user_id"],
            "alerts_enabled": row["alerts_enabled"],
            "last_alert_sent": str(row["last_alert_sent"]) if row["last_alert_sent"] else None,
            "updated_at": str(row["updated_at"]),
        }
    return {"user_id": user_id, "alerts_enabled": False, "last_alert_sent": None, "updated_at": None}


def set_alert_settings(user_id: int, alerts_enabled: bool) -> dict:
    """Upsert alert settings for a user."""
    query = text("""
        INSERT INTO alert_settings (user_id, alerts_enabled, updated_at)
        VALUES (:user_id, :alerts_enabled, NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET alerts_enabled = EXCLUDED.alerts_enabled, updated_at = NOW()
        RETURNING user_id, alerts_enabled, last_alert_sent, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"user_id": user_id, "alerts_enabled": alerts_enabled}).mappings().first()
    return {
        "user_id": row["user_id"],
        "alerts_enabled": row["alerts_enabled"],
        "last_alert_sent": str(row["last_alert_sent"]) if row["last_alert_sent"] else None,
        "updated_at": str(row["updated_at"]),
    }


def update_last_alert_sent(user_id: int) -> None:
    """Mark the current time as when the last alert was sent."""
    query = text("""
        UPDATE alert_settings SET last_alert_sent = NOW(), updated_at = NOW()
        WHERE user_id = :user_id
    """)
    with engine.begin() as conn:
        conn.execute(query, {"user_id": user_id})


def get_all_users_with_alerts_enabled() -> list[dict]:
    """Return all users who have alerts enabled, joined with their email."""
    query = text("""
        SELECT u.id, u.name, u.email, a.last_alert_sent
        FROM users u
        INNER JOIN alert_settings a ON a.user_id = u.id
        WHERE a.alerts_enabled = TRUE AND u.is_active = TRUE
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(r) for r in rows]


def get_at_risk_skus() -> list[dict]:
    """
    Return ALL SKUs with their current stock and replenishment settings.
    Uses defaults when no custom replenishment settings exist.
    The caller (main.py) applies forecast-based filtering.
    """
    query = text("""
        SELECT
            s.sku_id,
            s.sku_name,
            s.stock_level AS current_stock,
            COALESCE(r.reorder_point, 50)       AS reorder_point,
            COALESCE(r.safety_stock, 25)         AS safety_stock,
            COALESCE(r.lead_time_days, 7)        AS lead_time_days,
            COALESCE(r.min_order_qty, 10)        AS min_order_qty,
            COALESCE(r.target_stock_level, 150)  AS target_stock_level
        FROM (
            SELECT DISTINCT ON (sku_id)
                sku_id, sku_name, stock_level
            FROM inventory_sales
            ORDER BY sku_id, sale_date DESC, id DESC
        ) s
        LEFT JOIN replenishment_settings r ON r.sku_id = s.sku_id
        ORDER BY s.stock_level ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()
    return [dict(r) for r in rows]


# ============================================================================
# WMS 2.0 – Business, Product, Inventory Transaction helpers
# ============================================================================

# ── Business CRUD ────────────────────────────────────────────────────────────

def create_business(name: str, location: str | None = None) -> dict:
    query = text("""
        INSERT INTO businesses (name, location)
        VALUES (:name, :location)
        RETURNING id, name, location, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"name": name, "location": location}).mappings().first()
    return dict(row)


def get_business_by_id(business_id: int) -> dict | None:
    query = text("""
        SELECT id, name, location, created_at, updated_at
        FROM businesses WHERE id = :id
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_business(business_id: int, name: str, location: str | None) -> dict | None:
    query = text("""
        UPDATE businesses SET name = :name, location = :location, updated_at = NOW()
        WHERE id = :id
        RETURNING id, name, location, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"id": business_id, "name": name, "location": location}).mappings().fetchone()
    return dict(row) if row else None


# ── Product CRUD ─────────────────────────────────────────────────────────────

PRODUCT_COLUMNS = (
    "id, name, sku_code, business_id, price, stock_at_warehouse, uom, "
    "par_level, reorder_point, safety_stock, lead_time_days, max_stock_level, "
    "location_zone, location_aisle, location_rack, location_shelf, location_level, location_bin, "
    "created_at, updated_at"
)


def create_product(name: str, sku_code: str, business_id: int, price: float = 0, stock_at_warehouse: int = 0, uom: str = "pcs",
                   par_level: int = 0, reorder_point: int = 0, safety_stock: int = 0, lead_time_days: int = 0, max_stock_level: int = 0,
                   location_zone: str = "", location_aisle: str = "", location_rack: str = "",
                   location_shelf: str = "", location_level: str = "", location_bin: str = "") -> dict:
    query = text(f"""
        INSERT INTO products (name, sku_code, business_id, price, stock_at_warehouse, uom,
                              par_level, reorder_point, safety_stock, lead_time_days, max_stock_level,
                              location_zone, location_aisle, location_rack, location_shelf, location_level, location_bin)
        VALUES (:name, :sku_code, :business_id, :price, :stock, :uom,
                :par_level, :reorder_point, :safety_stock, :lead_time_days, :max_stock_level,
                :location_zone, :location_aisle, :location_rack, :location_shelf, :location_level, :location_bin)
        RETURNING {PRODUCT_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "name": name, "sku_code": sku_code, "business_id": business_id,
            "price": price, "stock": stock_at_warehouse, "uom": uom,
            "par_level": par_level, "reorder_point": reorder_point,
            "safety_stock": safety_stock, "lead_time_days": lead_time_days,
            "max_stock_level": max_stock_level,
            "location_zone": location_zone, "location_aisle": location_aisle,
            "location_rack": location_rack, "location_shelf": location_shelf,
            "location_level": location_level, "location_bin": location_bin,
        }).mappings().first()
    return dict(row)


def get_products_by_business(business_id: int, page: int = 1, per_page: int = 20, search: str = "") -> dict:
    """Return paginated products for a business with optional search."""
    offset = (page - 1) * per_page

    count_query = text("""
        SELECT COUNT(*)::int AS total FROM products
        WHERE business_id = :biz
          AND (name ILIKE :search OR sku_code ILIKE :search)
    """)
    data_query = text(f"""
        SELECT {PRODUCT_COLUMNS}
        FROM products
        WHERE business_id = :biz
          AND (name ILIKE :search OR sku_code ILIKE :search)
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """)
    search_pattern = f"%{search}%"
    with engine.connect() as conn:
        total = conn.execute(count_query, {"biz": business_id, "search": search_pattern}).scalar()
        rows = conn.execute(data_query, {
            "biz": business_id, "search": search_pattern,
            "limit": per_page, "offset": offset,
        }).mappings().all()
    return {
        "products": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_product_by_id(product_id: int, business_id: int) -> dict | None:
    query = text(f"""
        SELECT {PRODUCT_COLUMNS}
        FROM products WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": product_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_product(product_id: int, business_id: int, name: str, sku_code: str, price: float, uom: str = "pcs",
                   par_level: int = 0, reorder_point: int = 0, safety_stock: int = 0, lead_time_days: int = 0, max_stock_level: int = 0,
                   location_zone: str = "", location_aisle: str = "", location_rack: str = "",
                   location_shelf: str = "", location_level: str = "", location_bin: str = "") -> dict | None:
    query = text(f"""
        UPDATE products
        SET name = :name, sku_code = :sku_code, price = :price, uom = :uom,
            par_level = :par_level, reorder_point = :reorder_point,
            safety_stock = :safety_stock, lead_time_days = :lead_time_days,
            max_stock_level = :max_stock_level,
            location_zone = :location_zone, location_aisle = :location_aisle,
            location_rack = :location_rack, location_shelf = :location_shelf,
            location_level = :location_level, location_bin = :location_bin,
            updated_at = NOW()
        WHERE id = :id AND business_id = :biz
        RETURNING {PRODUCT_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": product_id, "biz": business_id,
            "name": name, "sku_code": sku_code, "price": price, "uom": uom,
            "par_level": par_level, "reorder_point": reorder_point,
            "safety_stock": safety_stock, "lead_time_days": lead_time_days,
            "max_stock_level": max_stock_level,
            "location_zone": location_zone, "location_aisle": location_aisle,
            "location_rack": location_rack, "location_shelf": location_shelf,
            "location_level": location_level, "location_bin": location_bin,
        }).mappings().fetchone()
    return dict(row) if row else None


# ── Product Audit Log ────────────────────────────────────────────────────────

def create_product_audit_entries(
    product_id: int,
    business_id: int,
    updated_by: int,
    changes: list[dict],
) -> list[dict]:
    """Insert one audit-log row per changed field.

    `changes` is a list of dicts: [{"field_name": str, "old_value": str, "new_value": str}, ...]
    """
    if not changes:
        return []

    insert_q = text("""
        INSERT INTO product_audit_log (product_id, business_id, updated_by, field_name, old_value, new_value)
        VALUES (:pid, :biz, :uid, :field, :old, :new)
        RETURNING id, product_id, business_id, updated_by, field_name, old_value, new_value, created_at
    """)
    results = []
    with engine.begin() as conn:
        for ch in changes:
            row = conn.execute(insert_q, {
                "pid": product_id, "biz": business_id, "uid": updated_by,
                "field": ch["field_name"], "old": ch["old_value"], "new": ch["new_value"],
            }).mappings().first()
            r = dict(row)
            r["created_at"] = str(r["created_at"])
            results.append(r)
    return results


def get_product_audit_log(product_id: int, business_id: int, page: int = 1, per_page: int = 50) -> dict:
    """Return paginated audit log for a product, newest first."""
    offset = (page - 1) * per_page

    count_q = text("""
        SELECT COUNT(*)::int AS total FROM product_audit_log
        WHERE product_id = :pid AND business_id = :biz
    """)
    data_q = text("""
        SELECT a.id, a.product_id, a.field_name, a.old_value, a.new_value, a.created_at,
               u.name AS updated_by_name
        FROM product_audit_log a
        JOIN users u ON u.id = a.updated_by
        WHERE a.product_id = :pid AND a.business_id = :biz
        ORDER BY a.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        total = conn.execute(count_q, {"pid": product_id, "biz": business_id}).scalar()
        rows = conn.execute(data_q, {
            "pid": product_id, "biz": business_id,
            "limit": per_page, "offset": offset,
        }).mappings().all()

    entries = []
    for r in rows:
        e = dict(r)
        e["created_at"] = str(e["created_at"])
        entries.append(e)

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def delete_product(product_id: int, business_id: int) -> bool:
    query = text("DELETE FROM products WHERE id = :id AND business_id = :biz")
    with engine.begin() as conn:
        result = conn.execute(query, {"id": product_id, "biz": business_id})
    return result.rowcount > 0


def check_skus_exist(business_id: int, sku_codes: list[str]) -> list[str]:
    """Return the subset of sku_codes that already exist for this business."""
    if not sku_codes:
        return []
    query = text("""
        SELECT sku_code FROM products
        WHERE business_id = :biz AND LOWER(sku_code) = ANY(:skus)
    """)
    lowered = [s.lower() for s in sku_codes]
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "skus": lowered}).fetchall()
    return [r[0] for r in rows]


# ── Inventory Overview ───────────────────────────────────────────────────────

def get_inventory_overview(business_id: int, page: int = 1, per_page: int = 20, search: str = "") -> dict:
    """Return all products with current stock for a business (paginated)."""
    offset = (page - 1) * per_page
    search_pattern = f"%{search}%"

    count_query = text("""
        SELECT COUNT(*)::int AS total FROM products
        WHERE business_id = :biz
          AND (name ILIKE :search OR sku_code ILIKE :search)
    """)
    data_query = text("""
        SELECT id, name, sku_code, price, stock_at_warehouse, uom, updated_at
        FROM products
        WHERE business_id = :biz
          AND (name ILIKE :search OR sku_code ILIKE :search)
        ORDER BY name
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        total = conn.execute(count_query, {"biz": business_id, "search": search_pattern}).scalar()
        rows = conn.execute(data_query, {
            "biz": business_id, "search": search_pattern,
            "limit": per_page, "offset": offset,
        }).mappings().all()
    return {
        "products": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_inventory_summary(business_id: int) -> dict:
    """High-level inventory stats for dashboard."""
    query = text("""
        SELECT
            COUNT(*)::int                           AS total_products,
            COALESCE(SUM(stock_at_warehouse), 0)::int AS total_stock,
            COUNT(*) FILTER (WHERE stock_at_warehouse = 0)::int AS out_of_stock,
            COUNT(*) FILTER (WHERE stock_at_warehouse > 0 AND stock_at_warehouse <= 10)::int AS low_stock
        FROM products
        WHERE business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"biz": business_id}).mappings().fetchone()
    return dict(row) if row else {"total_products": 0, "total_stock": 0, "out_of_stock": 0, "low_stock": 0}


# ── Inventory Transactions ───────────────────────────────────────────────────

def create_inventory_transaction(
    product_id: int,
    business_id: int,
    created_by: int,
    stock_adjusted: int,
    reason: str,
    reference_no: str | None = None,
    transaction_at: str | None = None,
) -> dict:
    """Record an inventory adjustment and update the product stock."""
    # Get current stock
    prod = get_product_by_id(product_id, business_id)
    if not prod:
        raise ValueError(f"Product {product_id} not found for this business")

    previous_stock = prod["stock_at_warehouse"]
    new_stock = previous_stock + stock_adjusted

    if new_stock < 0:
        raise ValueError(f"Insufficient stock. Current: {previous_stock}, Adjustment: {stock_adjusted}")

    # Update product stock
    update_stock = text("""
        UPDATE products SET stock_at_warehouse = :new_stock, updated_at = NOW()
        WHERE id = :id AND business_id = :biz
    """)

    # Insert transaction record
    insert_tx = text("""
        INSERT INTO inventory_transactions
            (product_id, business_id, created_by, stock_adjusted, previous_stock, current_stock,
             transaction_at, reference_no, reason)
        VALUES
            (:product_id, :biz, :user_id, :adjusted, :prev, :curr,
             COALESCE(:tx_at::timestamptz, NOW()), :ref, :reason)
        RETURNING id, product_id, business_id, created_by, stock_adjusted, previous_stock,
                  current_stock, transaction_at, reference_no, reason
    """)

    with engine.begin() as conn:
        conn.execute(update_stock, {"new_stock": new_stock, "id": product_id, "biz": business_id})
        row = conn.execute(insert_tx, {
            "product_id": product_id, "biz": business_id, "user_id": created_by,
            "adjusted": stock_adjusted, "prev": previous_stock, "curr": new_stock,
            "tx_at": transaction_at, "ref": reference_no, "reason": reason,
        }).mappings().first()

    result = dict(row)
    result["transaction_at"] = str(result["transaction_at"])
    return result


def get_inventory_transactions(
    business_id: int,
    product_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Return paginated inventory transactions for a business, optionally filtered by product and date range."""
    offset = (page - 1) * per_page

    where_clauses = ["t.business_id = :biz"]
    params: dict = {"biz": business_id, "limit": per_page, "offset": offset}

    if product_id:
        where_clauses.append("t.product_id = :pid")
        params["pid"] = product_id
    if start_date:
        where_clauses.append("t.transaction_at >= :start::timestamptz")
        params["start"] = start_date
    if end_date:
        where_clauses.append("t.transaction_at <= (:end::date + INTERVAL '1 day')")
        params["end"] = end_date

    where_sql = " AND ".join(where_clauses)

    count_query = text(f"SELECT COUNT(*)::int AS total FROM inventory_transactions t WHERE {where_sql}")
    data_query = text(f"""
        SELECT t.id, t.product_id, p.name AS product_name, p.sku_code,
               t.stock_adjusted, t.previous_stock, t.current_stock,
               t.transaction_at, t.reference_no, t.reason,
               u.name AS created_by_name
        FROM inventory_transactions t
        JOIN products p ON p.id = t.product_id
        JOIN users u ON u.id = t.created_by
        WHERE {where_sql}
        ORDER BY t.transaction_at DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        total = conn.execute(count_query, params).scalar()
        rows = conn.execute(data_query, params).mappings().all()

    transactions = []
    for r in rows:
        tx = dict(r)
        tx["transaction_at"] = str(tx["transaction_at"])
        transactions.append(tx)

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


# ── Inventory Batches ────────────────────────────────────────────────────────

def create_inventory_batch(
    business_id: int,
    created_by: int,
    reason: str,
    items: list[dict],
    reference_no: str | None = None,
    notes: str = "",
    transaction_at: str | None = None,
) -> dict:
    """Create a batch transaction that groups multiple product adjustments into one event.

    `items` is a list of dicts: [{"product_id": int, "stock_adjusted": int}, ...]
    Returns the batch record plus its line items.
    """
    if not items:
        raise ValueError("At least one line item is required")

    with engine.begin() as conn:
        # Validate all products belong to this business and compute totals
        total_items = 0
        total_amount = 0.0
        line_data = []

        for item in items:
            pid = item["product_id"]
            adj = item["stock_adjusted"]
            prod_q = text("SELECT id, name, sku_code, price, stock_at_warehouse FROM products WHERE id = :id AND business_id = :biz")
            prod = conn.execute(prod_q, {"id": pid, "biz": business_id}).mappings().fetchone()
            if not prod:
                raise ValueError(f"Product {pid} not found for this business")

            prev = prod["stock_at_warehouse"]
            new = prev + adj
            if new < 0:
                raise ValueError(f"Insufficient stock for {prod['name']}. Current: {prev}, Adjustment: {adj}")

            total_items += abs(adj)
            total_amount += abs(adj) * float(prod["price"])
            line_data.append({
                "product_id": pid,
                "product_name": prod["name"],
                "sku_code": prod["sku_code"],
                "price": float(prod["price"]),
                "stock_adjusted": adj,
                "previous_stock": prev,
                "current_stock": new,
            })

        # Insert batch
        batch_q = text("""
            INSERT INTO inventory_batches
                (business_id, created_by, reason, reference_no, notes, total_items, total_amount, transaction_at)
            VALUES
                (:biz, :uid, :reason, :ref, :notes, :total_items, :total_amount,
                 COALESCE(:tx_at::timestamptz, NOW()))
            RETURNING id, business_id, created_by, reason, reference_no, notes,
                      total_items, total_amount, transaction_at, created_at
        """)
        batch_row = conn.execute(batch_q, {
            "biz": business_id, "uid": created_by, "reason": reason,
            "ref": reference_no, "notes": notes,
            "total_items": total_items, "total_amount": total_amount,
            "tx_at": transaction_at,
        }).mappings().first()
        batch = dict(batch_row)
        batch_id = batch["id"]

        # Insert each line item and update product stock
        for ld in line_data:
            conn.execute(text("""
                UPDATE products SET stock_at_warehouse = :new_stock, updated_at = NOW()
                WHERE id = :id AND business_id = :biz
            """), {"new_stock": ld["current_stock"], "id": ld["product_id"], "biz": business_id})

            conn.execute(text("""
                INSERT INTO inventory_transactions
                    (product_id, business_id, created_by, stock_adjusted, previous_stock, current_stock,
                     transaction_at, reference_no, reason, batch_id)
                VALUES
                    (:pid, :biz, :uid, :adj, :prev, :curr,
                     COALESCE(:tx_at::timestamptz, NOW()), :ref, :reason, :batch_id)
            """), {
                "pid": ld["product_id"], "biz": business_id, "uid": created_by,
                "adj": ld["stock_adjusted"], "prev": ld["previous_stock"], "curr": ld["current_stock"],
                "tx_at": transaction_at, "ref": reference_no, "reason": reason, "batch_id": batch_id,
            })

    batch["transaction_at"] = str(batch["transaction_at"])
    batch["created_at"] = str(batch["created_at"])
    batch["items"] = line_data
    return batch


def get_inventory_batches(
    business_id: int,
    page: int = 1,
    per_page: int = 20,
    start_date: str | None = None,
    end_date: str | None = None,
    reason: str | None = None,
) -> dict:
    """Return paginated inventory batches for the business."""
    offset = (page - 1) * per_page

    where_clauses = ["b.business_id = :biz"]
    params: dict = {"biz": business_id, "limit": per_page, "offset": offset}

    if start_date:
        where_clauses.append("b.transaction_at >= :start::timestamptz")
        params["start"] = start_date
    if end_date:
        where_clauses.append("b.transaction_at <= (:end::date + INTERVAL '1 day')")
        params["end"] = end_date
    if reason:
        where_clauses.append("b.reason = :reason")
        params["reason"] = reason

    where_sql = " AND ".join(where_clauses)

    count_q = text(f"SELECT COUNT(*)::int AS total FROM inventory_batches b WHERE {where_sql}")
    data_q = text(f"""
        SELECT b.id, b.reason, b.reference_no, b.notes, b.total_items,
               b.total_amount, b.transaction_at, b.created_at,
               u.name AS created_by_name
        FROM inventory_batches b
        JOIN users u ON u.id = b.created_by
        WHERE {where_sql}
        ORDER BY b.transaction_at DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        total = conn.execute(count_q, params).scalar()
        rows = conn.execute(data_q, params).mappings().all()

    batches = []
    for r in rows:
        b = dict(r)
        b["transaction_at"] = str(b["transaction_at"])
        b["created_at"] = str(b["created_at"])
        batches.append(b)

    return {
        "batches": batches,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_inventory_batch_detail(batch_id: int, business_id: int) -> dict | None:
    """Return a single batch with its line items."""
    batch_q = text("""
        SELECT b.id, b.reason, b.reference_no, b.notes, b.total_items,
               b.total_amount, b.transaction_at, b.created_at,
               u.name AS created_by_name
        FROM inventory_batches b
        JOIN users u ON u.id = b.created_by
        WHERE b.id = :id AND b.business_id = :biz
    """)
    items_q = text("""
        SELECT t.id, t.product_id, p.name AS product_name, p.sku_code, p.price,
               t.stock_adjusted, t.previous_stock, t.current_stock
        FROM inventory_transactions t
        JOIN products p ON p.id = t.product_id
        WHERE t.batch_id = :batch_id AND t.business_id = :biz
        ORDER BY p.name
    """)

    with engine.connect() as conn:
        batch_row = conn.execute(batch_q, {"id": batch_id, "biz": business_id}).mappings().fetchone()
        if not batch_row:
            return None
        items_rows = conn.execute(items_q, {"batch_id": batch_id, "biz": business_id}).mappings().all()

    batch = dict(batch_row)
    batch["transaction_at"] = str(batch["transaction_at"])
    batch["created_at"] = str(batch["created_at"])
    batch["items"] = [dict(r) for r in items_rows]
    return batch


# ── User management (WMS 2.0 – updated) ─────────────────────────────────────

def create_user_v2(username: str, name: str, email: str, hashed_password: str, business_id: int | None = None, role: str = "employee") -> dict:
    query = text("""
        INSERT INTO users (username, name, email, hashed_password, business_id, role)
        VALUES (:username, :name, :email, :hashed_password, :business_id, :role)
        RETURNING id, username, name, email, business_id, role, is_active, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "username": username, "name": name, "email": email,
            "hashed_password": hashed_password, "business_id": business_id, "role": role,
        }).mappings().first()
    return dict(row)


def get_users_by_business(business_id: int) -> list[dict]:
    query = text("""
        SELECT id, username, name, email, role, is_active, created_at, updated_at
        FROM users WHERE business_id = :biz AND is_active = TRUE
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def update_user_business(user_id: int, business_id: int) -> dict | None:
    query = text("""
        UPDATE users SET business_id = :biz, updated_at = NOW()
        WHERE id = :uid
        RETURNING id, username, name, email, business_id, role, is_active, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"uid": user_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_user_role(user_id: int, role: str, business_id: int) -> dict | None:
    query = text("""
        UPDATE users SET role = :role, updated_at = NOW()
        WHERE id = :uid AND business_id = :biz
        RETURNING id, username, name, email, business_id, role, is_active, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"uid": user_id, "role": role, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


# ── Invite system ────────────────────────────────────────────────────────────

def get_users_without_business(search: str = "") -> list[dict]:
    """Return users who don't belong to any business."""
    query = text("""
        SELECT id, username, name, email, created_at
        FROM users
        WHERE business_id IS NULL AND is_active = TRUE
          AND (name ILIKE :search OR email ILIKE :search)
        ORDER BY name
        LIMIT 50
    """)
    search_pattern = f"%{search}%"
    with engine.connect() as conn:
        rows = conn.execute(query, {"search": search_pattern}).mappings().all()
    return [dict(r) for r in rows]


def create_invite(from_business_id: int, from_user_id: int, to_user_id: int) -> dict:
    """Create an invite. Raises if duplicate pending invite exists."""
    query = text("""
        INSERT INTO invites (from_business_id, from_user_id, to_user_id, status)
        VALUES (:biz, :from_uid, :to_uid, 'pending')
        RETURNING id, from_business_id, from_user_id, to_user_id, status, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": from_business_id, "from_uid": from_user_id, "to_uid": to_user_id,
        }).mappings().first()
    return dict(row)


def get_sent_invites(business_id: int) -> list[dict]:
    """Return all invites sent from a business, with invitee info."""
    query = text("""
        SELECT i.id, i.from_business_id, i.from_user_id, i.to_user_id, i.status,
               i.created_at, i.updated_at,
               u.name AS to_user_name, u.email AS to_user_email
        FROM invites i
        JOIN users u ON u.id = i.to_user_id
        WHERE i.from_business_id = :biz
        ORDER BY i.created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_received_invites(user_id: int) -> list[dict]:
    """Return all invites received by a user, with business + sender info."""
    query = text("""
        SELECT i.id, i.from_business_id, i.from_user_id, i.to_user_id, i.status,
               i.created_at, i.updated_at,
               b.name AS business_name, b.location AS business_location,
               u.name AS from_user_name
        FROM invites i
        JOIN businesses b ON b.id = i.from_business_id
        JOIN users u ON u.id = i.from_user_id
        WHERE i.to_user_id = :uid
        ORDER BY i.created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"uid": user_id}).mappings().all()
    return [dict(r) for r in rows]


def accept_invite(invite_id: int, user_id: int) -> dict | None:
    """Accept an invite: update invite status, set user's business_id + role."""
    get_q = text("""
        SELECT id, from_business_id, to_user_id, status
        FROM invites WHERE id = :id AND to_user_id = :uid AND status = 'pending'
    """)
    update_invite_q = text("""
        UPDATE invites SET status = 'accepted', updated_at = NOW()
        WHERE id = :id
        RETURNING id, from_business_id, from_user_id, to_user_id, status, created_at, updated_at
    """)
    update_user_q = text("""
        UPDATE users SET business_id = :biz, role = 'employee', updated_at = NOW()
        WHERE id = :uid
        RETURNING id, username, name, email, business_id, role
    """)
    reject_others_q = text("""
        UPDATE invites SET status = 'rejected', updated_at = NOW()
        WHERE to_user_id = :uid AND status = 'pending' AND id != :id
    """)
    with engine.begin() as conn:
        invite = conn.execute(get_q, {"id": invite_id, "uid": user_id}).mappings().fetchone()
        if not invite:
            return None
        conn.execute(update_invite_q, {"id": invite_id})
        conn.execute(update_user_q, {"uid": user_id, "biz": invite["from_business_id"]})
        conn.execute(reject_others_q, {"uid": user_id, "id": invite_id})
    return {"message": "Invite accepted", "business_id": invite["from_business_id"]}


def reject_invite(invite_id: int, user_id: int) -> dict | None:
    """Reject an invite."""
    query = text("""
        UPDATE invites SET status = 'rejected', updated_at = NOW()
        WHERE id = :id AND to_user_id = :uid AND status = 'pending'
        RETURNING id, from_business_id, from_user_id, to_user_id, status, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {"id": invite_id, "uid": user_id}).mappings().fetchone()
    return dict(row) if row else None


def check_pending_invite(from_business_id: int, to_user_id: int) -> bool:
    """Check if there's already a pending invite from this business to this user."""
    query = text("""
        SELECT 1 FROM invites
        WHERE from_business_id = :biz AND to_user_id = :uid AND status = 'pending'
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"biz": from_business_id, "uid": to_user_id}).fetchone()
    return row is not None


# ── Delivery Locations CRUD ──────────────────────────────────────────────────

def create_delivery_location(business_id: int, name: str, address: str = "",
                             city: str = "", state: str = "", zip_code: str = "",
                             contact_person: str = "", contact_phone: str = "",
                             notes: str = "") -> dict:
    query = text("""
        INSERT INTO delivery_locations
            (business_id, name, address, city, state, zip_code, contact_person, contact_phone, notes)
        VALUES (:biz, :name, :address, :city, :state, :zip_code, :contact_person, :contact_phone, :notes)
        RETURNING id, business_id, name, address, city, state, zip_code,
                  contact_person, contact_phone, notes, is_active, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "name": name, "address": address,
            "city": city, "state": state, "zip_code": zip_code,
            "contact_person": contact_person, "contact_phone": contact_phone,
            "notes": notes,
        }).mappings().first()
    return dict(row)


def get_delivery_locations(business_id: int, include_inactive: bool = False) -> list[dict]:
    if include_inactive:
        query = text("""
            SELECT id, business_id, name, address, city, state, zip_code,
                   contact_person, contact_phone, notes, is_active, created_at, updated_at
            FROM delivery_locations WHERE business_id = :biz
            ORDER BY name
        """)
    else:
        query = text("""
            SELECT id, business_id, name, address, city, state, zip_code,
                   contact_person, contact_phone, notes, is_active, created_at, updated_at
            FROM delivery_locations WHERE business_id = :biz AND is_active = TRUE
            ORDER BY name
        """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_delivery_location_by_id(location_id: int, business_id: int) -> dict | None:
    query = text("""
        SELECT id, business_id, name, address, city, state, zip_code,
               contact_person, contact_phone, notes, is_active, created_at, updated_at
        FROM delivery_locations WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": location_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_delivery_location(location_id: int, business_id: int, name: str,
                             address: str = "", city: str = "", state: str = "",
                             zip_code: str = "", contact_person: str = "",
                             contact_phone: str = "", notes: str = "",
                             is_active: bool = True) -> dict | None:
    query = text("""
        UPDATE delivery_locations
        SET name = :name, address = :address, city = :city, state = :state,
            zip_code = :zip_code, contact_person = :contact_person,
            contact_phone = :contact_phone, notes = :notes,
            is_active = :is_active, updated_at = NOW()
        WHERE id = :id AND business_id = :biz
        RETURNING id, business_id, name, address, city, state, zip_code,
                  contact_person, contact_phone, notes, is_active, created_at, updated_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": location_id, "biz": business_id, "name": name,
            "address": address, "city": city, "state": state,
            "zip_code": zip_code, "contact_person": contact_person,
            "contact_phone": contact_phone, "notes": notes,
            "is_active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


def delete_delivery_location(location_id: int, business_id: int) -> bool:
    query = text("DELETE FROM delivery_locations WHERE id = :id AND business_id = :biz")
    with engine.begin() as conn:
        result = conn.execute(query, {"id": location_id, "biz": business_id})
    return result.rowcount > 0


# ── Dashboard helpers ────────────────────────────────────────────────────────

def get_products_without_location(business_id: int) -> list[dict]:
    """Return products that have no warehouse location set (all location fields empty)."""
    query = text(f"""
        SELECT {PRODUCT_COLUMNS}
        FROM products
        WHERE business_id = :biz
          AND location_zone  = ''
          AND location_aisle = ''
          AND location_rack  = ''
          AND location_shelf = ''
          AND location_level = ''
          AND location_bin   = ''
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_dashboard_stats(business_id: int) -> dict:
    """Aggregate stats for the dashboard."""
    queries = {
        "total_products": text("""
            SELECT COUNT(*)::int FROM products WHERE business_id = :biz
        """),
        "products_without_location": text("""
            SELECT COUNT(*)::int FROM products
            WHERE business_id = :biz
              AND location_zone  = ''
              AND location_aisle = ''
              AND location_rack  = ''
              AND location_shelf = ''
              AND location_level = ''
              AND location_bin   = ''
        """),
        "low_stock_products": text("""
            SELECT COUNT(*)::int FROM products
            WHERE business_id = :biz
              AND reorder_point > 0
              AND stock_at_warehouse <= reorder_point
        """),
        "out_of_stock_products": text("""
            SELECT COUNT(*)::int FROM products
            WHERE business_id = :biz AND stock_at_warehouse = 0
        """),
    }
    stats = {}
    with engine.connect() as conn:
        for key, q in queries.items():
            stats[key] = conn.execute(q, {"biz": business_id}).scalar() or 0
    return stats