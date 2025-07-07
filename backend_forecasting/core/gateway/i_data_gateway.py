from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataInputGateway(ABC):

    @abstractmethod
    def sales_stocks_daily(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def promo(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def weather(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def holidays(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def promo_links(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def daily_prices(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def category_hierarchy(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def product_cost_prices(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def load_features(self, start_date: date, end_date: date) -> pd.DataFrame:
        ...
