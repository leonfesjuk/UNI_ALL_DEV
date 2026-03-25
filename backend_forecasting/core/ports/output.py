from abc import ABC, abstractmethod

import pandas as pd


class AIPort(ABC):
    """Port for AI-based forecasting adapters."""

    @abstractmethod
    def predict(
        self,
        context: pd.DataFrame,
        forecast_features: pd.DataFrame,
    ) -> pd.DataFrame:
        ...
