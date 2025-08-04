from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from autoorder.analysis import (
    day_sales_stocs,
    prices_daily,
    day_sales_stocs_by_shop,
    prices_daily_by_shop,
)

from autoorder.conections import (
    promo_with_type as promo,
    promo_items,
    product,
    category,
    shop_name,
    Productprices,
    thread_local,
)
from api.helpers.categoey_column_maker import add_category_hierarchy
from config.weather import get_weather
from config.holidays import get_holidays
from config.category_types import ensure_mappings, HIERARCHY_LEVELS
from config.promo_types import PROMO_TYPES
from core.gateway.i_data_gateway import DataInputGateway


def _resolve_shop_id(int_id: int) -> str:
    shops = shop_name()
    rt_id = f"RT-{int_id:06d}"
    if not shops.empty and rt_id in shops["id"].values:
        return rt_id
    for sid in shops["id"]:
        if sid.endswith(str(int_id)):
            return sid
    return rt_id


class ErpDataInputGateway(DataInputGateway):
    def __init__(self, start_date: date, end_date: date, shop_id: Optional[int] = None):
        self.start_date = start_date
        self.end_date = end_date
        self._shop_id = shop_id
        self._shop_rt: Optional[str] = None

    def _get_shop_rt(self) -> Optional[str]:
        if self._shop_id is not None and self._shop_rt is None:
            self._shop_rt = _resolve_shop_id(self._shop_id)
        return self._shop_rt

    def _shop_ids(self) -> list[str]:
        rt = self._get_shop_rt()
        return [rt] if rt else []

    def sales_stocks_daily(self) -> pd.DataFrame:
        if self._shop_rt:
            df = day_sales_stocs_by_shop(
                self.start_date, self.end_date, self._shop_ids()
            )
        else:
            df = day_sales_stocs(start_date=self.start_date, end_date=self.end_date)
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("day_sales_stocs returned empty DataFrame")
        return df

    def promo(self) -> pd.DataFrame:
        result = promo(self.start_date)
        if not isinstance(result, pd.DataFrame) or result.empty:
            raise ValueError("promo returned empty DataFrame")
        return result

    def weather(self) -> pd.DataFrame:
        df = get_weather(self.start_date, self.end_date)
        if df.empty:
            raise ValueError("weather returned empty DataFrame")
        return df

    def holidays(self) -> pd.DataFrame:
        df = get_holidays(self.start_date, self.end_date)
        if df.empty:
            raise ValueError("holidays returned empty DataFrame")
        return df

    def promo_links(self) -> pd.DataFrame:
        df = promo_items()
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("promo_items returned empty DataFrame")
        if self._shop_rt:
            df = df[df["shop_id"] == self._shop_rt]
        return df

    def daily_prices(self) -> pd.DataFrame:
        if self._shop_rt:
            df = prices_daily_by_shop(self.start_date, self.end_date, self._shop_ids())
        else:
            df = prices_daily(self.start_date, self.end_date)
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("prices_daily returned empty DataFrame")
        return df

    def product_cost_prices(self) -> pd.DataFrame:
        results = (
            thread_local.session.query(
                Productprices.product_id,
                Productprices.price_incoming,
                Productprices.date,
            )
            .filter(Productprices.date <= self.end_date)
            .all()
        )
        if not results:
            return pd.DataFrame(columns=["product_id", "price_incoming"])
        df = pd.DataFrame(results, columns=["product_id", "price_incoming", "date"])
        df = df.sort_values("date").groupby("product_id", as_index=False).last()
        return df[["product_id", "price_incoming"]]

    def category_hierarchy(self) -> pd.DataFrame:
        products_df = product()
        categories_df = category()
        if products_df.empty or categories_df.empty:
            return pd.DataFrame(
                columns=[
                    "product_id",
                    "group_id",
                    "subgroup_id",
                    "subsubgroup_id",
                    "subsubsubgroup_id",
                    "subsubsubgroups_id",
                ]
            )

        ensure_mappings(categories_df)

        hierarchy = add_category_hierarchy(products_df, categories_df)
        result = hierarchy[["id"]].rename(columns={"id": "product_id"})

        for name, mapping in HIERARCHY_LEVELS:
            result[f"{name}_id"] = hierarchy[name].map(mapping).fillna(0).astype(int)

        return result

    def load_features(self, start_date: date, end_date: date) -> pd.DataFrame:
        self.start_date = start_date
        self.end_date = end_date

        sales = self.sales_stocks_daily()
        promo_defs = self.promo()
        promo_links = self.promo_links()
        prices = self.daily_prices()
        weather = self.weather()
        holidays = self.holidays()
        cats = self.category_hierarchy()

        product_ids_in_scope = sales["product_id"].unique().tolist()

        if self._shop_rt:
            prices = prices[prices["product_id"].isin(product_ids_in_scope)]
            cats = cats[cats["product_id"].isin(product_ids_in_scope)]

        promo_active = promo_links.merge(
            promo_defs[["id", "type_id", "date_from", "date_to"]],
            left_on="promo_id",
            right_on="id",
            how="inner",
        )

        promo_daily = promo_active.assign(
            date=promo_active.apply(
                lambda r: pd.date_range(r["date_from"], r["date_to"], freq="D"),
                axis=1,
            ),
        ).explode("date")
        promo_daily["date"] = pd.to_datetime(promo_daily["date"]).dt.date
        promo_daily = promo_daily[
            ["shop_id", "product_id", "date", "type_id"]
        ].drop_duplicates()

        if self._shop_rt:
            promo_daily = promo_daily[
                promo_daily["product_id"].isin(product_ids_in_scope)
            ]

        df = sales.merge(promo_daily, on=["shop_id", "product_id", "date"], how="left")
        df["is_promo"] = df["type_id"].notna()
        df["promo_type_id"] = df["type_id"].map(PROMO_TYPES).fillna(0).astype(int)
        df = df.drop(columns=["type_id"])

        daily_price = prices.groupby(["shop_id", "product_id", "date"], as_index=False)[
            "price"
        ].mean()
        daily_price["price"] = daily_price["price"].round(1)

        df = df.merge(
            daily_price[["shop_id", "product_id", "date", "price"]],
            on=["shop_id", "product_id", "date"],
            how="left",
        )
        df = df.merge(weather, on="date", how="left")
        df = df.merge(holidays, on="date", how="left")
        df = df.merge(cats, on="product_id", how="left")

        df["has_stock"] = ((df["sales_qty"] > 0) | (df["stocs_qty"] > 0)).astype(bool)

        df["day"] = pd.to_datetime(df["date"]).dt.day.astype(np.int8)
        df["day_of_week"] = pd.to_datetime(df["date"]).dt.dayofweek.astype(np.int8)
        df["month"] = pd.to_datetime(df["date"]).dt.month.astype(np.int8)

        df["sales_qty"] = np.round(df["sales_qty"]).clip(0).astype(np.int32)
        df["price"] = df["price"].astype(np.float32)

        df = df.drop(columns=["stocs_qty", "is_weekend"])

        return df
