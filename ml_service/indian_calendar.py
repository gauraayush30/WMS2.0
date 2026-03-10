"""
Indian holiday & festival calendar for ML feature engineering.

Provides gazetted holidays via the `holidays` library and manually defined
lunar-calendar festivals (approximate Gregorian dates) for 2020-2030.
"""

from datetime import date, timedelta
from typing import Optional

import holidays
import pandas as pd

# ── Gazetted / fixed holidays via library ────────────────────────────────────

_india_holidays_cache: dict[int, holidays.India] = {}


def _get_india_holidays(year: int) -> holidays.India:
    if year not in _india_holidays_cache:
        _india_holidays_cache[year] = holidays.India(years=year)
    return _india_holidays_cache[year]


# ── Major Indian festivals (lunar-calendar, approximate Gregorian dates) ─────
# These shift every year.  Dates sourced from drikpanchang / timeanddate.

FESTIVALS: dict[str, dict[int, list[tuple[int, int]]]] = {
    # festival_name -> { year -> [(month, day), ...] }
    "Diwali": {
        2020: [(11, 14)], 2021: [(11, 4)], 2022: [(10, 24)], 2023: [(11, 12)],
        2024: [(11, 1)], 2025: [(10, 20)], 2026: [(11, 8)], 2027: [(10, 29)],
        2028: [(10, 17)], 2029: [(11, 5)], 2030: [(10, 26)],
    },
    "Holi": {
        2020: [(3, 10)], 2021: [(3, 29)], 2022: [(3, 18)], 2023: [(3, 8)],
        2024: [(3, 25)], 2025: [(3, 14)], 2026: [(3, 4)], 2027: [(3, 22)],
        2028: [(3, 11)], 2029: [(3, 1)], 2030: [(3, 20)],
    },
    "Navratri": {
        2020: [(10, 17)], 2021: [(10, 7)], 2022: [(9, 26)], 2023: [(10, 15)],
        2024: [(10, 3)], 2025: [(9, 22)], 2026: [(10, 11)], 2027: [(10, 1)],
        2028: [(9, 20)], 2029: [(10, 9)], 2030: [(9, 28)],
    },
    "Durga Puja": {
        2020: [(10, 22)], 2021: [(10, 11)], 2022: [(10, 1)], 2023: [(10, 20)],
        2024: [(10, 9)], 2025: [(9, 29)], 2026: [(10, 18)], 2027: [(10, 7)],
        2028: [(9, 25)], 2029: [(10, 14)], 2030: [(10, 4)],
    },
    "Ganesh Chaturthi": {
        2020: [(8, 22)], 2021: [(9, 10)], 2022: [(8, 31)], 2023: [(9, 19)],
        2024: [(9, 7)], 2025: [(8, 27)], 2026: [(9, 15)], 2027: [(9, 4)],
        2028: [(8, 24)], 2029: [(9, 12)], 2030: [(9, 2)],
    },
    "Eid ul-Fitr": {
        2020: [(5, 25)], 2021: [(5, 14)], 2022: [(5, 3)], 2023: [(4, 22)],
        2024: [(4, 11)], 2025: [(3, 31)], 2026: [(3, 20)], 2027: [(3, 10)],
        2028: [(2, 27)], 2029: [(2, 15)], 2030: [(2, 5)],
    },
    "Eid ul-Adha": {
        2020: [(8, 1)], 2021: [(7, 21)], 2022: [(7, 10)], 2023: [(6, 29)],
        2024: [(6, 17)], 2025: [(6, 7)], 2026: [(5, 27)], 2027: [(5, 17)],
        2028: [(5, 5)], 2029: [(4, 24)], 2030: [(4, 14)],
    },
    "Pongal": {
        2020: [(1, 15)], 2021: [(1, 15)], 2022: [(1, 15)], 2023: [(1, 15)],
        2024: [(1, 15)], 2025: [(1, 15)], 2026: [(1, 15)], 2027: [(1, 15)],
        2028: [(1, 15)], 2029: [(1, 15)], 2030: [(1, 15)],
    },
    "Onam": {
        2020: [(8, 31)], 2021: [(8, 21)], 2022: [(9, 8)], 2023: [(8, 29)],
        2024: [(9, 15)], 2025: [(9, 5)], 2026: [(8, 25)], 2027: [(9, 13)],
        2028: [(9, 2)], 2029: [(8, 23)], 2030: [(9, 10)],
    },
    "Baisakhi": {
        2020: [(4, 13)], 2021: [(4, 14)], 2022: [(4, 14)], 2023: [(4, 14)],
        2024: [(4, 13)], 2025: [(4, 14)], 2026: [(4, 14)], 2027: [(4, 14)],
        2028: [(4, 13)], 2029: [(4, 14)], 2030: [(4, 14)],
    },
    "Raksha Bandhan": {
        2020: [(8, 3)], 2021: [(8, 22)], 2022: [(8, 11)], 2023: [(8, 30)],
        2024: [(8, 19)], 2025: [(8, 9)], 2026: [(8, 28)], 2027: [(8, 17)],
        2028: [(8, 6)], 2029: [(8, 25)], 2030: [(8, 14)],
    },
    "Janmashtami": {
        2020: [(8, 11)], 2021: [(8, 30)], 2022: [(8, 19)], 2023: [(9, 6)],
        2024: [(8, 26)], 2025: [(8, 16)], 2026: [(9, 4)], 2027: [(8, 25)],
        2028: [(8, 13)], 2029: [(9, 1)], 2030: [(8, 21)],
    },
    "Chhath Puja": {
        2020: [(11, 20)], 2021: [(11, 10)], 2022: [(10, 30)], 2023: [(11, 19)],
        2024: [(11, 7)], 2025: [(10, 27)], 2026: [(11, 15)], 2027: [(11, 4)],
        2028: [(10, 24)], 2029: [(11, 12)], 2030: [(11, 2)],
    },
    "Lohri": {
        2020: [(1, 13)], 2021: [(1, 13)], 2022: [(1, 13)], 2023: [(1, 13)],
        2024: [(1, 13)], 2025: [(1, 13)], 2026: [(1, 13)], 2027: [(1, 13)],
        2028: [(1, 13)], 2029: [(1, 13)], 2030: [(1, 13)],
    },
    "Makar Sankranti": {
        2020: [(1, 14)], 2021: [(1, 14)], 2022: [(1, 14)], 2023: [(1, 14)],
        2024: [(1, 15)], 2025: [(1, 14)], 2026: [(1, 14)], 2027: [(1, 14)],
        2028: [(1, 15)], 2029: [(1, 14)], 2030: [(1, 14)],
    },
}

