import os
from pathlib import Path

import numpy as np
import pandas as pd

from core.ports.output import AIPort


class KronosAdapter(AIPort):

    def __init__(self, model_path: str = "amazon/chronos-2"):
        from chronos import Chronos2Pipeline

        self.pipeline = Chronos2Pipeline.from_pretrained(
            model_path,
            device_map="cpu",
        )

    def predict(
        self,
        context: pd.DataFrame,
        forecast_features: pd.DataFrame,
    ) -> pd.DataFrame:
        forecast = forecast_features.copy()
        forecast_horizon = forecast["date"].nunique()
        covariates = [
            c for c in forecast_features.columns
            if c not in ("shop_id", "product_id", "date", "sales_qty")
        ]

        context_cols = ["product_id", "date", "sales_qty"]
        for c in covariates:
            if c in context.columns:
                context_cols.append(c)
        context_df = context[context_cols].copy()
        context_df.rename(
            columns={"product_id": "id", "date": "timestamp", "sales_qty": "target"},
            inplace=True,
        )
        context_df["timestamp"] = pd.to_datetime(context_df["timestamp"])

        ts_min = context_df["timestamp"].min()
        ts_max = context_df["timestamp"].max()
        idx = pd.date_range(ts_min, ts_max, freq="D", name="timestamp")
        full = []
        for pid, sub in context_df.groupby("id"):
            sub = sub.set_index("timestamp").reindex(idx).reset_index()
            sub["id"] = pid
            full.append(sub)
        context_df = pd.concat(full, ignore_index=True)

        future_dfs = []
        for pid in forecast["product_id"].unique():
            prod_forecast = forecast[forecast["product_id"] == pid]
            future_df = prod_forecast[["date"] + covariates].copy()
            future_df["id"] = pid
            future_df.rename(columns={"date": "timestamp"}, inplace=True)
            future_df["timestamp"] = pd.to_datetime(future_df["timestamp"])
            future_dfs.append(future_df)

        future_combined = pd.concat(future_dfs, ignore_index=True)

        context_df['target'] = context_df['target'].fillna(0)
        cov_in_context = [c for c in covariates if c in context_df.columns]
        if cov_in_context:
            context_df[cov_in_context] = context_df.groupby("id")[cov_in_context].transform(
                lambda g: g.ffill().bfill()
            )
            for c in cov_in_context:
                if context_df[c].dtype.kind in ('i', 'b'):
                    context_df[c] = context_df[c].fillna(0)
                elif context_df[c].dtype.kind == 'f':
                    context_df[c] = context_df[c].fillna(1.0)
        for c in covariates:
            if c not in future_combined.columns:
                continue
            if future_combined[c].dtype.kind == 'f':
                future_combined[c] = future_combined[c].fillna(1.0)
            else:
                future_combined[c] = future_combined[c].fillna(0)
            if c in context_df.columns:
                future_combined[c] = future_combined[c].astype(context_df[c].dtype)

        pred_df = self.pipeline.predict_df(
            context_df,
            future_df=future_combined,
            prediction_length=forecast_horizon,
            quantile_levels=[0.5],
            id_column="id",
            timestamp_column="timestamp",
            target="target",
            cross_learning=True,
        )

        pred_df['date'] = pd.to_datetime(pred_df['timestamp']).dt.date
        pred_df['pred_qty'] = pred_df['predictions'].clip(0).astype(np.float32)

        forecast = forecast.merge(
            pred_df[['id', 'date', 'pred_qty']].rename(columns={'id': 'product_id'}),
            on=['product_id', 'date'],
            how='left',
        )
        forecast['sales_qty'] = forecast['pred_qty'].fillna(forecast['sales_qty']).fillna(0.0).astype(np.float32)
        forecast = forecast.drop(columns=['pred_qty'])
        return forecast
