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


def migrate_products_table_v4() -> None:
    """Add expiry_days column to products table."""
    columns = [
        ("expiry_days", "INTEGER NOT NULL DEFAULT 0"),
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
    print("[migrations] products table v4 (expiry_days) migration complete.")


def create_stock_batches_table() -> None:
    """Stock batches – tracks individual stock lots with expiry dates."""
    query = text("""
        CREATE TABLE IF NOT EXISTS stock_batches (
            id              SERIAL          PRIMARY KEY,
            product_id      INTEGER         NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            business_id     INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            quantity         INTEGER         NOT NULL,
            remaining_qty   INTEGER         NOT NULL,
            purchased_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            expires_at      DATE,
            is_expired      BOOLEAN         NOT NULL DEFAULT FALSE,
            transaction_id  INTEGER         REFERENCES inventory_transactions(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] stock_batches table is ready.")


def create_warehouse_location_config_table() -> None:
    """Warehouse location config – stores accessibility priority per zone/aisle."""
    query = text("""
        CREATE TABLE IF NOT EXISTS warehouse_location_config (
            id            SERIAL          PRIMARY KEY,
            business_id   INTEGER         NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            zone          VARCHAR(50)     NOT NULL,
            aisle         VARCHAR(50)     NOT NULL DEFAULT '',
            priority      INTEGER         NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
            label         VARCHAR(100)    DEFAULT '',
            created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE(business_id, zone, aisle)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] warehouse_location_config table is ready.")


# ── WMS 2.0 v5 multi-tenant migration (warehouses + customers) ──────────────

CANONICAL_ROLES = {
    "warehouse_admin", "warehouse_staff",
    "customer_admin",  "customer_staff",
}


def create_warehouses_table() -> None:
    """Physical warehouses owned by a business."""
    query = text("""
        CREATE TABLE IF NOT EXISTS warehouses (
            id            SERIAL PRIMARY KEY,
            business_id   INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name          VARCHAR(255) NOT NULL,
            code          VARCHAR(50)  NOT NULL,
            address       TEXT         NOT NULL DEFAULT '',
            city          VARCHAR(255) NOT NULL DEFAULT '',
            state         VARCHAR(255) NOT NULL DEFAULT '',
            zip_code      VARCHAR(50)  NOT NULL DEFAULT '',
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE(business_id, code)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] warehouses table is ready.")


def create_customers_table() -> None:
    """Customers (tenants) whose inventory is stored at the warehouse."""
    query = text("""
        CREATE TABLE IF NOT EXISTS customers (
            id            SERIAL PRIMARY KEY,
            business_id   INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name          VARCHAR(255) NOT NULL,
            code          VARCHAR(50)  NOT NULL,
            contact_name  VARCHAR(255) NOT NULL DEFAULT '',
            contact_email VARCHAR(255) NOT NULL DEFAULT '',
            contact_phone VARCHAR(50)  NOT NULL DEFAULT '',
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE(business_id, code)
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] customers table is ready.")


def _column_exists(conn, table: str, column: str) -> bool:
    return conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).fetchone() is not None


def _add_column_if_missing(conn, table: str, column: str, definition: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        print(f"[migrations] Added column {table}.{column}")


def add_tenancy_columns() -> None:
    """Add nullable customer_id / warehouse_id columns to all owned tables."""
    targets = [
        # (table,                       add_customer_id, add_warehouse_id)
        ("users",                       True,  False),  # customer_id: which customer the user belongs to
        ("products",                    True,  True),
        ("inventory_transactions",      True,  True),
        ("inventory_batches",           True,  True),
        ("stock_batches",               True,  True),
        ("delivery_locations",          True,  False),
        ("ml_uploaded_history",         True,  True),
        ("ml_model_metadata",           True,  True),
    ]
    with engine.begin() as conn:
        for table, add_cust, add_wh in targets:
            if add_cust:
                _add_column_if_missing(
                    conn, table, "customer_id",
                    "INTEGER REFERENCES customers(id) ON DELETE CASCADE",
                )
            if add_wh:
                _add_column_if_missing(
                    conn, table, "warehouse_id",
                    "INTEGER REFERENCES warehouses(id) ON DELETE CASCADE",
                )
    print("[migrations] tenancy columns added.")


def backfill_default_warehouse_and_customer() -> None:
    """For each business, ensure a default warehouse + default customer exist
    and back-fill all existing owned rows to point at them.

    Idempotent: safe to run multiple times.
    """
    with engine.begin() as conn:
        # Ensure every business has a default warehouse
        conn.execute(text("""
            INSERT INTO warehouses (business_id, name, code)
            SELECT b.id, 'Main Warehouse', 'MAIN'
            FROM businesses b
            WHERE NOT EXISTS (
                SELECT 1 FROM warehouses w WHERE w.business_id = b.id
            )
        """))

        # Ensure every business has a default customer (legacy bucket)
        conn.execute(text("""
            INSERT INTO customers (business_id, name, code)
            SELECT b.id, 'Default Customer', 'DEFAULT'
            FROM businesses b
            WHERE NOT EXISTS (
                SELECT 1 FROM customers c WHERE c.business_id = b.id
            )
        """))

        # Backfill products, inventory_transactions, inventory_batches,
        # stock_batches, delivery_locations, ml_uploaded_history, ml_model_metadata
        # to point at (default warehouse, default customer) for their business.
        backfill_pairs = [
            ("products",                True,  True),
            ("inventory_transactions",  True,  True),
            ("inventory_batches",       True,  True),
            ("stock_batches",           True,  True),
            ("delivery_locations",      True,  False),
            ("ml_uploaded_history",     True,  True),
            ("ml_model_metadata",       True,  True),
        ]
        for table, set_cust, set_wh in backfill_pairs:
            if set_cust:
                conn.execute(text(f"""
                    UPDATE {table} t
                    SET customer_id = c.id
                    FROM customers c
                    WHERE t.business_id = c.business_id
                      AND c.code = 'DEFAULT'
                      AND t.customer_id IS NULL
                """))
            if set_wh:
                conn.execute(text(f"""
                    UPDATE {table} t
                    SET warehouse_id = w.id
                    FROM warehouses w
                    WHERE t.business_id = w.business_id
                      AND w.code = 'MAIN'
                      AND t.warehouse_id IS NULL
                """))

        # Backfill users.customer_id only for users that are NOT warehouse staff;
        # heuristic: leave NULL for now — onboarding flow assigns it.
    print("[migrations] tenancy backfill complete.")


def tighten_tenancy_columns() -> None:
    """After backfill, set NOT NULL on customer_id / warehouse_id for owned tables."""
    targets = [
        ("products",                "customer_id"),
        ("products",                "warehouse_id"),
        ("inventory_transactions",  "customer_id"),
        ("inventory_transactions",  "warehouse_id"),
        ("inventory_batches",       "customer_id"),
        ("inventory_batches",       "warehouse_id"),
        ("stock_batches",           "customer_id"),
        ("stock_batches",           "warehouse_id"),
        ("ml_uploaded_history",     "customer_id"),
        ("ml_uploaded_history",     "warehouse_id"),
        ("ml_model_metadata",       "customer_id"),
        ("ml_model_metadata",       "warehouse_id"),
    ]
    with engine.begin() as conn:
        for table, col in targets:
            # Only tighten if every row has a value (idempotent / safe)
            null_count = conn.execute(text(
                f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL"
            )).scalar()
            if null_count == 0:
                conn.execute(text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL"
                ))
    print("[migrations] tenancy columns tightened.")


def create_tenancy_indices() -> None:
    """Hot-path indices on the (business, warehouse, customer) scoping tuple."""
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_products_biz_cust         ON products(business_id, customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_products_biz_wh           ON products(business_id, warehouse_id)",
        "CREATE INDEX IF NOT EXISTS ix_invtx_biz_cust_at         ON inventory_transactions(business_id, customer_id, transaction_at)",
        "CREATE INDEX IF NOT EXISTS ix_invtx_biz_wh_at           ON inventory_transactions(business_id, warehouse_id, transaction_at)",
        "CREATE INDEX IF NOT EXISTS ix_invtx_product_at          ON inventory_transactions(product_id, transaction_at)",
        "CREATE INDEX IF NOT EXISTS ix_stock_batches_biz_cust    ON stock_batches(business_id, customer_id)",
        "CREATE INDEX IF NOT EXISTS ix_users_biz_cust            ON users(business_id, customer_id)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    print("[migrations] tenancy indices created.")


def rekey_user_roles() -> None:
    """Rename legacy roles to canonical 4-role taxonomy.

    admin    + business_id NOT NULL  → warehouse_admin
    employee + business_id NOT NULL  → warehouse_staff
    Anything else stays as-is (will be assigned during onboarding).
    """
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE users
            SET role = 'warehouse_admin'
            WHERE role = 'admin' AND business_id IS NOT NULL
        """))
        conn.execute(text("""
            UPDATE users
            SET role = 'warehouse_staff'
            WHERE role = 'employee' AND business_id IS NOT NULL
        """))
    print("[migrations] legacy user roles rekeyed.")


def make_product_sku_unique_per_customer() -> None:
    """Replace UNIQUE(sku_code, business_id) with UNIQUE(business_id, customer_id, sku_code)
    so two customers can have the same SKU code under one warehouse.
    """
    with engine.begin() as conn:
        # Drop legacy constraint if present (name varies by Postgres version)
        constraint_rows = conn.execute(text("""
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'products'::regclass AND contype = 'u'
        """)).fetchall()
        for (cname,) in constraint_rows:
            # Drop the legacy 2-column unique only; keep the new one (added below)
            cols = conn.execute(text("""
                SELECT array_to_string(
                    ARRAY(
                        SELECT a.attname
                        FROM unnest((SELECT conkey FROM pg_constraint WHERE conname = :cname)) AS k(attnum)
                        JOIN pg_attribute a ON a.attrelid = 'products'::regclass AND a.attnum = k.attnum
                        ORDER BY k.attnum
                    ), ','
                )
            """), {"cname": cname}).scalar()
            if cols == "sku_code,business_id" or cols == "business_id,sku_code":
                conn.execute(text(f'ALTER TABLE products DROP CONSTRAINT "{cname}"'))
                print(f"[migrations] Dropped legacy unique constraint {cname}")

        # Add new unique on (business_id, customer_id, sku_code) if missing
        existing = conn.execute(text("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'products'::regclass
              AND conname = 'products_biz_cust_sku_unique'
        """)).fetchone()
        if not existing:
            # Only add if customer_id is NOT NULL (i.e. tighten step ran)
            null_cust = conn.execute(text(
                "SELECT COUNT(*) FROM products WHERE customer_id IS NULL"
            )).scalar()
            if null_cust == 0:
                conn.execute(text("""
                    ALTER TABLE products
                    ADD CONSTRAINT products_biz_cust_sku_unique
                    UNIQUE (business_id, customer_id, sku_code)
                """))
                print("[migrations] Added unique (business_id, customer_id, sku_code).")


# ── WMS 2.0 v6: detailed inbound / outbound (Phase 2) ───────────────────────

def create_suppliers_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id            SERIAL PRIMARY KEY,
            business_id   INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            customer_id   INTEGER NOT NULL REFERENCES customers(id)  ON DELETE CASCADE,
            name          VARCHAR(255) NOT NULL,
            gstin         VARCHAR(20)  NOT NULL DEFAULT '',
            contact_name  VARCHAR(255) NOT NULL DEFAULT '',
            contact_email VARCHAR(255) NOT NULL DEFAULT '',
            contact_phone VARCHAR(50)  NOT NULL DEFAULT '',
            address       TEXT         NOT NULL DEFAULT '',
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] suppliers table is ready.")


