import argparse
import gc
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .erp_gateway import ErpDataInputGateway, _resolve_shop_id
from .category_types import CATEGORY_GROUP, CATEGORY_SUBGROUP, CATEGORY_SUBSUBGROUP, CATEGORY_SUBSUBSUBGROUP, CATEGORY_SUBSUBSUBGROUPS, LEVEL_COLUMNS


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _resolve_category(category_id: str) -> tuple[str, int]:
    from autoorder.conections import category as cat_fn
    cats_df = cat_fn()

    from .category_types import ensure_mappings
    ensure_mappings(cats_df)

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo features.parquet from ERP")
    parser.add_argument("--shop-id", type=str, default="RT-000003")
    parser.add_argument("--category-id", type=str, default="00021634")
    parser.add_argument("--date-from", type=parse_date, default=parse_date((date.today() - timedelta(days=365)).isoformat()))
    parser.add_argument("--date-to", type=parse_date, default=parse_date(date.today().isoformat()))
    parser.add_argument("--output", type=str, default="/tmp/features.parquet")
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    shop_int = int(args.shop_id.split("-")[1])
    gw = ErpDataInputGateway(args.date_from, args.date_to, shop_id=shop_int)
    gw._shop_rt = args.shop_id

    # --- data fetched once outside the loop ---
    promo_defs = gw.promo()
    promo_links = gw.promo_links()
    weather_all = gw.weather()
    holidays_all = gw.holidays()
    cats = gw.category_hierarchy()
    cost_prices = gw.product_cost_prices()

    level_col, level_id = _resolve_category(args.category_id)

    writer = None
    total_rows = 0
    current = args.date_from

    while current <= args.date_to:
        month_end = (current.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        if month_end > args.date_to:
            month_end = args.date_to

        gw.start_date = current
        gw.end_date = month_end

        sales = gw.sales_stocks_daily()
        product_ids_in_scope = sales["product_id"].unique().tolist()

        prices = gw.daily_prices()
        if product_ids_in_scope:
            prices = prices[prices["product_id"].isin(product_ids_in_scope)]

        daily_price = prices.groupby(["shop_id", "product_id", "date"], as_index=False)["price"].mean()
        daily_price["price"] = daily_price["price"].round(1)

        # promo for current month only
        promo_active = promo_links.merge(
            promo_defs[["id", "date_from", "date_to"]],
            left_on="promo_id", right_on="id", how="inner",
        )
        promo_overlap = promo_active[
            (promo_active["date_from"] <= month_end) &
            (promo_active["date_to"] >= current)
        ]
        if not promo_overlap.empty:
            promo_overlap = promo_overlap.assign(
                date=promo_overlap.apply(
                    lambda r: pd.date_range(
                        max(r["date_from"], current),
                        min(r["date_to"], month_end),
                        freq="D",
                    ),
                    axis=1,
                ),
            )
            promo_month = promo_overlap.explode("date")
            promo_month["date"] = pd.to_datetime(promo_month["date"]).dt.date
            promo_month["is_promo"] = True
        else:
            promo_month = pd.DataFrame(columns=["shop_id", "product_id", "date", "is_promo"])

        promo_month = promo_month[["shop_id", "product_id", "date", "is_promo"]].drop_duplicates()
        if product_ids_in_scope:
            promo_month = promo_month[promo_month["product_id"].isin(product_ids_in_scope)]

        month_dates = pd.date_range(current, month_end, freq="D").date
        grid = pd.MultiIndex.from_product(
            [product_ids_in_scope, month_dates],
            names=["product_id", "date"],
        ).to_frame(index=False)
        grid["shop_id"] = args.shop_id

        df = grid.merge(sales, on=["shop_id", "product_id", "date"], how="left")
        df = df.merge(promo_month, on=["shop_id", "product_id", "date"], how="left")
        df["is_promo"] = df["is_promo"].fillna(False)

        df = df.merge(
            daily_price[["shop_id", "product_id", "date", "price"]],
            on=["shop_id", "product_id", "date"], how="left",
        )

        weather = weather_all[weather_all["date"].between(current, month_end)]
        holidays = holidays_all[holidays_all["date"].between(current, month_end)]
        df = df.merge(weather, on="date", how="left")
        df = df.merge(holidays, on="date", how="left")
        df = df.merge(cats, on="product_id", how="left")

        df["sales_qty"] = df["sales_qty"].fillna(0.0)
        df["stocs_qty"] = df["stocs_qty"].fillna(0.0)

        df = df.sort_values("date")
        df["price"] = df.groupby("product_id", sort=False)["price"].ffill()
        df["price"] = df.groupby("product_id", sort=False)["price"].bfill()

        df = df.merge(cost_prices, on="product_id", how="left")
        if "price_incoming" in df.columns:
            df.loc[df["price"].isna() & df["price_incoming"].notna(), "price"] = df["price_incoming"].round(1)
            df = df.drop(columns=["price_incoming"])

        df["has_stock"] = ((df["sales_qty"] > 0) | (df["stocs_qty"] > 0)).astype(bool)

        df["day"] = pd.to_datetime(df["date"]).dt.day.astype(np.int8)
        df["day_of_week"] = pd.to_datetime(df["date"]).dt.dayofweek.astype(np.int8)
        df["month"] = pd.to_datetime(df["date"]).dt.month.astype(np.int8)

        df["sales_qty"] = np.round(df["sales_qty"]).clip(0).astype(np.int32)
        df["price"] = df["price"].astype(np.float32)

        df = df.drop(columns=["stocs_qty"])

        for col in LEVEL_COLUMNS:
            if col in df.columns:
                df[col] = df[col].fillna(0).astype(np.int64)

        df = df[df[level_col] == level_id]

        if not df.empty:
            table = pa.Table.from_pandas(df, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(args.output, table.schema)
            writer.write_table(table)
            total_rows += len(df)

        print(f"  {current} — {month_end}: {len(df)} rows")

        del sales, prices, daily_price, promo_month, grid, df, weather, holidays
        gc.collect()

        current = month_end + timedelta(days=1)

    if writer:
        writer.close()

    print(f"Total rows: {total_rows}")
    print(f"Output: {args.output}")

    # --- generate category_map.json for API resolution ---
    print("Generating category_map.json...")
    from autoorder.conections import category as cat_fn
    cats_df = cat_fn()
    from .category_types import ensure_mappings
    ensure_mappings(cats_df)

    cat_index = cats_df.set_index("id").to_dict("index")
    import json as _json

    def _walk_cat(cid):
        p = []
        while cid and cid != "0" and cid in cat_index:
            p.insert(0, cat_index[cid]["name"])
            cid = cat_index[cid].get("parent_id", "0")
        return p

    MAPPINGS = {
        4: CATEGORY_GROUP,
        3: CATEGORY_SUBGROUP,
        2: CATEGORY_SUBSUBGROUP,
        1: CATEGORY_SUBSUBSUBGROUP,
        0: CATEGORY_SUBSUBSUBGROUPS,
    }

    cat_map = {}
    for cid in cat_index:
        path = _walk_cat(cid)
        if not path:
            continue
        level_idx = 4 - (len(path) - 1)
        if level_idx < 0 or level_idx > 4:
            continue
        cat_name = path[-1]
        mapping = MAPPINGS[level_idx]
        lid = mapping.get(cat_name, 0)
        if lid == 0:
            continue
        cat_map[cid] = {"level": level_idx, "level_id": int(lid)}

    map_path = Path(args.output).parent / "category_map.json"
    with open(map_path, "w") as f:
        _json.dump(cat_map, f, ensure_ascii=False, indent=2)
    print(f"Category map: {len(cat_map)} entries -> {map_path}")


if __name__ == "__main__":
    main()
