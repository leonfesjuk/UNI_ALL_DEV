import numpy as np
import pandas as pd

from core.ports.output import AIPort


class FallbackAdapter(AIPort):

    def predict(
        self,
        context: pd.DataFrame,
        forecast_features: pd.DataFrame,
    ) -> pd.DataFrame:
        forecast = forecast_features.copy()

        for pid in forecast["product_id"].unique():
            hist = context[context["product_id"] == pid]["sales_qty"]

            if hist.empty or len(hist) < 7:
                fallback_qty = 0
            else:
                fallback_qty = hist.rolling(7, min_periods=1).mean().iloc[-1]

            mask = forecast["product_id"] == pid
            forecast.loc[mask, "sales_qty"] = max(round(fallback_qty), 0)

        forecast["sales_qty"] = forecast["sales_qty"].astype(np.int32)
        return forecast
