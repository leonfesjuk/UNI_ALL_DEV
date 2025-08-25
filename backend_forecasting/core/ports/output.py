from abc import ABC, abstractmethod

import pandas as pd


class DataPort(ABC):

    @abstractmethod
    def sales_stocks_daily(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def promo(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def promo_links(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def daily_prices(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def weather(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def holidays(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def category_hierarchy(self) -> pd.DataFrame:
        ...


class AIPort(ABC):

    @abstractmethod
    def predict(
        self,
        context: pd.DataFrame,
        forecast_features: pd.DataFrame,
    ) -> pd.DataFrame:
        ...
