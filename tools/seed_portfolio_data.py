#!/usr/bin/env python3
"""
seed_portfolio_data.py
======================
Seeds 365 days of realistic supply-chain history for one WMS customer so
the Portfolio AI global model can be trained with high accuracy immediately.

What it creates
---------------
  8 products   - FMCG / staples (rice, oil, tea, soap ...)
  4 suppliers  - each covering a product category
  5 buyers     - distinct weekly ordering patterns (retail, e-commerce,
                 convenience, wholesale distributor, premium)
  1 large seed stock_batch per product  (satisfies outbound_picks FK)
  ~365 days of inbound_orders / inbound_lines  (restocking every 10-14 days)
  ~365 days of outbound_orders / outbound_lines / outbound_picks
    with realistic weekly + seasonal + trend demand patterns

After inserting the script refreshes both portfolio materialized views so the
global model can be trained immediately.

Usage
-----
  cd <project-root>
  python tools/seed_portfolio_data.py <customer_id>

  Example:
    python tools/seed_portfolio_data.py 3

The script is idempotent: products / suppliers / buyers are looked up by name
before inserting.  Historical orders are skipped if their GRN / shipment
number already exists.

Requirements: psycopg2, python-dotenv  (both in ml_service/requirements.txt)
"""

import os
import sys
import random
import time
from datetime import date, timedelta, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    sys.exit("psycopg2 not found - run: pip install psycopg2")

# ── Configuration ──────────────────────────────────────────────────────────────

DB_URL = os.getenv("DB_URL", "")
if not DB_URL:
    sys.exit("DB_URL not set. Ensure .env is present in the project root.")

HISTORY_DAYS = 365          # days of history to generate
random.seed(42)             # reproducible

TODAY      = date.today()
START_DATE = TODAY - timedelta(days=HISTORY_DAYS)

# ── Product catalogue ─────────────────────────────────────────────────────────
# (display_name, sku_suffix, unit_price)
PRODUCTS = [
    ("Basmati Rice 25kg",     "RICE25",  1200.00),
    ("Whole Wheat Flour 10kg","WF10",     320.00),
    ("Refined Oil 5L",        "OIL5",    650.00),
    ("Sugar 5kg",             "SUG5",    225.00),
    ("Tea 500g",              "TEA500",  180.00),
    ("Coffee 200g",           "COF200",  260.00),
    ("Detergent Powder 1kg",  "DET1K",   180.00),
    ("Soap Bar 100g",         "SOAP100",  35.00),
]

# ── Supplier catalogue ─────────────────────────────────────────────────────────
# (name, list-of-product-indices-they-supply)
SUPPLIERS = [
    ("AgroFarms India Pvt Ltd",   [0, 1, 3]),    # Rice, Wheat, Sugar
    ("PureOil Company Ltd",       [2]),           # Oil
    ("Beverages Corp India",      [4, 5]),        # Tea, Coffee
    ("HomeGoods Supplies Ltd",    [6, 7]),        # Detergent, Soap
]

# ── Buyer catalogue ────────────────────────────────────────────────────────────
# (name, weekly_order_probability[Mon..Sun], base_volume_multiplier)
BUYERS = [
    # Large retail chain - weekday heavy
    ("MetroMart Retail Chain",
     [0.90, 0.85, 0.90, 0.85, 0.90, 0.60, 0.30], 1.50),
    # Online grocery - weekend spike
    ("FreshDirect Online",
     [0.50, 0.50, 0.60, 0.60, 0.85, 0.90, 0.75], 1.00),
    # Convenience store network - steady every day
    ("QuickMart Convenience",
     [0.70, 0.70, 0.70, 0.70, 0.80, 0.70, 0.65], 0.40),
    # Bulk distributor - Monday and Friday big orders
    ("WholesaleHub Distributors",
     [0.95, 0.10, 0.10, 0.10, 0.95, 0.05, 0.05], 4.00),
    # Premium supermarket - weekday, closed Sunday
    ("CitySuper Premium",
     [0.85, 0.70, 0.85, 0.70, 0.85, 0.50, 0.15], 0.80),
]

