"""
generate_inventory_history.py
==============================
Realistic fake inventory history generator for WMS 2.0.

Generates two outputs:
  1. A daily-aggregated CSV ready to upload via the ML service upload endpoint.
     (One row per date — matches the ml_uploaded_history table schema.)
  2. A granular transactions CSV with multiple rows per day, suitable for
     bulk-inserting into inventory_transactions via the backend API.
     (Useful to get 5000+ rows of realistic data for analytics / ML training.)

Usage
-----
  # Default (Alaskan Cod, 2024-01-01 → 2026-03-28, opens output folder):
  python generate_inventory_history.py

  # Custom product and date range:
  python generate_inventory_history.py \\
      --product-name "Fresh Salmon" \\
      --sku-code SKU042 \\
      --start 2024-01-01 \\
      --end 2026-03-28 \\
      --initial-stock 800 \\
      --out-dir "D:/Downloads"

  # Upload daily CSV via the API after running:
  #   POST /products/{product_id}/forecast/upload  (with Bearer token)

Dependencies: pip install pandas numpy
"""

from __future__ import annotations

import argparse
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


# ── Seed for reproducibility (remove for different random data each run) ────
SEED = 42


# ──────────────────────────────────────────────────────────────────────────────
# Core generation logic
# ──────────────────────────────────────────────────────────────────────────────

def _day_of_year_fraction(d: date) -> float:
    """Fraction of year elapsed on date d (0.0 – 1.0)."""
    doy = d.timetuple().tm_yday
    year_len = 366 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) else 365
    return doy / year_len


def _seasonal_multiplier(d: date) -> float:
    """
    Returns a seasonal demand multiplier based on month:
      - Lent spike: Feb–Apr  (+30–50 % for seafood / fish)
      - Christmas/New Year:  (+20–35 %)
      - Summer trough:       (−15–25 %)
    """
    m = d.month
    if m in (2, 3):          # Lent peak
        return 1.45
    elif m == 4:             # Easter / end of Lent
        return 1.30
    elif m in (6, 7, 8):     # Summer low (B2B/restaurant slow)
        return 0.78
    elif m == 11:            # Pre-Christmas ramp
        return 1.20
    elif m == 12:            # Christmas season
        return 1.35
    elif m == 1:             # Post-Christmas hangover
        return 0.88
    else:
        return 1.0


def _weekday_multiplier(d: date) -> float:
    """Lower demand on weekends (restaurant / B2B pattern)."""
    wd = d.weekday()   # 0=Mon … 6=Sun
    if wd == 5:        # Saturday
        return 0.55
    elif wd == 6:      # Sunday
        return 0.30
    return 1.0


def _is_major_holiday(d: date) -> bool:
    """Very rough check for major Indian public holidays (closed/minimal ops)."""
    # Republic Day, Independence Day, Gandhi Jayanti + major festivals (approximate)
    _FIXED = {(1, 26), (8, 15), (10, 2)}
    if (d.month, d.day) in _FIXED:
        return True
    # Approximate Diwali range (Oct 20 – Nov 15)
    if d.month == 10 and d.day >= 20:
        return True
    if d.month == 11 and d.day <= 5:
        return True
    return False


