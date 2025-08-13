from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

import numpy as np
import pandas as pd

from config.promo_types import PROMO_TYPE_NAMES
from config.settings import Settings
from adapters.factory import create_ai_adapter, create_data_adapter
from core.ports.output import AIPort
from core.usecases.forecast_promo import (
    ForecastRequest,
    ProductForecastInput,
    forecast_for_group,
)


EXCEL_COL_RENAME = {
    "total_base": "total_base_sales_qty",
    "total_promo": "total_promo_sales_qty",
    "diff_qty": "diff_sales_qty",
    "diff_%": "diff_percent",
    "margin_base": "margin_base_uah",
    "margin_promo": "margin_promo_uah",
    "margin_diff": "margin_diff_uah",
}


class ProductInput(BaseModel):
    product_id: int
    expected_price: float
    promo_type_id: Optional[int] = None
    promo_start: Optional[date] = None
    promo_end: Optional[date] = None


MAX_FORECAST_DAYS = 16


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
    merged = merged.merge(cost_prices, on="product_id", how="left")
    merged["price_incoming"] = merged["price_incoming"].fillna(0.0)
    merged = merged.sort_values(["product_id", "date"])
    dates = sorted(merged["date"].unique())

    detail_rows = []
    for pid in merged["product_id"].unique():
        sub = merged[merged["product_id"] == pid]
        pid_int = int(pid) if isinstance(pid, str) else pid
        total_base = int(sub["sales_qty_baseline"].sum())
        total_promo = int(sub["sales_qty_with"].sum())
        diff_qty = total_promo - total_base
        diff_pct = round((diff_qty / total_base * 100), 1) if total_base else 0

        cost_price = float(sub["price_incoming"].iloc[0]) if not sub["price_incoming"].isna().all() else 0.0

        margin_base = 0.0
        margin_promo = 0.0
        for _, dr in sub.iterrows():
            p_base = float(dr["price_baseline"])
            p_promo = float(dr["price_with"])
            margin_base += (p_base - cost_price) * int(dr["sales_qty_baseline"])
            margin_promo += (p_promo - cost_price) * int(dr["sales_qty_with"])

        row = {
            "product_id": pid_int,
            "total_base": total_base,
            "total_promo": total_promo,
            "diff_qty": diff_qty,
            "diff_%": diff_pct,
            "margin_base": round(margin_base, 2),
            "margin_promo": round(margin_promo, 2),
            "margin_diff": round(margin_promo - margin_base, 2),
        }
        for d in dates:
            day_data = sub[sub["date"] == d]
            row[f"{d}_base"] = int(day_data["sales_qty_baseline"].iloc[0]) if not day_data.empty else 0
        for d in dates:
            day_data = sub[sub["date"] == d]
            row[f"{d}_promo"] = int(day_data["sales_qty_with"].iloc[0]) if not day_data.empty else 0

        detail_rows.append(row)

    detail_df = pd.DataFrame(detail_rows)
    detail_df = detail_df.sort_values("diff_%", ascending=False).reset_index(drop=True)

    cat_row = {"product_id": "CATEGORY", "total_base": int(detail_df["total_base"].sum())}
    cat_row["total_promo"] = int(detail_df["total_promo"].sum())
    cat_row["diff_qty"] = cat_row["total_promo"] - cat_row["total_base"]
    cat_row["diff_%"] = round((cat_row["diff_qty"] / cat_row["total_base"] * 100), 1) if cat_row["total_base"] else 0
    cat_row["margin_base"] = round(detail_df["margin_base"].sum(), 2)
    cat_row["margin_promo"] = round(detail_df["margin_promo"].sum(), 2)
    cat_row["margin_diff"] = round(detail_df["margin_diff"].sum(), 2)
    for d in dates:
        cat_row[f"{d}_base"] = int(detail_df[f"{d}_base"].sum())
        cat_row[f"{d}_promo"] = int(detail_df[f"{d}_promo"].sum())
    cat_df = pd.DataFrame([cat_row])

    col_order = ["product_id", "total_base", "total_promo", "diff_qty", "diff_%",
                 "margin_base", "margin_promo", "margin_diff"]
    for d in dates:
        col_order.append(f"{d}_base")
    for d in dates:
        col_order.append(f"{d}_promo")

    detail_df = detail_df[col_order].rename(columns=EXCEL_COL_RENAME)
    cat_df = cat_df[col_order].rename(columns=EXCEL_COL_RENAME)
    col_rename_daily = {}
    for d in dates:
        col_rename_daily[f"{d}_base"] = f"{d}_base_qty"
        col_rename_daily[f"{d}_promo"] = f"{d}_promo_qty"
    detail_df = detail_df.rename(columns=col_rename_daily)
    cat_df = cat_df.rename(columns=col_rename_daily)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="Детально", index=False)
        cat_df.to_excel(writer, sheet_name="Підсумок", index=False)


