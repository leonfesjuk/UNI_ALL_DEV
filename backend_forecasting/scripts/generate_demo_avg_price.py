import argparse
from datetime import date, datetime

import numpy as np
import pandas as pd

from adapters.secondary.data.erp_gateway import ErpDataInputGateway


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def generate_avg_price_dataset(
    date_from: date,
    date_to: date,
    output: str = "data/demo/avg_price.parquet",
) -> dict:
    from pathlib import Path

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    gw = ErpDataInputGateway(date_from, date_to)
    prices = gw.daily_prices()

    avg = prices.groupby("product_id", as_index=False)["price"].mean()
    avg["price"] = avg["price"].round(2).astype(np.float32)
    avg.rename(columns={"price": "avg_price"}, inplace=True)

    avg.to_parquet(output, index=False, compression="snappy")

    return {"products": len(avg), "output": output}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate demo avg_price.parquet from ERP"
    )
    parser.add_argument("--date-from", type=parse_date, required=True)
    parser.add_argument("--date-to", type=parse_date, required=True)
    parser.add_argument("--output", type=str, default="data/demo/avg_price.parquet")
    args = parser.parse_args()

    result = generate_avg_price_dataset(
        date_from=args.date_from,
        date_to=args.date_to,
        output=args.output,
    )

    print(f"Products: {result['products']}")
    print(f"Output: {result['output']}")


if __name__ == "__main__":
    main()
