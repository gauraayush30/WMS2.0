"""
Feature engineering for the ML stock prediction model.

Builds a full feature matrix from a daily time-series DataFrame by combining:
  - Temporal features (day of week, month, quarter, …)
  - Indian holiday / festival features incl. ±7-day proximity window
  - Lag & rolling-window features (7d/30d averages, std)
  - Trend features (7-day linear slope)
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from indian_calendar import get_holiday_features_for_dates

# ── Feature column names (excluding lag/trend which need history) ────────────

TEMPORAL_FEATURES = [
    "day_of_week",
    "month",
    "day_of_month",
    "day_of_year",
    "week_of_year",
    "is_weekend",
    "quarter",
]

HOLIDAY_FEATURES = [
    "is_public_holiday",
    "is_major_festival",
    "is_any_holiday",
    "in_holiday_window",
    "holiday_window_direction",
    "holiday_window_intensity",
    "days_to_next_holiday",
    "days_since_last_holiday",
    "festival_season",
]

LAG_FEATURES = [
    "outbound_7d_avg",
    "outbound_30d_avg",
    "inbound_7d_avg",
    "outbound_7d_std",
]

TREND_FEATURES = [
    "outbound_trend_7d",
]

ALL_FEATURES = TEMPORAL_FEATURES + HOLIDAY_FEATURES + LAG_FEATURES + TREND_FEATURES

# Features that can be computed without historical lag data
# (used for future-date prediction where we don't have actuals yet)
PREDICTION_FEATURES = TEMPORAL_FEATURES + HOLIDAY_FEATURES


def _add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar-based features derived from the ``date`` column."""
    dt = pd.to_datetime(df["date"])
    df = df.copy()
    df["day_of_week"] = dt.dt.dayofweek
    df["month"] = dt.dt.month
    df["day_of_month"] = dt.dt.day
    df["day_of_year"] = dt.dt.dayofyear
    df["week_of_year"] = dt.dt.isocalendar().week.astype(int)
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["quarter"] = dt.dt.quarter
    return df


def _add_holiday_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge holiday/festival features (including the ±7 day proximity
    window) from the Indian calendar module.
    """
    dates_list = [d if isinstance(d, date) else d.date() for d in pd.to_datetime(df["date"])]
    hol_df = get_holiday_features_for_dates(dates_list)

    if hol_df.empty:
        for col in HOLIDAY_FEATURES:
            df[col] = 0
        return df

    # Align by position (both are sorted by date)
    hol_df = hol_df.reset_index(drop=True)
    df = df.reset_index(drop=True)

    for col in HOLIDAY_FEATURES:
        df[col] = hol_df[col].values

    return df


def _add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling-window lag features.  Requires ``outbound_qty`` and
    ``inbound_qty`` columns.  NaN rows at the start (before the window
    fills) will be forward-filled then back-filled.
    """
    df = df.copy()
    df["outbound_7d_avg"] = df["outbound_qty"].rolling(7, min_periods=1).mean()
    df["outbound_30d_avg"] = df["outbound_qty"].rolling(30, min_periods=1).mean()
    df["inbound_7d_avg"] = df["inbound_qty"].rolling(7, min_periods=1).mean()
    df["outbound_7d_std"] = df["outbound_qty"].rolling(7, min_periods=1).std().fillna(0)
    return df


def _add_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a 7-day linear slope feature for trend detection.
    Uses a rolling OLS-style calculation via numpy.
    """
    df = df.copy()
    window = 7
    slopes = []
    outbound = df["outbound_qty"].values

    for i in range(len(outbound)):
        if i < window - 1:
            # Not enough history – use 0
            slopes.append(0.0)
        else:
            segment = outbound[i - window + 1 : i + 1]
            x = np.arange(window, dtype=float)
            x_mean = x.mean()
            y_mean = segment.mean()
            denom = ((x - x_mean) ** 2).sum()
            if denom == 0:
                slopes.append(0.0)
            else:
                slope = ((x - x_mean) * (segment - y_mean)).sum() / denom
                slopes.append(round(float(slope), 4))

    df["outbound_trend_7d"] = slopes
    return df


# ── Public API ───────────────────────────────────────────────────────────────

def build_feature_matrix(daily_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Given a daily DataFrame with columns ``[date, inbound_qty, outbound_qty]``,
    return ``(X, y)`` where ``X`` is the feature matrix and ``y`` is the target
    (daily outbound quantity).

    Rows with insufficient lag history (first 7 days) are kept but use
    partial-window statistics so no data is discarded.
    """
    df = daily_df.copy().sort_values("date").reset_index(drop=True)

    df = _add_temporal_features(df)
    df = _add_holiday_features(df)
    df = _add_lag_features(df)
    df = _add_trend_features(df)

    X = df[ALL_FEATURES].astype(float)
    y = df["outbound_qty"].astype(float)

    return X, y


def build_prediction_features(future_dates: list[date], last_known_outbound: list[float] | None = None, last_known_inbound: list[float] | None = None) -> pd.DataFrame:
    """
    Build a feature matrix for future dates (where actual outbound/inbound
    are unknown).

    For lag features on future dates we use the ``last_known_*`` series
    (most recent actuals) to seed the rolling windows, then propagate
    predictions forward.

    If ``last_known_*`` is None, lag features are filled with 0.
    """
    df = pd.DataFrame({"date": future_dates})
    df = _add_temporal_features(df)
    df = _add_holiday_features(df)

    # Seed lag features from last known actuals
    if last_known_outbound and len(last_known_outbound) >= 7:
        avg_7 = float(np.mean(last_known_outbound[-7:]))
        avg_30 = float(np.mean(last_known_outbound[-30:])) if len(last_known_outbound) >= 30 else avg_7
        std_7 = float(np.std(last_known_outbound[-7:]))
        trend = _compute_slope(last_known_outbound[-7:])
    else:
        avg_7 = avg_30 = std_7 = trend = 0.0

    if last_known_inbound and len(last_known_inbound) >= 7:
        in_avg_7 = float(np.mean(last_known_inbound[-7:]))
    else:
        in_avg_7 = 0.0

    df["outbound_7d_avg"] = avg_7
    df["outbound_30d_avg"] = avg_30
    df["inbound_7d_avg"] = in_avg_7
    df["outbound_7d_std"] = std_7
    df["outbound_trend_7d"] = trend

    return df[ALL_FEATURES].astype(float)


def _compute_slope(values: list[float]) -> float:
    """Simple linear regression slope over a list of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)
    x_m, y_m = x.mean(), y.mean()
    denom = ((x - x_m) ** 2).sum()
    if denom == 0:
        return 0.0
    return float(((x - x_m) * (y - y_m)).sum() / denom)
