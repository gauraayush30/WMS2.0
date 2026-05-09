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
        SELECT id, username, name, email, hashed_password, business_id, role,
               customer_id, is_active, created_at
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
        SELECT id, username, name, email, is_active, created_at,
               business_id, role, customer_id
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
    "expiry_days, "
    "location_zone, location_aisle, location_rack, location_shelf, location_level, location_bin, "
    "created_at, updated_at"
)


def create_product(name: str, sku_code: str, business_id: int, price: float = 0, stock_at_warehouse: int = 0, uom: str = "pcs",
                   par_level: int = 0, reorder_point: int = 0, safety_stock: int = 0, lead_time_days: int = 0, max_stock_level: int = 0,
                   expiry_days: int = 0,
                   location_zone: str = "", location_aisle: str = "", location_rack: str = "",
                   location_shelf: str = "", location_level: str = "", location_bin: str = "") -> dict:
    query = text(f"""
        INSERT INTO products (name, sku_code, business_id, price, stock_at_warehouse, uom,
                              par_level, reorder_point, safety_stock, lead_time_days, max_stock_level,
                              expiry_days,
                              location_zone, location_aisle, location_rack, location_shelf, location_level, location_bin)
        VALUES (:name, :sku_code, :business_id, :price, :stock, :uom,
                :par_level, :reorder_point, :safety_stock, :lead_time_days, :max_stock_level,
                :expiry_days,
                :location_zone, :location_aisle, :location_rack, :location_shelf, :location_level, :location_bin)
        RETURNING {PRODUCT_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "name": name, "sku_code": sku_code, "business_id": business_id,
            "price": price, "stock": stock_at_warehouse, "uom": uom,
            "par_level": par_level, "reorder_point": reorder_point,
            "safety_stock": safety_stock, "lead_time_days": lead_time_days,
            "max_stock_level": max_stock_level, "expiry_days": expiry_days,
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
                   expiry_days: int = 0,
                   location_zone: str = "", location_aisle: str = "", location_rack: str = "",
                   location_shelf: str = "", location_level: str = "", location_bin: str = "") -> dict | None:
    query = text(f"""
        UPDATE products
        SET name = :name, sku_code = :sku_code, price = :price, uom = :uom,
            par_level = :par_level, reorder_point = :reorder_point,
            safety_stock = :safety_stock, lead_time_days = :lead_time_days,
            max_stock_level = :max_stock_level, expiry_days = :expiry_days,
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
            "max_stock_level": max_stock_level, "expiry_days": expiry_days,
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

def get_inventory_overview(
    business_id: int,
    customer_id: int | None = None,
    page: int = 1,
    per_page: int = 20,
    search: str = "",
) -> dict:
    """Return all products with current stock for a business (paginated).

    `customer_id=None` shows all customers (warehouse view).
    """
    offset = (page - 1) * per_page
    search_pattern = f"%{search}%"

    where = ["p.business_id = :biz", "(p.name ILIKE :search OR p.sku_code ILIKE :search)"]
    params: dict = {"biz": business_id, "search": search_pattern}
    if customer_id is not None:
        where.append("p.customer_id = :cust")
        params["cust"] = customer_id

    where_sql = " AND ".join(where)
    count_query = text(f"SELECT COUNT(*)::int AS total FROM products p WHERE {where_sql}")
    data_query = text(f"""
        SELECT p.id, p.name, p.sku_code, p.price, p.stock_at_warehouse, p.uom, p.updated_at,
               p.customer_id, c.name AS customer_name, c.code AS customer_code
        FROM products p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE {where_sql}
        ORDER BY p.name
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        total = conn.execute(count_query, params).scalar()
        rows = conn.execute(data_query, {**params, "limit": per_page, "offset": offset}).mappings().all()
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
             COALESCE(CAST(:tx_at AS timestamptz), NOW()), :ref, :reason)
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
        where_clauses.append("t.transaction_at >= CAST(:start AS timestamptz)")
        params["start"] = start_date
    if end_date:
        where_clauses.append("t.transaction_at <= (CAST(:end AS date) + INTERVAL '1 day')")
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
                 COALESCE(CAST(:tx_at AS timestamptz), NOW()))
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
                     COALESCE(CAST(:tx_at AS timestamptz), NOW()), :ref, :reason, :batch_id)
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
        where_clauses.append("b.transaction_at >= CAST(:start AS timestamptz)")
        params["start"] = start_date
    if end_date:
        where_clauses.append("b.transaction_at <= (CAST(:end AS date) + INTERVAL '1 day')")
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


def get_product_analytics(product_id: int, business_id: int, days: int = 90,
                          start_date: str | None = None, end_date: str | None = None) -> dict:
    """Return daily-aggregated transaction analytics for a single product.

    Includes daily inbound/outbound/net, closing stock, reason breakdown,
    and summary statistics.  Also merges uploaded ML history data.

    If start_date/end_date are provided they take precedence over days.
    """
    # Build the date filter clause depending on which params are set
    if start_date and end_date:
        tx_date_filter = "AND t.transaction_at >= CAST(:start_date AS date) AND t.transaction_at < (CAST(:end_date AS date) + INTERVAL '1 day')"
        ml_date_filter = "AND m.date >= CAST(:start_date AS date) AND m.date <= CAST(:end_date AS date)"
        reason_tx_filter = "AND transaction_at >= CAST(:start_date AS date) AND transaction_at < (CAST(:end_date AS date) + INTERVAL '1 day')"
        reason_ml_filter = "AND date >= CAST(:start_date AS date) AND date <= CAST(:end_date AS date)"
    else:
        tx_date_filter = "AND t.transaction_at >= NOW() - MAKE_INTERVAL(days => :days)"
        ml_date_filter = "AND m.date >= (CURRENT_DATE - MAKE_INTERVAL(days => :days))"
        reason_tx_filter = "AND transaction_at >= NOW() - MAKE_INTERVAL(days => :days)"
        reason_ml_filter = "AND date >= (CURRENT_DATE - MAKE_INTERVAL(days => :days))"

    daily_query = text(f"""
        WITH combined AS (
            SELECT
                DATE(t.transaction_at)  AS date,
                t.stock_adjusted,
                t.current_stock,
                t.reason,
                t.transaction_at
            FROM inventory_transactions t
            WHERE t.product_id  = :pid
              AND t.business_id = :biz
              {tx_date_filter}

            UNION ALL

            SELECT
                m.date                          AS date,
                (m.inbound_qty - m.outbound_qty) AS stock_adjusted,
                m.stock_level                   AS current_stock,
                'uploaded_history'              AS reason,
                m.date::timestamp               AS transaction_at
            FROM ml_uploaded_history m
            WHERE m.product_id  = :pid
              AND m.business_id = :biz
              {ml_date_filter}
        )
        SELECT
            date,
            SUM(CASE WHEN stock_adjusted > 0 THEN stock_adjusted ELSE 0 END)::int             AS inbound,
            SUM(CASE WHEN stock_adjusted < 0 THEN ABS(stock_adjusted) ELSE 0 END)::int        AS outbound,
            SUM(stock_adjusted)::int                                                            AS net_change,
            (ARRAY_AGG(current_stock ORDER BY transaction_at DESC))[1]::int                    AS closing_stock,
            COUNT(*)::int                                                                       AS tx_count,
            SUM(CASE WHEN reason IN ('stock_in','delivery') AND stock_adjusted > 0
                     THEN stock_adjusted ELSE 0 END)::int                                      AS stock_in_qty,
            SUM(CASE WHEN reason IN ('stock_out','shipment') AND stock_adjusted < 0
                     THEN ABS(stock_adjusted) ELSE 0 END)::int                                 AS stock_out_qty,
            SUM(CASE WHEN reason = 'return'
                     THEN ABS(stock_adjusted) ELSE 0 END)::int                                 AS return_qty,
            SUM(CASE WHEN reason = 'damage'
                     THEN ABS(stock_adjusted) ELSE 0 END)::int                                 AS damage_qty,
            SUM(CASE WHEN reason = 'adjustment'
                     THEN stock_adjusted ELSE 0 END)::int                                      AS adjustment_qty,
            SUM(CASE WHEN reason = 'uploaded_history' AND stock_adjusted > 0
                     THEN stock_adjusted ELSE 0 END)::int                                      AS uploaded_inbound_qty,
            SUM(CASE WHEN reason = 'uploaded_history' AND stock_adjusted < 0
                     THEN ABS(stock_adjusted) ELSE 0 END)::int                                 AS uploaded_outbound_qty
        FROM combined
        GROUP BY date
        ORDER BY date
    """)

    summary_query = text("""
        WITH combined AS (
            SELECT stock_adjusted, transaction_at
            FROM inventory_transactions
            WHERE product_id  = :pid AND business_id = :biz

            UNION ALL

            SELECT (inbound_qty - outbound_qty) AS stock_adjusted,
                   date::timestamp              AS transaction_at
            FROM ml_uploaded_history
            WHERE product_id  = :pid AND business_id = :biz
        )
        SELECT
            COUNT(*)::int                                                                      AS total_transactions,
            COALESCE(SUM(CASE WHEN stock_adjusted > 0 THEN stock_adjusted ELSE 0 END), 0)::int AS total_inbound,
            COALESCE(SUM(CASE WHEN stock_adjusted < 0 THEN ABS(stock_adjusted) ELSE 0 END), 0)::int AS total_outbound,
            MIN(transaction_at)                                                                 AS first_transaction,
            MAX(transaction_at)                                                                 AS last_transaction,
            COUNT(DISTINCT DATE(transaction_at))::int                                           AS active_days
        FROM combined
    """)

    reason_query = text(f"""
        WITH combined AS (
            SELECT reason, stock_adjusted, transaction_at
            FROM inventory_transactions
            WHERE product_id  = :pid
              AND business_id = :biz
              {reason_tx_filter}

            UNION ALL

            SELECT
                'uploaded_history'              AS reason,
                (inbound_qty - outbound_qty)    AS stock_adjusted,
                date::timestamp                 AS transaction_at
            FROM ml_uploaded_history
            WHERE product_id  = :pid
              AND business_id = :biz
              {reason_ml_filter}
        )
        SELECT
            reason,
            COUNT(*)::int AS count,
            SUM(ABS(stock_adjusted))::int AS total_qty
        FROM combined
        GROUP BY reason
        ORDER BY total_qty DESC
    """)

    params: dict = {"pid": product_id, "biz": business_id, "days": days}
    if start_date and end_date:
        params["start_date"] = start_date
        params["end_date"] = end_date

    with engine.connect() as conn:
        daily_rows = conn.execute(daily_query, params).mappings().all()
        summary_row = conn.execute(summary_query, {"pid": product_id, "biz": business_id}).mappings().fetchone()
        reason_rows = conn.execute(reason_query, params).mappings().all()

    daily = []
    for r in daily_rows:
        d = dict(r)
        d["date"] = str(d["date"])
        daily.append(d)

    summary = dict(summary_row) if summary_row else {}
    if summary.get("first_transaction"):
        summary["first_transaction"] = str(summary["first_transaction"])
    if summary.get("last_transaction"):
        summary["last_transaction"] = str(summary["last_transaction"])

    reasons = [dict(r) for r in reason_rows]

    return {"daily": daily, "summary": summary, "reasons": reasons}


# ── Stock Batches (Expiry Tracking) ──────────────────────────────────────────

def create_stock_batch(
    product_id: int,
    business_id: int,
    quantity: int,
    purchased_at: str | None = None,
    expires_at: str | None = None,
    transaction_id: int | None = None,
) -> dict:
    """Insert a new stock batch row."""
    query = text("""
        INSERT INTO stock_batches
            (product_id, business_id, quantity, remaining_qty, purchased_at, expires_at, transaction_id)
        VALUES
            (:pid, :biz, :qty, :qty, COALESCE(CAST(:purchased_at AS timestamptz), NOW()), CAST(:expires_at AS date), :tx_id)
        RETURNING id, product_id, business_id, quantity, remaining_qty,
                  purchased_at, expires_at, is_expired, transaction_id, created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "pid": product_id, "biz": business_id, "qty": quantity,
            "purchased_at": purchased_at, "expires_at": expires_at,
            "tx_id": transaction_id,
        }).mappings().first()
    result = dict(row)
    result["purchased_at"] = str(result["purchased_at"])
    result["expires_at"] = str(result["expires_at"]) if result["expires_at"] else None
    result["created_at"] = str(result["created_at"])
    return result


