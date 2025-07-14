from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from config.category_types import LEVEL_COLUMNS, resolve_category_id
from config.promo_types import PROMO_TYPES
from config.holidays import get_holidays
from config.weather import get_weather
from core.gateway.i_data_gateway import DataInputGateway
from core.ports.output import AIPort
from core.usecases.build_features import build_feature_dataframe


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
    date_end: int
    products: list[ProductForecastInput]


def _kronos_predict(
    context: pd.DataFrame,
    forecast_features: pd.DataFrame,
) -> pd.DataFrame:
    forecast = forecast_features.copy()
    products = forecast["product_id"].unique()
    rng = np.random.default_rng(42)
    for pid in products:
        hist = context[context["product_id"] == pid]["sales_qty"]
        if hist.empty:
            forecast.loc[forecast["product_id"] == pid, "sales_qty"] = 0
            continue
        base = hist.mean()
        forecast.loc[forecast["product_id"] == pid, "sales_qty"] = (
            base * rng.uniform(0.8, 1.2, size=(forecast["product_id"] == pid).sum())
        ).clip(0)
    return forecast


def forecast_for_group(
    request: ForecastRequest,
    gateway: DataInputGateway | None = None,
    ai_adapter: AIPort | None = None,
    context_days: int = 730,
) -> pd.DataFrame:
    history_end = request.date_start - timedelta(days=1)
    history_start = request.date_start - timedelta(days=context_days)
    forecast_end = request.date_start + timedelta(days=request.date_end - 1)

    if gateway is not None:
        df = gateway.load_features(history_start, history_end)
    else:
        df = build_feature_dataframe(history_start, history_end)
    level, level_id = resolve_category_id(request.category_id)
    level_col = LEVEL_COLUMNS[level]
    df = df[(df["shop_id"] == request.shop_id) & (df[level_col] == level_id)]

    product_ids = [p.product_id for p in request.products]
    df = df[df["product_id"].isin(product_ids)]

    forecast_dates = pd.date_range(request.date_start, forecast_end, freq="D").date
    product_last_price = {pid: _last_non_promo_price(df, pid) for pid in product_ids}
    forecast_rows = []
    for pid in product_ids:
        last_price = product_last_price[pid]
        for d in forecast_dates:
            forecast_rows.append(
                {
                    "shop_id": request.shop_id,
                    "product_id": pid,
                    "date": d,
                    "sales_qty": np.nan,
                    "has_stock": True,
                    "day_of_week": d.weekday(),
                    "month": d.month,
                    "price": last_price,
                    "is_promo": False,
                    "promo_type_id": 0,
                }
            )

    fcast = pd.DataFrame(forecast_rows)

    prod_map = {p.product_id: p for p in request.products}
    for pid in product_ids:
        p = prod_map[pid]
        mask = fcast["product_id"] == pid

        if p.promo_type_id > 0:
            if p.promo_start and p.promo_end:
                promo_mask = (
                    mask
                    & (fcast["date"] >= p.promo_start)
                    & (fcast["date"] <= p.promo_end)
                )
                fcast.loc[promo_mask, "price"] = p.expected_price
                fcast.loc[promo_mask, "is_promo"] = True
                fcast.loc[promo_mask, "promo_type_id"] = p.promo_type_id
            else:
                fcast.loc[mask, "price"] = p.expected_price
                fcast.loc[mask, "is_promo"] = True
                fcast.loc[mask, "promo_type_id"] = p.promo_type_id

    fcast = _merge_existing_forecast_promos(fcast, request, forecast_end)

    for col in LEVEL_COLUMNS:
        val = level_id if col == level_col else 0
        fcast[col] = val

    weather = get_weather(request.date_start, forecast_end)
    if not weather.empty:
        for c in [
            "feels_id_morning",
            "feels_id_afternoon",
            "precip_id_morning",
            "precip_id_afternoon",
        ]:
            weather[c] = weather[c].astype(int)
        fcast = fcast.merge(weather, on="date", how="left")
    for c in [
        "feels_id_morning",
        "feels_id_afternoon",
        "precip_id_morning",
        "precip_id_afternoon",
    ]:
        if c not in fcast.columns:
            fcast[c] = 0
        else:
            fcast[c] = fcast[c].fillna(0).astype(int)

    holidays = get_holidays(request.date_start, forecast_end)
    if not holidays.empty:
        fcast = fcast.merge(holidays, on="date", how="left")
    for c in ["is_holiday", "holiday_id"]:
        if c not in fcast.columns:
            fcast[c] = 0 if c == "holiday_id" else False
        else:
            fcast[c] = fcast[c].fillna(0)
    fcast["is_holiday"] = fcast["is_holiday"].astype(bool)
    fcast["holiday_id"] = fcast["holiday_id"].astype(int)

    if ai_adapter is not None:
        fcast = ai_adapter.predict(df, fcast)
    else:
        fcast = _kronos_predict(df, fcast)
    return fcast


