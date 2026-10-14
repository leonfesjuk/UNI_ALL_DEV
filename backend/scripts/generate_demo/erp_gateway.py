from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from autoorder.analysis import day_sales_stocs, prices_daily
from autoorder.conections import (
    promo_with_type as promo,
    promo_items,
    product,
    category,
    shop_name,
    prices_for_shop,
    sales_for_shop,
    latest_cost_prices,
)
from api.helpers.categoey_column_maker import add_category_hierarchy

from .weather import get_weather
from .holidays import get_holidays
from .category_types import ensure_mappings, HIERARCHY_LEVELS
from .i_data_gateway import DataInputGateway


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
            df = sales_for_shop(self.start_date, self.end_date, self._shop_ids())
        else:
            df = day_sales_stocs(start_date=self.start_date, end_date=self.end_date)
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("sales_stocks_daily returned empty DataFrame")
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
            df = prices_for_shop(self.start_date, self.end_date, self._shop_ids())
        else:
            df = prices_daily(self.start_date, self.end_date)
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("prices_daily returned empty DataFrame")
        return df

    def product_cost_prices(self) -> pd.DataFrame:
        df = latest_cost_prices(self.end_date)
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame(columns=["product_id", "price_incoming"])
        return df

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
        return pd.DataFrame()
