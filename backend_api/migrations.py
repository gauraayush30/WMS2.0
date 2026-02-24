"""
Database migrations – run once on app startup.
Creates any tables that don't already exist.
"""

from sqlalchemy import text
from db import engine


def create_replenishment_settings_table() -> None:
    """Create the replenishment_settings table if it does not exist."""
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


def create_users_table() -> None:
    """Create the users table if it does not exist."""
    query = text("""
        CREATE TABLE IF NOT EXISTS users (
            id               SERIAL          PRIMARY KEY,
            name             VARCHAR(100)    NOT NULL,
            email            VARCHAR(255)    UNIQUE NOT NULL,
            hashed_password  VARCHAR(255)    NOT NULL,
            is_active        BOOLEAN         NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(query)
    print("[migrations] users table is ready.")


def create_alert_settings_table() -> None:
    """Create the alert_settings table if it does not exist."""
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
    """Run all migrations in order."""
    create_replenishment_settings_table()
    create_users_table()
    create_alert_settings_table()
