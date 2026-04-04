"""
Feature engineering for the ML stock prediction model.

Builds a full feature matrix from a daily time-series DataFrame by combining:
  - Temporal features (day of week, month, quarter, …)
  - Cyclical temporal features (sin/cos encodings for periodicity)
  - Indian holiday / festival features incl. ±7-day proximity window
  - Shifted lag features (actual lagged values: 1d, 2d, 3d, 7d, 14d)
  - Rolling-window statistics (3d, 7d, 14d, 30d, 60d averages, std, median, EWM)
  - Ratio / momentum features (short vs long-term averages)
  - Trend features (7d, 14d, 30d linear slopes)
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from indian_calendar import get_holiday_features_for_dates

# ── Feature column names ────────────────────────────────────────────────────

TEMPORAL_FEATURES = [
    "day_of_week",
    "month",
    "day_of_month",
    "day_of_year",
    "week_of_year",
    "is_weekend",
    "quarter",
]

CYCLICAL_FEATURES = [
    "sin_day_of_week",
    "cos_day_of_week",
    "sin_month",
    "cos_month",
    "sin_day_of_year",
    "cos_day_of_year",
    "sin_week_of_year",
    "cos_week_of_year",
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

SHIFTED_LAG_FEATURES = [
    "outbound_lag_1",
    "outbound_lag_2",
    "outbound_lag_3",
    "outbound_lag_7",
    "outbound_lag_14",
    "inbound_lag_1",
    "inbound_lag_7",
]

WEEKDAY_FEATURES = [
    "outbound_same_dow_4w_avg",
    "outbound_same_dow_4w_median",
]

ROLLING_FEATURES = [
    "outbound_3d_avg",
    "outbound_7d_avg",
    "outbound_14d_avg",
    "outbound_30d_avg",
    "outbound_7d_median",
    "outbound_7d_std",
    "outbound_30d_std",
    "outbound_7d_max",
    "outbound_7d_min",
    "outbound_ewm_7",
    "outbound_ewm_30",
    "inbound_7d_avg",
    "inbound_30d_avg",
]

RATIO_FEATURES = [
    "outbound_ratio_7_30",
    "net_flow_7d",
]

TREND_FEATURES = [
    "outbound_trend_7d",
    "outbound_trend_14d",
    "days_since_start",
]

ALL_FEATURES = (
    TEMPORAL_FEATURES
    + CYCLICAL_FEATURES
    + HOLIDAY_FEATURES
    + SHIFTED_LAG_FEATURES
    + WEEKDAY_FEATURES
    + ROLLING_FEATURES
    + RATIO_FEATURES
    + TREND_FEATURES
)

# Features computable without historical lag data (for future-date prediction)
PREDICTION_FEATURES = TEMPORAL_FEATURES + CYCLICAL_FEATURES + HOLIDAY_FEATURES

# Rows to drop from the start during training (insufficient lag history)
LAG_WARMUP_ROWS = 7


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
    dates_list = pd.to_datetime(df["date"]).dt.date.tolist()
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


def _add_cyclical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add sin/cos cyclical encodings so the model understands periodicity."""
    df = df.copy()
    df["sin_day_of_week"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["cos_day_of_week"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["sin_month"] = np.sin(2 * np.pi * (df["month"] - 1) / 12)
    df["cos_month"] = np.cos(2 * np.pi * (df["month"] - 1) / 12)
    df["sin_day_of_year"] = np.sin(2 * np.pi * df["day_of_year"] / 365.25)
    df["cos_day_of_year"] = np.cos(2 * np.pi * df["day_of_year"] / 365.25)
    df["sin_week_of_year"] = np.sin(2 * np.pi * df["week_of_year"] / 52)
    df["cos_week_of_year"] = np.cos(2 * np.pi * df["week_of_year"] / 52)
    return df


def _add_shifted_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add actual lagged values shifted by N days (no target leakage)."""
    df = df.copy()
    df["outbound_lag_1"] = df["outbound_qty"].shift(1)
    df["outbound_lag_2"] = df["outbound_qty"].shift(2)
    df["outbound_lag_3"] = df["outbound_qty"].shift(3)
    df["outbound_lag_7"] = df["outbound_qty"].shift(7)
    df["outbound_lag_14"] = df["outbound_qty"].shift(14)
    df["inbound_lag_1"] = df["inbound_qty"].shift(1)
    df["inbound_lag_7"] = df["inbound_qty"].shift(7)
    return df


def _add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling-window statistics using the natural rolling window.
    Uses min_periods matching partial window for early rows.
    """
    df = df.copy()
    out = df["outbound_qty"]
    inp = df["inbound_qty"]

    # Rolling averages at multiple horizons
    df["outbound_3d_avg"] = out.rolling(3, min_periods=1).mean()
    df["outbound_7d_avg"] = out.rolling(7, min_periods=1).mean()
    df["outbound_14d_avg"] = out.rolling(14, min_periods=1).mean()
    df["outbound_30d_avg"] = out.rolling(30, min_periods=1).mean()

    # Rolling median, std, min, max
    df["outbound_7d_median"] = out.rolling(7, min_periods=1).median()
    df["outbound_7d_std"] = out.rolling(7, min_periods=1).std().fillna(0)
    df["outbound_30d_std"] = out.rolling(30, min_periods=1).std().fillna(0)
    df["outbound_7d_max"] = out.rolling(7, min_periods=1).max()
    df["outbound_7d_min"] = out.rolling(7, min_periods=1).min()

    # Exponential weighted moving average (reacts faster to recent changes)
    df["outbound_ewm_7"] = out.ewm(span=7, min_periods=1).mean()
    df["outbound_ewm_30"] = out.ewm(span=30, min_periods=1).mean()

    # Inbound rolling
    df["inbound_7d_avg"] = inp.rolling(7, min_periods=1).mean()
    df["inbound_30d_avg"] = inp.rolling(30, min_periods=1).mean()

    return df


def _add_weekday_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add same-day-of-week historical averages.  Captures weekly seasonality
    e.g. Mondays are always high, Sundays always low.
    """
    df = df.copy()
    out = df["outbound_qty"].values
    dow = pd.to_datetime(df["date"]).dt.dayofweek.values

    avg_4w = np.zeros(len(df))
    med_4w = np.zeros(len(df))

    for i in range(len(df)):
        target_dow = dow[i]
        # Collect same-weekday values in the last 28 days (4 weeks)
        same_dow_vals = []
        for j in range(max(0, i - 28), i):
            if dow[j] == target_dow:
                same_dow_vals.append(out[j])
        if same_dow_vals:
            avg_4w[i] = float(np.mean(same_dow_vals))
            med_4w[i] = float(np.median(same_dow_vals))
        else:
            # Fallback to overall recent average
            recent = out[max(0, i - 7):i]
            avg_4w[i] = float(np.mean(recent)) if len(recent) > 0 else 0.0
            med_4w[i] = avg_4w[i]

    df["outbound_same_dow_4w_avg"] = avg_4w
    df["outbound_same_dow_4w_median"] = med_4w
    return df


def _add_ratio_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add momentum / ratio features that capture acceleration and net flow."""
    df = df.copy()
    out_30 = df["outbound_30d_avg"].replace(0, np.nan)
    df["outbound_ratio_7_30"] = (df["outbound_7d_avg"] / out_30).fillna(1.0)
    df["net_flow_7d"] = df["inbound_7d_avg"] - df["outbound_7d_avg"]
    return df


def _add_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add linear slope features at 7d and 14d windows,
    plus days_since_start for long-term trend capture.
    """
    df = df.copy()
    outbound = df["outbound_qty"].values

    for window, col in [
        (7, "outbound_trend_7d"),
        (14, "outbound_trend_14d"),
    ]:
        slopes: list[float] = []
        for i in range(len(outbound)):
            if i < window - 1:
                slopes.append(0.0)
            else:
                segment = outbound[i - window + 1 : i + 1]
                slopes.append(round(_compute_slope(segment), 4))
        df[col] = slopes

    dates = pd.to_datetime(df["date"])
    df["days_since_start"] = (dates - dates.min()).dt.days

    return df


# ── Public API ───────────────────────────────────────────────────────────────

def build_feature_matrix(daily_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Given a daily DataFrame with columns ``[date, inbound_qty, outbound_qty]``,
    return ``(X, y_outbound, y_inbound)`` where ``X`` is the feature matrix.

    Drops the first ``LAG_WARMUP_ROWS`` rows where lag features are
    unreliable (partial-window noise).
    """
    df = daily_df.copy().sort_values("date").reset_index(drop=True)

    df = _add_temporal_features(df)
    df = _add_cyclical_features(df)
    df = _add_holiday_features(df)
    df = _add_shifted_lag_features(df)
    df = _add_weekday_features(df)
    df = _add_rolling_features(df)
    df = _add_ratio_features(df)
    df = _add_trend_features(df)

    # Drop warmup rows (but never more than 25 % of the data)
    warmup = min(LAG_WARMUP_ROWS, len(df) // 4)
    df = df.iloc[warmup:].reset_index(drop=True)

    X = df[ALL_FEATURES].astype(float).fillna(0)
    y_outbound = df["outbound_qty"].astype(float)
    y_inbound = df["inbound_qty"].astype(float)

    return X, y_outbound, y_inbound


def build_prediction_features(
    target_date: date,
    outbound_history: list[float],
    inbound_history: list[float],
) -> pd.DataFrame:
    """
    Build a single-row feature matrix for one future date.

    Uses the same feature computation logic as training:
      - Lag features reference the history buffer (which may include prior
        predictions appended iteratively)
      - Rolling features computed over the history buffer
      - Weekday features match training's same-day-of-week lookback logic
      - days_since_start continues from history length (proxy for training length)

    Parameters
    ----------
    target_date : date
        The future date to predict for.
    outbound_history : list[float]
        Full outbound history up to (not including) target_date.
        May include prior predictions appended iteratively.
    inbound_history : list[float]
        Full inbound history up to (not including) target_date.
    """
    df = pd.DataFrame({"date": [target_date]})
    df = _add_temporal_features(df)
    df = _add_cyclical_features(df)
    df = _add_holiday_features(df)

    out = list(outbound_history) if outbound_history else []
    inp = list(inbound_history) if inbound_history else []

    # ── Helpers ──────────────────────────────────────────────────
    def _tail(arr: list, n: int) -> list:
        return arr[-n:] if len(arr) >= n else arr[:]

    def _mean(arr: list, n: int) -> float:
        s = _tail(arr, n)
        return float(np.mean(s)) if s else 0.0

    def _std(arr: list, n: int) -> float:
        s = _tail(arr, n)
        return float(np.std(s, ddof=1)) if len(s) > 1 else 0.0

    def _med(arr: list, n: int) -> float:
        s = _tail(arr, n)
        return float(np.median(s)) if s else 0.0

    def _safe(arr: list, idx: int) -> float:
        return float(arr[-idx]) if len(arr) >= idx else 0.0

    # ── Shifted lag features (match training's shift logic) ──────
    df["outbound_lag_1"] = _safe(out, 1)
    df["outbound_lag_2"] = _safe(out, 2)
    df["outbound_lag_3"] = _safe(out, 3)
    df["outbound_lag_7"] = _safe(out, 7)
    df["outbound_lag_14"] = _safe(out, 14)
    df["inbound_lag_1"] = _safe(inp, 1)
    df["inbound_lag_7"] = _safe(inp, 7)

    # ── Weekday features (same logic as training) ────────────────
    # Look back up to 28 days in history for same-day-of-week values,
    # matching _add_weekday_features() used during training.
    target_dow = target_date.weekday()
    same_dow_vals = []
    history_len = len(out)
    lookback = min(28, history_len)
    for j in range(history_len - lookback, history_len):
        days_back = history_len - j
        past_date = target_date - timedelta(days=days_back)
        if past_date.weekday() == target_dow:
            same_dow_vals.append(out[j])

    if same_dow_vals:
        df["outbound_same_dow_4w_avg"] = float(np.mean(same_dow_vals))
        df["outbound_same_dow_4w_median"] = float(np.median(same_dow_vals))
    else:
        recent_avg = _mean(out, 7)
        df["outbound_same_dow_4w_avg"] = recent_avg
        df["outbound_same_dow_4w_median"] = recent_avg

    # ── Rolling features (match training's rolling window logic) ─
    df["outbound_3d_avg"] = _mean(out, 3)
    df["outbound_7d_avg"] = _mean(out, 7)
    df["outbound_14d_avg"] = _mean(out, 14)
    df["outbound_30d_avg"] = _mean(out, 30)
    df["outbound_7d_median"] = _med(out, 7)
    df["outbound_7d_std"] = _std(out, 7)
    df["outbound_30d_std"] = _std(out, 30)
    df["outbound_7d_max"] = float(max(_tail(out, 7))) if out else 0.0
    df["outbound_7d_min"] = float(min(_tail(out, 7))) if out else 0.0

    if out:
        s = pd.Series(out)
        df["outbound_ewm_7"] = float(s.ewm(span=7, min_periods=1).mean().iloc[-1])
        df["outbound_ewm_30"] = float(s.ewm(span=30, min_periods=1).mean().iloc[-1])
    else:
        df["outbound_ewm_7"] = 0.0
        df["outbound_ewm_30"] = 0.0

    df["inbound_7d_avg"] = _mean(inp, 7)
    df["inbound_30d_avg"] = _mean(inp, 30)

    # ── Ratio features ───────────────────────────────────────────
    avg_7 = _mean(out, 7)
    avg_30 = _mean(out, 30)
    df["outbound_ratio_7_30"] = (avg_7 / avg_30) if avg_30 > 0 else 1.0
    df["net_flow_7d"] = _mean(inp, 7) - avg_7

    # ── Trend features ───────────────────────────────────────────
    df["outbound_trend_7d"] = _compute_slope(out[-7:]) if len(out) >= 7 else 0.0
    df["outbound_trend_14d"] = _compute_slope(out[-14:]) if len(out) >= 14 else 0.0
    # Continue from the end of training data so the model sees a
    # realistic position on the time axis, not "day 0".
    df["days_since_start"] = len(out)

    return df[ALL_FEATURES].astype(float)


def _compute_slope(values) -> float:
    """Simple linear regression slope over a list/array of values."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    x_m, y_m = x.mean(), values.mean()
    denom = ((x - x_m) ** 2).sum()
    if denom == 0:
        return 0.0
    return float(((x - x_m) * (values - y_m)).sum() / denom)
