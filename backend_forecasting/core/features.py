"""Shared feature-engineering helpers.

Pure pandas transformations with no dependency on adapters, config
or external services — usable from any layer (usecases, scripts,
adapters) without violating Clean Architecture boundaries.
"""

from datetime import date

import numpy as np
import pandas as pd

from core.ports.output import AIPort  # noqa: F401  (re-exported for convenience)

FEATURE_LEVEL_COLUMNS: list[str] = [
    "group_id",
    "subgroup_id",
    "subsubgroup_id",
    "subsubsubgroup_id",
    "subsubsubgroups_id",
]

DAILY_BASE_COLUMNS: list[str] = ["shop_id", "product_id", "date", "sales_qty"]


def expand_promo_daily(
    promo_defs: pd.DataFrame,
    promo_links: pd.DataFrame,
) -> pd.DataFrame:
    """Explode promo definitions into one row per (shop, product, date).

    Returns columns: shop_id, product_id, date, type_id, promo_id.
    """
    if promo_defs.empty or promo_links.empty:
        return pd.DataFrame(
            columns=["shop_id", "product_id", "date", "type_id", "promo_id"]
        )

    active = promo_links.merge(
        promo_defs[["id", "type_id", "date_from", "date_to"]],
        left_on="promo_id",
        right_on="id",
        how="inner",
    )

    expanded = active.assign(
        date=active.apply(
            lambda r: pd.date_range(r["date_from"], r["date_to"], freq="D"),
            axis=1,
        )
    ).explode("date", ignore_index=True)

    expanded["date"] = pd.to_datetime(expanded["date"]).dt.date
    return expanded[
        ["shop_id", "product_id", "date", "type_id", "promo_id"]
    ].drop_duplicates()


def attach_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar-derived columns used by forecasting models."""
    dates = pd.to_datetime(df["date"])
    df["day"] = dates.dt.day.astype(np.int8)
    df["day_of_week"] = dates.dt.dayofweek.astype(np.int8)
    df["month"] = dates.dt.month.astype(np.int8)
    df["has_stock"] = (
        (df["sales_qty"] > 0) | (df.get("stocs_qty", 0) > 0)
    ).astype(np.int8)
    return df


def normalize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Cast quantities and prices to compact numeric types."""
    df["sales_qty"] = np.round(df["sales_qty"]).clip(0).astype(np.int32)
    if "price" in df.columns:
        df["price"] = df["price"].round(1).astype(np.float32)
    return df


def average_daily_price(prices: pd.DataFrame) -> pd.DataFrame:
    """Collapse raw prices to one mean price per (shop, product, date)."""
    daily = prices.groupby(
        ["shop_id", "product_id", "date"], as_index=False
    )["price"].mean()
    daily["price"] = daily["price"].round(1)
    return daily


def impute_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing prices: regular price via ffill/bfill, promo price
    from the same promo's mean, then final ffill per product."""
    df["reg_price"] = df["price"].where(~df["is_promo"])
    df["reg_price"] = df.groupby("product_id")["reg_price"].ffill()
    df["reg_price"] = df.groupby("product_id")["reg_price"].bfill()

    promo_fill = (
        df[df["is_promo"] & df["price"].notna()]
        .groupby(["product_id", "promo_id"])["price"]
        .mean()
        .rename("promo_fill")
    )
    df = df.merge(promo_fill, on=["product_id", "promo_id"], how="left")
    df["price"] = np.where(
        df["is_promo"], df["promo_fill"].fillna(0), df["reg_price"]
    )
    df["price"] = df.groupby("product_id")["price"].ffill().fillna(0)
    return df.drop(columns=["reg_price", "promo_fill"])


def baseline_mean_predict(
    context: pd.DataFrame,
    forecast_features: pd.DataFrame,
) -> pd.DataFrame:
    """Deterministic fallback predictor: historical mean per product."""
    forecast = forecast_features.copy()
    for pid in forecast["product_id"].unique():
        hist = context[context["product_id"] == pid]["sales_qty"]
        base = float(hist.mean()) if not hist.empty else 0.0
        mask = forecast["product_id"] == pid
        forecast.loc[mask, "sales_qty"] = max(round(base), 0)
    forecast["sales_qty"] = forecast["sales_qty"].astype(np.int32)
    return forecast


def last_non_promo_price(df: pd.DataFrame, product_id: int) -> float:
    """Last observed non-promo price for a product (0.0 if unknown)."""
    sub = df[df["product_id"] == product_id].dropna(subset=["price"])
    if sub.empty:
        return 0.0
    non_promo = sub[sub["is_promo"] == False]  # noqa: E712
    if not non_promo.empty:
        return float(non_promo.iloc[-1]["price"])
    return float(sub.iloc[-1]["price"])