# ── Demand matrix: base units per order when a buyer places an order ───────────
# Rows = products 0..7, Cols = buyers 0..4
DEMAND_BASE = [
    #  Metro  Fresh  Quick  Whole  City
    [   50,    20,    10,   200,   30],   # Rice
    [   40,    15,     8,   150,   25],   # Wheat Flour
    [   30,    25,    12,   100,   20],   # Refined Oil
    [   35,    20,    10,   120,   25],   # Sugar
    [   20,    15,     8,    80,   18],   # Tea
    [   15,    20,    10,    50,   20],   # Coffee
    [   25,    18,     8,    90,   20],   # Detergent
    [   30,    20,    10,   100,   15],   # Soap
]

# Monthly seasonality - Indian FMCG market (Jan=0 ... Dec=11)
MONTHLY_SEA = [1.00, 0.95, 1.00, 1.05, 1.10, 0.95, 0.90, 0.95, 1.00, 1.15, 1.20, 1.10]

# Product-specific seasonal adjustments on top of MONTHLY_SEA
PRODUCT_SEA_OVERLAY = {
    4: {0: 1.30, 1: 1.30, 2: 1.10, 5: 0.80, 6: 0.75, 7: 0.75},  # Tea: winter spike
    5: {0: 1.20, 1: 1.20, 5: 0.85, 6: 0.80, 7: 0.85},             # Coffee: winter spike
}


# ── Demand helpers ────────────────────────────────────────────────────────────

def _demand_qty(prod_idx: int, buyer_idx: int, d: date) -> int:
    """Compute a realistic order quantity with seasonality, trend, and noise."""
    base   = DEMAND_BASE[prod_idx][buyer_idx] * BUYERS[buyer_idx][2]
    sea    = MONTHLY_SEA[d.month - 1]
    sea   *= PRODUCT_SEA_OVERLAY.get(prod_idx, {}).get(d.month - 1, 1.0)
    # Slight upward growth: +1.5 % per month from start
    months = (d - START_DATE).days / 30.0
    trend  = 1.0 + 0.015 * months
    # Gaussian noise ±10 %, clamped to [0.75, 1.25]
    noise  = max(0.75, min(1.25, random.gauss(1.0, 0.10)))
    return max(1, round(base * sea * trend * noise))


