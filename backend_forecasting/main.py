"""Forecasting service entry point."""

import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query

from adapters.primary.api import router
from config.category_types import LEVEL_COLUMNS
from scripts.generate_demo_avg_price import generate_avg_price_dataset
from scripts.generate_demo_features import generate_features_dataset

logger = logging.getLogger(__name__)

app = FastAPI(title="Forecasting Service")
app.include_router(router)

FEATURES_PATH = os.getenv(
    "FC_FEATURES_PATH", "data/demo/features.parquet"
)


def _load_features() -> pd.DataFrame:
    try:
        return pd.read_parquet(FEATURES_PATH)
    except Exception as e:
        logger.warning("Could not load features from %s: %s", FEATURES_PATH, e)
        return pd.DataFrame()


@app.get("/promo-forecast/shops")
async def get_shops():
    df = _load_features()
    if df.empty:
        return {"shops": []}
    return {"shops": sorted(df["shop_id"].unique().tolist())}


@app.get("/promo-forecast/categories")
async def get_categories(level: int = Query(..., ge=0, le=4)):
    df = _load_features()
    if df.empty:
        return {"categories": []}
    col = LEVEL_COLUMNS[level]
    ids = sorted(df[col].unique().tolist())
    return {"categories": [{"id": int(i), "name": ""} for i in ids]}


@app.get("/promo-forecast/products")
async def get_products(
    level: int = Query(..., ge=0, le=4),
    level_id: int = Query(...),
):
    df = _load_features()
    if df.empty:
        return {"products": []}
    col = LEVEL_COLUMNS[level]
    sub = df[df[col] == level_id]
    product_ids = sorted(sub["product_id"].unique().tolist())
    return {
        "products": [
            {"product_id": int(pid), "product_name": ""}
            for pid in product_ids
        ]
    }


@app.post("/promo-forecast/generate-dataset")
async def generate_dataset(
    days: int = Query(..., description="Days of history from yesterday"),
    shop_id: str = Query(..., description="Shop ID, e.g. RT-000001"),
    category_id: str = Query(..., description="Category ID, e.g. 00000134"),
):
    today = date.today()
    yesterday = today - timedelta(days=1)
    date_from = yesterday - timedelta(days=days - 1)

    period = f"{date_from.isoformat()}_{yesterday.isoformat()}"
    base = f"data/demo/{shop_id}_{category_id}_{period}"

    f_result = generate_features_dataset(
        shop_id=shop_id,
        category_id=category_id,
        date_from=date_from,
        date_to=yesterday,
        output=f"{base}_features.parquet",
    )
    p_result = generate_avg_price_dataset(
        date_from=date_from,
        date_to=yesterday,
        output=f"{base}_prices.parquet",
    )

    return {
        "status": "ok",
        "shop_id": shop_id,
        "category_id": category_id,
        "period": {
            "from": date_from.isoformat(),
            "to": yesterday.isoformat(),
        },
        "features": {
            "path": f_result["output"],
            "rows": f_result["rows"],
        },
        "prices": {
            "path": p_result["output"],
            "products": p_result["products"],
        },
    }