def consume_stock_batches(product_id: int, business_id: int, qty_to_consume: int) -> None:
    """FIFO deduction from active stock batches when stock is sold/out.

    Consumes from the batch expiring soonest first (NULL expires_at = last).
    """
    if qty_to_consume <= 0:
        return

    fetch_q = text("""
        SELECT id, remaining_qty FROM stock_batches
        WHERE product_id = :pid AND business_id = :biz
          AND remaining_qty > 0 AND is_expired = FALSE
        ORDER BY expires_at ASC NULLS LAST, purchased_at ASC
    """)
    update_q = text("""
        UPDATE stock_batches SET remaining_qty = :rem WHERE id = :id
    """)

    with engine.begin() as conn:
        rows = conn.execute(fetch_q, {"pid": product_id, "biz": business_id}).mappings().all()
        remaining = qty_to_consume
        for batch in rows:
            if remaining <= 0:
                break
            deduct = min(remaining, batch["remaining_qty"])
            new_rem = batch["remaining_qty"] - deduct
            conn.execute(update_q, {"rem": new_rem, "id": batch["id"]})
            remaining -= deduct


def get_stock_batches_by_product(product_id: int, business_id: int) -> list[dict]:
    """Return all stock batches for a product, ordered by expiry date."""
    query = text("""
        SELECT id, product_id, business_id, quantity, remaining_qty,
               purchased_at, expires_at, is_expired, transaction_id, created_at
        FROM stock_batches
        WHERE product_id = :pid AND business_id = :biz
        ORDER BY is_expired ASC, expires_at ASC NULLS LAST, purchased_at ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"pid": product_id, "biz": business_id}).mappings().all()
    results = []
    for r in rows:
        d = dict(r)
        d["purchased_at"] = str(d["purchased_at"])
        d["expires_at"] = str(d["expires_at"]) if d["expires_at"] else None
        d["created_at"] = str(d["created_at"])
        results.append(d)
    return results


def expire_stock_batches_for_business(business_id: int) -> list[dict]:
    """Find and expire all batches past their expires_at date for a business.

    For each expired batch:
      1. Mark it as is_expired = TRUE
      2. Deduct remaining_qty from the product's stock_at_warehouse
      3. Create an inventory transaction with reason 'expired'
    Returns a list of expired batch summaries.
    """
    fetch_q = text("""
        SELECT sb.id, sb.product_id, sb.remaining_qty, sb.expires_at,
               p.stock_at_warehouse, p.name AS product_name
        FROM stock_batches sb
        JOIN products p ON p.id = sb.product_id
        WHERE sb.business_id = :biz
          AND sb.is_expired = FALSE
          AND sb.remaining_qty > 0
          AND sb.expires_at IS NOT NULL
          AND sb.expires_at < CURRENT_DATE
    """)
    mark_q = text("UPDATE stock_batches SET is_expired = TRUE, remaining_qty = 0 WHERE id = :id")
    update_stock_q = text("""
        UPDATE products SET stock_at_warehouse = GREATEST(stock_at_warehouse - :qty, 0), updated_at = NOW()
        WHERE id = :pid AND business_id = :biz
    """)
    insert_tx_q = text("""
        INSERT INTO inventory_transactions
            (product_id, business_id, created_by, stock_adjusted, previous_stock, current_stock,
             transaction_at, reason)
        VALUES
            (:pid, :biz, 1, :adj, :prev, :curr, NOW(), 'expired')
    """)

    expired_list = []
    with engine.begin() as conn:
        rows = conn.execute(fetch_q, {"biz": business_id}).mappings().all()
        for r in rows:
            batch_id = r["id"]
            pid = r["product_id"]
            rem = r["remaining_qty"]
            prev_stock = r["stock_at_warehouse"]
            new_stock = max(prev_stock - rem, 0)

            conn.execute(mark_q, {"id": batch_id})
            conn.execute(update_stock_q, {"qty": rem, "pid": pid, "biz": business_id})
            conn.execute(insert_tx_q, {
                "pid": pid, "biz": business_id,
                "adj": -rem, "prev": prev_stock, "curr": new_stock,
            })
            expired_list.append({
                "batch_id": batch_id,
                "product_id": pid,
                "product_name": r["product_name"],
                "expired_qty": rem,
                "expires_at": str(r["expires_at"]),
            })
    return expired_list


def get_all_business_ids() -> list[int]:
    """Return all business IDs."""
    query = text("SELECT id FROM businesses ORDER BY id")
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return [r[0] for r in rows]


# ── Location Utilization ─────────────────────────────────────────────────────

def get_product_velocity_classification(business_id: int, days: int = 90) -> list[dict]:
    """Classify products as A/B/C based on outbound volume over last N days.

    A = top 20% by outbound volume (fast movers)
    B = next 30% (medium movers)
    C = bottom 50% (slow movers)
    """
    query = text("""
        SELECT
            p.id, p.name, p.sku_code, p.stock_at_warehouse,
            p.location_zone, p.location_aisle, p.location_rack,
            p.location_shelf, p.location_level, p.location_bin,
            COALESCE(SUM(CASE WHEN t.stock_adjusted < 0
                              THEN ABS(t.stock_adjusted) ELSE 0 END), 0)::int AS outbound_volume,
            COUNT(CASE WHEN t.stock_adjusted < 0 THEN 1 END)::int AS outbound_tx_count
        FROM products p
        LEFT JOIN inventory_transactions t
            ON t.product_id = p.id
           AND t.business_id = p.business_id
           AND t.transaction_at >= NOW() - MAKE_INTERVAL(days => :days)
        WHERE p.business_id = :biz
        GROUP BY p.id
        ORDER BY outbound_volume DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "days": days}).mappings().all()

    products = [dict(r) for r in rows]
    total = len(products)
    if total == 0:
        return []

    # Calculate daily average and assign ABC class using Pareto thresholds
    for p in products:
        p["daily_avg"] = round(p["outbound_volume"] / max(days, 1), 1)

    a_cutoff = max(int(total * 0.2), 1)
    b_cutoff = a_cutoff + max(int(total * 0.3), 1)

    for i, p in enumerate(products):
        if i < a_cutoff:
            p["velocity_class"] = "A"
        elif i < b_cutoff:
            p["velocity_class"] = "B"
        else:
            p["velocity_class"] = "C"

    return products


