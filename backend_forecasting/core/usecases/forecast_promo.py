"""Promo vs baseline scenario forecasting.

The use case is deliberately free of infrastructure imports: weather,
holidays, category mappings and AI adapters arrive as injected data
frames / ports from the caller (primary adapter).
"""

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from core.features import (
    last_non_promo_price,
    baseline_mean_predict,
    FEATURE_LEVEL_COLUMNS,
)
from core.ports.output import AIPort


@dataclass
class ProductForecastInput:
    product_id: int
    promo_type_id: int = 0
    expected_price: float = 1.0
    promo_start: date | None = None
    promo_end: date | None = None


@dataclass
class ForecastRequest:
    shop_id: str
    category_id: str
    date_start: date
    forecast_days: int
    products: list[ProductForecastInput]


@dataclass
class ExternalContext:
    """Pre-loaded external data injected by the caller."""

    weather: pd.DataFrame | None = None
    holidays: pd.DataFrame | None = None


WEATHER_COLUMNS = [
    "feels_id_morning",
    "feels_id_afternoon",
    "precip_id_morning",
    "precip_id_afternoon",
]

HOLIDAY_COLUMNS = ["is_holiday", "holiday_id"]


def _build_forecast_grid(
    request: ForecastRequest,
    level_col: str,
    level_id: int,
    history: pd.DataFrame,
) -> pd.DataFrame:
    forecast_end = request.date_start + timedelta(
        days=request.forecast_days - 1
    )
    forecast_dates = pd.date_range(
        request.date_start, forecast_end, freq="D"
    ).date

    product_ids = [p.product_id for p in request.products]
    last_prices = {pid: last_non_promo_price(history, pid) for pid in product_ids}

    rows = []
    for pid in product_ids:
        for d in forecast_dates:
            rows.append(
                {
                    "shop_id": request.shop_id,
                    "product_id": pid,
                    "date": d,
                    "sales_qty": 0.0,
                    "has_stock": True,
                    "day_of_week": d.weekday(),
                    "month": d.month,
                    "price": last_prices[pid],
                    "is_promo": False,
                    "promo_type_id": 0,
                }
            )

    grid = pd.DataFrame(rows)

    for col in FEATURE_LEVEL_COLUMNS:
        grid[col] = level_id if col == level_col else 0

    return grid


def _apply_user_promos(
    grid: pd.DataFrame,
    request: ForecastRequest,
) -> pd.DataFrame:
    prod_map = {p.product_id: p for p in request.products}
    for pid, product in prod_map.items():
        mask = grid["product_id"] == pid
        if product.promo_type_id <= 0:
            continue
        if product.promo_start and product.promo_end:
            promo_mask = (
                mask
                & (grid["date"] >= product.promo_start)
                & (grid["date"] <= product.promo_end)
            )
        else:
            promo_mask = mask
        grid.loc[promo_mask, "price"] = product.expected_price
        grid.loc[promo_mask, "is_promo"] = True
        grid.loc[promo_mask, "promo_type_id"] = product.promo_type_id
    return grid


def _attach_external(
    grid: pd.DataFrame,
    context: ExternalContext,
) -> pd.DataFrame:
    if context.weather is not None and not context.weather.empty:
        weather = context.weather.copy()
        for col in WEATHER_COLUMNS:
            if col in weather.columns:
                weather[col] = weather[col].astype(int)
        grid = grid.merge(weather, on="date", how="left")

    for col in WEATHER_COLUMNS:
        if col not in grid.columns:
            grid[col] = 0
        else:
            grid[col] = grid[col].fillna(0).astype(int)

    if context.holidays is not None and not context.holidays.empty:
        grid = grid.merge(context.holidays, on="date", how="left")

    for col in HOLIDAY_COLUMNS:
        if col not in grid.columns:
            grid[col] = 0 if col == "holiday_id" else False
        else:
            grid[col] = grid[col].fillna(0)
    grid["is_holiday"] = grid["is_holiday"].astype(bool)
    grid["holiday_id"] = grid["holiday_id"].astype(int)
    return grid


def _apply_existing_promos(
    grid: pd.DataFrame,
    request: ForecastRequest,
    existing_promos: pd.DataFrame | None,
) -> pd.DataFrame:
    if existing_promos is None or existing_promos.empty:
        return grid

    merged = grid.merge(existing_promos, on=["product_id", "date"], how="left")
    no_user_promo = merged["promo_type_id"] == 0
    has_existing = merged["existing_type_id"].notna()
    merged.loc[no_user_promo & has_existing, "promo_type_id"] = (
        merged.loc[no_user_promo & has_existing, "existing_type_id"].astype(int)
    )
    merged.loc[no_user_promo & has_existing, "is_promo"] = True
    return merged


def forecast_for_group(
    request: ForecastRequest,
    history: pd.DataFrame,
    level_col: str,
    level_id: int,
    ai_adapter: AIPort | None = None,
    external: ExternalContext | None = None,
    existing_promos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Forecast sales for a shop/category group.

    history      — feature dataframe for the same shop/category (past)
    level_col    — e.g. "group_id"; the hierarchy column being filtered
    level_id     — integer id of that hierarchy level
    external     — optional weather/holidays frames
    existing_promos — optional (product_id, date, existing_type_id) frame
    """
    external = external or ExternalContext()

    grid = _build_forecast_grid(request, level_col, level_id, history)
    grid = _apply_user_promos(grid, request)
    grid = _apply_existing_promos(grid, request, existing_promos)
    grid = _attach_external(grid, external)

    if ai_adapter is not None:
        return ai_adapter.predict(history, grid)
    return baseline_mean_predict(history, grid)


def build_summary(
    daily: pd.DataFrame,
    cost_prices: pd.DataFrame,
    shop_id: str = "",
    level_name: str = "",
    category_id: str = "",
) -> pd.DataFrame:
    """Aggregate daily comparison into per-product summary rows."""
    summary_rows = []
    for pid in daily["product_id"].unique():
        sub = daily[daily["product_id"] == pid]
        qty_with = int(sub["sales_qty_with"].sum())
        qty_base = int(sub["sales_qty_baseline"].sum())

        cp_row = cost_prices[cost_prices["product_id"] == pid]
        cost_price = (
            float(cp_row["price_incoming"].iloc[0]) if not cp_row.empty else 0.0
        )
        margin_with = round(
            (float(sub["price_with"].iloc[0]) - cost_price) * qty_with, 2
        )
        margin_baseline = round(
            (float(sub["price_baseline"].iloc[0]) - cost_price) * qty_base, 2
        )

        summary_rows.append(
            {
                "shop_id": shop_id,
                "level": level_name,
                "category_id": category_id,
                "product_id": pid,
                "total_sales_with": qty_with,
                "total_sales_baseline": qty_base,
                "diff_qty": qty_with - qty_base,
                "cost_price": round(cost_price, 2),
                "margin_with": margin_with,
                "margin_baseline": margin_baseline,
                "diff_margin": round(margin_with - margin_baseline, 2),
            }
        )
    return pd.DataFrame(summary_rows)


def export_comparison_to_excel(
    daily: pd.DataFrame,
    summary: pd.DataFrame,
    path: str,
) -> None:
    """Write daily + summary sheets to an Excel workbook."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        daily.to_excel(writer, sheet_name="Daily", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
