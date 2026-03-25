"""Generate demo features.parquet from live ERP data."""

import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from adapters.secondary.data.erp_gateway import ErpDataInputGateway
from config.category_types import (
    LEVEL_COLUMNS,
    resolve_category_path,
)
from core.features import (
    attach_daily_features,
    average_daily_price,
    expand_promo_daily,
    impute_prices,
    normalize_dtypes,
)

logger = logging.getLogger(__name__)


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def generate_features_dataset(
    shop_id: str,
    category_id: str,
    date_from: date,
    date_to: date,
    output: str = "data/demo/features.parquet",
) -> dict:
    """Build a features parquet for one shop/category over a date range.

    Processes month-by-month to keep memory usage bounded.
    """
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    level_col, level_id = resolve_category_path(category_id)
    shop_int = int(shop_id.split("-")[1])

    gw = ErpDataInputGateway(
        date_from, date_to, shop_id=shop_int, shop_rt=shop_id
    )

    promo_defs = gw.promo()
    promo_links = gw.promo_links()
    promo_daily = expand_promo_daily(promo_defs, promo_links)

    weather_all = gw.weather()
    holidays_all = gw.holidays()
    cats = gw.category_hierarchy()

    writer = None
    total_rows = 0
    current = date_from

    while current <= date_to:
        month_end = (
            current.replace(day=1) + timedelta(days=32)
        ).replace(day=1) - timedelta(days=1)
        if month_end > date_to:
            month_end = date_to

        gw.start_date = current
        gw.end_date = month_end

        sales = gw.sales_stocks_daily()
        product_ids = sales["product_id"].unique().tolist()

        prices = gw.daily_prices()
        if product_ids:
            prices = prices[prices["product_id"].isin(product_ids)]

        promo_month = promo_daily[
            promo_daily["date"].between(current, month_end)
        ]
        if product_ids:
            promo_month = promo_month[
                promo_month["product_id"].isin(product_ids)
            ]

        df = sales.merge(
            promo_month, on=["shop_id", "product_id", "date"], how="left"
        )
        df["is_promo"] = df["type_id"].notna()
        df = df.drop(columns=["type_id"])

        df = df.merge(
            average_daily_price(prices),
            on=["shop_id", "product_id", "date"],
            how="left",
        )
        df = impute_prices(df)

        weather = weather_all[
            weather_all["date"].between(current, month_end)
        ]
        holidays = holidays_all[
            holidays_all["date"].between(current, month_end)
        ]
        df = df.merge(weather, on="date", how="left")
        df = df.merge(holidays, on="date", how="left")
        df = df.merge(cats, on="product_id", how="left")

        df = attach_daily_features(df)
        df = normalize_dtypes(df)
        df = df.drop(columns=["stocs_qty"])

        for col in LEVEL_COLUMNS:
            if col in df.columns:
                df[col] = df[col].fillna(0).astype(np.int64)

        df = df[df[level_col] == level_id]

        if not df.empty:
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output, table.schema)
            writer.write_table(table)
            total_rows += len(df)

        logger.info("  %s — %s: %d rows", current, month_end, len(df))
        current = month_end + timedelta(days=1)

    if writer:
        writer.close()

    return {"rows": total_rows, "output": output}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Generate demo features.parquet from ERP"
    )
    parser.add_argument("--shop-id", type=str, required=True)
    parser.add_argument("--category-id", type=str, required=True)
    parser.add_argument("--date-from", type=parse_date, required=True)
    parser.add_argument("--date-to", type=parse_date, required=True)
    parser.add_argument(
        "--output", type=str, default="data/demo/features.parquet"
    )
    args = parser.parse_args()

    result = generate_features_dataset(
        shop_id=args.shop_id,
        category_id=args.category_id,
        date_from=args.date_from,
        date_to=args.date_to,
        output=args.output,
    )
    logger.info("Total rows: %d", result["rows"])
    logger.info("Output: %s", result["output"])


if __name__ == "__main__":
    main()
