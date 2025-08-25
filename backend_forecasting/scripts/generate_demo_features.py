import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from adapters.secondary.data.erp_gateway import ErpDataInputGateway
from config.category_types import (
    LEVEL_COLUMNS,
    CATEGORY_GROUP,
    CATEGORY_SUBGROUP,
    CATEGORY_SUBSUBGROUP,
    CATEGORY_SUBSUBSUBGROUP,
    CATEGORY_SUBSUBSUBGROUPS,
)
from config.promo_types import PROMO_TYPES


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _resolve_category(category_id: str) -> tuple[str, int]:
    from autoorder.conections import category as cat_fn

    cats_df = cat_fn()
    row = cats_df[cats_df["id"] == category_id]
    if row.empty:
        raise ValueError(f"Category {category_id} not found")

    cat_dict = cats_df.set_index("id").to_dict("index")

    path = []
    cid = category_id
    while cid and cid != "0" and cid in cat_dict:
        path.insert(0, cat_dict[cid]["name"])
        cid = cat_dict[cid].get("parent_id", "0")

    if not path:
        raise ValueError(f"Cannot resolve path for category {category_id}")

    depth = len(path) - 1
    level_idx = 4 - depth

    MAPPINGS = {
        4: CATEGORY_GROUP,
        3: CATEGORY_SUBGROUP,
        2: CATEGORY_SUBSUBGROUP,
        1: CATEGORY_SUBSUBSUBGROUP,
        0: CATEGORY_SUBSUBSUBGROUPS,
    }

    cat_name = path[-1]
    mapping = MAPPINGS[level_idx]
    level_id = mapping.get(cat_name, 0)
    if level_id == 0:
        raise ValueError(
            f"Category '{cat_name}' (id={category_id}) not found in level {level_idx} mapping"
        )

    return LEVEL_COLUMNS[level_idx], level_id


def generate_features_dataset(
    shop_id: str,
    category_id: str,
    date_from: date,
    date_to: date,
    output: str = "data/demo/features.parquet",
) -> dict:
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    shop_int = int(shop_id.split("-")[1])
    gw = ErpDataInputGateway(date_from, date_to, shop_id=shop_int)
    gw._shop_rt = shop_id

    promo_defs = gw.promo()
    promo_links = gw.promo_links()
    weather_all = gw.weather()
    holidays_all = gw.holidays()
    cats = gw.category_hierarchy()

    promo_active = promo_links.merge(
        promo_defs[["id", "type_id", "date_from", "date_to"]],
        left_on="promo_id",
        right_on="id",
        how="inner",
    )

    promo_daily = promo_active.assign(
        date=promo_active.apply(
            lambda r: pd.date_range(r["date_from"], r["date_to"], freq="D"),
            axis=1,
        ),
    ).explode("date")
    promo_daily["date"] = pd.to_datetime(promo_daily["date"]).dt.date
    promo_daily = promo_daily[
        ["shop_id", "product_id", "date", "type_id", "promo_id"]
    ].drop_duplicates()

    level_col, level_id = _resolve_category(category_id)
    writer = None
    total_rows = 0
    current = date_from

    while current <= date_to:
        month_end = (current.replace(day=1) + timedelta(days=32)).replace(
            day=1
        ) - timedelta(days=1)
        if month_end > date_to:
            month_end = date_to

        gw.start_date = current
        gw.end_date = month_end

        sales = gw.sales_stocks_daily()

        product_ids_in_scope = sales["product_id"].unique().tolist()

        prices = gw.daily_prices()
        if product_ids_in_scope:
            prices = prices[prices["product_id"].isin(product_ids_in_scope)]

        daily_price = prices.groupby(["shop_id", "product_id", "date"], as_index=False)[
            "price"
        ].mean()

        promo_month = promo_daily[promo_daily["date"].between(current, month_end)]
        if product_ids_in_scope:
            promo_month = promo_month[
                promo_month["product_id"].isin(product_ids_in_scope)
            ]

        df = sales.merge(promo_month, on=["shop_id", "product_id", "date"], how="left")
        df["is_promo"] = df["type_id"].notna()
        df["promo_type_id"] = df["type_id"].map(PROMO_TYPES).fillna(0).astype(int)
        df = df.drop(columns=["type_id"])

        df = df.merge(
            daily_price[["shop_id", "product_id", "date", "price"]],
            on=["shop_id", "product_id", "date"],
            how="left",
        )

        df["reg_price"] = df["price"].where(~df["is_promo"])
        df["reg_price"] = df.groupby("product_id")["reg_price"].ffill()
        df["reg_price"] = df.groupby("product_id")["reg_price"].bfill()
        promo_price_by_promo = (
            df[df["is_promo"] & df["price"].notna()]
            .groupby(["product_id", "promo_id"])["price"]
            .mean()
            .rename("promo_fill")
        )
        df = df.merge(promo_price_by_promo, on=["product_id", "promo_id"], how="left")
        df["price"] = np.where(
            df["is_promo"], df["promo_fill"].fillna(0), df["reg_price"]
        )
        df["price"] = df.groupby("product_id")["price"].ffill().fillna(0)
        df = df.drop(columns=["reg_price", "promo_fill", "promo_id"])

        weather = weather_all[weather_all["date"].between(current, month_end)]
        holidays = holidays_all[holidays_all["date"].between(current, month_end)]
        df = df.merge(weather, on="date", how="left")
        df = df.merge(holidays, on="date", how="left")
        df = df.merge(cats, on="product_id", how="left")

        df["has_stock"] = ((df["sales_qty"] > 0) | (df["stocs_qty"] > 0)).astype(
            np.int8
        )

        df["day"] = pd.to_datetime(df["date"]).dt.day.astype(np.int8)
        df["day_of_week"] = pd.to_datetime(df["date"]).dt.dayofweek.astype(np.int8)
        df["month"] = pd.to_datetime(df["date"]).dt.month.astype(np.int8)

        df["sales_qty"] = np.round(df["sales_qty"]).clip(0).astype(np.int32)
        df["price"] = df["price"].round(1).astype(np.float32)

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

        print(f"  {current} — {month_end}: {len(df)} rows")

        current = month_end + timedelta(days=1)

    if writer:
        writer.close()

    return {"rows": total_rows, "output": output}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate demo features.parquet from ERP"
    )
    parser.add_argument("--shop-id", type=str, required=True)
    parser.add_argument("--category-id", type=str, required=True)
    parser.add_argument("--date-from", type=parse_date, required=True)
    parser.add_argument("--date-to", type=parse_date, required=True)
    parser.add_argument("--output", type=str, default="data/demo/features.parquet")
    args = parser.parse_args()

    result = generate_features_dataset(
        shop_id=args.shop_id,
        category_id=args.category_id,
        date_from=args.date_from,
        date_to=args.date_to,
        output=args.output,
    )

    print(f"Total rows: {result['rows']}")
    print(f"Output: {result['output']}")


if __name__ == "__main__":
    main()
