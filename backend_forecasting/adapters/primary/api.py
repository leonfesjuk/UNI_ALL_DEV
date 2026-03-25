"""HTTP layer for the promo forecasting service."""

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

import pandas as pd

from adapters.factory import create_ai_adapter, create_data_adapter
from config.category_types import resolve_category_id
from config.promo_types import PROMO_TYPE_NAMES
from config.settings import Settings
from core.usecases.forecast_promo import (
    ExternalContext,
    ForecastRequest,
    ProductForecastInput,
    build_summary,
    export_comparison_to_excel,
    forecast_for_group,
)

MAX_FORECAST_DAYS = 16

EXCEL_COL_RENAME = {
    "total_sales_with": "total_promo_sales_qty",
    "total_sales_baseline": "total_base_sales_qty",
    "diff_qty": "diff_sales_qty",
    "margin_with": "margin_promo_uah",
    "margin_baseline": "margin_base_uah",
    "diff_margin": "margin_diff_uah",
}


class ProductInput(BaseModel):
    product_id: int
    expected_price: float
    promo_type_id: Optional[int] = None
    promo_start: Optional[date] = None
    promo_end: Optional[date] = None


class PredictRequest(BaseModel):
    shop_id: str
    category_id: str
    forecast_days: int
    context_days: int = 730
    products: list[ProductInput]

    @field_validator("forecast_days")
    @classmethod
    def validate_forecast_days(cls, v: int) -> int:
        if v > MAX_FORECAST_DAYS:
            raise ValueError(
                f"forecast_days ({v}) exceeds max {MAX_FORECAST_DAYS}"
            )
        return v


router = APIRouter()


def _fmt_pid(pid: int) -> str:
    return f"{pid:08d}"


def _export_comparison_excel(
    merged: pd.DataFrame,
    cost_prices: pd.DataFrame,
    path: str,
) -> None:
    detail = merged.merge(cost_prices, on="product_id", how="left")
    detail["price_incoming"] = detail["price_incoming"].fillna(0.0)
    detail = detail.sort_values(["product_id", "date"])

    detail["margin_base_uah"] = (
        (detail["price_baseline"] - detail["price_incoming"])
        * detail["sales_qty_baseline"]
    )
    detail["margin_promo_uah"] = (
        (detail["price_with"] - detail["price_incoming"])
        * detail["sales_qty_with"]
    )
    detail = detail.rename(
        columns={
            "sales_qty_with": "forecast_promo_qty",
            "sales_qty_baseline": "forecast_base_qty",
            "price_with": "price_promo",
            "price_baseline": "price_base",
            "price_incoming": "cost_price_uah",
        }
    )

    summary = build_summary(merged, cost_prices).rename(
        columns=EXCEL_COL_RENAME
    )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        detail.to_excel(writer, sheet_name="Detail", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)


