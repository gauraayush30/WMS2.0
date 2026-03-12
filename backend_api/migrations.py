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


def create_inventory_batches_table() -> None:
    """Batch groups multiple inventory line-items into a single event."""
    query = text("""
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id              SERIAL          PRIMARY KEY,
            business_id     INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            created_by      INTEGER         NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            reason          VARCHAR(100)    NOT NULL,
            reference_no    VARCHAR(255),
            notes           TEXT            DEFAULT '',
            total_items     INTEGER         NOT NULL DEFAULT 0,
            total_amount    DECIMAL(14, 2)  NOT NULL DEFAULT 0,
            transaction_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] inventory_batches table is ready.")


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
            reason          VARCHAR(100)    NOT NULL,
            batch_id        INTEGER         REFERENCES inventory_batches(id) ON DELETE SET NULL
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] inventory_transactions table is ready.")


def migrate_inventory_transactions_table() -> None:
    """Add batch_id column to existing inventory_transactions table if missing."""
    with engine.begin() as conn:
        check = text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'inventory_transactions' AND column_name = 'batch_id'
        """)
        exists = conn.execute(check).fetchone()
        if not exists:
            conn.execute(text(
                "ALTER TABLE inventory_transactions "
                "ADD COLUMN batch_id INTEGER REFERENCES inventory_batches(id) ON DELETE SET NULL"
            ))
            print("[migrations] Added column inventory_transactions.batch_id")
    print("[migrations] inventory_transactions migration complete.")


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


