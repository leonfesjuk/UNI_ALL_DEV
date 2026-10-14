import json
import os
import urllib.request
import urllib.error
from datetime import date, datetime

import pandas as pd

from .holiday_types import HOLIDAY_NAMES

API_URL_TEMPLATE = "https://date.nager.at/api/v3/PublicHolidays/{}/UA"
EXCLUDED_TYPES = {"Bank", "School"}
MIN_YEAR = 2022
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config")
CACHE_FILE = os.path.join(CACHE_DIR, "ukraine_holidays.json")


def _fetch_year(year: int) -> list[dict]:
    url = API_URL_TEMPLATE.format(year)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to fetch holidays for {year}: {e}") from e

    filtered = [
        {"date": item["date"], "name": item["localName"]}
        for item in data
        if not EXCLUDED_TYPES.intersection(item.get("types", []))
    ]
    return filtered


def _cached_years() -> set[int]:
    if not os.path.exists(CACHE_FILE):
        return set()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return set(cache.get("cached_years", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _ensure_cache(start_year: int, end_year: int) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    needed = set(range(start_year, end_year + 1))
    existing = _cached_years()
    missing = needed - existing

    if not missing:
        return

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        all_holidays = cache.get("data", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        all_holidays = []

    for year in sorted(missing):
        all_holidays.extend(_fetch_year(year))

    seen = set()
    deduped = []
    for h in all_holidays:
        key = (h["date"], h["name"])
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    updated_years = existing | missing
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"cached_years": sorted(updated_years), "data": deduped}, f, ensure_ascii=False, indent=2)


def _load_cache() -> pd.DataFrame:
    if not os.path.exists(CACHE_FILE):
        return pd.DataFrame(columns=["date", "name"])
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return pd.DataFrame(cache.get("data", []))
    except (json.JSONDecodeError, OSError):
        return pd.DataFrame(columns=["date", "name"])


def get_holidays(date_from: date, date_to: date) -> pd.DataFrame:
    if date_from > date_to:
        raise ValueError(f"date_from ({date_from}) must be before date_to ({date_to})")

    today = date.today()
    start_year = min(MIN_YEAR, date_from.year)
    end_year = max(date_to.year, today.year + 1)

    _ensure_cache(start_year, end_year)

    holidays_df = _load_cache()
    if holidays_df.empty:
        return pd.DataFrame(columns=["date", "is_holiday", "holiday_id"])

    holidays_df["holiday_id"] = holidays_df["name"].map(HOLIDAY_NAMES).fillna(0).astype(int)
    holidays_df["date"] = pd.to_datetime(holidays_df["date"]).dt.date

    all_dates = pd.DataFrame(
        {"date": pd.date_range(date_from, date_to, freq="D").date}
    )
    merged = all_dates.merge(
        holidays_df[["date", "holiday_id"]],
        on="date",
        how="left",
    )
    merged["holiday_id"] = merged["holiday_id"].fillna(0).astype(int)
    merged["is_holiday"] = merged["holiday_id"] > 0
    return merged[["date", "is_holiday", "holiday_id"]]
