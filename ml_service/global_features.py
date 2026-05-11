"""
Feature engineering for the global per-(customer, warehouse) demand model.

The global model is trained on panel data: one row per (date, product, buyer).
This module builds a feature matrix that combines:

  - Categorical IDs: product_id, buyer_id  (handled as pandas Categorical)
  - Temporal & calendar features (reuses indian_calendar from per-product module)
  - Per-(product, buyer) lag and rolling features
  - Per-product cross-buyer aggregate features (rolling 7d / 30d sum across buyers)

The single trained model can answer:
  - product-level demand    (sum across buyer_id slices)
  - buyer-level demand      (single buyer_id slice)
  - aggregate demand        (set buyer_id to a synthetic "ALL" category)
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from indian_calendar import get_holiday_features_for_dates


CATEGORICAL_FEATURES = ["product_id_cat", "buyer_id_cat"]

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
    # Per (product, buyer) lags
    "qty_lag_1", "qty_lag_7", "qty_lag_14", "qty_lag_30",
    # Per (product, buyer) rolling
    "qty_roll_7d", "qty_roll_14d", "qty_roll_30d",
    "qty_roll_7d_std",
    # Per product cross-buyer aggregates
    "product_roll_7d", "product_roll_30d",
    # Buyer-share over the recent window
    "buyer_share_30d",
    # Days since the buyer last ordered this product
    "days_since_last_order",
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
    # hol is indexed positionally; rebuild mapping by date
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
    buyer_series: pd.DataFrame,
) -> pd.DataFrame:
    """Expand a long-form (date, buyer_id, product_id, outbound_qty) frame
    into a contiguous panel: every (buyer, product, date) combination from
    each pair's first appearance through the global max date.

    Returns a DataFrame with columns: date, buyer_id, product_id, outbound_qty
    where missing days are filled with 0 outbound.
    """
    if buyer_series.empty:
        return buyer_series
    bs = buyer_series.copy()
    bs["date"] = pd.to_datetime(bs["date"]).dt.normalize()
    global_end = bs["date"].max()

    rows: list[pd.DataFrame] = []
    for (buyer, product), grp in bs.groupby(["buyer_id", "product_id"], sort=False):
        start = grp["date"].min()
        full = pd.date_range(start, global_end, freq="D")
        idx = pd.DataFrame({"date": full})
        idx["buyer_id"] = buyer
        idx["product_id"] = product
        merged = idx.merge(grp[["date", "outbound_qty"]], on="date", how="left")
        merged["outbound_qty"] = merged["outbound_qty"].fillna(0).astype(int)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True).sort_values(["date", "product_id", "buyer_id"]).reset_index(drop=True)


def add_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, share, and recency features to the panel."""
    if panel.empty:
        return panel
    df = panel.sort_values(["product_id", "buyer_id", "date"]).copy()

    # (product, buyer) lags & rollings
    grp = df.groupby(["product_id", "buyer_id"])["outbound_qty"]
    df["qty_lag_1"]  = grp.shift(1)
    df["qty_lag_7"]  = grp.shift(7)
    df["qty_lag_14"] = grp.shift(14)
    df["qty_lag_30"] = grp.shift(30)
    df["qty_roll_7d"]  = grp.shift(1).rolling(7,  min_periods=1).mean().reset_index(level=[0, 1], drop=True)
    df["qty_roll_14d"] = grp.shift(1).rolling(14, min_periods=1).mean().reset_index(level=[0, 1], drop=True)
    df["qty_roll_30d"] = grp.shift(1).rolling(30, min_periods=1).mean().reset_index(level=[0, 1], drop=True)
    df["qty_roll_7d_std"] = grp.shift(1).rolling(7, min_periods=1).std().reset_index(level=[0, 1], drop=True)

    # days since this (product, buyer) last had a non-zero order
    def _days_since(s: pd.Series) -> pd.Series:
        out = np.zeros(len(s), dtype=float)
        last = -1
        for i, v in enumerate(s.values):
            if last < 0:
                out[i] = i  # before any order
            else:
                out[i] = i - last
            if v > 0:
                last = i
        return pd.Series(out, index=s.index)
    df["days_since_last_order"] = grp.transform(_days_since)

    # Per-product cross-buyer rolling sums (use a date-level pivot for speed)
    prod_daily = df.groupby(["product_id", "date"])["outbound_qty"].sum().reset_index()
    prod_daily = prod_daily.sort_values(["product_id", "date"])
    pgrp = prod_daily.groupby("product_id")["outbound_qty"]
    prod_daily["product_roll_7d"]  = pgrp.shift(1).rolling(7,  min_periods=1).mean().reset_index(level=0, drop=True)
    prod_daily["product_roll_30d"] = pgrp.shift(1).rolling(30, min_periods=1).mean().reset_index(level=0, drop=True)
    df = df.merge(
        prod_daily[["product_id", "date", "product_roll_7d", "product_roll_30d"]],
        on=["product_id", "date"], how="left",
    )

    # Buyer share over a trailing 30-day window: this buyer's qty / product total
    df["buyer_share_30d"] = np.where(
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
    out["buyer_id_cat"] = out["buyer_id"].fillna(-1).astype(int).astype("category")
    return out[ALL_FEATURES]
