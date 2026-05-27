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


def get_daily_aggregated_transactions(
    product_id: int,
    business_id: int,
    customer_id: int | None = None,
) -> pd.DataFrame:
    """
    Aggregate ``inventory_transactions`` into daily inbound/outbound
    for a single product. Customer-scoped when ``customer_id`` is given.
    """
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {"product_id": product_id, "business_id": business_id}
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    query = text(f"""
        SELECT
            DATE(transaction_at)                                          AS date,
            COALESCE(SUM(CASE WHEN stock_adjusted > 0
                              THEN stock_adjusted ELSE 0 END), 0)        AS inbound_qty,
            COALESCE(SUM(CASE WHEN stock_adjusted < 0
                              THEN ABS(stock_adjusted) ELSE 0 END), 0)   AS outbound_qty
        FROM inventory_transactions
        WHERE {' AND '.join(where)}
        GROUP BY DATE(transaction_at)
        ORDER BY date
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()

    if not rows:
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["inbound_qty"] = df["inbound_qty"].astype(int)
    df["outbound_qty"] = df["outbound_qty"].astype(int)
    return df


def get_customer_outbound_history(
    business_id: int, customer_id: int, days: int = 365,
) -> pd.DataFrame:
    """Cross-product daily outbound for a customer (used for cold-start fallback)."""
    query = text("""
        SELECT
            DATE(transaction_at) AS date,
            COALESCE(SUM(ABS(stock_adjusted)), 0) AS outbound_qty
        FROM inventory_transactions
        WHERE business_id = :biz
          AND customer_id = :cust
          AND stock_adjusted < 0
          AND transaction_at >= NOW() - INTERVAL ':d days'
        GROUP BY DATE(transaction_at)
        ORDER BY date
    """.replace(":d", str(int(days))))
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["date", "outbound_qty"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["outbound_qty"] = df["outbound_qty"].astype(int)
    return df


def get_product_replenishment_inputs(product_id: int, business_id: int) -> dict:
    """Per-product config used for replenishment math."""
    query = text("""
        SELECT id, name, sku_code, customer_id,
               stock_at_warehouse, lead_time_days, safety_stock,
               reorder_point, max_stock_level, par_level, expiry_days
        FROM products
        WHERE id = :pid AND business_id = :biz
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"pid": product_id, "biz": business_id}).mappings().fetchone()
    return dict(row) if row else {}


