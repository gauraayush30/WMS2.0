"""
Database migrations – run once on app startup.
Creates any tables that don't already exist.
New WMS 2.0 schema: businesses, users (with business), products, inventory_transactions.
Legacy tables (replenishment_settings, alert_settings) are kept intact.
"""

from sqlalchemy import text
from db import engine


# ── New WMS 2.0 tables ──────────────────────────────────────────────────────

def create_businesses_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS businesses (
            id              SERIAL          PRIMARY KEY,
            name            VARCHAR(255)    NOT NULL,
            location        VARCHAR(500),
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] businesses table is ready.")


def create_users_table() -> None:
    """Users table – includes username, business_id, role, updated_at."""
    query = text("""
        CREATE TABLE IF NOT EXISTS users (
            id               SERIAL          PRIMARY KEY,
            username         VARCHAR(100)    NOT NULL DEFAULT '',
            name             VARCHAR(100)    NOT NULL,
            email            VARCHAR(255)    UNIQUE NOT NULL,
            hashed_password  VARCHAR(255)    NOT NULL,
            business_id      INTEGER         REFERENCES businesses(id) ON DELETE SET NULL,
            role             VARCHAR(50)     NOT NULL DEFAULT 'employee',
            is_active        BOOLEAN         NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] users table is ready.")


def migrate_users_table() -> None:
    """Add columns to existing users table if they don't exist (idempotent)."""
    columns = [
        ("username",    "VARCHAR(100) NOT NULL DEFAULT ''"),
        ("business_id", "INTEGER REFERENCES businesses(id) ON DELETE SET NULL"),
        ("role",        "VARCHAR(50) NOT NULL DEFAULT 'employee'"),
        ("updated_at",  "TIMESTAMPTZ NOT NULL DEFAULT NOW()"),
    ]
    with engine.begin() as conn:
        for col_name, col_def in columns:
            check = text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = :col
            """)
            exists = conn.execute(check, {"col": col_name}).fetchone()
            if not exists:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                print(f"[migrations] Added column users.{col_name}")
    print("[migrations] users table migration complete.")


def create_products_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS products (
            id                  SERIAL          PRIMARY KEY,
            name                VARCHAR(255)    NOT NULL,
            sku_code            VARCHAR(100)    NOT NULL,
            business_id         INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            price               DECIMAL(12, 2)  NOT NULL DEFAULT 0,
            stock_at_warehouse  INTEGER         NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE(sku_code, business_id)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] products table is ready.")


def create_inventory_transactions_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id              SERIAL          PRIMARY KEY,
            product_id      INTEGER         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            business_id     INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            created_by      INTEGER         NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            stock_adjusted  INTEGER         NOT NULL,
            previous_stock  INTEGER         NOT NULL,
            current_stock   INTEGER         NOT NULL,
            transaction_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            reference_no    VARCHAR(255),
            reason          VARCHAR(100)    NOT NULL
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] inventory_transactions table is ready.")


# ── Legacy tables (kept for backward compatibility) ──────────────────────────

def create_replenishment_settings_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS replenishment_settings (
            sku_id              VARCHAR(50)     PRIMARY KEY,
            lead_time_days      INTEGER         NOT NULL DEFAULT 7,
            min_order_qty       INTEGER         NOT NULL DEFAULT 10,
            reorder_point       INTEGER         NOT NULL DEFAULT 50,
            safety_stock        INTEGER         NOT NULL DEFAULT 25,
            target_stock_level  INTEGER         NOT NULL DEFAULT 150,
            created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] replenishment_settings table is ready.")


def create_alert_settings_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS alert_settings (
            id               SERIAL          PRIMARY KEY,
            user_id          INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            alerts_enabled   BOOLEAN         NOT NULL DEFAULT FALSE,
            last_alert_sent  TIMESTAMPTZ,
            created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE(user_id)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] alert_settings table is ready.")


def run_all() -> None:
    """Run all migrations in dependency order."""
    create_businesses_table()
    create_users_table()
    migrate_users_table()
    create_products_table()
    create_inventory_transactions_table()
    create_replenishment_settings_table()
    create_alert_settings_table()
    print("[migrations] All migrations complete.")