def get_location_utilization(business_id: int, days: int = 90) -> list[dict]:
    """Aggregate utilization metrics per zone/aisle."""
    query = text("""
        SELECT
            p.location_zone   AS zone,
            p.location_aisle  AS aisle,
            COUNT(DISTINCT p.id)::int AS product_count,
            COALESCE(SUM(p.stock_at_warehouse), 0)::int AS total_stock,
            COALESCE(SUM(out_data.outbound_volume), 0)::int AS total_outbound,
            COALESCE(SUM(out_data.tx_count), 0)::int AS total_tx_count
        FROM products p
        LEFT JOIN (
            SELECT
                product_id,
                SUM(CASE WHEN stock_adjusted < 0 THEN ABS(stock_adjusted) ELSE 0 END)::int AS outbound_volume,
                COUNT(CASE WHEN stock_adjusted < 0 THEN 1 END)::int AS tx_count
            FROM inventory_transactions
            WHERE business_id = :biz
              AND transaction_at >= NOW() - MAKE_INTERVAL(days => :days)
            GROUP BY product_id
        ) out_data ON out_data.product_id = p.id
        WHERE p.business_id = :biz
          AND (p.location_zone IS NOT NULL AND p.location_zone != '')
        GROUP BY p.location_zone, p.location_aisle
        ORDER BY total_outbound DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "days": days}).mappings().all()

    results = []
    for r in rows:
        d = dict(r)
        d["turnover_rate"] = round(d["total_outbound"] / max(d["total_stock"], 1), 2)
        results.append(d)
    return results


def generate_placement_suggestions(business_id: int, days: int = 90) -> list[dict]:
    """Generate smart placement suggestions by cross-referencing product velocity with location priority.

    Returns a list of suggestion dicts with type, priority, product info,
    current location, suggested location, and description.
    """
    # 1. Get product velocity classification
    products = get_product_velocity_classification(business_id, days)
    if not products:
        return []

    # 2. Get location priority config
    config = get_warehouse_location_configs(business_id)
    priority_map: dict[str, dict] = {}
    for c in config:
        key = f"{c['zone']}|{c['aisle']}" if c["aisle"] else c["zone"]
        priority_map[key] = c

    def get_location_priority(zone: str, aisle: str) -> int:
        """Lookup priority for a zone/aisle, defaulting to 3."""
        if not zone:
            return 3
        exact = f"{zone}|{aisle}" if aisle else zone
        if exact in priority_map:
            return priority_map[exact]["priority"]
        # Try zone-level match
        if zone in priority_map:
            return priority_map[zone]["priority"]
        for key, cfg in priority_map.items():
            if cfg["zone"] == zone and not cfg["aisle"]:
                return cfg["priority"]
        return 3  # default

    def get_location_label(zone: str, aisle: str) -> str:
        if not zone:
            return "No location"
        parts = [zone]
        if aisle:
            parts.append(f"Aisle {aisle}")
        return ", ".join(parts)

    # 3. Build lookup of products by location priority
    products_by_priority: dict[int, list[dict]] = {1: [], 2: [], 3: [], 4: [], 5: []}
    for p in products:
        zone = p.get("location_zone") or ""
        aisle = p.get("location_aisle") or ""
        p["_priority"] = get_location_priority(zone, aisle)
        p["_loc_label"] = get_location_label(zone, aisle)
        if zone:
            products_by_priority[p["_priority"]].append(p)

    # 4. Find products in premium locations (priority 1-2) that are available for swapping
    premium_slow = [p for p in products if p["velocity_class"] == "C" and p["_priority"] <= 2 and p.get("location_zone")]
    deep_fast = [p for p in products if p["velocity_class"] == "A" and p["_priority"] >= 4 and p.get("location_zone")]

    # 5. Find best available locations per priority
    location_product_count: dict[str, int] = {}
    for p in products:
        zone = p.get("location_zone") or ""
        aisle = p.get("location_aisle") or ""
        if zone:
            key = f"{zone}|{aisle}"
            location_product_count[key] = location_product_count.get(key, 0) + 1

    suggestions: list[dict] = []
    used_products = set()  # track to avoid duplicate suggestions

    # 5a. Generate SWAP suggestions (A-class in bad spot ↔ C-class in good spot)
    for fast in deep_fast:
        if fast["id"] in used_products:
            continue
        for slow in premium_slow:
            if slow["id"] in used_products:
                continue
            suggestions.append({
                "type": "swap",
                "priority": "high",
                "product_a": {"id": fast["id"], "name": fast["name"], "sku": fast["sku_code"],
                              "velocity": fast["velocity_class"], "outbound": fast["outbound_volume"]},
                "product_b": {"id": slow["id"], "name": slow["name"], "sku": slow["sku_code"],
                              "velocity": slow["velocity_class"], "outbound": slow["outbound_volume"]},
                "current_location_a": fast["_loc_label"],
                "current_location_b": slow["_loc_label"],
                "suggested_location_a": slow["_loc_label"],
                "suggested_location_b": fast["_loc_label"],
                "description": (
                    f"Swap \"{fast['name']}\" (A-class, {fast['outbound_volume']} units out) "
                    f"from {fast['_loc_label']} with \"{slow['name']}\" (C-class, {slow['outbound_volume']} units out) "
                    f"from {slow['_loc_label']}. Fast mover should be in the more accessible location."
                ),
            })
            used_products.add(fast["id"])
            used_products.add(slow["id"])
            break

    # 5b. Relocate remaining fast movers in bad locations
    for p in products:
        if p["id"] in used_products:
            continue
        if p["velocity_class"] == "A" and p["_priority"] >= 4 and p.get("location_zone"):
            # Find best available premium location
            best_loc = None
            for cfg in sorted(config, key=lambda c: c["priority"]):
                if cfg["priority"] <= 2:
                    best_loc = cfg
                    break
            suggested = f"{best_loc['zone']}" + (f", Aisle {best_loc['aisle']}" if best_loc.get("aisle") else "") if best_loc else "a premium zone (priority 1-2)"
            suggestions.append({
                "type": "relocate_fast",
                "priority": "high",
                "product": {"id": p["id"], "name": p["name"], "sku": p["sku_code"],
                            "velocity": p["velocity_class"], "outbound": p["outbound_volume"]},
                "current_location": p["_loc_label"],
                "suggested_location": suggested,
                "description": (
                    f"\"{p['name']}\" is a fast mover (A-class, {p['outbound_volume']} units/{days}d) "
                    f"but is stored in {p['_loc_label']} (low-access area). "
                    f"Move to {suggested} for faster picking."
                ),
            })
            used_products.add(p["id"])
        elif p["velocity_class"] == "A" and p["_priority"] == 3 and p.get("location_zone"):
            best_loc = None
            for cfg in sorted(config, key=lambda c: c["priority"]):
                if cfg["priority"] <= 2:
                    best_loc = cfg
                    break
            if best_loc:
                suggested = f"{best_loc['zone']}" + (f", Aisle {best_loc['aisle']}" if best_loc.get("aisle") else "")
                suggestions.append({
                    "type": "relocate_fast",
                    "priority": "medium",
                    "product": {"id": p["id"], "name": p["name"], "sku": p["sku_code"],
                                "velocity": p["velocity_class"], "outbound": p["outbound_volume"]},
                    "current_location": p["_loc_label"],
                    "suggested_location": suggested,
                    "description": (
                        f"\"{p['name']}\" is a fast mover (A-class, {p['outbound_volume']} units/{days}d) "
                        f"in a normal zone ({p['_loc_label']}). Consider moving to {suggested} for faster picking."
                    ),
                })
                used_products.add(p["id"])

    # 5c. Move slow movers out of premium locations
    for p in products:
        if p["id"] in used_products:
            continue
        if p["velocity_class"] == "C" and p["_priority"] <= 2 and p.get("location_zone"):
            deep_loc = None
            for cfg in sorted(config, key=lambda c: -c["priority"]):
                if cfg["priority"] >= 4:
                    deep_loc = cfg
                    break
            suggested = f"{deep_loc['zone']}" + (f", Aisle {deep_loc['aisle']}" if deep_loc.get("aisle") else "") if deep_loc else "a lower-priority zone (priority 4-5)"
            suggestions.append({
                "type": "move_slow",
                "priority": "medium",
                "product": {"id": p["id"], "name": p["name"], "sku": p["sku_code"],
                            "velocity": p["velocity_class"], "outbound": p["outbound_volume"]},
                "current_location": p["_loc_label"],
                "suggested_location": suggested,
                "description": (
                    f"\"{p['name']}\" is a slow mover (C-class, {p['outbound_volume']} units/{days}d) "
                    f"but occupies prime space in {p['_loc_label']}. "
                    f"Move to {suggested} to free premium space for fast movers."
                ),
            })
            used_products.add(p["id"])

    # 5d. Products without any location assigned
    for p in products:
        if p["id"] in used_products:
            continue
        zone = p.get("location_zone") or ""
        if not zone and p["outbound_volume"] > 0:
            if p["velocity_class"] == "A":
                best_loc = None
                for cfg in sorted(config, key=lambda c: c["priority"]):
                    if cfg["priority"] <= 2:
                        best_loc = cfg
                        break
                suggested = f"{best_loc['zone']}" + (f", Aisle {best_loc['aisle']}" if best_loc.get("aisle") else "") if best_loc else "a premium zone (priority 1-2)"
            else:
                suggested = "any available zone"
            suggestions.append({
                "type": "assign_location",
                "priority": "low" if p["velocity_class"] == "C" else "medium",
                "product": {"id": p["id"], "name": p["name"], "sku": p["sku_code"],
                            "velocity": p["velocity_class"], "outbound": p["outbound_volume"]},
                "current_location": "No location assigned",
                "suggested_location": suggested,
                "description": (
                    f"\"{p['name']}\" ({p['velocity_class']}-class) has no warehouse location assigned. "
                    f"Assign it to {suggested}."
                ),
            })

    # Sort: high > medium > low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: priority_order.get(s["priority"], 9))

    return suggestions


# ── Warehouse Location Config CRUD ───────────────────────────────────────────

def get_warehouse_location_configs(business_id: int) -> list[dict]:
    """Return all location configs for a business."""
    query = text("""
        SELECT id, business_id, zone, aisle, priority, label, created_at
        FROM warehouse_location_config
        WHERE business_id = :biz
        ORDER BY priority ASC, zone ASC, aisle ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def upsert_warehouse_location_config(business_id: int, zone: str, aisle: str = "",
                                       priority: int = 3, label: str = "") -> dict:
    """Create or update a location config entry."""
    query = text("""
        INSERT INTO warehouse_location_config (business_id, zone, aisle, priority, label)
        VALUES (:biz, :zone, :aisle, :priority, :label)
        ON CONFLICT (business_id, zone, aisle)
        DO UPDATE SET priority = :priority, label = :label
        RETURNING id, business_id, zone, aisle, priority, label, created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "zone": zone, "aisle": aisle,
            "priority": priority, "label": label,
        }).mappings().first()
    return dict(row)


def delete_warehouse_location_config(config_id: int, business_id: int) -> bool:
    """Delete a location config entry. Returns True if deleted."""
    query = text("""
        DELETE FROM warehouse_location_config
        WHERE id = :id AND business_id = :biz
    """)
    with engine.begin() as conn:
        result = conn.execute(query, {"id": config_id, "biz": business_id})
    return result.rowcount > 0


def get_distinct_zones(business_id: int) -> list[dict]:
    """Return distinct zone/aisle combos from products for auto-suggesting config."""
    query = text("""
        SELECT DISTINCT location_zone AS zone, location_aisle AS aisle
        FROM products
        WHERE business_id = :biz
          AND location_zone IS NOT NULL AND location_zone != ''
        ORDER BY location_zone, location_aisle
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


# ============================================================================
# WMS 2.0 v5 — Multi-tenant: warehouses + customers + scoped lookups
# ============================================================================

# ── Warehouses ──────────────────────────────────────────────────────────────

WAREHOUSE_COLUMNS = (
    "id, business_id, name, code, address, city, state, zip_code, "
    "is_active, created_at, updated_at"
)


def list_warehouses(business_id: int, include_inactive: bool = False) -> list[dict]:
    where = "business_id = :biz" + ("" if include_inactive else " AND is_active = TRUE")
    query = text(f"SELECT {WAREHOUSE_COLUMNS} FROM warehouses WHERE {where} ORDER BY name")
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_warehouse_by_id(warehouse_id: int, business_id: int) -> dict | None:
    query = text(f"""
        SELECT {WAREHOUSE_COLUMNS} FROM warehouses
        WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": warehouse_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def create_warehouse(business_id: int, name: str, code: str, address: str = "",
                     city: str = "", state: str = "", zip_code: str = "") -> dict:
    query = text(f"""
        INSERT INTO warehouses (business_id, name, code, address, city, state, zip_code)
        VALUES (:biz, :name, :code, :addr, :city, :state, :zip)
        RETURNING {WAREHOUSE_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "name": name, "code": code,
            "addr": address, "city": city, "state": state, "zip": zip_code,
        }).mappings().first()
    return dict(row)


def update_warehouse(warehouse_id: int, business_id: int, *, name: str, code: str,
                     address: str, city: str, state: str, zip_code: str,
                     is_active: bool) -> dict | None:
    query = text(f"""
        UPDATE warehouses
        SET name = :name, code = :code, address = :addr, city = :city,
            state = :state, zip_code = :zip, is_active = :active, updated_at = NOW()
        WHERE id = :id AND business_id = :biz
        RETURNING {WAREHOUSE_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": warehouse_id, "biz": business_id,
            "name": name, "code": code, "addr": address, "city": city,
            "state": state, "zip": zip_code, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


# ── Customers ───────────────────────────────────────────────────────────────

CUSTOMER_COLUMNS = (
    "id, business_id, name, code, contact_name, contact_email, contact_phone, "
    "is_active, created_at, updated_at"
)


def list_customers(business_id: int, include_inactive: bool = False) -> list[dict]:
    where = "business_id = :biz" + ("" if include_inactive else " AND is_active = TRUE")
    query = text(f"SELECT {CUSTOMER_COLUMNS} FROM customers WHERE {where} ORDER BY name")
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_customer_by_id(customer_id: int, business_id: int) -> dict | None:
    query = text(f"""
        SELECT {CUSTOMER_COLUMNS} FROM customers
        WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": customer_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def create_customer(business_id: int, name: str, code: str,
                    contact_name: str = "", contact_email: str = "",
                    contact_phone: str = "") -> dict:
    query = text(f"""
        INSERT INTO customers (business_id, name, code, contact_name, contact_email, contact_phone)
        VALUES (:biz, :name, :code, :cname, :cemail, :cphone)
        RETURNING {CUSTOMER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "name": name, "code": code,
            "cname": contact_name, "cemail": contact_email, "cphone": contact_phone,
        }).mappings().first()
    return dict(row)


def update_customer(customer_id: int, business_id: int, *, name: str, code: str,
                    contact_name: str, contact_email: str, contact_phone: str,
                    is_active: bool) -> dict | None:
    query = text(f"""
        UPDATE customers
        SET name = :name, code = :code, contact_name = :cname, contact_email = :cemail,
            contact_phone = :cphone, is_active = :active, updated_at = NOW()
        WHERE id = :id AND business_id = :biz
        RETURNING {CUSTOMER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": customer_id, "biz": business_id,
            "name": name, "code": code, "cname": contact_name,
            "cemail": contact_email, "cphone": contact_phone, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


def get_default_customer_id(business_id: int) -> int | None:
    """Return the id of the 'DEFAULT' customer for a business (created by backfill)."""
    row = None
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM customers WHERE business_id = :biz AND code = 'DEFAULT' LIMIT 1"
        ), {"biz": business_id}).fetchone()
    return int(row[0]) if row else None


def get_default_warehouse_id(business_id: int) -> int | None:
    """Return the id of the 'MAIN' warehouse for a business (created by backfill)."""
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM warehouses WHERE business_id = :biz AND code = 'MAIN' LIMIT 1"
        ), {"biz": business_id}).fetchone()
    return int(row[0]) if row else None


# ── Tenancy-scoped product helpers ──────────────────────────────────────────