def get_uploaded_history(
    product_id: int, business_id: int, customer_id: int | None = None,
) -> pd.DataFrame:
    """
    Fetch CSV-uploaded historical data from ``ml_uploaded_history``.

    Customer-scoped when ``customer_id`` is given.
    """
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {"product_id": product_id, "business_id": business_id}
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id
    query = text(f"""
        SELECT date, inbound_qty, outbound_qty, stock_level
        FROM ml_uploaded_history
        WHERE {' AND '.join(where)}
        ORDER BY date
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
    except Exception:
        # Table may not exist yet – return empty
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty", "stock_level"])

    if not rows:
        return pd.DataFrame(columns=["date", "inbound_qty", "outbound_qty", "stock_level"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
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


def get_product_tenant_ids(product_id: int, business_id: int) -> dict:
    """
    Resolve the multi-tenant IDs (customer_id, warehouse_id) for a product.

    Every product belongs to exactly one customer and one warehouse.
    This is the authoritative source for tenancy — callers should never
    need to guess or accept these values from the API.

    Returns ``{"customer_id": int, "warehouse_id": int}`` or raises ValueError.
    """
    query = text("""
        SELECT customer_id, warehouse_id
        FROM products
        WHERE id = :product_id AND business_id = :business_id
    """)
    with engine.connect() as conn:
        row = conn.execute(
            query, {"product_id": product_id, "business_id": business_id}
        ).mappings().fetchone()
    if not row or row["customer_id"] is None:
        raise ValueError(
            f"Cannot resolve tenant IDs for product {product_id} / "
            f"business {business_id}. Ensure the product exists and has "
            f"customer_id set."
        )
    return {"customer_id": int(row["customer_id"]), "warehouse_id": int(row["warehouse_id"])}


def save_uploaded_history(
    product_id: int,
    business_id: int,
    uploaded_by: int,
    df: pd.DataFrame,
    customer_id: int | None = None,
    warehouse_id: int | None = None,
) -> int:
    """
    Upsert rows from a validated CSV upload into ``ml_uploaded_history``.

    ``df`` must have columns: date, inbound_qty, outbound_qty
    Optional columns: stock_level, notes

    If ``customer_id`` / ``warehouse_id`` are not provided they are
    resolved from the product.
    Returns the number of rows upserted.
    """
    if customer_id is None or warehouse_id is None:
        tenant = get_product_tenant_ids(product_id, business_id)
        customer_id = customer_id or tenant["customer_id"]
        warehouse_id = warehouse_id or tenant["warehouse_id"]

    upsert = text("""
        INSERT INTO ml_uploaded_history
            (product_id, business_id, customer_id, warehouse_id,
             uploaded_by, date,
             inbound_qty, outbound_qty, stock_level, notes)
        VALUES
            (:product_id, :business_id, :customer_id, :warehouse_id,
             :uploaded_by, :date,
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
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
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
    customer_id: int | None = None,
    warehouse_id: int | None = None,
) -> dict:
    """Upsert model metadata after training.

    If ``customer_id`` / ``warehouse_id`` are not provided they are
    resolved from the product.
    """
    if customer_id is None or warehouse_id is None:
        tenant = get_product_tenant_ids(product_id, business_id)
        customer_id = customer_id or tenant["customer_id"]
        warehouse_id = warehouse_id or tenant["warehouse_id"]

    upsert = text("""
        INSERT INTO ml_model_metadata
            (product_id, business_id, customer_id, warehouse_id,
             model_path, trained_at,
             data_start_date, data_end_date, total_data_points,
             cv_mae, cv_mape, features_used, status)
        VALUES
            (:product_id, :business_id, :customer_id, :warehouse_id,
             :model_path, NOW(),
             :data_start, :data_end, :total_points,
             :cv_mae, :cv_mape, :features_used, 'ready')
        ON CONFLICT (product_id, business_id)
        DO UPDATE SET
            model_path       = EXCLUDED.model_path,
            customer_id      = EXCLUDED.customer_id,
            warehouse_id     = EXCLUDED.warehouse_id,
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
            "customer_id": customer_id,
            "warehouse_id": warehouse_id,
            "model_path": model_path,
            "data_start": data_start,
            "data_end": data_end,
            "total_points": total_points,
            "cv_mae": round(cv_mae, 2),
            "cv_mape": round(cv_mape, 2),
            "features_used": features_used,
        }).mappings().fetchone()
    return dict(row) if row else {}


def get_model_metadata(
    product_id: int, business_id: int, customer_id: int | None = None,
) -> dict | None:
    """Return model metadata for a product, or None."""
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {"product_id": product_id, "business_id": business_id}
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    query = text(f"""
        SELECT * FROM ml_model_metadata
        WHERE {' AND '.join(where)}
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, params).mappings().fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def update_model_status(
    product_id: int, business_id: int, status: str,
    customer_id: int | None = None,
) -> None:
    """Set model status (training / ready / failed)."""
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {
        "product_id": product_id,
        "business_id": business_id,
        "status": status,
    }
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    query = text(f"""
        UPDATE ml_model_metadata
        SET status = :status
        WHERE {' AND '.join(where)}
    """)
    try:
        with engine.begin() as conn:
            conn.execute(query, params)
    except Exception:
        pass


def delete_model_metadata(
    product_id: int, business_id: int, customer_id: int | None = None,
) -> bool:
    """Delete model metadata row. Returns True if a row was deleted."""
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {"product_id": product_id, "business_id": business_id}
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    query = text(f"""
        DELETE FROM ml_model_metadata
        WHERE {' AND '.join(where)}
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(query, params)
        return result.rowcount > 0
    except Exception:
        return False


# ── Portfolio / global-model reads (Phase 1) ────────────────────────────────

def _mv_exists(name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT 1 FROM pg_matviews WHERE matviewname = :n
        """), {"n": name}).fetchone()
    return row is not None


