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
        SELECT id, name, email, hashed_password, is_active, created_at
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
        SELECT id, name, email, is_active, created_at
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