# Pre-built lookup: date -> list of festival names
_festival_lookup: dict[date, list[str]] = {}


def _build_festival_lookup() -> None:
    """Populate the module-level festival date lookup (lazy, called once)."""
    if _festival_lookup:
        return
    for name, year_map in FESTIVALS.items():
        for year, dates in year_map.items():
            for m, d in dates:
                dt = date(year, m, d)
                _festival_lookup.setdefault(dt, []).append(name)


def is_gazetted_holiday(dt: date) -> bool:
    cal = _get_india_holidays(dt.year)
    return dt in cal


def get_gazetted_holiday_name(dt: date) -> Optional[str]:
    cal = _get_india_holidays(dt.year)
    return cal.get(dt)


def is_festival(dt: date) -> bool:
    _build_festival_lookup()
    return dt in _festival_lookup


def get_festival_names(dt: date) -> list[str]:
    _build_festival_lookup()
    return _festival_lookup.get(dt, [])


def is_any_holiday(dt: date) -> bool:
    return is_gazetted_holiday(dt) or is_festival(dt)


def get_all_holiday_name(dt: date) -> Optional[str]:
    """Return the holiday/festival name for a date, or None."""
    name = get_gazetted_holiday_name(dt)
    if name:
        return name
    festivals = get_festival_names(dt)
    return festivals[0] if festivals else None