def get_seller_product_series(
    business_id: int,
    customer_id: int,
    seller_id: int | None = None,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Daily inbound qty per (seller, product). Uses mv when available."""
    use_mv = _mv_exists("mv_seller_product_daily")
    if use_mv:
        sql = """
            SELECT date, seller_id, product_id, inbound_qty, avg_unit_cost
            FROM mv_seller_product_daily
            WHERE business_id = :biz AND customer_id = :cust
        """
        params: dict = {"biz": business_id, "cust": customer_id}
        if warehouse_id is not None:
            sql += " AND warehouse_id = :wh"
            params["wh"] = warehouse_id
        if seller_id is not None:
            sql += " AND seller_id = :sid"
            params["sid"] = seller_id
        if product_id is not None:
            sql += " AND product_id = :pid"
            params["pid"] = product_id
        if start_date is not None:
            sql += " AND date >= :start"
            params["start"] = start_date
        if end_date is not None:
            sql += " AND date <= :end"
            params["end"] = end_date
        sql += " ORDER BY date"
    else:
        sql = """
            SELECT DATE(io.received_at) AS date,
                   io.supplier_id        AS seller_id,
                   il.product_id,
                   SUM(il.received_qty)::INT AS inbound_qty,
                   AVG(il.unit_cost)     AS avg_unit_cost
            FROM inbound_lines il
            JOIN inbound_orders io ON io.id = il.inbound_id
            WHERE io.business_id = :biz AND io.customer_id = :cust
              AND io.status = 'received' AND io.supplier_id IS NOT NULL
        """
        params = {"biz": business_id, "cust": customer_id}
        if warehouse_id is not None:
            sql += " AND io.warehouse_id = :wh"
            params["wh"] = warehouse_id
        if seller_id is not None:
            sql += " AND io.supplier_id = :sid"
            params["sid"] = seller_id
        if product_id is not None:
            sql += " AND il.product_id = :pid"
            params["pid"] = product_id
        if start_date is not None:
            sql += " AND io.received_at >= :start"
            params["start"] = start_date
        if end_date is not None:
            sql += " AND io.received_at < (DATE :end + INTERVAL '1 day')"
            params["end"] = end_date
        sql += """
            GROUP BY DATE(io.received_at), io.supplier_id, il.product_id
            ORDER BY date
        """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["date", "seller_id", "product_id", "inbound_qty", "avg_unit_cost"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["inbound_qty"] = df["inbound_qty"].fillna(0).astype(int)
    return df


def get_buyer_product_series(
    business_id: int,
    customer_id: int,
    buyer_id: int | None = None,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Daily outbound qty per (buyer, product). Uses mv when available."""
    use_mv = _mv_exists("mv_buyer_product_daily")
    if use_mv:
        sql = """
            SELECT date, buyer_id, product_id, outbound_qty, avg_cogs
            FROM mv_buyer_product_daily
            WHERE business_id = :biz AND customer_id = :cust
        """
        params: dict = {"biz": business_id, "cust": customer_id}
        if warehouse_id is not None:
            sql += " AND warehouse_id = :wh"
            params["wh"] = warehouse_id
        if buyer_id is not None:
            sql += " AND buyer_id = :bid"
            params["bid"] = buyer_id
        if product_id is not None:
            sql += " AND product_id = :pid"
            params["pid"] = product_id
        if start_date is not None:
            sql += " AND date >= :start"
            params["start"] = start_date
        if end_date is not None:
            sql += " AND date <= :end"
            params["end"] = end_date
        sql += " ORDER BY date"
    else:
        sql = """
            SELECT DATE(oo.shipped_at) AS date,
                   oo.buyer_id,
                   ol.product_id,
                   SUM(op.qty)::INT  AS outbound_qty,
                   AVG(op.unit_cost) AS avg_cogs
            FROM outbound_picks op
            JOIN outbound_lines ol  ON ol.id = op.outbound_line_id
            JOIN outbound_orders oo ON oo.id = ol.outbound_id
            WHERE oo.business_id = :biz AND oo.customer_id = :cust
              AND oo.status = 'shipped' AND oo.buyer_id IS NOT NULL
        """
        params = {"biz": business_id, "cust": customer_id}
        if warehouse_id is not None:
            sql += " AND oo.warehouse_id = :wh"
            params["wh"] = warehouse_id
        if buyer_id is not None:
            sql += " AND oo.buyer_id = :bid"
            params["bid"] = buyer_id
        if product_id is not None:
            sql += " AND ol.product_id = :pid"
            params["pid"] = product_id
        if start_date is not None:
            sql += " AND oo.shipped_at >= :start"
            params["start"] = start_date
        if end_date is not None:
            sql += " AND oo.shipped_at < (DATE :end + INTERVAL '1 day')"
            params["end"] = end_date
        sql += """
            GROUP BY DATE(oo.shipped_at), oo.buyer_id, ol.product_id
            ORDER BY date
        """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["date", "buyer_id", "product_id", "outbound_qty", "avg_cogs"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["outbound_qty"] = df["outbound_qty"].fillna(0).astype(int)
    return df


def get_all_sellers(business_id: int, customer_id: int) -> list[dict]:
    """All suppliers for this customer with primary-location summary."""
    query = text("""
        SELECT s.id, s.name, s.gstin, s.is_active,
               (SELECT sl.city  FROM seller_locations sl
                 WHERE sl.supplier_id = s.id AND sl.is_active LIMIT 1) AS city,
               (SELECT sl.state FROM seller_locations sl
                 WHERE sl.supplier_id = s.id AND sl.is_active LIMIT 1) AS state
        FROM suppliers s
        WHERE s.business_id = :biz AND s.customer_id = :cust
        ORDER BY s.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


def get_all_buyers(business_id: int, customer_id: int) -> list[dict]:
    """All buyers for this customer with primary-location summary."""
    query = text("""
        SELECT b.id, b.name, b.gstin, b.is_active,
               (SELECT bl.city  FROM buyer_locations bl
                 WHERE bl.buyer_id = b.id AND bl.is_active LIMIT 1) AS city,
               (SELECT bl.state FROM buyer_locations bl
                 WHERE bl.buyer_id = b.id AND bl.is_active LIMIT 1) AS state
        FROM buyers b
        WHERE b.business_id = :biz AND b.customer_id = :cust
        ORDER BY b.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


def get_portfolio_product_list(
    business_id: int, customer_id: int, warehouse_id: int | None = None,
) -> list[dict]:
    """Products with current stock + per-product model metadata (joined)."""
    where = ["p.business_id = :biz", "p.customer_id = :cust"]
    params: dict = {"biz": business_id, "cust": customer_id}
    if warehouse_id is not None:
        where.append("p.warehouse_id = :wh")
        params["wh"] = warehouse_id
    sql = f"""
        SELECT
            p.id, p.name, p.sku_code, p.price, p.uom,
            p.stock_at_warehouse, p.lead_time_days, p.reorder_point, p.safety_stock,
            mm.status AS model_status, mm.trained_at, mm.cv_mae, mm.cv_mape,
            mm.data_end_date
        FROM products p
        LEFT JOIN ml_model_metadata mm
               ON mm.product_id = p.id AND mm.business_id = p.business_id
        WHERE {' AND '.join(where)}
        ORDER BY p.name
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def get_warehouses_for_customer(business_id: int, customer_id: int) -> list[dict]:
    """Warehouses that hold this customer's inventory (have any products)."""
    query = text("""
        SELECT DISTINCT w.id, w.name, w.code
        FROM warehouses w
        JOIN products p ON p.warehouse_id = w.id
        WHERE p.business_id = :biz AND p.customer_id = :cust
        ORDER BY w.name
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"biz": business_id, "cust": customer_id}).mappings().all()
    return [dict(r) for r in rows]


# ── Global ML model metadata ────────────────────────────────────────────────

def save_global_model_metadata(
    business_id: int, customer_id: int, warehouse_id: int,
    model_path: str,
    data_start: date, data_end: date,
    total_points: int, n_products: int, n_buyers: int, n_sellers: int,
    cv_mae: float, cv_mape: float, features_used: list[str],
) -> dict:
    upsert = text("""
        INSERT INTO ml_global_model_metadata
            (business_id, customer_id, warehouse_id, model_path, trained_at,
             data_start_date, data_end_date, total_data_points,
             n_products, n_buyers, n_sellers,
             cv_mae, cv_mape, features_used, status)
        VALUES
            (:biz, :cust, :wh, :path, NOW(),
             :ds, :de, :tp, :np, :nb, :ns,
             :mae, :mape, :feats, 'ready')
        ON CONFLICT (business_id, customer_id, warehouse_id)
        DO UPDATE SET
            model_path        = EXCLUDED.model_path,
            trained_at        = NOW(),
            data_start_date   = EXCLUDED.data_start_date,
            data_end_date     = EXCLUDED.data_end_date,
            total_data_points = EXCLUDED.total_data_points,
            n_products        = EXCLUDED.n_products,
            n_buyers          = EXCLUDED.n_buyers,
            n_sellers         = EXCLUDED.n_sellers,
            cv_mae            = EXCLUDED.cv_mae,
            cv_mape           = EXCLUDED.cv_mape,
            features_used     = EXCLUDED.features_used,
            status            = 'ready'
        RETURNING *
    """)
    with engine.begin() as conn:
        row = conn.execute(upsert, {
            "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            "path": model_path,
            "ds": data_start, "de": data_end, "tp": total_points,
            "np": n_products, "nb": n_buyers, "ns": n_sellers,
            "mae": round(cv_mae, 2), "mape": round(cv_mape, 2),
            "feats": features_used,
        }).mappings().fetchone()
    return dict(row) if row else {}


def get_global_model_metadata(
    business_id: int, customer_id: int, warehouse_id: int,
) -> dict | None:
    query = text("""
        SELECT * FROM ml_global_model_metadata
        WHERE business_id = :biz AND customer_id = :cust AND warehouse_id = :wh
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {
                "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            }).mappings().fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def update_global_model_status(
    business_id: int, customer_id: int, warehouse_id: int, status: str,
) -> None:
    query = text("""
        UPDATE ml_global_model_metadata SET status = :s
        WHERE business_id = :biz AND customer_id = :cust AND warehouse_id = :wh
    """)
    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "biz": business_id, "cust": customer_id, "wh": warehouse_id, "s": status,
            })
    except Exception:
        pass


# ── Forecast cache ──────────────────────────────────────────────────────────

def save_forecast_cache(
    business_id: int, customer_id: int, warehouse_id: int,
    rows: list[dict],
) -> int:
    """Bulk-upsert forecast rows.

    Each row: {product_id, buyer_id (or None), forecast_date, p10, p50, p90}.
    Uses two queries to handle the buyer_id-NULL partial unique index.
    """
    if not rows:
        return 0
    agg_rows = [r for r in rows if r.get("buyer_id") is None]
    buyer_rows = [r for r in rows if r.get("buyer_id") is not None]

    inserted = 0
    with engine.begin() as conn:
        if agg_rows:
            stmt = text("""
                INSERT INTO ml_forecast_cache
                    (business_id, customer_id, warehouse_id, product_id,
                     buyer_id, forecast_date, p10, p50, p90, computed_at)
                VALUES
                    (:biz, :cust, :wh, :pid, NULL, :d, :p10, :p50, :p90, NOW())
                ON CONFLICT (business_id, customer_id, warehouse_id, product_id, forecast_date)
                WHERE buyer_id IS NULL
                DO UPDATE SET p10 = EXCLUDED.p10, p50 = EXCLUDED.p50,
                              p90 = EXCLUDED.p90, computed_at = NOW()
            """)
            params = [{
                "biz": business_id, "cust": customer_id, "wh": warehouse_id,
                "pid": r["product_id"], "d": r["forecast_date"],
                "p10": float(r["p10"]), "p50": float(r["p50"]), "p90": float(r["p90"]),
            } for r in agg_rows]
            conn.execute(stmt, params)
            inserted += len(agg_rows)
        if buyer_rows:
            stmt = text("""
                INSERT INTO ml_forecast_cache
                    (business_id, customer_id, warehouse_id, product_id,
                     buyer_id, forecast_date, p10, p50, p90, computed_at)
                VALUES
                    (:biz, :cust, :wh, :pid, :bid, :d, :p10, :p50, :p90, NOW())
                ON CONFLICT (business_id, customer_id, warehouse_id, product_id, buyer_id, forecast_date)
                WHERE buyer_id IS NOT NULL
                DO UPDATE SET p10 = EXCLUDED.p10, p50 = EXCLUDED.p50,
                              p90 = EXCLUDED.p90, computed_at = NOW()
            """)
            params = [{
                "biz": business_id, "cust": customer_id, "wh": warehouse_id,
                "pid": r["product_id"], "bid": r["buyer_id"], "d": r["forecast_date"],
                "p10": float(r["p10"]), "p50": float(r["p50"]), "p90": float(r["p90"]),
            } for r in buyer_rows]
            conn.execute(stmt, params)
            inserted += len(buyer_rows)
    return inserted


def get_forecast_cache(
    business_id: int, customer_id: int, warehouse_id: int,
    product_id: int | None = None,
    buyer_id: int | None = None,  # use sentinel below for aggregate-only
    aggregate_only: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    where = ["business_id = :biz", "customer_id = :cust", "warehouse_id = :wh"]
    params: dict = {"biz": business_id, "cust": customer_id, "wh": warehouse_id}
    if product_id is not None:
        where.append("product_id = :pid")
        params["pid"] = product_id
    if aggregate_only:
        where.append("buyer_id IS NULL")
    elif buyer_id is not None:
        where.append("buyer_id = :bid")
        params["bid"] = buyer_id
    if start_date is not None:
        where.append("forecast_date >= :start")
        params["start"] = start_date
    if end_date is not None:
        where.append("forecast_date <= :end")
        params["end"] = end_date
    sql = f"""
        SELECT product_id, buyer_id, forecast_date, p10, p50, p90, computed_at
        FROM ml_forecast_cache
        WHERE {' AND '.join(where)}
        ORDER BY forecast_date
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    if not rows:
        return pd.DataFrame(columns=["product_id", "buyer_id", "forecast_date", "p10", "p50", "p90", "computed_at"])
    df = pd.DataFrame(rows)
    df["forecast_date"] = pd.to_datetime(df["forecast_date"]).dt.normalize()
    for c in ("p10", "p50", "p90"):
        df[c] = df[c].astype(float)
    return df


def clear_forecast_cache_for_scope(
    business_id: int, customer_id: int, warehouse_id: int,
) -> int:
    query = text("""
        DELETE FROM ml_forecast_cache
        WHERE business_id = :biz AND customer_id = :cust AND warehouse_id = :wh
    """)
    with engine.begin() as conn:
        return conn.execute(query, {
            "biz": business_id, "cust": customer_id, "wh": warehouse_id,
        }).rowcount


# ── Insights cache ──────────────────────────────────────────────────────────

def save_insights(
    business_id: int, customer_id: int, warehouse_id: int,
    insights: list[dict],
) -> int:
    """Replace all insights for the scope with the new batch."""
    import json
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM ml_insights_cache
            WHERE business_id = :biz AND customer_id = :cust AND warehouse_id = :wh
        """), {"biz": business_id, "cust": customer_id, "wh": warehouse_id})
        if not insights:
            return 0
        stmt = text("""
            INSERT INTO ml_insights_cache
                (business_id, customer_id, warehouse_id, insight_type, severity,
                 product_id, entity_type, entity_id, message, value, threshold, meta)
            VALUES
                (:biz, :cust, :wh, :type, :sev, :pid, :etype, :eid,
                 :msg, :val, :thr, CAST(:meta AS JSONB))
        """)
        params = [{
            "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            "type": i["type"], "sev": i.get("severity", "info"),
            "pid": i.get("product_id"),
            "etype": i.get("entity_type"), "eid": i.get("entity_id"),
            "msg": i.get("message", ""),
            "val": i.get("value"), "thr": i.get("threshold"),
            "meta": json.dumps(i.get("meta", {})),
        } for i in insights]
        conn.execute(stmt, params)
    return len(insights)


def get_insights(
    business_id: int, customer_id: int, warehouse_id: int,
) -> list[dict]:
    query = text("""
        SELECT insight_type, severity, product_id, entity_type, entity_id,
               message, value, threshold, meta, computed_at
        FROM ml_insights_cache
        WHERE business_id = :biz AND customer_id = :cust AND warehouse_id = :wh
        ORDER BY
            CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            computed_at DESC
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {
                "biz": business_id, "cust": customer_id, "wh": warehouse_id,
            }).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_uploaded_history(
    product_id: int, business_id: int, customer_id: int | None = None,
) -> int:
    """Delete all uploaded history for a product. Returns rows deleted."""
    where = ["product_id = :product_id", "business_id = :business_id"]
    params: dict = {"product_id": product_id, "business_id": business_id}
    if customer_id is not None:
        where.append("customer_id = :customer_id")
        params["customer_id"] = customer_id

    query = text(f"""
        DELETE FROM ml_uploaded_history
        WHERE {' AND '.join(where)}
    """)
    try:
        with engine.begin() as conn:
            result = conn.execute(query, params)
        return result.rowcount
    except Exception:
        return 0
