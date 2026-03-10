"""
Read-only database access for the ML service.

Queries the main WMS database to aggregate inventory_transactions into
daily inbound/outbound per product and to fetch uploaded historical CSV data.
"""

from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text

from config import DB_URL

engine = create_engine(DB_URL, pool_pre_ping=True)


def get_daily_aggregated_transactions(product_id: int, business_id: int) -> pd.DataFrame:
    """
    Aggregate ``inventory_transactions`` into daily inbound/outbound
    for a single product.

    Returns a DataFrame with columns:
        date, inbound_qty, outbound_qty
    sorted by date ascending.
    """
    query = text("""
        SELECT
            DATE(transaction_at)                                          AS date,
            COALESCE(SUM(CASE WHEN stock_adjusted > 0
                              THEN stock_adjusted ELSE 0 END), 0)        AS inbound_qty,
            COALESCE(SUM(CASE WHEN stock_adjusted < 0
                              THEN ABS(stock_adjusted) ELSE 0 END), 0)   AS outbound_qty
        FROM inventory_transactions
        WHERE product_id = :product_id
          AND business_id = :business_id
        GROUP BY DATE(transaction_at)
        ORDER BY date
    """)
    with engine.connect() as conn:
        rows = conn.execute(
            query, {"product_id": product_id, "business_id": business_id}
        ).mappings().all()

    if not rows:
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["inbound_qty"] = df["inbound_qty"].astype(int)
    df["outbound_qty"] = df["outbound_qty"].astype(int)
    return df