@router.post("/promo-forecast/predict")
async def predict(request: PredictRequest):
    settings = Settings.load()
    today = date.today()

    shop_id_int = int(request.shop_id.split("-")[-1])
    gw = create_data_adapter(settings, today - timedelta(days=request.context_days + 1),
                              today - timedelta(days=1), shop_id=shop_id_int)
    ai = create_ai_adapter(settings)

    cost_prices = gw.product_cost_prices()

    context = gw.load_features(
        today - timedelta(days=request.context_days + 1),
        today - timedelta(days=1),
    )
    context = context[context["shop_id"] == request.shop_id]
    all_pids = sorted(context["product_id"].unique().tolist())

    promo_map = {_fmt_pid(p.product_id): p for p in request.products}

    products_with = []
    products_baseline = []
    for pid in all_pids:
        p = promo_map.get(pid)
        if p:
            products_with.append(ProductForecastInput(
                product_id=pid,
                promo_type_id=p.promo_type_id or 0,
                expected_price=p.expected_price,
                promo_start=p.promo_start,
                promo_end=p.promo_end,
            ))
        else:
            products_with.append(ProductForecastInput(product_id=pid))
        products_baseline.append(ProductForecastInput(product_id=pid))

    req_with = ForecastRequest(
        shop_id=request.shop_id,
        category_id=request.category_id,
        date_start=today,
        date_end=request.forecast_days,
        products=products_with,
    )

    req_baseline = ForecastRequest(
        shop_id=request.shop_id,
        category_id=request.category_id,
        date_start=today,
        date_end=request.forecast_days,
        products=products_baseline,
    )

    fcast_with = forecast_for_group(req_with, gateway=gw, ai_adapter=ai, context_days=request.context_days)
    fcast_baseline = forecast_for_group(req_baseline, gateway=gw, ai_adapter=ai, context_days=request.context_days)

    merged = fcast_with.merge(
        fcast_baseline,
        on=["product_id", "date"],
        suffixes=["_with", "_baseline"],
    )

    products_response = []
    for pid in merged["product_id"].unique():
        sub = merged[merged["product_id"] == pid]
        p = promo_map.get(pid)
        prod_input = p if p else ProductInput(product_id=int(pid), expected_price=0.0)

        cp_row = cost_prices[cost_prices["product_id"] == pid]
        cost_price = float(cp_row["price_incoming"].iloc[0]) if not cp_row.empty else 0.0

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

            daily.append({
                "date": str(row["date"]),
                "forecast_promo_qty": qty_with,
                "forecast_base_qty": qty_base,
                "diff_percent": diff_pct,
                "price_promo_uah": price_with,
                "price_base_uah": price_base,
            })

        total_promo = int(sub["sales_qty_with"].sum())
        total_base = int(sub["sales_qty_baseline"].sum())
        total_diff_qty = total_promo - total_base
        total_diff_pct = round((total_diff_qty / total_base * 100), 1) if total_base else 0

        promo_type_name = PROMO_TYPE_NAMES.get(prod_input.promo_type_id or 0, "")

        products_response.append({
            "product_id": int(pid),
            "product_name": "",
            "cost_price_uah": round(cost_price, 2),
            "has_promo": pid in promo_map,
            "promo_type": promo_type_name,
            "daily": daily,
            "totals": {
                "forecast_promo_qty": total_promo,
                "forecast_base_qty": total_base,
                "diff_qty": total_diff_qty,
                "diff_percent": total_diff_pct,
                "margin_base_uah": round(margin_base, 2),
                "margin_promo_uah": round(margin_promo, 2),
                "margin_diff_uah": round(margin_promo - margin_base, 2),
            },
        })

    today_str = today.isoformat()
    base_name = f"forecast_cat{request.category_id}_{today_str}"
    out_dir = f"data/forecast/{today_str}"
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    excel_path = f"{out_dir}/{base_name}.xlsx"
    _export_comparison_excel(merged, cost_prices, excel_path)

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
    daily_export["margin_diff_uah"] = daily_export["margin_promo_uah"] - daily_export["margin_base_uah"]
    daily_export["diff_sales_qty"] = daily_export["sales_qty_with"] - daily_export["sales_qty_baseline"]
    daily_export["diff_percent"] = daily_export.apply(
        lambda r: round((r["diff_sales_qty"] / r["sales_qty_baseline"] * 100), 1) if r["sales_qty_baseline"] else 0,
        axis=1,
    )
    daily_export = daily_export.rename(columns={
        "sales_qty_with": "forecast_promo_qty",
        "sales_qty_baseline": "forecast_base_qty",
        "price_with": "price_promo",
        "price_baseline": "price_base",
        "price_incoming": "cost_price_uah",
    })
    daily_export.to_parquet(f"{out_dir}/{base_name}_daily.parquet", index=False)

    return {
        "shop_id": request.shop_id,
        "category_id": request.category_id,
        "products": products_response,
    }