def create_buyers_table() -> None:
    query = text("""
        CREATE TABLE IF NOT EXISTS buyers (
            id            SERIAL PRIMARY KEY,
            business_id   INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            customer_id   INTEGER NOT NULL REFERENCES customers(id)  ON DELETE CASCADE,
            name          VARCHAR(255) NOT NULL,
            gstin         VARCHAR(20)  NOT NULL DEFAULT '',
            delivery_location_id INTEGER REFERENCES delivery_locations(id) ON DELETE SET NULL,
            contact_name  VARCHAR(255) NOT NULL DEFAULT '',
            contact_phone VARCHAR(50)  NOT NULL DEFAULT '',
            is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] buyers table is ready.")


def create_inbound_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inbound_orders (
                id              SERIAL PRIMARY KEY,
                business_id     INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                customer_id     INTEGER NOT NULL REFERENCES customers(id)  ON DELETE CASCADE,
                warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
                supplier_id     INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
                grn_number      VARCHAR(64) NOT NULL,
                po_number       VARCHAR(255) NOT NULL DEFAULT '',
                invoice_number  VARCHAR(255) NOT NULL DEFAULT '',
                invoice_date    DATE,
                received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                total_qty       INTEGER NOT NULL DEFAULT 0,
                total_amount    DECIMAL(14,2) NOT NULL DEFAULT 0,
                tax_amount      DECIMAL(14,2) NOT NULL DEFAULT 0,
                notes           TEXT NOT NULL DEFAULT '',
                created_by      INTEGER NOT NULL REFERENCES users(id),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(business_id, customer_id, grn_number)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inbound_lines (
                id              SERIAL PRIMARY KEY,
                inbound_id      INTEGER NOT NULL REFERENCES inbound_orders(id) ON DELETE CASCADE,
                product_id      INTEGER NOT NULL REFERENCES products(id),
                expected_qty    INTEGER NOT NULL,
                received_qty    INTEGER NOT NULL DEFAULT 0,
                rejected_qty    INTEGER NOT NULL DEFAULT 0,
                unit_cost       DECIMAL(12,4) NOT NULL DEFAULT 0,
                line_amount     DECIMAL(14,2) NOT NULL DEFAULT 0,
                tax_pct         DECIMAL(5,2)  NOT NULL DEFAULT 0,
                discount_pct    DECIMAL(5,2)  NOT NULL DEFAULT 0,
                batch_code      VARCHAR(64) NOT NULL DEFAULT '',
                manufactured_at DATE,
                expires_at      DATE,
                stock_batch_id  INTEGER REFERENCES stock_batches(id),
                transaction_id  INTEGER REFERENCES inventory_transactions(id),
                notes           TEXT NOT NULL DEFAULT ''
            );
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_inbound_orders_biz_cust_at
                ON inbound_orders(business_id, customer_id, received_at);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_inbound_lines_product
                ON inbound_lines(product_id);
        """))
    print("[migrations] inbound_orders / inbound_lines ready.")


