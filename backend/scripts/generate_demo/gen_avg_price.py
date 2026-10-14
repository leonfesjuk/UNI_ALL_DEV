import argparse
from datetime import date, datetime

import pandas as pd

from .erp_gateway import ErpDataInputGateway


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo avg_price.parquet from ERP")
    parser.add_argument("--date-from", type=parse_date, default=parse_date((date.today() - __import__("datetime").timedelta(days=365)).isoformat()))
    parser.add_argument("--date-to", type=parse_date, default=parse_date(date.today().isoformat()))
    parser.add_argument("--output", type=str, default="/tmp/avg_price.parquet")
    args = parser.parse_args()

    gw = ErpDataInputGateway(args.date_from, args.date_to)
    prices = gw.daily_prices()

    avg = prices.groupby("product_id", as_index=False)["price"].mean()
    avg["price"] = avg["price"].round(2).astype("float32")
    avg.rename(columns={"price": "avg_price"}, inplace=True)

    avg.to_parquet(args.output, index=False, compression="snappy")

    print(f"Products: {len(avg)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
