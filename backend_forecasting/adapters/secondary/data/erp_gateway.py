"""ERP data adapter — reads sales, prices, promos and categories from the
live MySQL/PostgreSQL databases via the autoorder infrastructure layer."""

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
from autoorder.connections import (
    promo_with_type,
    promo_items,
    product,
    category,
    shop_name,
    Productprices,
    thread_local,
)
from api.helpers.category_column_maker import add_category_hierarchy
from config.category_types import ensure_mappings, HIERARCHY_LEVELS
from config.weather import get_weather
from config.holidays import get_holidays
from core.features import expand_promo_daily
from core.gateway.i_data_gateway import DataInputGateway


def resolve_shop_id(int_id: int) -> str:
    """Map a numeric shop id to its RT-xxxxxx string form."""
    shops = shop_name()
    rt_id = f"RT-{int_id:06d}"
    if not shops.empty and rt_id in shops["id"].values:
        return rt_id
    for sid in shops["id"]:
        if sid.endswith(str(int_id)):
            return sid
    return rt_id


class ErpDataInputGateway(DataInputGateway):
    """Reads live ERP data for a shop (optional) and date range."""

    def __init__(
        self,
        start_date: date,
        end_date: date,
        shop_id: Optional[int] = None,
        shop_rt: Optional[str] = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self._shop_id = shop_id
        self._shop_rt: Optional[str] = shop_rt

    def _get_shop_rt(self) -> Optional[str]:
        if self._shop_id is not None and self._shop_rt is None:
            self._shop_rt = resolve_shop_id(self._shop_id)
        return self._shop_rt

    def _shop_ids(self) -> list[str]:
        rt = self._get_shop_rt()
        return [rt] if rt else []

    def sales_stocks_daily(self) -> pd.DataFrame:
        if self._shop_rt:
            return day_sales_stocs_by_shop(
                self.start_date, self.end_date, self._shop_ids()
            )
        return day_sales_stocs(start_date=self.start_date, end_date=self.end_date)

    def promo(self) -> pd.DataFrame:
        return promo_with_type(self.start_date)

    def promo_links(self) -> pd.DataFrame:
        df = promo_items()
        if self._shop_rt and not df.empty:
            df = df[df["shop_id"] == self._shop_rt]
        return df

    def daily_prices(self) -> pd.DataFrame:
        if self._shop_rt:
            return prices_daily_by_shop(
                self.start_date, self.end_date, self._shop_ids()
            )
        return prices_daily(self.start_date, self.end_date)

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
        df = pd.DataFrame(
            results, columns=["product_id", "price_incoming", "date"]
        )
        df = df.sort_values("date").groupby("product_id", as_index=False).last()
        return df[["product_id", "price_incoming"]]

    def weather(self) -> pd.DataFrame:
        return get_weather(self.start_date, self.end_date)

    def holidays(self) -> pd.DataFrame:
        return get_holidays(self.start_date, self.end_date)

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
            result[f"{name}_id"] = (
                hierarchy[name].map(mapping).fillna(0).astype(int)
            )
        return result

    def existing_promos(self, product_ids: list[int]) -> pd.DataFrame:
        """Active promo (product, date, type) rows for the forecast window."""
        promo_defs = self.promo()
        promo_links = self.promo_links()
        if promo_defs.empty or promo_links.empty:
            return pd.DataFrame(
                columns=["product_id", "date", "existing_type_id"]
            )

        promo_daily = expand_promo_daily(promo_defs, promo_links)
        promo_daily = promo_daily[
            (promo_daily["date"] >= self.start_date)
            & (promo_daily["date"] <= self.end_date)
            & (promo_daily["product_id"].isin(product_ids))
        ]
        if promo_daily.empty:
            return pd.DataFrame(
                columns=["product_id", "date", "existing_type_id"]
            )

        existing = promo_daily[
            ["product_id", "date", "type_id"]
        ].drop_duplicates()
        return existing.rename(columns={"type_id": "existing_type_id"})

    def load_features(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Build the full feature frame for the given date range."""
        from core.usecases.build_features import build_feature_dataframe

        self.start_date = start_date
        self.end_date = end_date
        return build_feature_dataframe(start_date, end_date, gateway=self)
