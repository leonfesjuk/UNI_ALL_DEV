from datetime import date
from pathlib import Path

import pandas as pd

from core.gateway.i_data_gateway import DataInputGateway


class FakeDataAdapter(DataInputGateway):
    def __init__(self, path: str = "data/demo/features.parquet"):
        self._path = path
        self._cost_prices_path = "data/demo/cost_prices.parquet"

    def load_features(self, start_date: date, end_date: date) -> pd.DataFrame:
        df = pd.read_parquet(self._path)
        return df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    def product_cost_prices(self) -> pd.DataFrame:
        path = Path(self._cost_prices_path)
        if path.exists():
            return pd.read_parquet(str(path))
        return pd.DataFrame(columns=["product_id", "price_incoming"])

    def sales_stocks_daily(self) -> pd.DataFrame:
        return pd.DataFrame()

    def promo(self) -> pd.DataFrame:
        return pd.DataFrame()

    def weather(self) -> pd.DataFrame:
        return pd.DataFrame()

    def holidays(self) -> pd.DataFrame:
        return pd.DataFrame()

    def promo_links(self) -> pd.DataFrame:
        return pd.DataFrame()

    def daily_prices(self) -> pd.DataFrame:
        return pd.DataFrame()

    def category_hierarchy(self) -> pd.DataFrame:
        return pd.DataFrame()