def get_products_scoped(
    business_id: int,
    customer_id: int | None,
    warehouse_id: int | None,
    page: int = 1,
    per_page: int = 20,
    search: str = "",
) -> dict:
    """Paginated products with optional customer / warehouse filters.

    `customer_id=None` means "all customers under this business" (warehouse view).
    `warehouse_id=None` means "all warehouses".
    """
    offset = (page - 1) * per_page
    where = ["p.business_id = :biz", "(p.name ILIKE :q OR p.sku_code ILIKE :q)"]
    params: dict = {"biz": business_id, "q": f"%{search}%"}
    if customer_id is not None:
        where.append("p.customer_id = :cust"); params["cust"] = customer_id
    if warehouse_id is not None:
        where.append("p.warehouse_id = :wh"); params["wh"] = warehouse_id

    where_sql = " AND ".join(where)
    count_q = text(f"SELECT COUNT(*)::int FROM products p WHERE {where_sql}")
    data_q = text(f"""
        SELECT p.*, c.name AS customer_name, c.code AS customer_code
        FROM products p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE {where_sql}
        ORDER BY p.name
        LIMIT :limit OFFSET :offset
    """)
    with engine.connect() as conn:
        total = conn.execute(count_q, params).scalar()
        rows = conn.execute(data_q, {**params, "limit": per_page, "offset": offset}).mappings().all()
    return {
        "products": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_product_scoped(product_id: int, business_id: int,
                       customer_id: int | None) -> dict | None:
    """Get a product enforcing customer scope when set."""
    where = ["id = :id", "business_id = :biz"]
    params: dict = {"id": product_id, "biz": business_id}
    if customer_id is not None:
        where.append("customer_id = :cust"); params["cust"] = customer_id
    query = text(f"""
        SELECT {PRODUCT_COLUMNS}, customer_id, warehouse_id
        FROM products WHERE {' AND '.join(where)}
    """)
    with engine.connect() as conn:
        row = conn.execute(query, params).mappings().fetchone()
    return dict(row) if row else None


def create_product_scoped(
    *, name: str, sku_code: str, business_id: int,
    customer_id: int, warehouse_id: int,
    price: float = 0, stock_at_warehouse: int = 0, uom: str = "pcs",
    par_level: int = 0, reorder_point: int = 0, safety_stock: int = 0,
    lead_time_days: int = 0, max_stock_level: int = 0, expiry_days: int = 0,
    location_zone: str = "", location_aisle: str = "", location_rack: str = "",
    location_shelf: str = "", location_level: str = "", location_bin: str = "",
) -> dict:
    """Create a product owned by (business, customer) and stored at warehouse."""
    query = text(f"""
        INSERT INTO products (
            name, sku_code, business_id, customer_id, warehouse_id,
            price, stock_at_warehouse, uom,
            par_level, reorder_point, safety_stock, lead_time_days, max_stock_level,
            expiry_days,
            location_zone, location_aisle, location_rack, location_shelf, location_level, location_bin
        ) VALUES (
            :name, :sku, :biz, :cust, :wh,
            :price, :stock, :uom,
            :par, :rp, :ss, :ltd, :max,
            :ed,
            :lz, :la, :lr, :ls, :ll, :lb
        )
        RETURNING {PRODUCT_COLUMNS}, customer_id, warehouse_id
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "name": name, "sku": sku_code, "biz": business_id,
            "cust": customer_id, "wh": warehouse_id,
            "price": price, "stock": stock_at_warehouse, "uom": uom,
            "par": par_level, "rp": reorder_point, "ss": safety_stock,
            "ltd": lead_time_days, "max": max_stock_level, "ed": expiry_days,
            "lz": location_zone, "la": location_aisle, "lr": location_rack,
            "ls": location_shelf, "ll": location_level, "lb": location_bin,
        }).mappings().first()
    return dict(row)


# ── User onboarding (customer staff) ────────────────────────────────────────

def create_user_for_customer(
    *, username: str, name: str, email: str, hashed_password: str,
    business_id: int, customer_id: int, role: str = "customer_staff",
) -> dict:
    """Create a user attached to a customer (role = customer_admin / customer_staff)."""
    query = text("""
        INSERT INTO users (username, name, email, hashed_password,
                           business_id, customer_id, role, is_active)
        VALUES (:un, :n, :e, :hp, :biz, :cust, :role, TRUE)
        RETURNING id, username, name, email, business_id, customer_id, role,
                  is_active, created_at
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "un": username, "n": name, "e": email, "hp": hashed_password,
            "biz": business_id, "cust": customer_id, "role": role,
        }).mappings().first()
    return dict(row)


