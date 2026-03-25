"""Kronos (Chronos-2) forecasting adapter."""

import numpy as np
import pandas as pd

from core.ports.output import AIPort


class KronosAdapter(AIPort):
    """Wraps the Chronos-2 pipeline behind the AIPort interface."""

    def __init__(self, model_path: str = "amazon/chronos-2"):
        from chronos import Chronos2Pipeline

        self.pipeline = Chronos2Pipeline.from_pretrained(
            model_path, device_map="cpu"
        )

    def predict(
        self,
        context: pd.DataFrame,
        forecast_features: pd.DataFrame,
    ) -> pd.DataFrame:
        forecast = forecast_features.copy()
        forecast_horizon = forecast["date"].nunique()

        covariates = [
            c
            for c in forecast_features.columns
            if c not in ("shop_id", "product_id", "date", "sales_qty")
        ]

        context_df = context[
            ["product_id", "date", "sales_qty"] + covariates
        ].copy()
        context_df.rename(
            columns={
                "product_id": "id",
                "date": "timestamp",
                "sales_qty": "target",
            },
            inplace=True,
        )
        context_df["timestamp"] = pd.to_datetime(context_df["timestamp"])

        idx = pd.date_range(
            context_df["timestamp"].min(),
            context_df["timestamp"].max(),
            freq="D",
            name="timestamp",
        )
        frames = []
        for pid, sub in context_df.groupby("id"):
            sub = sub.set_index("timestamp").reindex(idx).reset_index()
            sub["id"] = pid
            frames.append(sub)
        context_df = pd.concat(frames, ignore_index=True)

        future_frames = []
        for pid in forecast["product_id"].unique():
            prod = forecast[forecast["product_id"] == pid]
            future = prod[["date"] + covariates].copy()
            future["id"] = pid
            future.rename(columns={"date": "timestamp"}, inplace=True)
            future["timestamp"] = pd.to_datetime(future["timestamp"])
            future_frames.append(future)
        future_df = pd.concat(future_frames, ignore_index=True)

        context_df["target"] = context_df["target"].fillna(0)
        for c in covariates:
            if c not in context_df.columns or c not in future_df.columns:
                continue
            if context_df[c].dtype.kind == "f":
                context_df[c] = context_df[c].fillna(1.0)
                future_df[c] = future_df[c].fillna(1.0)
            else:
                context_df[c] = context_df[c].fillna(0)
                future_df[c] = future_df[c].fillna(0)
            future_df[c] = future_df[c].astype(context_df[c].dtype)

        pred_df = self.pipeline.predict_df(
            context_df,
            future_df=future_df,
            prediction_length=forecast_horizon,
            quantile_levels=[0.5],
            id_column="id",
            timestamp_column="timestamp",
            target="target",
            cross_learning=True,
        )

        pred_df["date"] = pd.to_datetime(pred_df["timestamp"]).dt.date
        pred_df["pred_qty"] = (
            pred_df["predictions"].clip(0).astype(np.float32)
        )

        forecast = forecast.merge(
            pred_df[["id", "date", "pred_qty"]].rename(
                columns={"id": "product_id"}
            ),
            on=["product_id", "date"],
            how="left",
        )
        forecast["sales_qty"] = (
            forecast["pred_qty"]
            .fillna(forecast["sales_qty"])
            .fillna(0.0)
            .astype(np.float32)
        )
        return forecast.drop(columns=["pred_qty"])
