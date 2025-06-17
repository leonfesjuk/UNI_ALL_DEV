
import pandas as pd
from datetime import date
from typing import List, Dict

from api.helpers.loger import init_logger
from .helpers.data_retriever import get_all_base_data, filter_and_merge_base_data
from .helpers.calculator import calculate_recipient_need, calculate_donor_surplus
from .helpers.allocator import allocate_redistribution

my_logger = init_logger()

def redistribution_plan_generator(
    date_start: date, # This is analysis_start_date
    date_finish: date, # This is analysis_end_date
    days_of_analysis: int, # This is projection_days
    min_surplus_coefficient: float,
    donor_markets_ids: List[str],
    recipient_markets_ids: List[str],
    specific_product_ids: List[str],
    today_stocs_mode: bool = False # Added today_stocs_mode
) -> pd.DataFrame:
    """
    Generates a redistribution plan for surplus products between specified donor and recipient markets.

    Args:
        date_start (date): Start date for the historical sales analysis period.
        date_finish (date): End date for the historical sales analysis period.
        days_of_analysis (int): Number of days for future sales forecasting (projection period).
        min_surplus_coefficient (float): Multiplier to determine actual surplus for redistribution.
        donor_markets_ids (List[str]): List of shop IDs considered as donors.
        recipient_markets_ids (List[str]): List of shop IDs considered as recipients.
        specific_product_ids (List[str]): List of product IDs to include in the analysis.
        today_stocs_mode (bool): If True, uses today's stock for current levels; otherwise, uses yesterday's.

    Returns:
        pd.DataFrame: A DataFrame representing the redistribution plan, ready for Excel export.
    """
    my_logger.info("Starting redistribution_plan_generator.")

    # 1. Retrieve all necessary base data
    base_data = get_all_base_data(date_start, date_finish, days_of_analysis, today_stocs_mode) # Pass today_stocs_mode

    # 2. Filter and merge base data into a single DataFrame
    # This DataFrame will contain all relevant info for product-shop combinations
    base_merged_df = filter_and_merge_base_data(
        base_data=base_data,
        specific_product_ids=specific_product_ids,
        donor_markets_ids=donor_markets_ids,
        recipient_markets_ids=recipient_markets_ids,
        analysis_start_date=date_start, # Pass analysis_start_date
        analysis_end_date=date_finish,   # Pass analysis_end_date
        projection_days=days_of_analysis, # Pass projection_days
        current_stock_date=base_data['current_stock_date'] # Pass the actual date used for current stock
    )

    if base_merged_df.empty:
        my_logger.warning("Base merged DataFrame is empty after filtering. No plan to generate.")
        return pd.DataFrame()

    # 3. Calculate need for recipient shops
    # Apply to all rows, but 'needed_qty_recipient' will only be relevant for recipient shops
    base_merged_df = calculate_recipient_need(base_merged_df)

    # 4. Calculate surplus for donor shops
    # Apply to all rows, but 'surplus_qty_donor' will only be relevant for donor shops
    base_merged_df = calculate_donor_surplus(base_merged_df, min_surplus_coefficient)
    
    # 5. Allocate redistribution based on calculated needs and surpluses
    redistribution_plan_df = allocate_redistribution(base_merged_df)

    my_logger.info("redistribution_plan_generator finished.")
    return redistribution_plan_df
