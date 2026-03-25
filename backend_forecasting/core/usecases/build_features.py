"""Build the feature dataframe used for model training / context."""

from datetime import date

import pandas as pd

from core.features import (
    attach_daily_features,
    average_daily_price,
    expand_promo_daily,
    normalize_dtypes,
)
from core.gateway.i_data_gateway import DataInputGateway


def build_feature_dataframe(
    start_date: date,
    end_date: date,
    gateway: DataInputGateway,
) -> pd.DataFrame:
    """Merge sales, promos, prices, weather, holidays and category
    hierarchy into one flat feature frame.

    The gateway must be provided by the caller (Clean Architecture:
    use cases never import adapters directly).
    """
    sales = gateway.sales_stocks_daily()
    promo_defs = gateway.promo()
    promo_links = gateway.promo_links()
    prices = gateway.daily_prices()
    weather = gateway.weather()
    holidays = gateway.holidays()
    cats = gateway.category_hierarchy()

    promo_daily = expand_promo_daily(promo_defs, promo_links)

    df = sales.merge(
        promo_daily, on=["shop_id", "product_id", "date"], how="left"
    )
    df["is_promo"] = df["type_id"].notna()
    df = df.drop(columns=["type_id"])

    daily_price = average_daily_price(prices)
    df = df.merge(
        daily_price[["shop_id", "product_id", "date", "price"]],
        on=["shop_id", "product_id", "date"],
        how="left",
    )

    df = df.merge(weather, on="date", how="left")
    df = df.merge(holidays, on="date", how="left")
    df = df.merge(cats, on="product_id", how="left")

    df = attach_daily_features(df)
    df = normalize_dtypes(df)
    return df.drop(columns=["stocs_qty"])
