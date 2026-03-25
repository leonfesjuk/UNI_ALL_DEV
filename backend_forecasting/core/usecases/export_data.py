"""Export forecasting datasets to parquet files."""

from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def export_to_parquet(
    df: pd.DataFrame,
    shop_id: str,
    category_id: str,
    last_date: date,
    output_dir: str,
) -> str:
    """Write a dataframe to <output_dir>/<shop>_<category>_<date>.parquet."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"{shop_id}_{category_id}_{last_date.isoformat()}.parquet"
    path = str(Path(output_dir) / filename)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, path, compression="snappy")
    return path
