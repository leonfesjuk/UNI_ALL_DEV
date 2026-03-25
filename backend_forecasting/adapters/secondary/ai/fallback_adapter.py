"""Fallback AI adapter — deterministic mean-based prediction."""

from core.features import baseline_mean_predict
from core.ports.output import AIPort


class FallbackAdapter(AIPort):
    """Predicts the historical mean sales per product.

    Used when the ML model is unavailable or disabled.
    """

    def predict(self, context, forecast_features):
        return baseline_mean_predict(context, forecast_features)