def create_product_audit_log_table() -> None:
    """Audit log – records every field-level change on a product."""
    query = text("""
        CREATE TABLE IF NOT EXISTS product_audit_log (
            id              SERIAL          PRIMARY KEY,
            product_id      INTEGER         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            business_id     INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            updated_by      INTEGER         NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            field_name      VARCHAR(100)    NOT NULL,
            old_value       TEXT,
            new_value       TEXT,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] product_audit_log table is ready.")


def migrate_products_table() -> None:
    """Add columns to existing products table if they don't exist (idempotent)."""
    columns = [
        ("uom", "VARCHAR(50) NOT NULL DEFAULT 'pcs'"),
    ]
    with engine.begin() as conn:
        for col_name, col_def in columns:
            check = text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'products' AND column_name = :col
            """)
            exists = conn.execute(check, {"col": col_name}).fetchone()
            if not exists:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"))
                print(f"[migrations] Added column products.{col_name}")
    print("[migrations] products table migration complete.")


def create_invites_table() -> None:
    """Invites table – admins invite users without a business."""
    query = text("""
        CREATE TABLE IF NOT EXISTS invites (
            id                SERIAL          PRIMARY KEY,
            from_business_id  INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            from_user_id      INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            to_user_id        INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status            VARCHAR(20)     NOT NULL DEFAULT 'pending',
            created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] invites table is ready.")


def create_delivery_locations_table() -> None:
    """Delivery locations belonging to a business."""
    query = text("""
        CREATE TABLE IF NOT EXISTS delivery_locations (
            id               SERIAL          PRIMARY KEY,
            business_id      INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name             VARCHAR(255)    NOT NULL,
            address          TEXT            NOT NULL DEFAULT '',
            city             VARCHAR(255)    NOT NULL DEFAULT '',
            state            VARCHAR(255)    NOT NULL DEFAULT '',
            zip_code         VARCHAR(50)     NOT NULL DEFAULT '',
            contact_person   VARCHAR(255)    NOT NULL DEFAULT '',
            contact_phone    VARCHAR(50)     NOT NULL DEFAULT '',
            notes            TEXT            NOT NULL DEFAULT '',
            is_active        BOOLEAN         NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] delivery_locations table is ready.")


def migrate_products_table_v2() -> None:
    """Add PAR level, reorder point, safety stock, lead time, max stock to products."""
    columns = [
        ("par_level",        "INTEGER NOT NULL DEFAULT 0"),
        ("reorder_point",    "INTEGER NOT NULL DEFAULT 0"),
        ("safety_stock",     "INTEGER NOT NULL DEFAULT 0"),
        ("lead_time_days",   "INTEGER NOT NULL DEFAULT 0"),
        ("max_stock_level",  "INTEGER NOT NULL DEFAULT 0"),
    ]
    with engine.begin() as conn:
        for col_name, col_def in columns:
            check = text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'products' AND column_name = :col
            """)
            exists = conn.execute(check, {"col": col_name}).fetchone()
            if not exists:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"))
                print(f"[migrations] Added column products.{col_name}")
    print("[migrations] products table v2 migration complete.")


def migrate_products_table_v3() -> None:
    """Add warehouse location fields to products (zone, aisle, rack, shelf, level, bin)."""
    columns = [
        ("location_zone",   "VARCHAR(50) NOT NULL DEFAULT ''"),
        ("location_aisle",  "VARCHAR(50) NOT NULL DEFAULT ''"),
        ("location_rack",   "VARCHAR(50) NOT NULL DEFAULT ''"),
        ("location_shelf",  "VARCHAR(50) NOT NULL DEFAULT ''"),
        ("location_level",  "VARCHAR(50) NOT NULL DEFAULT ''"),
        ("location_bin",    "VARCHAR(50) NOT NULL DEFAULT ''"),
    ]
    with engine.begin() as conn:
        for col_name, col_def in columns:
            check = text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'products' AND column_name = :col
            """)
            exists = conn.execute(check, {"col": col_name}).fetchone()
            if not exists:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"))
                print(f"[migrations] Added column products.{col_name}")
    print("[migrations] products table v3 (warehouse locations) migration complete.")


# ── ML service tables ────────────────────────────────────────────────────────

def create_ml_uploaded_history_table() -> None:
    """Stores CSV-uploaded historical inventory data for ML training."""
    query = text("""
        CREATE TABLE IF NOT EXISTS ml_uploaded_history (
            id              SERIAL          PRIMARY KEY,
            product_id      INTEGER         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            business_id     INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            uploaded_by     INTEGER         REFERENCES users(id) ON DELETE SET NULL,
            date            DATE            NOT NULL,
            inbound_qty     INTEGER         NOT NULL DEFAULT 0,
            outbound_qty    INTEGER         NOT NULL DEFAULT 0,
            stock_level     INTEGER,
            notes           TEXT            NOT NULL DEFAULT '',
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE(product_id, business_id, date)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] ml_uploaded_history table is ready.")


def create_ml_model_metadata_table() -> None:
    """Tracks trained ML models per product."""
    query = text("""
        CREATE TABLE IF NOT EXISTS ml_model_metadata (
            id                  SERIAL          PRIMARY KEY,
            product_id          INTEGER         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            business_id         INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            model_path          VARCHAR(500)    NOT NULL,
            trained_at          TIMESTAMPTZ     NOT NULL,
            data_start_date     DATE,
            data_end_date       DATE,
            total_data_points   INTEGER,
            cv_mae              DECIMAL(10, 2),
            cv_mape             DECIMAL(10, 2),
            features_used       TEXT[]          DEFAULT '{}',
            status              VARCHAR(20)     NOT NULL DEFAULT 'ready',
            created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE(product_id, business_id)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] ml_model_metadata table is ready.")


def run_all() -> None:
    """Run all migrations in dependency order."""
    create_businesses_table()
    create_users_table()
    migrate_users_table()
    create_products_table()
    migrate_products_table()
    migrate_products_table_v2()
    migrate_products_table_v3()
    create_product_audit_log_table()
    create_inventory_batches_table()
    create_inventory_transactions_table()
    migrate_inventory_transactions_table()
    create_replenishment_settings_table()
    create_alert_settings_table()
    create_invites_table()
    create_delivery_locations_table()
    create_ml_uploaded_history_table()
    create_ml_model_metadata_table()
    print("[migrations] All migrations complete.")