def list_users_for_customer(business_id: int, customer_id: int) -> list[dict]:
    query = text("""
        SELECT id, username, name, email, role, is_active, created_at
        FROM users
        WHERE business_id = :biz AND customer_id = :cust
        ORDER BY created_at DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


def list_users_for_warehouse(business_id: int) -> list[dict]:
    """List warehouse staff (role in WAREHOUSE_ROLES) for a business."""
    query = text("""
        SELECT id, username, name, email, role, customer_id, is_active, created_at
        FROM users
        WHERE business_id = :biz
          AND role IN ('warehouse_admin', 'warehouse_staff')
        ORDER BY role, name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


# ============================================================================
# Phase 5 — Trend analytics (FIFO/FEFO, Complete, Behavior)
# ============================================================================

def get_fifo_fefo_compliance(
    business_id: int, customer_id: int | None,
    from_date: str | None = None, to_date: str | None = None,
) -> dict:
    """Compute FIFO and FEFO compliance scores by replaying outbound_picks.

    For each pick, we check whether the consumed batch was the optimal one
    available at pick time (the oldest by purchased_at for FIFO, earliest by
    expires_at for FEFO). Compliance = compliant_picks / total_picks.
    """
    where = ["op.transaction_id IS NOT NULL", "ol.outbound_id = oo.id",
             "oo.business_id = :biz", "oo.status = 'shipped'"]
    params: dict = {"biz": business_id}
    if customer_id is not None:
        where.append("oo.customer_id = :cust"); params["cust"] = customer_id
    if from_date:
        where.append("oo.shipped_at >= :fd"); params["fd"] = from_date
    if to_date:
        where.append("oo.shipped_at <= :td"); params["td"] = to_date

    where_sql = " AND ".join(where)

    query = text(f"""
        WITH pick_events AS (
            SELECT op.id            AS pick_id,
                   op.outbound_line_id,
                   op.stock_batch_id AS picked_batch_id,
                   op.qty,
                   op.transaction_id,
                   ol.product_id,
                   oo.id             AS outbound_id,
                   oo.customer_id,
                   it.transaction_at AS picked_at,
                   sb.purchased_at   AS picked_purchased_at,
                   sb.expires_at     AS picked_expires_at
            FROM outbound_picks op
            JOIN outbound_lines ol ON ol.id = op.outbound_line_id
            JOIN outbound_orders oo ON oo.id = ol.outbound_id
            JOIN inventory_transactions it ON it.id = op.transaction_id
            JOIN stock_batches sb ON sb.id = op.stock_batch_id
            WHERE {where_sql}
        )
        SELECT
            COUNT(*)                                                  AS total_picks,
            COALESCE(SUM(qty), 0)                                     AS total_qty,
            -- FIFO compliant: picked batch's purchased_at <= every other batch
            -- with remaining_qty > 0 at pick time
            COUNT(*) FILTER (WHERE NOT EXISTS (
                SELECT 1 FROM stock_batches sb2
                JOIN inventory_transactions it2 ON it2.id = sb2.transaction_id
                WHERE sb2.product_id = pe.product_id
                  AND sb2.customer_id = pe.customer_id
                  AND sb2.id <> pe.picked_batch_id
                  AND it2.transaction_at < pe.picked_at
                  AND sb2.purchased_at < pe.picked_purchased_at
            ))                                                        AS fifo_compliant_picks,
            COUNT(*) FILTER (WHERE NOT EXISTS (
                SELECT 1 FROM stock_batches sb3
                JOIN inventory_transactions it3 ON it3.id = sb3.transaction_id
                WHERE sb3.product_id = pe.product_id
                  AND sb3.customer_id = pe.customer_id
                  AND sb3.id <> pe.picked_batch_id
                  AND it3.transaction_at < pe.picked_at
                  AND sb3.expires_at IS NOT NULL
                  AND pe.picked_expires_at IS NOT NULL
                  AND sb3.expires_at < pe.picked_expires_at
            ))                                                        AS fefo_compliant_picks
        FROM pick_events pe
    """)
    with engine.connect() as conn:
        row = conn.execute(query, params).mappings().fetchone()
    d = dict(row) if row else {}
    total = int(d.get("total_picks", 0) or 0)
    fifo_pct = (
        100.0 * float(d.get("fifo_compliant_picks", 0) or 0) / total
        if total else None
    )
    fefo_pct = (
        100.0 * float(d.get("fefo_compliant_picks", 0) or 0) / total
        if total else None
    )
    return {
        "total_picks": total,
        "total_qty": int(d.get("total_qty", 0) or 0),
        "fifo_compliant_picks": int(d.get("fifo_compliant_picks", 0) or 0),
        "fefo_compliant_picks": int(d.get("fefo_compliant_picks", 0) or 0),
        "fifo_compliance_pct": round(fifo_pct, 2) if fifo_pct is not None else None,
        "fefo_compliance_pct": round(fefo_pct, 2) if fefo_pct is not None else None,
    }


def get_aging_buckets(business_id: int, customer_id: int | None) -> list[dict]:
    """Histogram of stock by age bucket (days since purchased_at)."""
    where = ["sb.business_id = :biz", "sb.remaining_qty > 0", "sb.is_expired = FALSE"]
    params: dict = {"biz": business_id}
    if customer_id is not None:
        where.append("sb.customer_id = :cust"); params["cust"] = customer_id

    query = text(f"""
        WITH aged AS (
            SELECT sb.id, sb.product_id, sb.remaining_qty,
                   GREATEST(EXTRACT(DAY FROM (NOW() - sb.purchased_at))::int, 0) AS age_days,
                   COALESCE(p.price, 0) AS price
            FROM stock_batches sb
            LEFT JOIN products p ON p.id = sb.product_id
            WHERE {' AND '.join(where)}
        )
        SELECT
            CASE
                WHEN age_days <= 30 THEN '0-30'
                WHEN age_days <= 60 THEN '31-60'
                WHEN age_days <= 90 THEN '61-90'
                ELSE '90+'
            END AS bucket,
            COUNT(DISTINCT product_id)         AS sku_count,
            COALESCE(SUM(remaining_qty), 0)    AS units,
            COALESCE(SUM(remaining_qty * price), 0) AS value
        FROM aged
        GROUP BY 1
        ORDER BY CASE 
            WHEN MIN(age_days) <= 30 THEN 1 
            WHEN MIN(age_days) <= 60 THEN 2 
            WHEN MIN(age_days) <= 90 THEN 3 
            ELSE 4 
        END
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [dict(r) for r in rows]


def get_expiry_risk(business_id: int, customer_id: int | None,
                    days_window: int = 30) -> list[dict]:
    """Batches expiring within `days_window` days, sorted by ₹ at risk."""
    where = ["sb.business_id = :biz", "sb.remaining_qty > 0",
             "sb.is_expired = FALSE", "sb.expires_at IS NOT NULL",
             "sb.expires_at <= CAST((CURRENT_DATE + CAST((:dw || ' days') AS interval)) AS date)"]
    params: dict = {"biz": business_id, "dw": str(int(days_window))}
    if customer_id is not None:
        where.append("sb.customer_id = :cust"); params["cust"] = customer_id

    query = text(f"""
        SELECT sb.id AS batch_id, sb.product_id, p.name AS product_name,
               p.sku_code, sb.remaining_qty,
               sb.purchased_at, sb.expires_at,
               (sb.expires_at - CURRENT_DATE) AS days_to_expiry,
               COALESCE(p.price, 0) AS price,
               COALESCE(sb.remaining_qty * p.price, 0) AS value_at_risk
        FROM stock_batches sb
        LEFT JOIN products p ON p.id = sb.product_id
        WHERE {' AND '.join(where)}
        ORDER BY sb.remaining_qty * COALESCE(p.price, 0) DESC, sb.expires_at
        LIMIT 100
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        d["purchased_at"] = str(d["purchased_at"])
        d["expires_at"] = str(d["expires_at"]) if d["expires_at"] else None
        out.append(d)
    return out


def get_complete_analysis(
    product_id: int, business_id: int, customer_id: int | None,
    days: int = 90,
) -> dict:
    """Full-funnel single-SKU report: inbound + outbound + economics."""
    where_p = ["id = :pid", "business_id = :biz"]
    params: dict = {"pid": product_id, "biz": business_id}
    if customer_id is not None:
        where_p.append("customer_id = :cust"); params["cust"] = customer_id
    with engine.connect() as conn:
        prod = conn.execute(text(f"""
            SELECT id, name, sku_code, customer_id, warehouse_id,
                   stock_at_warehouse, price, lead_time_days,
                   reorder_point, safety_stock, max_stock_level, expiry_days
            FROM products WHERE {' AND '.join(where_p)}
        """), params).mappings().fetchone()
        if not prod:
            return {}
        prod = dict(prod)

        # Inbound timeline
        inbounds = [dict(r) for r in conn.execute(text("""
            SELECT il.id, oo.grn_number, il.received_qty, il.unit_cost, il.line_amount,
                   il.expires_at, il.batch_code, oo.received_at
            FROM inbound_lines il
            JOIN inbound_orders oo ON oo.id = il.inbound_id
            WHERE il.product_id = :pid AND oo.business_id = :biz
              AND oo.status = 'received'
              AND oo.received_at >= NOW() - (:d || ' days')::interval
            ORDER BY oo.received_at DESC
            LIMIT 200
        """), {"pid": product_id, "biz": business_id, "d": str(days)}).mappings().all()]
        for ib in inbounds:
            ib["received_at"] = str(ib["received_at"])
            ib["expires_at"] = str(ib["expires_at"]) if ib["expires_at"] else None

        # Outbound timeline
        outbounds = [dict(r) for r in conn.execute(text("""
            SELECT ol.id, oo.shipment_number, ol.picked_qty, ol.unit_price,
                   ol.line_amount, ol.avg_cogs, oo.shipped_at
            FROM outbound_lines ol
            JOIN outbound_orders oo ON oo.id = ol.outbound_id
            WHERE ol.product_id = :pid AND oo.business_id = :biz
              AND oo.status = 'shipped'
              AND oo.shipped_at >= NOW() - (:d || ' days')::interval
            ORDER BY oo.shipped_at DESC
            LIMIT 200
        """), {"pid": product_id, "biz": business_id, "d": str(days)}).mappings().all()]
        for ob in outbounds:
            ob["shipped_at"] = str(ob["shipped_at"])

        # Daily stock curve from ledger
        ledger = [dict(r) for r in conn.execute(text("""
            SELECT DATE(transaction_at) AS date,
                   SUM(stock_adjusted)::int AS net_change
            FROM inventory_transactions
            WHERE product_id = :pid AND business_id = :biz
              AND transaction_at >= NOW() - (:d || ' days')::interval
            GROUP BY DATE(transaction_at)
            ORDER BY date
        """), {"pid": product_id, "biz": business_id, "d": str(days)}).mappings().all()]
        for r in ledger:
            r["date"] = str(r["date"])

        # Economics aggregates
        econ = conn.execute(text("""
            SELECT
                COALESCE(SUM(ol.line_amount), 0)                      AS revenue,
                COALESCE(SUM(ol.picked_qty * ol.avg_cogs), 0)         AS cogs,
                COALESCE(SUM(ol.picked_qty), 0)                       AS units_sold,
                COUNT(DISTINCT oo.id)                                 AS shipments
            FROM outbound_lines ol
            JOIN outbound_orders oo ON oo.id = ol.outbound_id
            WHERE ol.product_id = :pid AND oo.business_id = :biz
              AND oo.status = 'shipped'
              AND oo.shipped_at >= NOW() - (:d || ' days')::interval
        """), {"pid": product_id, "biz": business_id, "d": str(days)}).mappings().fetchone()
        econ = dict(econ) if econ else {}

    revenue = float(econ.get("revenue") or 0)
    cogs = float(econ.get("cogs") or 0)
    units_sold = int(econ.get("units_sold") or 0)
    gross_margin = revenue - cogs
    gross_margin_pct = (gross_margin / revenue * 100.0) if revenue > 0 else None
    avg_daily = (units_sold / max(1, days))
    dio = ((prod["stock_at_warehouse"] or 0) / avg_daily) if avg_daily > 0 else None
    inv_turns = (365.0 / dio) if dio and dio > 0 else None

    return {
        "product": prod,
        "inbounds": inbounds,
        "outbounds": outbounds,
        "ledger": ledger,
        "economics": {
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_margin": round(gross_margin, 2),
            "gross_margin_pct": round(gross_margin_pct, 2) if gross_margin_pct is not None else None,
            "units_sold": units_sold,
            "shipments": int(econ.get("shipments") or 0),
            "avg_daily_outbound": round(avg_daily, 2),
            "days_inventory_outstanding": round(dio, 1) if dio else None,
            "inventory_turns": round(inv_turns, 2) if inv_turns else None,
            "window_days": days,
        },
    }


def get_behavior_analysis(
    business_id: int, customer_id: int | None, days: int = 90,
) -> dict:
    """ABC × XYZ matrix + lifecycle classification."""
    where = ["oo.business_id = :biz", "oo.status = 'shipped'",
             "oo.shipped_at >= NOW() - (:d || ' days')::interval"]
    params: dict = {"biz": business_id, "d": str(days)}
    if customer_id is not None:
        where.append("oo.customer_id = :cust"); params["cust"] = customer_id

    where_sql = " AND ".join(where)
    query = text(f"""
        WITH per_product AS (
            SELECT p.id AS product_id, p.name, p.sku_code, p.customer_id,
                   COALESCE(SUM(ol.line_amount), 0)               AS revenue,
                   COALESCE(SUM(ol.picked_qty), 0)                AS units_sold,
                   COUNT(DISTINCT DATE(oo.shipped_at))            AS active_days
            FROM products p
            LEFT JOIN outbound_lines ol ON ol.product_id = p.id
            LEFT JOIN outbound_orders oo ON oo.id = ol.outbound_id AND {where_sql}
            WHERE p.business_id = :biz
              {"AND p.customer_id = :cust" if customer_id is not None else ""}
            GROUP BY p.id, p.name, p.sku_code, p.customer_id
        ),
        per_product_daily AS (
            SELECT ol.product_id, DATE(oo.shipped_at) AS day,
                   SUM(ol.picked_qty) AS qty
            FROM outbound_lines ol
            JOIN outbound_orders oo ON oo.id = ol.outbound_id AND {where_sql}
            GROUP BY ol.product_id, DATE(oo.shipped_at)
        ),
        per_product_cv AS (
            SELECT product_id,
                   AVG(qty)::float                          AS mean_qty,
                   COALESCE(STDDEV_POP(qty), 0)::float      AS std_qty,
                   COUNT(*)                                 AS active_days
            FROM per_product_daily
            GROUP BY product_id
        )
        SELECT pp.product_id, pp.name, pp.sku_code, pp.customer_id,
               pp.revenue, pp.units_sold, pp.active_days,
               COALESCE(cv.mean_qty, 0)  AS mean_qty,
               COALESCE(cv.std_qty, 0)   AS std_qty
        FROM per_product pp
        LEFT JOIN per_product_cv cv ON cv.product_id = pp.product_id
        ORDER BY pp.revenue DESC
    """)
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(query, params).mappings().all()]

    # ABC: cumulative revenue → A=top 80%, B=next 15%, C=last 5%
    total_rev = sum(float(r["revenue"]) for r in rows) or 1.0
    cum = 0.0
    for r in rows:
        cum += float(r["revenue"])
        share = cum / total_rev
        r["revenue"] = round(float(r["revenue"]), 2)
        r["units_sold"] = int(r["units_sold"] or 0)
        r["mean_qty"] = round(float(r["mean_qty"] or 0), 2)
        r["std_qty"] = round(float(r["std_qty"] or 0), 2)
        r["abc_class"] = "A" if share <= 0.80 else ("B" if share <= 0.95 else "C")
        # XYZ: CV thresholds 0.5 / 1.0
        cv = (r["std_qty"] / r["mean_qty"]) if r["mean_qty"] > 0 else 99.0
        r["cv"] = round(cv, 3)
        if cv <= 0.5:
            r["xyz_class"] = "X"
        elif cv <= 1.0:
            r["xyz_class"] = "Y"
        else:
            r["xyz_class"] = "Z"
        # Lifecycle by activity
        if r["active_days"] == 0:
            r["lifecycle"] = "Dormant"
        elif r["active_days"] < 7:
            r["lifecycle"] = "New"
        else:
            r["lifecycle"] = "Active"

    # Build the 3×3 matrix counts
    matrix: dict[str, dict[str, int]] = {
        a: {x: 0 for x in ("X", "Y", "Z")} for a in ("A", "B", "C")
    }
    for r in rows:
        matrix[r["abc_class"]][r["xyz_class"]] += 1

    return {
        "products": rows,
        "matrix": matrix,
        "total_revenue": round(total_rev, 2),
        "window_days": days,
    }


# ============================================================================
# Tenant-aware dashboard aggregates (Phase 4)
# ============================================================================

def get_customer_breakdown_stats(business_id: int) -> list[dict]:
    """One row per customer with key KPIs for the warehouse-admin dashboard."""
    query = text("""
        WITH customer_stock AS (
            SELECT customer_id,
                   COUNT(*)                         AS sku_count,
                   COALESCE(SUM(stock_at_warehouse), 0) AS total_units,
                   COALESCE(SUM(stock_at_warehouse * price), 0) AS stock_value,
                   COUNT(*) FILTER (
                       WHERE stock_at_warehouse <= COALESCE(reorder_point, 0)
                         AND stock_at_warehouse > 0
                   ) AS low_stock_count,
                   COUNT(*) FILTER (WHERE stock_at_warehouse = 0) AS out_of_stock_count
            FROM products
            WHERE business_id = :biz
            GROUP BY customer_id
        ),
        today_inbound AS (
            SELECT customer_id,
                   COALESCE(SUM(stock_adjusted), 0) AS qty,
                   COUNT(*) FILTER (WHERE reason = 'stock_in') AS rows
            FROM inventory_transactions
            WHERE business_id = :biz
              AND stock_adjusted > 0
              AND DATE(transaction_at) = CURRENT_DATE
            GROUP BY customer_id
        ),
        today_outbound AS (
            SELECT customer_id,
                   COALESCE(SUM(ABS(stock_adjusted)), 0) AS qty,
                   COUNT(*) FILTER (WHERE reason = 'stock_out') AS rows
            FROM inventory_transactions
            WHERE business_id = :biz
              AND stock_adjusted < 0
              AND DATE(transaction_at) = CURRENT_DATE
            GROUP BY customer_id
        )
        SELECT
            c.id   AS customer_id,
            c.name AS customer_name,
            c.code AS customer_code,
            c.is_active,
            COALESCE(cs.sku_count, 0)         AS sku_count,
            COALESCE(cs.total_units, 0)       AS total_units,
            COALESCE(cs.stock_value, 0)       AS stock_value,
            COALESCE(cs.low_stock_count, 0)   AS low_stock_count,
            COALESCE(cs.out_of_stock_count, 0) AS out_of_stock_count,
            COALESCE(ti.qty, 0)               AS today_inbound_qty,
            COALESCE(to_.qty, 0)              AS today_outbound_qty
        FROM customers c
        LEFT JOIN customer_stock cs   ON cs.customer_id = c.id
        LEFT JOIN today_inbound  ti   ON ti.customer_id = c.id
        LEFT JOIN today_outbound to_  ON to_.customer_id = c.id
        WHERE c.business_id = :biz
        ORDER BY cs.stock_value DESC NULLS LAST, c.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def get_warehouse_dashboard_stats(business_id: int) -> dict:
    """Top-line stats across all customers."""
    query = text("""
        SELECT
            (SELECT COUNT(*) FROM customers WHERE business_id = :biz)                AS total_customers,
            (SELECT COUNT(*) FROM customers WHERE business_id = :biz AND is_active)  AS active_customers,
            (SELECT COUNT(*) FROM warehouses WHERE business_id = :biz AND is_active) AS active_warehouses,
            (SELECT COUNT(*) FROM products WHERE business_id = :biz)                 AS total_skus,
            (SELECT COALESCE(SUM(stock_at_warehouse), 0) FROM products WHERE business_id = :biz) AS total_units,
            (SELECT COALESCE(SUM(stock_at_warehouse * price), 0) FROM products WHERE business_id = :biz) AS total_stock_value,
            (SELECT COALESCE(SUM(stock_adjusted), 0) FROM inventory_transactions
                WHERE business_id = :biz AND stock_adjusted > 0 AND DATE(transaction_at) = CURRENT_DATE) AS today_inbound_qty,
            (SELECT COALESCE(SUM(ABS(stock_adjusted)), 0) FROM inventory_transactions
                WHERE business_id = :biz AND stock_adjusted < 0 AND DATE(transaction_at) = CURRENT_DATE) AS today_outbound_qty,
            (SELECT COUNT(*) FROM inbound_orders WHERE business_id = :biz AND status = 'draft') AS pending_inbounds,
            (SELECT COUNT(*) FROM outbound_orders WHERE business_id = :biz AND status = 'draft') AS pending_outbounds
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"biz": business_id}).mappings().fetchone()
    return dict(row) if row else {}