def get_uploaded_history(product_id: int, business_id: int) -> pd.DataFrame:
    """
    Fetch CSV-uploaded historical data from ``ml_uploaded_history``.

    Returns a DataFrame with columns:
        date, inbound_qty, outbound_qty, stock_level
    sorted by date ascending.
    """
    query = text("""
        SELECT date, inbound_qty, outbound_qty, stock_level
        FROM ml_uploaded_history
        WHERE product_id = :product_id
          AND business_id = :business_id
        ORDER BY date
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                query, {"product_id": product_id, "business_id": business_id}
            ).mappings().all()
    except Exception:
        # Table may not exist yet – return empty
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty", "stock_level"])

    if not rows:
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty", "stock_level"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def get_product_info(product_id: int, business_id: int) -> dict | None:
    """Return basic product info (used for CSV template headers, etc.)."""
    query = text("""
        SELECT id, name, sku_code, stock_at_warehouse,
               location_zone, location_aisle, location_rack,
               location_shelf, location_level, location_bin
        FROM products
        WHERE id = :product_id AND business_id = :business_id
    """)
    with engine.connect() as conn:
        row = conn.execute(
            query, {"product_id": product_id, "business_id": business_id}
        ).mappings().fetchone()
    return dict(row) if row else None


def get_current_stock(product_id: int, business_id: int) -> int:
    """Return the current stock_at_warehouse for a product."""
    query = text("""
        SELECT stock_at_warehouse FROM products
        WHERE id = :product_id AND business_id = :business_id
    """)
    with engine.connect() as conn:
        row = conn.execute(
            query, {"product_id": product_id, "business_id": business_id}
        ).fetchone()
    return int(row[0]) if row else 0


def save_uploaded_history(
    product_id: int,
    business_id: int,
    uploaded_by: int,
    df: pd.DataFrame,
) -> int:
    """
    Upsert rows from a validated CSV upload into ``ml_uploaded_history``.

    ``df`` must have columns: date, inbound_qty, outbound_qty
    Optional columns: stock_level, notes

    Returns the number of rows upserted.
    """
    upsert = text("""
        INSERT INTO ml_uploaded_history
            (product_id, business_id, uploaded_by, date,
             inbound_qty, outbound_qty, stock_level, notes)
        VALUES
            (:product_id, :business_id, :uploaded_by, :date,
             :inbound_qty, :outbound_qty, :stock_level, :notes)
        ON CONFLICT (product_id, business_id, date)
        DO UPDATE SET
            inbound_qty  = EXCLUDED.inbound_qty,
            outbound_qty = EXCLUDED.outbound_qty,
            stock_level  = EXCLUDED.stock_level,
            notes        = EXCLUDED.notes,
            uploaded_by  = EXCLUDED.uploaded_by
    """)

    params = []
    for _, row in df.iterrows():
        params.append({
            "product_id": product_id,
            "business_id": business_id,
            "uploaded_by": uploaded_by,
            "date": row["date"],
            "inbound_qty": int(row.get("inbound_qty", 0)),
            "outbound_qty": int(row.get("outbound_qty", 0)),
            "stock_level": int(row["stock_level"]) if pd.notna(row.get("stock_level")) else None,
            "notes": str(row.get("notes", "")),
        })

    with engine.begin() as conn:
        conn.execute(upsert, params)

    return len(params)


def save_model_metadata(
    product_id: int,
    business_id: int,
    model_path: str,
    data_start: date,
    data_end: date,
    total_points: int,
    cv_mae: float,
    cv_mape: float,
    features_used: list[str],
) -> dict:
    """Upsert model metadata after training."""
    upsert = text("""
        INSERT INTO ml_model_metadata
            (product_id, business_id, model_path, trained_at,
             data_start_date, data_end_date, total_data_points,
             cv_mae, cv_mape, features_used, status)
        VALUES
            (:product_id, :business_id, :model_path, NOW(),
             :data_start, :data_end, :total_points,
             :cv_mae, :cv_mape, :features_used, 'ready')
        ON CONFLICT (product_id, business_id)
        DO UPDATE SET
            model_path       = EXCLUDED.model_path,
            trained_at       = NOW(),
            data_start_date  = EXCLUDED.data_start_date,
            data_end_date    = EXCLUDED.data_end_date,
            total_data_points= EXCLUDED.total_data_points,
            cv_mae           = EXCLUDED.cv_mae,
            cv_mape          = EXCLUDED.cv_mape,
            features_used    = EXCLUDED.features_used,
            status           = 'ready'
        RETURNING *
    """)
    with engine.begin() as conn:
        row = conn.execute(upsert, {
            "product_id": product_id,
            "business_id": business_id,
            "model_path": model_path,
            "data_start": data_start,
            "data_end": data_end,
            "total_points": total_points,
            "cv_mae": round(cv_mae, 2),
            "cv_mape": round(cv_mape, 2),
            "features_used": features_used,
        }).mappings().fetchone()
    return dict(row) if row else {}


def get_model_metadata(product_id: int, business_id: int) -> dict | None:
    """Return model metadata for a product, or None."""
    query = text("""
        SELECT * FROM ml_model_metadata
        WHERE product_id = :product_id AND business_id = :business_id
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                query, {"product_id": product_id, "business_id": business_id}
            ).mappings().fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def update_model_status(product_id: int, business_id: int, status: str) -> None:
    """Set model status (training / ready / failed)."""
    query = text("""
        UPDATE ml_model_metadata
        SET status = :status
        WHERE product_id = :product_id AND business_id = :business_id
    """)
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "product_id": product_id,
                "business_id": business_id,
                "status": status,
            })
    except Exception:
        pass


def delete_model_metadata(product_id: int, business_id: int) -> bool:
    """Delete model metadata row. Returns True if a row was deleted."""
    query = text("""
        DELETE FROM ml_model_metadata
        WHERE product_id = :product_id AND business_id = :business_id
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(query, {
                "product_id": product_id,
                "business_id": business_id,
            })
        return result.rowcount > 0
    except Exception:
        return False


def delete_uploaded_history(product_id: int, business_id: int) -> int:
    """Delete all uploaded history for a product. Returns rows deleted."""
    query = text("""
        DELETE FROM ml_uploaded_history
        WHERE product_id = :product_id AND business_id = :business_id
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(query, {
                "product_id": product_id,
                "business_id": business_id,
            })
        return result.rowcount
    except Exception:
        return 0
