"""
Feature engineering for the global per-(customer, warehouse) inbound model.

Parallel to global_features.py but for the inbound direction:
  - seller_id  instead of buyer_id
  - inbound_qty instead of outbound_qty

The panel is one row per (date, product, seller). All numeric feature names
are kept identical to the outbound module so the same training loop works
with a simple import swap.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from indian_calendar import get_holiday_features_for_dates


CATEGORICAL_FEATURES = ["product_id_cat", "seller_id_cat"]

NUMERIC_FEATURES = [
    # Temporal
    "day_of_week", "month", "day_of_month", "week_of_year",
    "is_weekend", "quarter",
    # Cyclical
    "sin_day_of_week", "cos_day_of_week", "sin_month", "cos_month",
    "sin_week_of_year", "cos_week_of_year",
    # Holidays
    "is_public_holiday", "is_major_festival", "is_any_holiday",
    "in_holiday_window", "days_to_next_holiday", "days_since_last_holiday",
    # Per (product, seller) lags
    "qty_lag_1", "qty_lag_7", "qty_lag_14", "qty_lag_30",
    # Per (product, seller) rolling
    "qty_roll_7d", "qty_roll_14d", "qty_roll_30d",
    "qty_roll_7d_std",
    # Per product cross-seller aggregates
    "product_roll_7d", "product_roll_30d",
    # Seller-share over the recent window
    "seller_share_30d",
    # Days since the seller last delivered this product
    "days_since_last_delivery",
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def _temporal(df: pd.DataFrame) -> pd.DataFrame:
    dt = pd.to_datetime(df["date"])
    df["day_of_week"] = dt.dt.dayofweek
    df["month"] = dt.dt.month
    df["day_of_month"] = dt.dt.day
    df["week_of_year"] = dt.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["quarter"] = dt.dt.quarter
    df["sin_day_of_week"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["cos_day_of_week"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["sin_month"] = np.sin(2 * np.pi * (df["month"] - 1) / 12)
    df["cos_month"] = np.cos(2 * np.pi * (df["month"] - 1) / 12)
    df["sin_week_of_year"] = np.sin(2 * np.pi * df["week_of_year"] / 52)
    df["cos_week_of_year"] = np.cos(2 * np.pi * df["week_of_year"] / 52)
    return df


def _holidays(df: pd.DataFrame) -> pd.DataFrame:
    """Add the subset of holiday features the global model uses."""
    unique_dates = sorted(set(pd.to_datetime(df["date"]).dt.date.tolist()))
    if not unique_dates:
        for c in ("is_public_holiday", "is_major_festival", "is_any_holiday",
                  "in_holiday_window", "days_to_next_holiday", "days_since_last_holiday"):
            df[c] = 0
        return df
    hol = get_holiday_features_for_dates(unique_dates)
    if hol.empty:
        for c in ("is_public_holiday", "is_major_festival", "is_any_holiday",
                  "in_holiday_window", "days_to_next_holiday", "days_since_last_holiday"):
            df[c] = 0
        return df
    hol = hol.reset_index(drop=True)
    hol["date"] = pd.to_datetime(unique_dates)
    keep = ["date", "is_public_holiday", "is_major_festival", "is_any_holiday",
            "in_holiday_window", "days_to_next_holiday", "days_since_last_holiday"]
    hol = hol[keep]
    df = df.merge(hol, on="date", how="left")
    for c in keep[1:]:
        df[c] = df[c].fillna(0)
    return df


def build_panel_dataframe(
    seller_series: pd.DataFrame,
) -> pd.DataFrame:
    """Expand a long-form (date, seller_id, product_id, inbound_qty) frame
    into a contiguous panel: every (seller, product, date) combination from
    each pair's first appearance through the global max date.

    Returns a DataFrame with columns: date, seller_id, product_id, inbound_qty
    where missing days are filled with 0 inbound.
    """
    if seller_series.empty:
        return seller_series
    ss = seller_series.copy()
    ss["date"] = pd.to_datetime(ss["date"]).dt.normalize()
    global_end = ss["date"].max()

    rows: list[pd.DataFrame] = []
    for (seller, product), grp in ss.groupby(["seller_id", "product_id"], sort=False):
        start = grp["date"].min()
        full = pd.date_range(start, global_end, freq="D")
        idx = pd.DataFrame({"date": full})
        idx["seller_id"] = seller
        idx["product_id"] = product
        merged = idx.merge(grp[["date", "inbound_qty"]], on="date", how="left")
        merged["inbound_qty"] = merged["inbound_qty"].fillna(0).astype(int)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True).sort_values(["date", "product_id", "seller_id"]).reset_index(drop=True)


def add_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, share, and recency features to the panel."""
    if panel.empty:
        return panel
    df = panel.sort_values(["product_id", "seller_id", "date"]).copy()

    # (product, seller) lags & rollings
    grp = df.groupby(["product_id", "seller_id"])["inbound_qty"]
    df["qty_lag_1"]  = grp.shift(1)
    df["qty_lag_7"]  = grp.shift(7)
    df["qty_lag_14"] = grp.shift(14)
    df["qty_lag_30"] = grp.shift(30)
    df["qty_roll_7d"]     = grp.transform(lambda s: s.shift(1).rolling(7,  min_periods=1).mean())
    df["qty_roll_14d"]    = grp.transform(lambda s: s.shift(1).rolling(14, min_periods=1).mean())
    df["qty_roll_30d"]    = grp.transform(lambda s: s.shift(1).rolling(30, min_periods=1).mean())
    df["qty_roll_7d_std"] = grp.transform(lambda s: s.shift(1).rolling(7,  min_periods=1).std())

    # days since this (product, seller) last had a non-zero delivery
    def _days_since(s: pd.Series) -> pd.Series:
        out = np.zeros(len(s), dtype=float)
        last = -1
        for i, v in enumerate(s.values):
            if last < 0:
                out[i] = i
            else:
                out[i] = i - last
            if v > 0:
                last = i
        return pd.Series(out, index=s.index)
    df["days_since_last_delivery"] = grp.transform(_days_since)

    # Per-product cross-seller rolling sums
    prod_daily = df.groupby(["product_id", "date"])["inbound_qty"].sum().reset_index()
    prod_daily = prod_daily.sort_values(["product_id", "date"])
    pgrp = prod_daily.groupby("product_id")["inbound_qty"]
    prod_daily["product_roll_7d"]  = pgrp.transform(lambda s: s.shift(1).rolling(7,  min_periods=1).mean())
    prod_daily["product_roll_30d"] = pgrp.transform(lambda s: s.shift(1).rolling(30, min_periods=1).mean())
    df = df.merge(
        prod_daily[["product_id", "date", "product_roll_7d", "product_roll_30d"]],
        on=["product_id", "date"], how="left",
    )

    # Seller share over a trailing 30-day window
    df["seller_share_30d"] = np.where(
        df["product_roll_30d"] > 0,
        df["qty_roll_30d"] / df["product_roll_30d"].replace(0, np.nan),
        0,
    )

    df = _temporal(df)
    df = _holidays(df)

    for c in NUMERIC_FEATURES:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return df


def to_model_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Convert ID columns to pandas Categoricals and return the feature subset."""
    out = df.copy()
    out["product_id_cat"] = out["product_id"].astype("category")
    out["seller_id_cat"] = out["seller_id"].fillna(-1).astype(int).astype("category")
    return out[ALL_FEATURES]
