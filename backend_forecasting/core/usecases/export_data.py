from datetime import date

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config.category_types import LEVEL_COLUMNS


def export_to_parquet(
    df: pd.DataFrame,
    shop_id: int,
    level: int,
    level_id: int,
    last_date: date,
    output_dir: str,
) -> str:
    level_col = LEVEL_COLUMNS[level]
    mask = (df['shop_id'] == shop_id) & (df[level_col] == level_id)
    subset = df[mask].copy()

    filename = f'{shop_id}_{level}_{level_id}_{last_date.isoformat()}.parquet'
    path = f'{output_dir}/{filename}'

    table = pa.Table.from_pandas(subset)
    pq.write_table(table, path, compression='snappy')
    return path
