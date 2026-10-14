import json
import os
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

LVIV_LAT = 49.84
LVIV_LON = 24.03
ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude={}&longitude={}"
    "&start_date={}&end_date={}"
    "&hourly=apparent_temperature,precipitation"
    "&timezone=Europe/Kyiv"
)
FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={}&longitude={}"
    "&start_date={}&end_date={}"
    "&hourly=apparent_temperature,precipitation"
    "&timezone=Europe/Kyiv"
)
MORNING_HOURS = list(range(8, 15))
AFTERNOON_HOURS = list(range(15, 22))
CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CACHE_DIR, "weather_cache.json")

FEELS_BINS = [-5.0, 7.0, 17.0, 28.0]
FEELS_IDS = [0, 1, 2, 3, 4]

PRECIP_THRESHOLD = 2.0


def _day_id() -> str:
    return date.today().isoformat()


def _parse_date(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


MAX_FORECAST_DAYS = 16


CHUNK_DAYS = 30

def _fetch_range_archive(start: date, end: date, retries: int = 3) -> dict:
    url = ARCHIVE_URL.format(LVIV_LAT, LVIV_LON, start.isoformat(), end.isoformat())
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            last_err = e
            if attempt < retries - 1:
                from time import sleep; sleep(3)
    raise RuntimeError(f"Failed to fetch archive weather {start}..{end} after {retries} retries: {last_err}") from last_err


def _fetch_range_forecast(start: date, end: date) -> dict:
    days = (end - start).days
    if days > MAX_FORECAST_DAYS:
        raise ValueError(
            f"Forecast range {days}d exceeds max {MAX_FORECAST_DAYS}d. "
            f"Requested {start}..{end} ({days}d)."
        )
    url = FORECAST_URL.format(LVIV_LAT, LVIV_LON, start.isoformat(), end.isoformat())
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f"Failed to fetch forecast weather {start}..{end}: {e}") from e


def _agg_morning(temps: list, precips: list) -> tuple:
    avg_temp = np.mean(temps)
    sum_precip = sum(precips)
    feels_id = int(np.digitize(avg_temp, FEELS_BINS))
    precip_id = 0 if sum_precip == 0 else (1 if sum_precip <= PRECIP_THRESHOLD else 2)
    return feels_id, precip_id


def _agg_afternoon(temps: list, precips: list) -> tuple:
    avg_temp = np.mean(temps)
    sum_precip = sum(precips)
    feels_id = int(np.digitize(avg_temp, FEELS_BINS))
    precip_id = 0 if sum_precip == 0 else (1 if sum_precip <= PRECIP_THRESHOLD else 2)
    return feels_id, precip_id


def _hourly_to_daily(raw: dict) -> list[dict]:
    times = raw["hourly"]["time"]
    feels = raw["hourly"]["apparent_temperature"]
    rain = raw["hourly"]["precipitation"]

    parsed = []
    for t_str, f_val, r_val in zip(times, feels, rain):
        dt_obj = datetime.fromisoformat(t_str)
        parsed.append((dt_obj, f_val if f_val is not None else 0.0, r_val if r_val is not None else 0.0))

    day_groups: dict[date, dict] = {}
    for dt_obj, f_val, r_val in parsed:
        d = dt_obj.date()
        if d not in day_groups:
            day_groups[d] = {"morning_t": [], "morning_p": [], "afternoon_t": [], "afternoon_p": []}
        if dt_obj.hour in MORNING_HOURS:
            day_groups[d]["morning_t"].append(f_val)
            day_groups[d]["morning_p"].append(r_val)
        elif dt_obj.hour in AFTERNOON_HOURS:
            day_groups[d]["afternoon_t"].append(f_val)
            day_groups[d]["afternoon_p"].append(r_val)

    result = []
    for d, slots in sorted(day_groups.items()):
        f_m, p_m = _agg_morning(slots["morning_t"], slots["morning_p"])
        f_a, p_a = _agg_afternoon(slots["afternoon_t"], slots["afternoon_p"])
        result.append({
            "date": d.isoformat(),
            "feels_id_morning": f_m,
            "feels_id_afternoon": f_a,
            "precip_id_morning": p_m,
            "precip_id_afternoon": p_a,
        })
    return result


def _cached_range() -> tuple[date | None, date | None]:
    if not os.path.exists(CACHE_FILE):
        return None, None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if not cache.get("data"):
            return None, None
        dates = [d["date"] for d in cache["data"]]
        return _parse_date(min(dates)), _parse_date(max(dates))
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return None, None


def _ensure_cache(date_from: date, date_to: date) -> None:
    cached_from, cached_to = _cached_range()

    if cached_from is not None and cached_to is not None:
        if cached_from <= date_from and cached_to >= date_to:
            return

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f).get("data", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        existing = []

    if cached_from is not None and cached_to is not None:
        fetch_start = min(date_from, cached_from)
        fetch_end = max(date_to, cached_to)
    else:
        fetch_start = date_from
        fetch_end = date_to

    today = date.today()

    def _merge_new(new_data: list[dict]) -> None:
        seen_dates = {r["date"] for r in existing}
        for record in new_data:
            if record["date"] not in seen_dates:
                existing.append(record)
                seen_dates.add(record["date"])

    # Archive part: fetch historical data in CHUNK_DAYS chunks
    if fetch_start <= today:
        archive_end = min(fetch_end, today)
        a_start = fetch_start
        while a_start <= archive_end:
            a_end = min(a_start + timedelta(days=CHUNK_DAYS - 1), archive_end)
            raw = _fetch_range_archive(a_start, a_end)
            _merge_new(_hourly_to_daily(raw))
            a_start = a_end + timedelta(days=1)

    # Forecast part: fetch future data in 16-day chunks
    if fetch_end > today:
        f_start = max(fetch_start, today + timedelta(days=1))
        while f_start <= fetch_end:
            chunk_end = min(f_start + timedelta(days=MAX_FORECAST_DAYS - 1), fetch_end)
            raw = _fetch_range_forecast(f_start, chunk_end)
            _merge_new(_hourly_to_daily(raw))
            f_start = chunk_end + timedelta(days=1)

    existing.sort(key=lambda r: r["date"])
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"data": existing}, f, ensure_ascii=False, indent=2)


def get_weather(date_from: date, date_to: date) -> pd.DataFrame:
    if date_from > date_to:
        raise ValueError(f"date_from ({date_from}) must be before date_to ({date_to})")

    _ensure_cache(date_from, date_to)

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        records = cache.get("data", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        records = []

    if not records:
        return pd.DataFrame(columns=["date", "feels_id_morning", "feels_id_afternoon", "precip_id_morning", "precip_id_afternoon"])

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    mask = (df["date"] >= date_from) & (df["date"] <= date_to)
    return df[mask].reset_index(drop=True)