@router.post("/promo-forecast/predict")
async def predict(request: PredictRequest):
    settings = Settings.load()
    today = date.today()

    level, level_id = resolve_category_id(request.category_id)
    level_col = f"level_{level}_id" if isinstance(level, int) else level

    context_start = today - timedelta(days=request.context_days + 1)
    context_end = today - timedelta(days=1)

    shop_id_int = int(request.shop_id.split("-")[-1])
    gw = create_data_adapter(
        settings, context_start, context_end, shop_id=shop_id_int
    )
    ai = create_ai_adapter(settings)

    cost_prices = gw.product_cost_prices()
    history = gw.load_features(context_start, context_end)

    weather = gw.weather()
    holidays = gw.holidays()
    external = ExternalContext(weather=weather, holidays=holidays)

    promo_map = {
        _fmt_pid(p.product_id): p for p in request.products
    }
    all_pids = sorted(history["product_id"].unique().tolist())

    def _inputs(baseline: bool) -> list[ProductForecastInput]:
        result = []
        for pid in all_pids:
            p = promo_map.get(pid)
            if p and not baseline:
                result.append(
                    ProductForecastInput(
                        product_id=pid,
                        promo_type_id=p.promo_type_id or 0,
                        expected_price=p.expected_price,
                        promo_start=p.promo_start,
                        promo_end=p.promo_end,
                    )
                )
            else:
                result.append(ProductForecastInput(product_id=pid))
        return result

    fc_request = ForecastRequest(
        shop_id=request.shop_id,
        category_id=request.category_id,
        date_start=today,
        forecast_days=request.forecast_days,
        products=_inputs(baseline=False),
    )
    base_request = ForecastRequest(
        shop_id=request.shop_id,
        category_id=request.category_id,
        date_start=today,
        forecast_days=request.forecast_days,
        products=_inputs(baseline=True),
    )

    existing = gw.existing_promos(all_pids)

    fcast_with = forecast_for_group(
        fc_request,
        history=history,
        level_col=level_col,
        level_id=level_id,
        ai_adapter=ai,
        external=external,
        existing_promos=existing,
    )
    fcast_baseline = forecast_for_group(
        base_request,
        history=history,
        level_col=level_col,
        level_id=level_id,
        ai_adapter=ai,
        external=external,
        existing_promos=existing,
    )

    merged = fcast_with.merge(
        fcast_baseline,
        on=["product_id", "date"],
        suffixes=["_with", "_baseline"],
    )

    products_response = []
    for pid in merged["product_id"].unique():
        sub = merged[merged["product_id"] == pid]
        p = promo_map.get(pid)

        cp_row = cost_prices[cost_prices["product_id"] == pid]
        cost_price = (
            float(cp_row["price_incoming"].iloc[0]) if not cp_row.empty else 0.0
        )

        daily = []
        margin_base = 0.0
        margin_promo = 0.0
        for _, row in sub.iterrows():
            qty_with = int(row["sales_qty_with"])
            qty_base = int(row["sales_qty_baseline"])
            diff_qty = qty_with - qty_base
            diff_pct = round((diff_qty / qty_base * 100), 1) if qty_base else 0
            price_with = round(float(row.get("price_with", 0.0)), 2)
            price_base = round(float(row.get("price_baseline", 0.0)), 2)
            margin_base += (price_base - cost_price) * qty_base
            margin_promo += (price_with - cost_price) * qty_with

            daily.append(
                {
                    "date": str(row["date"]),
                    "forecast_promo_qty": qty_with,
                    "forecast_base_qty": qty_base,
                    "diff_percent": diff_pct,
                    "price_promo_uah": price_with,
                    "price_base_uah": price_base,
                }
            )

        total_promo = int(sub["sales_qty_with"].sum())
        total_base = int(sub["sales_qty_baseline"].sum())
        total_diff = total_promo - total_base
        total_diff_pct = (
            round((total_diff / total_base * 100), 1) if total_base else 0
        )
        promo_type_name = (
            PROMO_TYPE_NAMES.get(p.promo_type_id or 0, "") if p else ""
        )

        products_response.append(
            {
                "product_id": int(pid),
                "product_name": "",
                "cost_price_uah": round(cost_price, 2),
                "has_promo": pid in promo_map,
                "promo_type": promo_type_name,
                "daily": daily,
                "totals": {
                    "forecast_promo_qty": total_promo,
                    "forecast_base_qty": total_base,
                    "diff_qty": total_diff,
                    "diff_percent": total_diff_pct,
                    "margin_base_uah": round(margin_base, 2),
                    "margin_promo_uah": round(margin_promo, 2),
                    "margin_diff_uah": round(margin_promo - margin_base, 2),
                },
            }
        )

    today_str = today.isoformat()
    out_dir = f"data/forecast/{today_str}"
    base_name = f"forecast_cat{request.category_id}_{today_str}"
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    _export_comparison_excel(
        merged, cost_prices, f"{out_dir}/{base_name}.xlsx"
    )

    daily_export = merged.merge(cost_prices, on="product_id", how="left")
    daily_export["price_incoming"] = daily_export["price_incoming"].fillna(0.0)
    daily_export["margin_base_uah"] = (
        (daily_export["price_baseline"] - daily_export["price_incoming"])
        * daily_export["sales_qty_baseline"]
    )
    daily_export["margin_promo_uah"] = (
        (daily_export["price_with"] - daily_export["price_incoming"])
        * daily_export["sales_qty_with"]
    )
    daily_export["margin_diff_uah"] = (
        daily_export["margin_promo_uah"] - daily_export["margin_base_uah"]
    )
    daily_export["diff_sales_qty"] = (
        daily_export["sales_qty_with"] - daily_export["sales_qty_baseline"]
    )
    daily_export = daily_export.rename(
        columns={
            "sales_qty_with": "forecast_promo_qty",
            "sales_qty_baseline": "forecast_base_qty",
            "price_with": "price_promo",
            "price_baseline": "price_base",
            "price_incoming": "cost_price_uah",
        }
    )
    daily_export.to_parquet(
        f"{out_dir}/{base_name}_daily.parquet", index=False
    )

    return {
        "shop_id": request.shop_id,
        "category_id": request.category_id,
        "products": products_response,
    }