def create_outbound_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS outbound_orders (
                id              SERIAL PRIMARY KEY,
                business_id     INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                customer_id     INTEGER NOT NULL REFERENCES customers(id)  ON DELETE CASCADE,
                warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
                buyer_id        INTEGER REFERENCES buyers(id) ON DELETE SET NULL,
                delivery_location_id INTEGER REFERENCES delivery_locations(id) ON DELETE SET NULL,
                shipment_number VARCHAR(64) NOT NULL,
                so_number       VARCHAR(255) NOT NULL DEFAULT '',
                invoice_number  VARCHAR(255) NOT NULL DEFAULT '',
                invoice_date    DATE,
                shipped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status          VARCHAR(20) NOT NULL DEFAULT 'draft',
                pick_strategy   VARCHAR(10) NOT NULL DEFAULT 'FIFO',
                total_qty       INTEGER NOT NULL DEFAULT 0,
                total_amount    DECIMAL(14,2) NOT NULL DEFAULT 0,
                tax_amount      DECIMAL(14,2) NOT NULL DEFAULT 0,
                notes           TEXT NOT NULL DEFAULT '',
                created_by      INTEGER NOT NULL REFERENCES users(id),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(business_id, customer_id, shipment_number)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS outbound_lines (
                id              SERIAL PRIMARY KEY,
                outbound_id     INTEGER NOT NULL REFERENCES outbound_orders(id) ON DELETE CASCADE,
                product_id      INTEGER NOT NULL REFERENCES products(id),
                requested_qty   INTEGER NOT NULL,
                picked_qty      INTEGER NOT NULL DEFAULT 0,
                unit_price      DECIMAL(12,4) NOT NULL DEFAULT 0,
                line_amount     DECIMAL(14,2) NOT NULL DEFAULT 0,
                tax_pct         DECIMAL(5,2)  NOT NULL DEFAULT 0,
                discount_pct    DECIMAL(5,2)  NOT NULL DEFAULT 0,
                avg_cogs        DECIMAL(12,4) NOT NULL DEFAULT 0,
                notes           TEXT NOT NULL DEFAULT ''
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS outbound_picks (
                id                  SERIAL PRIMARY KEY,
                outbound_line_id    INTEGER NOT NULL REFERENCES outbound_lines(id) ON DELETE CASCADE,
                stock_batch_id      INTEGER NOT NULL REFERENCES stock_batches(id),
                qty                 INTEGER NOT NULL,
                unit_cost           DECIMAL(12,4) NOT NULL,
                transaction_id      INTEGER REFERENCES inventory_transactions(id)
            );
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_outbound_orders_biz_cust_at
                ON outbound_orders(business_id, customer_id, shipped_at);
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_outbound_lines_product
                ON outbound_lines(product_id);
        """))
    print("[migrations] outbound_orders / outbound_lines / outbound_picks ready.")


def create_buyer_locations_table() -> None:
    """Multiple locations per buyer."""
    query = text("""
        CREATE TABLE IF NOT EXISTS buyer_locations (
            id              SERIAL PRIMARY KEY,
            buyer_id        INTEGER NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
            business_id     INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name            VARCHAR(255) NOT NULL,
            address         TEXT NOT NULL DEFAULT '',
            city            VARCHAR(255) NOT NULL DEFAULT '',
            state           VARCHAR(255) NOT NULL DEFAULT '',
            zip_code        VARCHAR(50) NOT NULL DEFAULT '',
            contact_person  VARCHAR(255) NOT NULL DEFAULT '',
            contact_phone   VARCHAR(50) NOT NULL DEFAULT '',
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] buyer_locations table is ready.")


def create_seller_locations_table() -> None:
    """Multiple locations per seller (supplier)."""
    query = text("""
        CREATE TABLE IF NOT EXISTS seller_locations (
            id              SERIAL PRIMARY KEY,
            supplier_id     INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            business_id     INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name            VARCHAR(255) NOT NULL,
            address         TEXT NOT NULL DEFAULT '',
            city            VARCHAR(255) NOT NULL DEFAULT '',
            state           VARCHAR(255) NOT NULL DEFAULT '',
            zip_code        VARCHAR(50) NOT NULL DEFAULT '',
            contact_person  VARCHAR(255) NOT NULL DEFAULT '',
            contact_phone   VARCHAR(50) NOT NULL DEFAULT '',
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] seller_locations table is ready.")



def run_all() -> None:
    """Run all migrations in dependency order."""
    create_businesses_table()
    create_users_table()
    migrate_users_table()
    create_products_table()
    migrate_products_table()
    migrate_products_table_v2()
    migrate_products_table_v3()
    migrate_products_table_v4()
    create_product_audit_log_table()
    create_inventory_batches_table()
    create_inventory_transactions_table()
    migrate_inventory_transactions_table()
    create_replenishment_settings_table()
    create_alert_settings_table()
    create_invites_table()
    create_delivery_locations_table()
    create_stock_batches_table()
    create_warehouse_location_config_table()
    create_ml_uploaded_history_table()
    create_ml_model_metadata_table()

    # ── v5: multi-tenant (warehouses + customers) ───────────────────────────
    create_warehouses_table()
    create_customers_table()
    add_tenancy_columns()
    backfill_default_warehouse_and_customer()
    tighten_tenancy_columns()
    create_tenancy_indices()
    rekey_user_roles()
    make_product_sku_unique_per_customer()

    # ── v6: detailed inbound / outbound (Phase 2) ───────────────────────────
    create_suppliers_table()
    create_buyers_table()
    create_inbound_tables()
    create_outbound_tables()

    # ── v7: buyer/seller locations ───────────────────────────────────────────
    create_buyer_locations_table()
    create_seller_locations_table()

    print("[migrations] All migrations complete.")
