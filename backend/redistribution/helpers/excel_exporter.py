
import pandas as pd
from datetime import datetime
import os

from api.helpers.loger import init_logger

my_logger = init_logger()


def format_redistribution_plan(df: pd.DataFrame) -> pd.DataFrame:
    """
    Formats the redistribution plan DataFrame with proper column order and Ukrainian names.
    
    Args:
        df (pd.DataFrame): The raw redistribution plan DataFrame.
    
    Returns:
        pd.DataFrame: Formatted DataFrame ready for export.
    """
    if df.empty:
        my_logger.warning("DataFrame is empty, nothing to format.")
        return df

    my_logger.info("Formatting redistribution plan with Ukrainian column names.")

    # Define column order for the report (logical order, without prices)
    # transfer_qty is LAST - it's the main info for shipping
    report_columns = [
        # Category hierarchy (first - for easy grouping/filtering)
        'department', 'category', 'subcategory', 'subsubcategory', 'group_hierarchy',
        # Product info
        'product_id', 'product_name', 'suppliers_name',
        # Donor info
        'donor_shop_id', 'donor_shop_name', 'current_stock_donor', 'incoming_qty_donor', 'surplus_qty_donor_calculated',
        # Recipient info
        'recipient_shop_id', 'recipient_shop_name', 'current_stock_recipient', 'incoming_qty_recipient', 'needed_qty_recipient_calculated', 'sdp_no_promo_recipient',
        # Packing info
        'packing_multiplicity',
        # Transfer info (LAST - most important for shipping)
        'transfer_qty'
    ]

    # Filter and reorder columns
    # Ensure all report_columns exist, if not, fill with placeholder to avoid errors
    for col in report_columns:
        if col not in df.columns:
            df[col] = '' # Add missing columns as empty strings or NaN

    df_export = df[report_columns].copy()

    # Rename columns to Ukrainian for the report
    df_export = df_export.rename(columns={
        # Category hierarchy
        'department': 'Відділ',
        'category': 'Категорія',
        'subcategory': 'Підкатегорія',
        'subsubcategory': 'Підпідкатегорія',
        'group_hierarchy': 'Група',
        # Product info
        'product_id': 'Код товару',
        'product_name': 'Найменування',
        'suppliers_name': 'Постачальник',
        # Donor info
        'donor_shop_id': 'Код магазину-донора',
        'donor_shop_name': 'Магазин-донор',
        'current_stock_donor': 'Поточний залишок донора, шт.',
        'incoming_qty_donor': 'Надходження до донора, шт.',
        'surplus_qty_donor_calculated': 'Розрахований надлишок донора, шт.',
        # Recipient info
        'recipient_shop_id': 'Код магазину-реципієнта',
        'recipient_shop_name': 'Магазин-реципієнт',
        'current_stock_recipient': 'Поточний залишок реципієнта, шт.',
        'incoming_qty_recipient': 'Надходження до реципієнта, шт.',
        'needed_qty_recipient_calculated': 'Розрахована потреба реципієнта, шт.',
        'sdp_no_promo_recipient': 'СДП без промо реципієнта, шт.',
        # Packing info
        'packing_multiplicity': 'Кратність пакування, шт.',
        # Transfer info (LAST - most important for shipping)
        'transfer_qty': 'Кількість для переміщення, шт.'
    })

    my_logger.info("Redistribution plan formatted successfully.")
    return df_export