# ── Holiday proximity helpers (±7 day window) ────────────────────────────────

HOLIDAY_WINDOW_DAYS = 7


def _collect_holiday_dates_for_range(start: date, end: date) -> set[date]:
    """Return all holiday/festival dates in [start - window, end + window]."""
    _build_festival_lookup()
    padded_start = start - timedelta(days=HOLIDAY_WINDOW_DAYS)
    padded_end = end + timedelta(days=HOLIDAY_WINDOW_DAYS)

    result: set[date] = set()

    # Gazetted holidays
    for year in range(padded_start.year, padded_end.year + 1):
        cal = _get_india_holidays(year)
        for dt in cal.keys():
            if padded_start <= dt <= padded_end:
                result.add(dt)

    # Lunar-calendar festivals
    for dt in _festival_lookup:
        if padded_start <= dt <= padded_end:
            result.add(dt)

    return result


def get_holiday_features_for_dates(dates: list[date]) -> pd.DataFrame:
    """
    Build a DataFrame with holiday/festival features for a list of dates.

    Columns returned:
        is_public_holiday   – 1 if gazetted holiday
        is_major_festival   – 1 if major festival (from FESTIVALS dict)
        is_any_holiday      – 1 if either of the above
        holiday_name        – name string or empty
        in_holiday_window   – 1 if within ±7 days of any holiday/festival
        holiday_window_direction – -1 pre-holiday, 0 on-holiday, +1 post-holiday
        holiday_window_intensity – 1.0 on holiday, linearly decays to 0 at ±7 days
        days_to_next_holiday
        days_since_last_holiday
        festival_season     – 1 if in a major festival season window
    """
    if not dates:
        return pd.DataFrame()

    start, end = min(dates), max(dates)
    all_holidays = sorted(_collect_holiday_dates_for_range(start, end))

    rows = []
    for dt in dates:
        pub = is_gazetted_holiday(dt)
        fest = is_festival(dt)
        any_h = pub or fest
        name = get_all_holiday_name(dt) or ""

        # ── Days to next / since last holiday ────────────────────────
        days_to_next = 365
        days_since_last = 365
        for h in all_holidays:
            delta = (h - dt).days
            if delta >= 0:
                days_to_next = min(days_to_next, delta)
            if delta <= 0:
                days_since_last = min(days_since_last, abs(delta))

        # ── ±7 day proximity window ──────────────────────────────────
        in_window = 0
        window_direction = 0
        window_intensity = 0.0

        closest_dist = None
        closest_delta = None
        for h in all_holidays:
            delta = (h - dt).days  # positive = holiday is in the future
            dist = abs(delta)
            if dist <= HOLIDAY_WINDOW_DAYS:
                if closest_dist is None or dist < closest_dist:
                    closest_dist = dist
                    closest_delta = delta

        if closest_dist is not None:
            in_window = 1
            if closest_delta > 0:
                window_direction = -1  # pre-holiday (holiday ahead)
            elif closest_delta < 0:
                window_direction = 1   # post-holiday (holiday behind)
            else:
                window_direction = 0   # on the holiday
            window_intensity = round(1.0 - (closest_dist / HOLIDAY_WINDOW_DAYS), 4)

        # ── Festival season (broad multi-week windows) ───────────────
        month = dt.month
        festival_season = 1 if month in (10, 11) or (month == 3) else 0

        rows.append({
            "is_public_holiday": int(pub),
            "is_major_festival": int(fest),
            "is_any_holiday": int(any_h),
            "holiday_name": name,
            "in_holiday_window": in_window,
            "holiday_window_direction": window_direction,
            "holiday_window_intensity": window_intensity,
            "days_to_next_holiday": days_to_next,
            "days_since_last_holiday": days_since_last,
            "festival_season": festival_season,
        })

    return pd.DataFrame(rows, index=dates)