def generate_daily_rows(
    start: date,
    end: date,
    initial_stock: int = 500,
    base_daily_outbound: float = 55.0,    # average units sold per active day
    inbound_frequency_days: int = 4,       # restock every ~N days
    inbound_batch_min: int = 120,
    inbound_batch_max: int = 350,
    rng: random.Random | None = None,
    np_rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """
    Generate a daily-aggregated history DataFrame.

    Returns columns:
        date, inbound_qty, outbound_qty, stock_level, notes
    """
    rng = rng or random.Random(SEED)
    np_rng = np_rng or np.random.default_rng(SEED)

    stock = float(initial_stock)
    rows: list[dict] = []

    current = start
    days_since_last_restock = 0

    while current <= end:
        seasonal   = _seasonal_multiplier(current)
        weekday    = _weekday_multiplier(current)
        holiday    = _is_major_holiday(current)

        # ── Outbound (demand) ──────────────────────────────────────
        if holiday:
            demand_factor = 0.05
        else:
            demand_factor = seasonal * weekday

        raw_demand = base_daily_outbound * demand_factor
        # Add Gaussian noise (±25 %)
        noise = np_rng.normal(loc=1.0, scale=0.25)
        raw_demand = max(0.0, raw_demand * noise)
        outbound = min(int(round(raw_demand)), int(stock))   # can't sell more than in stock

        # ── Inbound (replenishment) ────────────────────────────────
        inbound = 0
        days_since_last_restock += 1

        # Restock when stock falls below dynamic threshold OR at regular interval
        # Use a consumption-based batch size so stock stays realistic
        weekly_consumption = base_daily_outbound * seasonal * 5.5  # ~5.5 weighted days
        restock_threshold = weekly_consumption * 1.0  # keep ~1 week of cover
        max_desired_stock = weekly_consumption * 2.5   # cap so we don't over-order

        need_restock = (
            stock - outbound < restock_threshold
            or days_since_last_restock >= inbound_frequency_days + rng.randint(-1, 2)
        )

        if need_restock and not holiday and current.weekday() not in (6,):
            # Order only what brings stock to max_desired_stock
            shortfall = max_desired_stock - (stock - outbound)
            batch = max(inbound_batch_min, int(shortfall))
            batch = min(batch, inbound_batch_max)
            inbound = rng.randint(int(batch * 0.85), int(batch * 1.15))
            days_since_last_restock = 0

        stock = max(0.0, stock + inbound - outbound)

        # ── Notes ─────────────────────────────────────────────────
        note_parts = []
        if holiday:
            note_parts.append("public holiday")
        if inbound > 0:
            note_parts.append("restock delivery")
        if int(stock) == 0:
            note_parts.append("STOCKOUT")
        if seasonal >= 1.3 and outbound > 0:
            note_parts.append("seasonal peak")
        notes = "; ".join(note_parts) if note_parts else ""

        rows.append({
            "date":         str(current),
            "inbound_qty":  inbound,
            "outbound_qty": outbound,
            "stock_level":  int(round(stock)),
            "notes":        notes,
        })

        current += timedelta(days=1)

    return pd.DataFrame(rows)


def generate_granular_rows(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode daily rows into multiple per-day transaction rows to create
    a high-volume dataset (5000+ rows) for the inventory_transactions table.

    For each day the function creates:
      - 1 inbound transaction if inbound_qty > 0
      - 3–8 outbound transactions (partial shipments / sales orders)
      - Occasional return / adjustment rows

    Returns columns that match the /inventory/transactions API payload:
        date, reason, stock_adjusted, reference_no, notes
    """
    rng = random.Random(SEED + 1)
    tx_rows: list[dict] = []
    ref_counter = 10000

    for _, row in daily_df.iterrows():
        d = row["date"]
        inbound  = int(row["inbound_qty"])
        outbound = int(row["outbound_qty"])

        # Inbound transaction
        if inbound > 0:
            ref_counter += 1
            tx_rows.append({
                "date":          d,
                "reason":        rng.choice(["stock_in", "delivery"]),
                "stock_adjusted": inbound,
                "reference_no":  f"PO-{ref_counter:05d}",
                "notes":         rng.choice(["supplier delivery", "scheduled replenishment",
                                             "emergency restock", "bulk purchase"]),
            })

        # Split outbound into 4-10 separate orders / shipments (ensures 5000+ rows)
        remaining = outbound
        if remaining > 0:
            num_orders = rng.randint(4, min(10, max(4, remaining // 5 + 1)))
            # Generate proportional weights then assign integer qtys
            weights = [max(0.05, rng.random()) for _ in range(num_orders)]
            total_w = sum(weights)
            allocated = [max(1, round(remaining * w / total_w)) for w in weights]
            # Correct rounding drift on last element
            drift = remaining - sum(allocated[:-1])
            allocated[-1] = max(1, drift)
            for qty in allocated:
                if qty <= 0:
                    continue
                ref_counter += 1
                tx_rows.append({
                    "date":          d,
                    "reason":        rng.choice(["stock_out", "shipment", "stock_out", "stock_out"]),
                    "stock_adjusted": -qty,
                    "reference_no":  f"SO-{ref_counter:05d}",
                    "notes":         rng.choice([
                        "regular order", "wholesale order", "retail dispatch",
                        "online order", "express delivery", "B2B shipment",
                        "restaurant supply", "hotel supply", "supermarket order",
                    ]),
                })

        # ~8 % chance of a return
        if rng.random() < 0.08 and outbound > 0:
            return_qty = rng.randint(1, max(1, outbound // 6))
            ref_counter += 1
            tx_rows.append({
                "date":          d,
                "reason":        "return",
                "stock_adjusted": return_qty,
                "reference_no":  f"RET-{ref_counter:05d}",
                "notes":         rng.choice(["customer return", "damaged in transit",
                                             "wrong item", "quality issue", "over-delivery"]),
            })

        # ~6 % chance of a damage / adjustment write-off
        if rng.random() < 0.06:
            damage_qty = rng.randint(1, max(1, (inbound or 20) // 5))
            ref_counter += 1
            tx_rows.append({
                "date":          d,
                "reason":        rng.choice(["damage", "adjustment", "damage"]),
                "stock_adjusted":  -damage_qty,
                "reference_no":  f"ADJ-{ref_counter:05d}",
                "notes":         rng.choice(["spoilage", "quality rejection",
                                             "storage damage", "count correction",
                                             "expiry write-off", "cold chain failure"]),
            })

    return pd.DataFrame(tx_rows)


# ──────────────────────────────────────────────────────────────────────────────
# API bulk-insert helper (optional — calls your backend API)
# ──────────────────────────────────────────────────────────────────────────────

def post_transactions_via_api(
    tx_df: pd.DataFrame,
    product_id: int,
    api_base: str,
    token: str,
    batch_size: int = 50,
) -> None:
    """
    Insert granular transactions into the WMS backend via the API.
    Requires the `requests` package: pip install requests

    Args:
        tx_df:       Output DataFrame from generate_granular_rows()
        product_id:  Product ID in the WMS database
        api_base:    e.g. 'http://127.0.0.1:8000'
        token:       Bearer JWT token (login first)
        batch_size:  Rows per API call (keeps requests small)
    """
    try:
        import requests
    except ImportError:
        raise ImportError("pip install requests")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{api_base}/inventory/transactions"
    total = len(tx_df)
    success = 0
    errors = 0

    print(f"Posting {total} transactions to {url} ...")
    for i, (_, row) in enumerate(tx_df.iterrows()):
        payload = {
            "product_id":    product_id,
            "stock_adjusted": int(row["stock_adjusted"]),
            "reason":         row["reason"],
            "reference_no":   row["reference_no"],
            "transaction_at": f"{row['date']}T{random.randint(7,18):02d}:{random.randint(0,59):02d}:00",
        }
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code in (200, 201):
            success += 1
        else:
            errors += 1
            if errors <= 5:   # print first few errors
                print(f"  ✗ Row {i}: {resp.status_code} {resp.text[:120]}")

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{total} sent ({success} ok, {errors} errors)")

    print(f"\nDone. {success} inserted, {errors} failed.")


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="WMS fake inventory data generator")
    p.add_argument("--product-name", default="Alaskan Cod",   help="Product display name")
    p.add_argument("--sku-code",     default="SKU019",        help="SKU code")
    p.add_argument("--start",        default="2024-01-01",    help="Start date YYYY-MM-DD")
    p.add_argument("--end",          default="2026-04-02",    help="End date   YYYY-MM-DD")
    p.add_argument("--initial-stock",type=int, default=500,   help="Opening stock level")
    p.add_argument("--base-demand",  type=float, default=55.0,help="Average daily outbound units")
    p.add_argument("--out-dir",      default=str(Path.home() / "Downloads"), help="Output directory")
    # API upload flags
    p.add_argument("--upload",       action="store_true",     help="Also POST granular rows to API")
    p.add_argument("--product-id",   type=int, default=None,  help="Product ID for API upload")
    p.add_argument("--api-base",     default="http://127.0.0.1:8000")
    p.add_argument("--token",        default="",              help="Bearer JWT token")
    return p.parse_args()


def main():
    args = parse_args()

    start = date.fromisoformat(args.start)
    end   = date.fromisoformat(args.end)

    print(f"Generating data for {args.product_name} ({args.sku_code})")
    print(f"Date range : {start} → {end}  ({(end - start).days + 1} days)")
    print(f"Initial stock: {args.initial_stock} units")
    print()

    rng    = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)

    # 1. Daily-aggregated CSV (for ML service upload)
    daily_df = generate_daily_rows(
        start, end,
        initial_stock    = args.initial_stock,
        base_daily_outbound = args.base_demand,
        rng    = rng,
        np_rng = np_rng,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write with the comment header the ML service expects
    daily_path = out_dir / f"ml_history_{args.sku_code.lower()}_filled.csv"
    header_comment = (
        "# Historical Inventory Data Template\n"
        "# Fill in daily inbound (received) and outbound (shipped/sold) quantities.\n"
        "# date format: YYYY-MM-DD  |  quantities must be >= 0"
        "  |  stock_level and notes are optional\n"
        "# Delete these comment lines before uploading.\n"
        f"# Product: {args.product_name} ({args.sku_code})\n"
    )
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(header_comment)
        daily_df.to_csv(f, index=False)

    print(f"[1/2] Daily CSV  → {daily_path}  ({len(daily_df)} rows)")

    # Stats
    print(f"      Total inbound  : {daily_df['inbound_qty'].sum():,}")
    print(f"      Total outbound : {daily_df['outbound_qty'].sum():,}")
    print(f"      Min stock      : {daily_df['stock_level'].min()}")
    print(f"      Max stock      : {daily_df['stock_level'].max()}")
    print(f"      Stockout days  : {(daily_df['stock_level'] == 0).sum()}")
    print()

    # 2. Granular transactions CSV (for analytics / direct DB insert)
    tx_df = generate_granular_rows(daily_df)
    tx_path = out_dir / f"transactions_{args.sku_code.lower()}_granular.csv"
    tx_df.to_csv(tx_path, index=False)

    print(f"[2/2] Granular CSV → {tx_path}  ({len(tx_df):,} rows)")
    print(f"      Inbound rows   : {(tx_df['stock_adjusted'] > 0).sum():,}")
    print(f"      Outbound rows  : {(tx_df['stock_adjusted'] < 0).sum():,}")
    print()

    # 3. Optional: POST to API
    if args.upload:
        if not args.product_id or not args.token:
            print("ERROR: --product-id and --token are required for --upload")
        else:
            post_transactions_via_api(
                tx_df, args.product_id, args.api_base, args.token
            )

    print("Done!")
    print()
    print("Next steps:")
    print(f"  • Upload daily CSV to ML service:")
    print(f"    POST /products/{{product_id}}/forecast/upload")
    print(f"    (Use the file at {daily_path})")
    print(f"  • OR run with --upload --product-id <id> --token <jwt>")
    print(f"    to push {len(tx_df):,} granular transactions directly into the DB.")


if __name__ == "__main__":
    main()
