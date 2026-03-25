"""Generate demo avg_price.parquet from live ERP data."""

import argparse
import logging
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from adapters.secondary.data.erp_gateway import ErpDataInputGateway

logger = logging.getLogger(__name__)


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def generate_avg_price_dataset(
    date_from: date,
    date_to: date,
    output: str = "data/demo/avg_price.parquet",
) -> dict:
    """Average selling price per product over the date range."""
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    gw = ErpDataInputGateway(date_from, date_to)
    prices = gw.daily_prices()

    avg = prices.groupby("product_id", as_index=False)["price"].mean()
    avg["price"] = avg["price"].round(2).astype(np.float32)
    avg = avg.rename(columns={"price": "avg_price"})

    avg.to_parquet(output, index=False, compression="snappy")
    return {"products": len(avg), "output": output}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Generate demo avg_price.parquet from ERP"
    )
    parser.add_argument("--date-from", type=parse_date, required=True)
    parser.add_argument("--date-to", type=parse_date, required=True)
    parser.add_argument(
        "--output", type=str, default="data/demo/avg_price.parquet"
    )
    args = parser.parse_args()

    result = generate_avg_price_dataset(
        date_from=args.date_from,
        date_to=args.date_to,
        output=args.output,
    )
    logger.info("Products: %d", result["products"])
    logger.info("Output: %s", result["output"])


if __name__ == "__main__":
    main()