def get_customer_dashboard_stats(business_id: int, customer_id: int) -> dict:
    """KPIs for a single customer's dashboard."""
    query = text("""
        SELECT
            (SELECT COUNT(*) FROM products WHERE business_id = :biz AND customer_id = :cust) AS sku_count,
            (SELECT COALESCE(SUM(stock_at_warehouse), 0) FROM products
                WHERE business_id = :biz AND customer_id = :cust)                              AS total_units,
            (SELECT COALESCE(SUM(stock_at_warehouse * price), 0) FROM products
                WHERE business_id = :biz AND customer_id = :cust)                              AS stock_value,
            (SELECT COUNT(*) FROM products
                WHERE business_id = :biz AND customer_id = :cust
                  AND stock_at_warehouse <= COALESCE(reorder_point, 0)
                  AND stock_at_warehouse > 0)                                                  AS low_stock_count,
            (SELECT COUNT(*) FROM products
                WHERE business_id = :biz AND customer_id = :cust AND stock_at_warehouse = 0)   AS out_of_stock_count,
            (SELECT COALESCE(SUM(stock_adjusted), 0) FROM inventory_transactions
                WHERE business_id = :biz AND customer_id = :cust
                  AND stock_adjusted > 0
                  AND transaction_at >= DATE_TRUNC('month', CURRENT_DATE))                     AS mtd_inbound_qty,
            (SELECT COALESCE(SUM(ABS(stock_adjusted)), 0) FROM inventory_transactions
                WHERE business_id = :biz AND customer_id = :cust
                  AND stock_adjusted < 0
                  AND transaction_at >= DATE_TRUNC('month', CURRENT_DATE))                     AS mtd_outbound_qty,
            (SELECT COUNT(*) FROM inbound_orders
                WHERE business_id = :biz AND customer_id = :cust AND status = 'draft')         AS pending_inbounds,
            (SELECT COUNT(*) FROM outbound_orders
                WHERE business_id = :biz AND customer_id = :cust AND status = 'draft')         AS pending_outbounds
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().fetchone()
    return dict(row) if row else {}


def get_outbound_trend_daily(
    business_id: int, customer_id: int | None, days: int = 90,
) -> list[dict]:
    """Daily outbound qty for the last N days. Used for the trend chart."""
    where = ["business_id = :biz", "stock_adjusted < 0",
             "transaction_at >= NOW() - (:d || ' days')::interval"]
    params: dict = {"biz": business_id, "d": str(int(days))}
    if customer_id is not None:
        where.append("customer_id = :cust"); params["cust"] = customer_id
    query = text(f"""
        SELECT DATE(transaction_at) AS date,
               COALESCE(SUM(ABS(stock_adjusted)), 0) AS qty
        FROM inventory_transactions
        WHERE {' AND '.join(where)}
        GROUP BY DATE(transaction_at)
        ORDER BY date
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [{"date": str(r["date"]), "qty": int(r["qty"])} for r in rows]


def get_reorder_now_list(business_id: int, customer_id: int | None) -> list[dict]:
    """Products whose stock is at or below their reorder_point."""
    where = ["business_id = :biz",
             "reorder_point > 0", "stock_at_warehouse <= reorder_point"]
    params: dict = {"biz": business_id}
    if customer_id is not None:
        where.append("customer_id = :cust"); params["cust"] = customer_id
    query = text(f"""
        SELECT id AS product_id, customer_id, name, sku_code,
               stock_at_warehouse, reorder_point, max_stock_level,
               lead_time_days, safety_stock,
               GREATEST(COALESCE(max_stock_level, 0) - stock_at_warehouse, 0) AS suggested_qty
        FROM products
        WHERE {' AND '.join(where)}
        ORDER BY (stock_at_warehouse::float / NULLIF(reorder_point, 0)) ASC NULLS LAST,
                 name
        LIMIT 50
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return [dict(r) for r in rows]


# ============================================================================
# WMS 2.0 v6 — Suppliers, Buyers, Inbound (GRN), Outbound (Shipment)
# ============================================================================

# ── Suppliers ───────────────────────────────────────────────────────────────

SUPPLIER_COLUMNS = (
    "id, business_id, customer_id, name, gstin, contact_name, contact_email, "
    "contact_phone, address, is_active, created_at"
)


def list_suppliers(business_id: int, customer_id: int) -> list[dict]:
    query = text(f"""
        SELECT {SUPPLIER_COLUMNS} FROM suppliers
        WHERE business_id = :biz AND customer_id = :cust AND is_active = TRUE
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


def create_supplier(*, business_id: int, customer_id: int, name: str,
                    gstin: str = "", contact_name: str = "",
                    contact_email: str = "", contact_phone: str = "",
                    address: str = "") -> dict:
    query = text(f"""
        INSERT INTO suppliers (business_id, customer_id, name, gstin,
                               contact_name, contact_email, contact_phone, address)
        VALUES (:biz, :cust, :n, :g, :cn, :ce, :cp, :a)
        RETURNING {SUPPLIER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "cust": customer_id, "n": name, "g": gstin,
            "cn": contact_name, "ce": contact_email, "cp": contact_phone, "a": address,
        }).mappings().first()
    return dict(row)


# ── Buyers ──────────────────────────────────────────────────────────────────

BUYER_COLUMNS = (
    "id, business_id, customer_id, name, gstin, delivery_location_id, "
    "contact_name, contact_phone, is_active, created_at"
)


def list_buyers(business_id: int, customer_id: int) -> list[dict]:
    query = text(f"""
        SELECT {BUYER_COLUMNS} FROM buyers
        WHERE business_id = :biz AND customer_id = :cust AND is_active = TRUE
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


def create_buyer(*, business_id: int, customer_id: int, name: str,
                 gstin: str = "", delivery_location_id: int | None = None,
                 contact_name: str = "", contact_phone: str = "") -> dict:
    query = text(f"""
        INSERT INTO buyers (business_id, customer_id, name, gstin,
                            delivery_location_id, contact_name, contact_phone)
        VALUES (:biz, :cust, :n, :g, :dl, :cn, :cp)
        RETURNING {BUYER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "biz": business_id, "cust": customer_id, "n": name, "g": gstin,
            "dl": delivery_location_id, "cn": contact_name, "cp": contact_phone,
        }).mappings().first()
    return dict(row)


def get_buyer_by_id(buyer_id: int, business_id: int) -> dict | None:
    query = text(f"""
        SELECT {BUYER_COLUMNS} FROM buyers
        WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": buyer_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_buyer(buyer_id: int, business_id: int, *, name: str,
                 gstin: str = "", contact_name: str = "",
                 contact_phone: str = "", is_active: bool = True) -> dict | None:
    query = text(f"""
        UPDATE buyers SET name = :n, gstin = :g, contact_name = :cn,
            contact_phone = :cp, is_active = :active
        WHERE id = :id AND business_id = :biz
        RETURNING {BUYER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": buyer_id, "biz": business_id, "n": name, "g": gstin,
            "cn": contact_name, "cp": contact_phone, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


# ── Buyer locations ─────────────────────────────────────────────────────────

BUYER_LOCATION_COLUMNS = (
    "id, buyer_id, business_id, name, address, city, state, zip_code, "
    "contact_person, contact_phone, is_active, created_at"
)


def list_buyer_locations(buyer_id: int, business_id: int) -> list[dict]:
    query = text(f"""
        SELECT {BUYER_LOCATION_COLUMNS} FROM buyer_locations
        WHERE buyer_id = :bid AND business_id = :biz AND is_active = TRUE
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"bid": buyer_id, "biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def create_buyer_location(*, buyer_id: int, business_id: int, name: str,
                           address: str = "", city: str = "", state: str = "",
                           zip_code: str = "", contact_person: str = "",
                           contact_phone: str = "") -> dict:
    query = text(f"""
        INSERT INTO buyer_locations (buyer_id, business_id, name, address, city,
                                      state, zip_code, contact_person, contact_phone)
        VALUES (:bid, :biz, :n, :a, :c, :s, :z, :cp, :cph)
        RETURNING {BUYER_LOCATION_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "bid": buyer_id, "biz": business_id, "n": name,
            "a": address, "c": city, "s": state, "z": zip_code,
            "cp": contact_person, "cph": contact_phone,
        }).mappings().first()
    return dict(row)


def update_buyer_location(location_id: int, business_id: int, *, name: str,
                           address: str = "", city: str = "", state: str = "",
                           zip_code: str = "", contact_person: str = "",
                           contact_phone: str = "",
                           is_active: bool = True) -> dict | None:
    query = text(f"""
        UPDATE buyer_locations
        SET name = :n, address = :a, city = :c, state = :s, zip_code = :z,
            contact_person = :cp, contact_phone = :cph, is_active = :active
        WHERE id = :id AND business_id = :biz
        RETURNING {BUYER_LOCATION_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": location_id, "biz": business_id, "n": name,
            "a": address, "c": city, "s": state, "z": zip_code,
            "cp": contact_person, "cph": contact_phone, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


def delete_buyer_location(location_id: int, business_id: int) -> bool:
    query = text("DELETE FROM buyer_locations WHERE id = :id AND business_id = :biz")
    with engine.begin() as conn:
        result = conn.execute(query, {"id": location_id, "biz": business_id})
    return result.rowcount > 0


# ── Supplier (Seller) helpers ───────────────────────────────────────────────

def get_supplier_by_id(supplier_id: int, business_id: int) -> dict | None:
    query = text(f"""
        SELECT {SUPPLIER_COLUMNS} FROM suppliers
        WHERE id = :id AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"id": supplier_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else None


def update_supplier(supplier_id: int, business_id: int, *, name: str,
                    gstin: str = "", contact_name: str = "",
                    contact_email: str = "", contact_phone: str = "",
                    address: str = "", is_active: bool = True) -> dict | None:
    query = text(f"""
        UPDATE suppliers SET name = :n, gstin = :g, contact_name = :cn,
            contact_email = :ce, contact_phone = :cp, address = :a, is_active = :active
        WHERE id = :id AND business_id = :biz
        RETURNING {SUPPLIER_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": supplier_id, "biz": business_id, "n": name, "g": gstin,
            "cn": contact_name, "ce": contact_email, "cp": contact_phone,
            "a": address, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


# ── Seller locations ────────────────────────────────────────────────────────

SELLER_LOCATION_COLUMNS = (
    "id, supplier_id, business_id, name, address, city, state, zip_code, "
    "contact_person, contact_phone, is_active, created_at"
)


def list_seller_locations(supplier_id: int, business_id: int) -> list[dict]:
    query = text(f"""
        SELECT {SELLER_LOCATION_COLUMNS} FROM seller_locations
        WHERE supplier_id = :sid AND business_id = :biz AND is_active = TRUE
        ORDER BY name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"sid": supplier_id, "biz": business_id}).mappings().all()
    return [dict(r) for r in rows]


def create_seller_location(*, supplier_id: int, business_id: int, name: str,
                            address: str = "", city: str = "", state: str = "",
                            zip_code: str = "", contact_person: str = "",
                            contact_phone: str = "") -> dict:
    query = text(f"""
        INSERT INTO seller_locations (supplier_id, business_id, name, address, city,
                                       state, zip_code, contact_person, contact_phone)
        VALUES (:sid, :biz, :n, :a, :c, :s, :z, :cp, :cph)
        RETURNING {SELLER_LOCATION_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "sid": supplier_id, "biz": business_id, "n": name,
            "a": address, "c": city, "s": state, "z": zip_code,
            "cp": contact_person, "cph": contact_phone,
        }).mappings().first()
    return dict(row)


def update_seller_location(location_id: int, business_id: int, *, name: str,
                            address: str = "", city: str = "", state: str = "",
                            zip_code: str = "", contact_person: str = "",
                            contact_phone: str = "",
                            is_active: bool = True) -> dict | None:
    query = text(f"""
        UPDATE seller_locations
        SET name = :n, address = :a, city = :c, state = :s, zip_code = :z,
            contact_person = :cp, contact_phone = :cph, is_active = :active
        WHERE id = :id AND business_id = :biz
        RETURNING {SELLER_LOCATION_COLUMNS}
    """)
    with engine.begin() as conn:
        row = conn.execute(query, {
            "id": location_id, "biz": business_id, "n": name,
            "a": address, "c": city, "s": state, "z": zip_code,
            "cp": contact_person, "cph": contact_phone, "active": is_active,
        }).mappings().fetchone()
    return dict(row) if row else None


def delete_seller_location(location_id: int, business_id: int) -> bool:
    query = text("DELETE FROM seller_locations WHERE id = :id AND business_id = :biz")
    with engine.begin() as conn:
        result = conn.execute(query, {"id": location_id, "biz": business_id})
    return result.rowcount > 0


# ── Inbound orders (GRN) ────────────────────────────────────────────────────

INBOUND_ORDER_COLUMNS = (
    "id, business_id, customer_id, warehouse_id, supplier_id, grn_number, "
    "po_number, invoice_number, invoice_date, received_at, status, "
    "total_qty, total_amount, tax_amount, notes, created_by, created_at, updated_at"
)


def _next_grn_number(conn, business_id: int, customer_id: int) -> str:
    """Generate the next sequential GRN number for a (business, customer)."""
    n = conn.execute(text("""
        SELECT COUNT(*) FROM inbound_orders
        WHERE business_id = :b AND customer_id = :c
    """), {"b": business_id, "c": customer_id}).scalar() or 0
    return f"GRN{n + 1:06d}"


def create_inbound_order(
    *, business_id: int, customer_id: int, warehouse_id: int,
    created_by: int, supplier_id: int | None,
    po_number: str, invoice_number: str, invoice_date: str | None,
    received_at: str | None, notes: str,
    lines: list[dict],
) -> dict:
    """Create a draft inbound (GRN) with line items.

    `lines` items: {product_id, expected_qty, unit_cost, tax_pct, discount_pct,
                    batch_code, manufactured_at, expires_at, notes}
    """
    if not lines:
        raise ValueError("At least one line item is required")
    with engine.begin() as conn:
        grn = _next_grn_number(conn, business_id, customer_id)
        total_qty = sum(int(l["expected_qty"]) for l in lines)
        total_amount = sum(
            int(l["expected_qty"]) * float(l.get("unit_cost", 0)) for l in lines
        )
        head = conn.execute(text(f"""
            INSERT INTO inbound_orders
                (business_id, customer_id, warehouse_id, supplier_id, grn_number,
                 po_number, invoice_number, invoice_date, received_at,
                 total_qty, total_amount, notes, created_by)
            VALUES
                (:biz, :cust, :wh, :sup, :grn, :po, :inv, :idate,
                 COALESCE(CAST(:rcv AS timestamptz), NOW()),
                 :tq, :ta, :n, :uid)
            RETURNING {INBOUND_ORDER_COLUMNS}
        """), {
            "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            "sup": supplier_id, "grn": grn,
            "po": po_number, "inv": invoice_number, "idate": invoice_date,
            "rcv": received_at,
            "tq": total_qty, "ta": total_amount, "n": notes, "uid": created_by,
        }).mappings().first()

        head_d = dict(head)
        line_rows: list[dict] = []
        for ln in lines:
            qty = int(ln["expected_qty"])
            unit_cost = float(ln.get("unit_cost", 0))
            line_amount = qty * unit_cost
            row = conn.execute(text("""
                INSERT INTO inbound_lines
                    (inbound_id, product_id, expected_qty, unit_cost, line_amount,
                     tax_pct, discount_pct, batch_code, manufactured_at, expires_at, notes)
                VALUES
                    (:iid, :pid, :eq, :uc, :la, :tp, :dp, :bc,
                     CAST(:mfg AS date), CAST(:exp AS date), :n)
                RETURNING id, product_id, expected_qty, received_qty, rejected_qty,
                          unit_cost, line_amount, tax_pct, discount_pct,
                          batch_code, manufactured_at, expires_at, notes
            """), {
                "iid": head_d["id"], "pid": int(ln["product_id"]),
                "eq": qty, "uc": unit_cost, "la": line_amount,
                "tp": float(ln.get("tax_pct", 0)),
                "dp": float(ln.get("discount_pct", 0)),
                "bc": ln.get("batch_code", ""),
                "mfg": ln.get("manufactured_at"),
                "exp": ln.get("expires_at"),
                "n": ln.get("notes", ""),
            }).mappings().first()
            line_rows.append(dict(row))

    head_d["lines"] = line_rows
    return head_d


def list_inbound_orders(
    business_id: int, customer_id: int | None,
    warehouse_id: int | None = None, status_filter: str | None = None,
    page: int = 1, per_page: int = 20,
) -> dict:
    where = ["io.business_id = :biz"]
    params: dict = {"biz": business_id}
    if customer_id is not None:
        where.append("io.customer_id = :cust"); params["cust"] = customer_id
    if warehouse_id is not None:
        where.append("io.warehouse_id = :wh"); params["wh"] = warehouse_id
    if status_filter:
        where.append("io.status = :st"); params["st"] = status_filter

    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM inbound_orders io WHERE {where_sql}"), params
        ).scalar()
        rows = conn.execute(text(f"""
            SELECT io.*, c.name AS customer_name, c.code AS customer_code
            FROM inbound_orders io
            LEFT JOIN customers c ON c.id = io.customer_id
            WHERE {where_sql}
            ORDER BY io.received_at DESC
            LIMIT :limit OFFSET :offset
        """), {**params, "limit": per_page, "offset": offset}).mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_inbound_order(inbound_id: int, business_id: int,
                      customer_id: int | None) -> dict | None:
    where = ["id = :id", "business_id = :biz"]
    params: dict = {"id": inbound_id, "biz": business_id}
    if customer_id is not None:
        where.append("customer_id = :cust"); params["cust"] = customer_id
    with engine.connect() as conn:
        head = conn.execute(text(f"""
            SELECT {INBOUND_ORDER_COLUMNS}
            FROM inbound_orders WHERE {' AND '.join(where)}
        """), params).mappings().fetchone()
        if not head:
            return None
        lines = conn.execute(text("""
            SELECT id, product_id, expected_qty, received_qty, rejected_qty,
                   unit_cost, line_amount, tax_pct, discount_pct, batch_code,
                   manufactured_at, expires_at, stock_batch_id, transaction_id, notes
            FROM inbound_lines WHERE inbound_id = :iid
            ORDER BY id
        """), {"iid": inbound_id}).mappings().all()
    head_d = dict(head)
    head_d["lines"] = [dict(l) for l in lines]
    return head_d


def receive_inbound_order(inbound_id: int, business_id: int,
                          customer_id: int | None) -> dict:
    """Commit an inbound: write stock_batches, ledger rows, and update product stock.

    Idempotent guard: refuses if status != 'draft'.
    """
    with engine.begin() as conn:
        head_q = "SELECT * FROM inbound_orders WHERE id = :id AND business_id = :biz"
        params: dict = {"id": inbound_id, "biz": business_id}
        if customer_id is not None:
            head_q += " AND customer_id = :cust"
            params["cust"] = customer_id
        head = conn.execute(text(head_q), params).mappings().fetchone()
        if not head:
            raise ValueError("Inbound not found")
        if head["status"] != "draft":
            raise ValueError(f"Inbound is not in 'draft' state (current: {head['status']})")

        lines = conn.execute(text("""
            SELECT * FROM inbound_lines WHERE inbound_id = :iid ORDER BY id
        """), {"iid": inbound_id}).mappings().all()

        for ln in lines:
            qty = int(ln["expected_qty"])  # for now received_qty == expected_qty
            if qty <= 0:
                continue

            # 1. previous + current stock — read product, update
            prev = conn.execute(text("""
                SELECT stock_at_warehouse FROM products WHERE id = :pid
            """), {"pid": ln["product_id"]}).scalar() or 0
            current = prev + qty
            conn.execute(text("""
                UPDATE products SET stock_at_warehouse = :s, updated_at = NOW()
                WHERE id = :pid
            """), {"s": current, "pid": ln["product_id"]})

            # 2. inventory_transactions ledger entry
            tx_row = conn.execute(text("""
                INSERT INTO inventory_transactions
                    (product_id, business_id, customer_id, warehouse_id, created_by,
                     stock_adjusted, previous_stock, current_stock,
                     transaction_at, reference_no, reason)
                VALUES
                    (:pid, :biz, :cust, :wh, :uid,
                     :adj, :prev, :curr,
                     COALESCE(CAST(:tat AS timestamptz), NOW()), :ref, 'stock_in')
                RETURNING id
            """), {
                "pid": ln["product_id"], "biz": business_id,
                "cust": head["customer_id"], "wh": head["warehouse_id"],
                "uid": head["created_by"],
                "adj": qty, "prev": prev, "curr": current,
                "tat": head["received_at"],
                "ref": head["grn_number"],
            }).mappings().first()
            tx_id = tx_row["id"]

            # 3. stock_batches row (with FEFO-relevant expires_at)
            sb_row = conn.execute(text("""
                INSERT INTO stock_batches
                    (product_id, business_id, customer_id, warehouse_id,
                     quantity, remaining_qty, purchased_at, expires_at, transaction_id)
                VALUES
                    (:pid, :biz, :cust, :wh,
                     :qty, :qty, COALESCE(CAST(:pat AS timestamptz), NOW()), CAST(:exp AS date), :tx)
                RETURNING id
            """), {
                "pid": ln["product_id"], "biz": business_id,
                "cust": head["customer_id"], "wh": head["warehouse_id"],
                "qty": qty,
                "pat": head["received_at"], "exp": ln["expires_at"], "tx": tx_id,
            }).mappings().first()
            sb_id = sb_row["id"]

            # 4. wire back into the line
            conn.execute(text("""
                UPDATE inbound_lines
                SET received_qty = :rq, stock_batch_id = :sb, transaction_id = :tx
                WHERE id = :id
            """), {
                "rq": qty, "sb": sb_id, "tx": tx_id, "id": ln["id"],
            })

        # 5. flip status
        conn.execute(text("""
            UPDATE inbound_orders SET status = 'received', updated_at = NOW()
            WHERE id = :id
        """), {"id": inbound_id})

    return get_inbound_order(inbound_id, business_id, customer_id) or {}


# ── Outbound orders (Shipment) ─────────────────────────────────────────────

OUTBOUND_ORDER_COLUMNS = (
    "id, business_id, customer_id, warehouse_id, buyer_id, delivery_location_id, "
    "shipment_number, so_number, invoice_number, invoice_date, shipped_at, "
    "status, pick_strategy, total_qty, total_amount, tax_amount, notes, "
    "created_by, created_at, updated_at"
)


def _next_shipment_number(conn, business_id: int, customer_id: int) -> str:
    n = conn.execute(text("""
        SELECT COUNT(*) FROM outbound_orders
        WHERE business_id = :b AND customer_id = :c
    """), {"b": business_id, "c": customer_id}).scalar() or 0
    return f"SHP{n + 1:06d}"


def create_outbound_order(
    *, business_id: int, customer_id: int, warehouse_id: int,
    created_by: int, buyer_id: int | None, delivery_location_id: int | None,
    so_number: str, invoice_number: str, invoice_date: str | None,
    shipped_at: str | None, pick_strategy: str, notes: str,
    lines: list[dict],
) -> dict:
    """Create a draft outbound (shipment).

    `lines` items: {product_id, requested_qty, unit_price, tax_pct, discount_pct, notes}
    """
    if pick_strategy not in ("FIFO", "FEFO", "manual"):
        raise ValueError("pick_strategy must be FIFO, FEFO, or manual")
    if not lines:
        raise ValueError("At least one line item is required")

    with engine.begin() as conn:
        ship = _next_shipment_number(conn, business_id, customer_id)
        total_qty = sum(int(l["requested_qty"]) for l in lines)
        total_amount = sum(
            int(l["requested_qty"]) * float(l.get("unit_price", 0)) for l in lines
        )
        head = conn.execute(text(f"""
            INSERT INTO outbound_orders
                (business_id, customer_id, warehouse_id, buyer_id, delivery_location_id,
                 shipment_number, so_number, invoice_number, invoice_date, shipped_at,
                 pick_strategy, total_qty, total_amount, notes, created_by)
            VALUES
                (:biz, :cust, :wh, :buyer, :dl,
                 :sh, :so, :inv, :idate, COALESCE(CAST(:sat AS timestamptz), NOW()),
                 :strat, :tq, :ta, :n, :uid)
            RETURNING {OUTBOUND_ORDER_COLUMNS}
        """), {
            "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            "buyer": buyer_id, "dl": delivery_location_id,
            "sh": ship, "so": so_number, "inv": invoice_number, "idate": invoice_date,
            "sat": shipped_at, "strat": pick_strategy,
            "tq": total_qty, "ta": total_amount, "n": notes, "uid": created_by,
        }).mappings().first()
        head_d = dict(head)
        line_rows = []
        for ln in lines:
            qty = int(ln["requested_qty"])
            unit_price = float(ln.get("unit_price", 0))
            row = conn.execute(text("""
                INSERT INTO outbound_lines
                    (outbound_id, product_id, requested_qty, unit_price, line_amount,
                     tax_pct, discount_pct, notes)
                VALUES (:oid, :pid, :rq, :up, :la, :tp, :dp, :n)
                RETURNING id, product_id, requested_qty, picked_qty, unit_price,
                          line_amount, tax_pct, discount_pct, avg_cogs, notes
            """), {
                "oid": head_d["id"], "pid": int(ln["product_id"]),
                "rq": qty, "up": unit_price, "la": qty * unit_price,
                "tp": float(ln.get("tax_pct", 0)),
                "dp": float(ln.get("discount_pct", 0)),
                "n": ln.get("notes", ""),
            }).mappings().first()
            line_rows.append(dict(row))
    head_d["lines"] = line_rows
    return head_d


def list_outbound_orders(
    business_id: int, customer_id: int | None,
    warehouse_id: int | None = None, status_filter: str | None = None,
    page: int = 1, per_page: int = 20,
) -> dict:
    where = ["oo.business_id = :biz"]
    params: dict = {"biz": business_id}
    if customer_id is not None:
        where.append("oo.customer_id = :cust"); params["cust"] = customer_id
    if warehouse_id is not None:
        where.append("oo.warehouse_id = :wh"); params["wh"] = warehouse_id
    if status_filter:
        where.append("oo.status = :st"); params["st"] = status_filter
    where_sql = " AND ".join(where)
    offset = (page - 1) * per_page
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM outbound_orders oo WHERE {where_sql}"), params
        ).scalar()
        rows = conn.execute(text(f"""
            SELECT oo.*, c.name AS customer_name, c.code AS customer_code
            FROM outbound_orders oo
            LEFT JOIN customers c ON c.id = oo.customer_id
            WHERE {where_sql}
            ORDER BY oo.shipped_at DESC
            LIMIT :limit OFFSET :offset
        """), {**params, "limit": per_page, "offset": offset}).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if total else 0,
    }


def get_outbound_order(outbound_id: int, business_id: int,
                       customer_id: int | None) -> dict | None:
    where = ["id = :id", "business_id = :biz"]
    params: dict = {"id": outbound_id, "biz": business_id}
    if customer_id is not None:
        where.append("customer_id = :cust"); params["cust"] = customer_id
    with engine.connect() as conn:
        head = conn.execute(text(f"""
            SELECT {OUTBOUND_ORDER_COLUMNS}
            FROM outbound_orders WHERE {' AND '.join(where)}
        """), params).mappings().fetchone()
        if not head:
            return None
        lines = conn.execute(text("""
            SELECT id, product_id, requested_qty, picked_qty, unit_price,
                   line_amount, tax_pct, discount_pct, avg_cogs, notes
            FROM outbound_lines WHERE outbound_id = :oid
            ORDER BY id
        """), {"oid": outbound_id}).mappings().all()
        line_ids = [int(l["id"]) for l in lines]
        picks: list[dict] = []
        if line_ids:
            picks = [dict(r) for r in conn.execute(text("""
                SELECT id, outbound_line_id, stock_batch_id, qty, unit_cost, transaction_id
                FROM outbound_picks
                WHERE outbound_line_id = ANY(:ids)
                ORDER BY id
            """), {"ids": line_ids}).mappings().all()]
    head_d = dict(head)
    head_d["lines"] = [dict(l) for l in lines]
    head_d["picks"] = picks
    return head_d


def _resolve_pick_plan(conn, *, product_id: int, business_id: int,
                       customer_id: int, warehouse_id: int,
                       qty: int, strategy: str) -> list[dict]:
    """Return the list of (stock_batch_id, qty, unit_cost) to consume.

    Raises ValueError if there isn't enough stock.
    """
    if strategy == "FEFO":
        order = "ORDER BY expires_at ASC NULLS LAST, purchased_at ASC, id ASC"
    else:  # FIFO (and 'manual' falls back to FIFO if no manual plan provided)
        order = "ORDER BY purchased_at ASC, id ASC"

    rows = conn.execute(text(f"""
        SELECT sb.id, sb.remaining_qty, sb.expires_at,
               COALESCE(il.unit_cost, 0) AS unit_cost
        FROM stock_batches sb
        LEFT JOIN inbound_lines il ON il.stock_batch_id = sb.id
        WHERE sb.product_id = :pid
          AND sb.business_id = :biz
          AND sb.customer_id = :cust
          AND sb.warehouse_id = :wh
          AND sb.remaining_qty > 0
          AND sb.is_expired = FALSE
        {order}
    """), {
        "pid": product_id, "biz": business_id,
        "cust": customer_id, "wh": warehouse_id,
    }).mappings().all()

    plan: list[dict] = []
    remaining = qty
    for r in rows:
        if remaining <= 0:
            break
        take = min(remaining, int(r["remaining_qty"]))
        plan.append({
            "stock_batch_id": int(r["id"]),
            "qty": take,
            "unit_cost": float(r["unit_cost"]),
        })
        remaining -= take

    if remaining > 0:
        raise ValueError(
            f"Insufficient stock for product {product_id}: need {qty}, "
            f"available {qty - remaining}"
        )
    return plan


def preview_outbound_pick_plan(outbound_id: int, business_id: int,
                               customer_id: int | None) -> dict:
    """Compute the FIFO/FEFO consumption plan without committing.

    Returns {lines: [{outbound_line_id, product_id, requested_qty, plan: [...]}]}.
    Raises ValueError if any line can't be fully covered.
    """
    head = get_outbound_order(outbound_id, business_id, customer_id)
    if not head:
        raise ValueError("Outbound not found")
    if head["status"] != "draft":
        raise ValueError(f"Outbound is not draft (current: {head['status']})")

    strategy = head["pick_strategy"]
    out_cust = head["customer_id"]
    warehouse_id = head["warehouse_id"]

    with engine.connect() as conn:
        result_lines = []
        for ln in head["lines"]:
            # FEFO is forced for perishable products (expiry_days > 0) when
            # the outbound is configured for FIFO at header level — only
            # if user didn't explicitly choose FIFO. We keep the header's
            # explicit choice as the source of truth.
            plan = _resolve_pick_plan(
                conn,
                product_id=int(ln["product_id"]),
                business_id=business_id,
                customer_id=out_cust,
                warehouse_id=warehouse_id,
                qty=int(ln["requested_qty"]),
                strategy=strategy,
            )
            result_lines.append({
                "outbound_line_id": int(ln["id"]),
                "product_id": int(ln["product_id"]),
                "requested_qty": int(ln["requested_qty"]),
                "strategy": strategy,
                "plan": plan,
            })
    return {"outbound_id": outbound_id, "lines": result_lines}


def ship_outbound_order(outbound_id: int, business_id: int,
                        customer_id: int | None) -> dict:
    """Commit an outbound: consume batches, write picks + ledger, decrement stock."""
    with engine.begin() as conn:
        head_q = "SELECT * FROM outbound_orders WHERE id = :id AND business_id = :biz"
        params: dict = {"id": outbound_id, "biz": business_id}
        if customer_id is not None:
            head_q += " AND customer_id = :cust"
            params["cust"] = customer_id
        head = conn.execute(text(head_q), params).mappings().fetchone()
        if not head:
            raise ValueError("Outbound not found")
        if head["status"] != "draft":
            raise ValueError(f"Outbound is not draft (current: {head['status']})")

        lines = conn.execute(text(
            "SELECT * FROM outbound_lines WHERE outbound_id = :oid ORDER BY id"
        ), {"oid": outbound_id}).mappings().all()

        for ln in lines:
            qty = int(ln["requested_qty"])
            if qty <= 0:
                continue

            plan = _resolve_pick_plan(
                conn,
                product_id=int(ln["product_id"]),
                business_id=business_id,
                customer_id=head["customer_id"],
                warehouse_id=head["warehouse_id"],
                qty=qty,
                strategy=head["pick_strategy"],
            )

            # Ledger row (single tx covering whole line, signed -qty)
            prev = conn.execute(text("""
                SELECT stock_at_warehouse FROM products WHERE id = :pid
            """), {"pid": ln["product_id"]}).scalar() or 0
            current = prev - qty
            conn.execute(text("""
                UPDATE products SET stock_at_warehouse = :s, updated_at = NOW()
                WHERE id = :pid
            """), {"s": current, "pid": ln["product_id"]})

            tx_row = conn.execute(text("""
                INSERT INTO inventory_transactions
                    (product_id, business_id, customer_id, warehouse_id, created_by,
                     stock_adjusted, previous_stock, current_stock,
                     transaction_at, reference_no, reason)
                VALUES
                    (:pid, :biz, :cust, :wh, :uid,
                     :adj, :prev, :curr,
                     COALESCE(CAST(:sat AS timestamptz), NOW()), :ref, 'stock_out')
                RETURNING id
            """), {
                "pid": ln["product_id"], "biz": business_id,
                "cust": head["customer_id"], "wh": head["warehouse_id"],
                "uid": head["created_by"],
                "adj": -qty, "prev": prev, "curr": current,
                "sat": head["shipped_at"], "ref": head["shipment_number"],
            }).mappings().first()
            tx_id = tx_row["id"]

            # Decrement batches; record picks
            total_cost = 0.0
            total_taken = 0
            for p in plan:
                # decrement batch
                conn.execute(text("""
                    UPDATE stock_batches
                    SET remaining_qty = remaining_qty - :q
                    WHERE id = :sb
                """), {"q": p["qty"], "sb": p["stock_batch_id"]})
                # pick row
                conn.execute(text("""
                    INSERT INTO outbound_picks
                        (outbound_line_id, stock_batch_id, qty, unit_cost, transaction_id)
                    VALUES (:line, :sb, :q, :uc, :tx)
                """), {
                    "line": ln["id"], "sb": p["stock_batch_id"],
                    "q": p["qty"], "uc": p["unit_cost"], "tx": tx_id,
                })
                total_cost += p["qty"] * p["unit_cost"]
                total_taken += p["qty"]

            avg_cogs = (total_cost / total_taken) if total_taken else 0
            conn.execute(text("""
                UPDATE outbound_lines SET picked_qty = :pq, avg_cogs = :ac WHERE id = :id
            """), {"pq": total_taken, "ac": avg_cogs, "id": ln["id"]})

        conn.execute(text("""
            UPDATE outbound_orders SET status = 'shipped', updated_at = NOW()
            WHERE id = :id
        """), {"id": outbound_id})

    return get_outbound_order(outbound_id, business_id, customer_id) or {}