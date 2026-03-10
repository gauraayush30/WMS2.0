"""
CSV template generation and upload validation for historical data ingestion.
"""

from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd


REQUIRED_COLUMNS = {"date", "inbound_qty", "outbound_qty"}
OPTIONAL_COLUMNS = {"stock_level", "notes"}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

TEMPLATE_HEADER = (
    "# Historical Inventory Data Template\n"
    "# Fill in daily inbound (received) and outbound (shipped/sold) quantities.\n"
    "# date format: YYYY-MM-DD  |  quantities must be >= 0  |  stock_level and notes are optional\n"
    "# Delete these comment lines before uploading.\n"
)


def generate_csv_template(product_name: str, sku_code: str) -> bytes:
    """
    Return a CSV file (as bytes) with headers, instructions, and 2 example rows.
    """
    lines = [
        TEMPLATE_HEADER,
        f"# Product: {product_name} ({sku_code})\n",
        "date,inbound_qty,outbound_qty,stock_level,notes",
        "2025-01-01,100,0,500,Initial stock",
        "2025-01-02,0,25,475,Regular sales",
    ]
    return "\n".join(lines).encode("utf-8")


def parse_and_validate_csv(file_bytes: bytes) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse uploaded CSV bytes and validate contents.

    Returns:
        (clean_df, errors)
        - clean_df: validated DataFrame ready for DB insert (may be empty on errors)
        - errors: list of human-readable error strings (empty if valid)
    """
    errors: list[str] = []

    # ── Parse ────────────────────────────────────────────────────
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except Exception:
            return pd.DataFrame(), ["File encoding not supported. Use UTF-8."]

    # Strip comment lines
    clean_lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    if len(clean_lines) < 2:
        return pd.DataFrame(), ["CSV must contain a header row and at least one data row."]

    try:
        df = pd.read_csv(io.StringIO("\n".join(clean_lines)))
    except Exception as e:
        return pd.DataFrame(), [f"CSV parse error: {str(e)}"]

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # ── Check required columns ───────────────────────────────────
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        return pd.DataFrame(), [f"Missing required columns: {', '.join(sorted(missing))}"]

    # ── Validate date column ─────────────────────────────────────
    today = date.today()
    parsed_dates = []
    for i, val in enumerate(df["date"], start=2):  # row 2 = first data row
        try:
            dt = pd.to_datetime(val).date()
        except Exception:
            errors.append(f"Row {i}: invalid date '{val}'. Use YYYY-MM-DD format.")
            continue

        if dt > today:
            errors.append(f"Row {i}: date {dt} is in the future.")
            continue

        parsed_dates.append((i, dt))

    if errors:
        return pd.DataFrame(), errors

    df["date"] = [pd.to_datetime(v).date() for v in df["date"]]

    # ── Validate quantity columns ────────────────────────────────
    for col in ["inbound_qty", "outbound_qty"]:
        for i, val in enumerate(df[col], start=2):
            try:
                v = int(val)
            except (ValueError, TypeError):
                errors.append(f"Row {i}: '{col}' must be an integer, got '{val}'.")
                continue
            if v < 0:
                errors.append(f"Row {i}: '{col}' cannot be negative ({v}).")

    if errors:
        return pd.DataFrame(), errors

    df["inbound_qty"] = df["inbound_qty"].astype(int)
    df["outbound_qty"] = df["outbound_qty"].astype(int)

    # ── Optional columns ─────────────────────────────────────────
    if "stock_level" in df.columns:
        df["stock_level"] = pd.to_numeric(df["stock_level"], errors="coerce")
    else:
        df["stock_level"] = None

    if "notes" not in df.columns:
        df["notes"] = ""

    # ── Check for duplicate dates ────────────────────────────────
    dupes = df[df.duplicated(subset=["date"], keep=False)]
    if not dupes.empty:
        dupe_dates = sorted(set(str(d) for d in dupes["date"]))
        errors.append(f"Duplicate dates found: {', '.join(dupe_dates[:10])}")

    if errors:
        return pd.DataFrame(), errors

    # ── Sort and return ──────────────────────────────────────────
    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "inbound_qty", "outbound_qty", "stock_level", "notes"]], []