def _buyer_orders_today(buyer_idx: int, d: date) -> bool:
    dow = d.weekday()   # 0 = Monday, 6 = Sunday
    return random.random() < BUYERS[buyer_idx][1][dow]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_or_create_product(cur, name, sku_code, price,
                            business_id, customer_id, warehouse_id):
    cur.execute(
        "SELECT id FROM products "
        "WHERE business_id=%s AND customer_id=%s AND sku_code=%s",
        (business_id, customer_id, sku_code),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        """
        INSERT INTO products
            (name, sku_code, price, stock_at_warehouse,
             business_id, customer_id, warehouse_id,
             lead_time_days, safety_stock, reorder_point,
             max_stock_level, par_level)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (name, sku_code, price, 10_000,
         business_id, customer_id, warehouse_id,
         7, 200, 400, 10_000, 800),
    )
    return cur.fetchone()[0], True


def _get_or_create_supplier(cur, name, business_id, customer_id):
    cur.execute(
        "SELECT id FROM suppliers "
        "WHERE business_id=%s AND customer_id=%s AND name=%s",
        (business_id, customer_id, name),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        "INSERT INTO suppliers (name, business_id, customer_id) "
        "VALUES (%s,%s,%s) RETURNING id",
        (name, business_id, customer_id),
    )
    return cur.fetchone()[0], True


def _get_or_create_buyer(cur, name, business_id, customer_id):
    cur.execute(
        "SELECT id FROM buyers "
        "WHERE business_id=%s AND customer_id=%s AND name=%s",
        (business_id, customer_id, name),
    )
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute(
        "INSERT INTO buyers (name, business_id, customer_id) "
        "VALUES (%s,%s,%s) RETURNING id",
        (name, business_id, customer_id),
    )
    return cur.fetchone()[0], True


def _ensure_stock_batch(cur, product_id, business_id, customer_id, warehouse_id):
    """Return existing seed batch id, or create a large one dated before history."""
    cur.execute(
        "SELECT id FROM stock_batches "
        "WHERE product_id=%s AND customer_id=%s LIMIT 1",
        (product_id, customer_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    seed_ts = datetime.combine(START_DATE - timedelta(days=10), datetime.min.time())
    cur.execute(
        """
        INSERT INTO stock_batches
            (product_id, business_id, customer_id, warehouse_id,
             quantity, remaining_qty, purchased_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (product_id, business_id, customer_id, warehouse_id,
         1_000_000, 1_000_000, seed_ts),
    )
    return cur.fetchone()[0]


def _grn_exists(cur, business_id, customer_id, grn):
    cur.execute(
        "SELECT 1 FROM inbound_orders "
        "WHERE business_id=%s AND customer_id=%s AND grn_number=%s",
        (business_id, customer_id, grn),
    )
    return cur.fetchone() is not None


def _shipment_exists(cur, business_id, customer_id, shp):
    cur.execute(
        "SELECT 1 FROM outbound_orders "
        "WHERE business_id=%s AND customer_id=%s AND shipment_number=%s",
        (business_id, customer_id, shp),
    )
    return cur.fetchone() is not None


# ── Inbound generation ────────────────────────────────────────────────────────

def _generate_inbound(cur, business_id, customer_id, warehouse_id, user_id,
                      product_ids, supplier_ids):
    """
    For every (supplier, product) pair, create restocking GRNs approximately
    every 10-14 days.  Quantity = ~30-day demand estimate.

    Returns count of inbound_orders created.
    """
    created = 0
    for sup_idx, (sup_name, prod_indices) in enumerate(SUPPLIERS):
        sup_db_id = supplier_ids[sup_idx]
        for prod_idx in prod_indices:
            prod_db_id = product_ids[prod_idx]
            unit_cost  = PRODUCTS[prod_idx][2] * 0.65   # ~65% of retail = cost

            # Estimate 30-day demand from all buyers combined
            daily_avg = sum(
                DEMAND_BASE[prod_idx][b] * BUYERS[b][2]
                * sum(BUYERS[b][1]) / 7.0          # avg daily order prob
                for b in range(len(BUYERS))
            )
            restock_qty = max(200, round(daily_avg * 30))

            # Schedule restock dates: every 10-14 days with jitter
            d = START_DATE
            order_seq = 0
            while d <= TODAY:
                grn = f"GRN-C{customer_id}-S{sup_idx}-P{prod_idx}-{order_seq:04d}"
                if not _grn_exists(cur, business_id, customer_id, grn):
                    received_ts = datetime(d.year, d.month, d.day, 10, 0, 0)
                    cur.execute(
                        """
                        INSERT INTO inbound_orders
                            (business_id, customer_id, warehouse_id,
                             supplier_id, grn_number, po_number,
                             received_at, status,
                             total_qty, total_amount,
                             created_by, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'received',%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (business_id, customer_id, warehouse_id,
                         sup_db_id, grn, f"PO-{grn}",
                         received_ts, restock_qty,
                         round(restock_qty * unit_cost, 2),
                         user_id, received_ts, received_ts),
                    )
                    inbound_id = cur.fetchone()[0]
                    cur.execute(
                        """
                        INSERT INTO inbound_lines
                            (inbound_id, product_id,
                             expected_qty, received_qty, unit_cost, line_amount)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        """,
                        (inbound_id, prod_db_id,
                         restock_qty, restock_qty,
                         round(unit_cost, 4),
                         round(restock_qty * unit_cost, 2)),
                    )
                    created += 1

                # Advance by 10-14 days
                d += timedelta(days=random.randint(10, 14))
                order_seq += 1

    return created


# ── Outbound generation ───────────────────────────────────────────────────────

def _generate_outbound(cur, business_id, customer_id, warehouse_id, user_id,
                       product_ids, buyer_ids, batch_ids):
    """
    For each day in the history window, decide which buyers order and generate
    outbound_orders / outbound_lines / outbound_picks.

    Returns count of outbound_orders created.
    """
    created = 0

    all_dates = [START_DATE + timedelta(days=i) for i in range(HISTORY_DAYS)]

    for d in all_dates:
        shipped_ts = datetime(d.year, d.month, d.day, 14, 0, 0)

        for b_idx, (buyer_name, _, _) in enumerate(BUYERS):
            if not _buyer_orders_today(b_idx, d):
                continue

            shp = f"SHP-C{customer_id}-B{b_idx}-{(d - START_DATE).days:04d}"
            if _shipment_exists(cur, business_id, customer_id, shp):
                continue

            # Determine which products are included in this order
            # (buyers always order all products to keep the panel dense)
            order_lines = [
                (_demand_qty(p_idx, b_idx, d), p_idx)
                for p_idx in range(len(PRODUCTS))
            ]
            total_qty = sum(q for q, _ in order_lines)

            cur.execute(
                """
                INSERT INTO outbound_orders
                    (business_id, customer_id, warehouse_id,
                     buyer_id, shipment_number, so_number,
                     shipped_at, status,
                     total_qty, total_amount,
                     created_by, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'shipped',%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (business_id, customer_id, warehouse_id,
                 buyer_ids[b_idx], shp, f"SO-{shp}",
                 shipped_ts, total_qty, 0.0,
                 user_id, shipped_ts, shipped_ts),
            )
            outbound_id = cur.fetchone()[0]

            for qty, p_idx in order_lines:
                prod_db_id  = product_ids[p_idx]
                batch_db_id = batch_ids[p_idx]
                unit_price  = PRODUCTS[p_idx][2]

                cur.execute(
                    """
                    INSERT INTO outbound_lines
                        (outbound_id, product_id,
                         requested_qty, picked_qty,
                         unit_price, line_amount)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (outbound_id, prod_db_id,
                     qty, qty,
                     round(unit_price, 4),
                     round(qty * unit_price, 2)),
                )
                line_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO outbound_picks
                        (outbound_line_id, stock_batch_id, qty, unit_cost)
                    VALUES (%s,%s,%s,%s)
                    """,
                    (line_id, batch_db_id, qty, round(unit_price * 0.65, 4)),
                )

            created += 1

    return created


# ── Main ──────────────────────────────────────────────────────────────────────

def main(customer_id: int) -> None:
    print(f"\n{'='*60}")
    print(f"  Portfolio AI Seed  -  customer_id={customer_id}")
    print(f"  History: {START_DATE}  ->  {TODAY}  ({HISTORY_DAYS} days)")
    print(f"{'='*60}\n")

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # ── 1. Resolve customer record ──────────────────────────────────────────
    cur.execute(
        "SELECT id, business_id, name FROM customers WHERE id=%s",
        (customer_id,),
    )
    cust_row = cur.fetchone()
    if not cust_row:
        cur.close(); conn.close()
        sys.exit(f"Customer id={customer_id} not found in the database.")
    _, business_id, cust_name = cust_row
    print(f"Customer  : {cust_name}  (id={customer_id}, business_id={business_id})")

    # ── 2. Resolve warehouse ────────────────────────────────────────────────
    # Prefer warehouse already used by this customer's products, else MAIN
    cur.execute(
        """
        SELECT DISTINCT w.id, w.name
        FROM warehouses w
        JOIN products p ON p.warehouse_id = w.id
        WHERE p.business_id=%s AND p.customer_id=%s
        LIMIT 1
        """,
        (business_id, customer_id),
    )
    wh_row = cur.fetchone()
    if not wh_row:
        cur.execute(
            "SELECT id, name FROM warehouses WHERE business_id=%s LIMIT 1",
            (business_id,),
        )
        wh_row = cur.fetchone()
    if not wh_row:
        cur.close(); conn.close()
        sys.exit(f"No warehouse found for business_id={business_id}.")
    warehouse_id, wh_name = wh_row
    print(f"Warehouse : {wh_name}  (id={warehouse_id})")

    # ── 3. Resolve created_by user ──────────────────────────────────────────
    cur.execute(
        "SELECT id, name FROM users WHERE business_id=%s LIMIT 1",
        (business_id,),
    )
    user_row = cur.fetchone()
    if not user_row:
        cur.close(); conn.close()
        sys.exit(f"No users found for business_id={business_id}. Create a user first.")
    user_id, user_name = user_row
    print(f"Created-by: {user_name}  (user_id={user_id})\n")

    # ── 4. Create products ──────────────────────────────────────────────────
    print("Creating products ...")
    product_ids = []
    new_prods = 0
    for name, sku_sfx, price in PRODUCTS:
        sku = f"C{customer_id}-{sku_sfx}"
        pid, created = _get_or_create_product(
            cur, name, sku, price, business_id, customer_id, warehouse_id,
        )
        product_ids.append(pid)
        if created:
            new_prods += 1
            print(f"  + {name} ({sku})")
        else:
            print(f"  ~ {name} ({sku})  [already exists]")
    conn.commit()
    print(f"  -> {new_prods} new, {len(PRODUCTS)-new_prods} existing\n")

    # ── 5. Create suppliers ─────────────────────────────────────────────────
    print("Creating suppliers ...")
    supplier_ids = []
    new_sups = 0
    for name, prod_indices in SUPPLIERS:
        sid, created = _get_or_create_supplier(
            cur, name, business_id, customer_id,
        )
        supplier_ids.append(sid)
        if created:
            new_sups += 1
            print(f"  + {name}")
        else:
            print(f"  ~ {name}  [already exists]")
    conn.commit()
    print(f"  -> {new_sups} new, {len(SUPPLIERS)-new_sups} existing\n")

    # ── 6. Create buyers ────────────────────────────────────────────────────
    print("Creating buyers ...")
    buyer_ids = []
    new_buys = 0
    for name, _, _ in BUYERS:
        bid, created = _get_or_create_buyer(cur, name, business_id, customer_id)
        buyer_ids.append(bid)
        if created:
            new_buys += 1
            print(f"  + {name}")
        else:
            print(f"  ~ {name}  [already exists]")
    conn.commit()
    print(f"  -> {new_buys} new, {len(BUYERS)-new_buys} existing\n")

    # ── 7. Ensure seed stock batches ────────────────────────────────────────
    print("Ensuring seed stock batches ...")
    batch_ids = []
    for prod_idx, pid in enumerate(product_ids):
        bid = _ensure_stock_batch(cur, pid, business_id, customer_id, warehouse_id)
        batch_ids.append(bid)
    conn.commit()
    print(f"  -> {len(batch_ids)} batches ready\n")

    # ── 8. Generate inbound history ─────────────────────────────────────────
    print("Generating inbound history ...")
    t0 = time.time()
    n_inbound = _generate_inbound(
        cur, business_id, customer_id, warehouse_id, user_id,
        product_ids, supplier_ids,
    )
    conn.commit()
    print(f"  -> {n_inbound} inbound orders created  ({time.time()-t0:.1f}s)\n")

    # ── 9. Generate outbound history ────────────────────────────────────────
    print("Generating outbound history (this may take ~30-60 s) ...")
    t0 = time.time()
    n_outbound = _generate_outbound(
        cur, business_id, customer_id, warehouse_id, user_id,
        product_ids, buyer_ids, batch_ids,
    )
    conn.commit()
    print(f"  -> {n_outbound} outbound orders created  ({time.time()-t0:.1f}s)\n")

    # ── 10. Refresh materialized views ──────────────────────────────────────
    print("Refreshing portfolio materialized views ...")
    for view in ("mv_seller_product_daily", "mv_buyer_product_daily"):
        try:
            conn.autocommit = True
            cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
            print(f"  OK {view}")
        except Exception:
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW {view}")
                print(f"  OK {view}  (non-concurrent)")
            except Exception as e:
                print(f"  ! {view}  failed: {e}  (views may not exist yet - run migrations)")
        conn.autocommit = False

    # ── 11. Summary ─────────────────────────────────────────────────────────
    cur.execute(
        "SELECT COUNT(*) FROM inbound_orders "
        "WHERE business_id=%s AND customer_id=%s",
        (business_id, customer_id),
    )
    total_inbound = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM outbound_orders "
        "WHERE business_id=%s AND customer_id=%s",
        (business_id, customer_id),
    )
    total_outbound = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(DISTINCT (buyer_id, product_id)) FROM outbound_picks op "
        "JOIN outbound_lines ol ON ol.id = op.outbound_line_id "
        "JOIN outbound_orders oo ON oo.id = ol.outbound_id "
        "WHERE oo.business_id=%s AND oo.customer_id=%s",
        (business_id, customer_id),
    )
    n_pairs = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print("  Seeding complete")
    print(f"{'='*60}")
    print(f"  Products            : {len(PRODUCTS)}")
    print(f"  Suppliers           : {len(SUPPLIERS)}")
    print(f"  Buyers              : {len(BUYERS)}")
    print(f"  Buyer-product pairs : {n_pairs}  (min required: 3)")
    print(f"  Total inbound orders: {total_inbound}")
    print(f"  Total shipments     : {total_outbound}")
    print(f"\n  You can now trigger model training via:")
    print(f"    POST /forecast/portfolio/train")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(__doc__)
        sys.exit("Usage: python tools/seed_portfolio_data.py <customer_id>")
    main(int(sys.argv[1]))