def _merge_existing_forecast_promos(
    fcast: pd.DataFrame,
    request: ForecastRequest,
    forecast_end: date,
) -> pd.DataFrame:
    try:
        from adapters.secondary.data.erp_gateway import ErpDataInputGateway

        gw = ErpDataInputGateway(request.date_start, forecast_end)
        promo_defs = gw.promo()
        promo_links = gw.promo_links()
    except Exception:
        return fcast

    if promo_defs.empty or promo_links.empty:
        return fcast

    active = promo_links.merge(
        promo_defs[["id", "type_id", "date_from", "date_to"]],
        left_on="promo_id",
        right_on="id",
        how="inner",
    )

    active.loc[:, "date"] = active.apply(
        lambda r: pd.date_range(r["date_from"], r["date_to"], freq="D"), axis=1
    )
    active = active.explode("date", ignore_index=True)
    active["date"] = pd.to_datetime(active["date"]).dt.date

    product_ids = [p.product_id for p in request.products]
    active = active[
        (active["product_id"].isin(product_ids))
        & (active["date"] >= request.date_start)
        & (active["date"] <= forecast_end)
    ]

    if active.empty:
        return fcast

    existing = active[["product_id", "date", "type_id"]].drop_duplicates()
    existing = existing.rename(columns={"type_id": "existing_type_id"})
    merged = fcast.merge(existing, on=["product_id", "date"], how="left")

    no_user_promo = merged["promo_type_id"] == 0
    has_existing = merged["existing_type_id"].notna()
    merged.loc[no_user_promo & has_existing, "promo_type_id"] = (
        merged.loc[no_user_promo & has_existing, "existing_type_id"]
        .map(PROMO_TYPES)
        .fillna(0)
        .astype(int)
    )
    merged.loc[no_user_promo & has_existing, "is_promo"] = True

    return merged.drop(columns=["existing_type_id"])


def _last_non_promo_price(df: pd.DataFrame, product_id: int) -> float:
    sub = df[df["product_id"] == product_id].dropna(subset=["price"])
    if sub.empty:
        return 0.0
    non_promo = sub[sub["is_promo"] == False]
    if not non_promo.empty:
        return non_promo.iloc[-1]["price"]
    return sub.iloc[-1]["price"]


def compare_scenarios(
    forecast_with: pd.DataFrame,
    forecast_baseline: pd.DataFrame,
    cost_prices: pd.DataFrame,
    expected_price: float,
    shop_id: str = "",
    level_name: str = "",
    category_id: str = "",
) -> dict:
    daily = forecast_with.merge(
        forecast_baseline,
        on=["product_id", "date"],
        suffixes=["_with", "_baseline"],
    )
    keep_cols = ["product_id", "date"]
    for suffix in ["_with", "_baseline"]:
        for base in ["sales_qty", "price", "promo_type_id"]:
            col = f"{base}{suffix}"
            if col in daily.columns:
                keep_cols.append(col)
    daily = daily[keep_cols]
    daily.insert(0, "category_id", category_id)
    daily.insert(1, "level", level_name)
    daily.insert(2, "shop_id", shop_id)

    summary_rows = []
    for pid in daily["product_id"].unique():
        sub = daily[daily["product_id"] == pid]
        qty_with = int(sub["sales_qty_with"].sum())
        qty_base = int(sub["sales_qty_baseline"].sum())
        diff_qty = qty_with - qty_base

        cp_row = cost_prices[cost_prices["product_id"] == pid]
        cost_price = (
            float(cp_row["price_incoming"].iloc[0]) if not cp_row.empty else 0.0
        )
        margin_with = round((expected_price - cost_price) * qty_with, 2)
        margin_baseline = round((expected_price - cost_price) * qty_base, 2)
        diff_margin = round(margin_with - margin_baseline, 2)

        summary_rows.append(
            {
                "shop_id": shop_id,
                "level": level_name,
                "category_id": category_id,
                "product_id": pid,
                "total_sales_with": qty_with,
                "total_sales_baseline": qty_base,
                "diff_qty": diff_qty,
                "cost_price": round(cost_price, 2),
                "expected_price": expected_price,
                "margin_with": margin_with,
                "margin_baseline": margin_baseline,
                "diff_margin": diff_margin,
            }
        )

    return {
        "daily": daily,
        "summary": pd.DataFrame(summary_rows),
    }


def export_compare_to_excel(data: dict, path: str) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        data["daily"].to_excel(writer, sheet_name="Денний зріз", index=False)
        data["summary"].to_excel(writer, sheet_name="Підсумок", index=False)
