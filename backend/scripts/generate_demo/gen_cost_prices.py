import argparse
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cost_prices.parquet from ERP")
    parser.add_argument("--date-to", type=parse_date, default=date.today())
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--features", type=str, default="/tmp/features.parquet")
    parser.add_argument("--output", type=str, default="/tmp/cost_prices.parquet")
    args = parser.parse_args()

    date_from = args.date_to - timedelta(days=args.months * 30)

    try:
        from .erp_gateway import ErpDataInputGateway

        gw = ErpDataInputGateway(date_from, args.date_to)
        cost_prices = gw.product_cost_prices()

        cost_prices["product_id"] = cost_prices["product_id"].apply(
            lambda x: f"{int(x):08d}" if pd.notna(x) else x
        )

        print(f"ERP: {len(cost_prices)} products")

    except Exception as e:
        print(f"ERP unavailable ({e}), generating simulated cost_prices from features...")

        features = pd.read_parquet(args.features)
        product_ids = features["product_id"].unique()

        rng = np.random.default_rng(42)
        costs = []
        for pid in product_ids:
            cost_price = round(rng.uniform(30, 400), 2)
            costs.append({"product_id": str(pid), "price_incoming": cost_price})

        cost_prices = pd.DataFrame(costs)

        print(f"Simulated: {len(cost_prices)} products")

    cost_prices.to_parquet(args.output, index=False, compression="snappy")
    print(f"Output: {args.output}")
    print(cost_prices.head())


if __name__ == "__main__":
    main()
