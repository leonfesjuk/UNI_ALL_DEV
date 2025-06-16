
import pandas as pd
from datetime import date
from typing import List, Dict, Optional

# Import necessary functions from existing modules
from api.helpers.loger import init_logger
from autoorder.conections import shop_name
from .redistribution_logic import redistribution_plan_generator
from .helpers.category_hierarchy import get_products_by_category_names

my_logger = init_logger()

def redistribution_api_handler(
    date_start_str: str,
    date_finish_str: str,
    days_of_analysis: int,
    min_surplus_coefficient: float,
    donor_markets_ids: List[str],
    recipient_markets_ids: List[str],
    selected_lowest_categories_names: Optional[List[str]] = None, # Changed from IDs to names
    today_stocs_mode: bool = False,
    output_dir: Optional[str] = None
) -> pd.DataFrame:
    """
    Handles API requests for generating a redistribution plan.
    Filters products by category names and orchestrates the redistribution logic.

    Args:
        date_start_str (str): Start date as a string (YYYY-MM-DD).
        date_finish_str (str): End date as a string (YYYY-MM-DD).
        days_of_analysis (int): Number of days for future sales forecasting and analysis.
        min_surplus_coefficient (float): Multiplier to determine actual surplus for redistribution.
        donor_markets_ids (List[str]): List of shop IDs considered as donors.
        recipient_markets_ids (List[str]): List of shop IDs considered as recipients.
        selected_lowest_categories_names (Optional[List[str]]): List of category names selected by the user.
        today_stocs_mode (bool): If True, uses today's stock; otherwise, uses yesterday's stock.
        output_dir (Optional[str]): Directory where the Excel file should be saved.

    Returns:
        pd.DataFrame: A DataFrame representing the redistribution plan.
    """
    my_logger.info(f"API Handler: Received request for redistribution plan. "
                   f"Dates: {date_start_str}-{date_finish_str}, "
                   f"Days: {days_of_analysis}, Coeff: {min_surplus_coefficient}, "
                   f"Donors: {donor_markets_ids}, Recipients: {recipient_markets_ids}, "
                   f"Category names: {selected_lowest_categories_names}, Today_stocs_mode: {today_stocs_mode}")

    try:
        date_start = date.fromisoformat(date_start_str)
        date_finish = date.fromisoformat(date_finish_str)
    except ValueError:
        my_logger.error("Invalid date format. Expected YYYY-MM-DD.")
        return pd.DataFrame()

    specific_product_ids = []
    if selected_lowest_categories_names:
        my_logger.info(f"Filtering products by selected category names: {selected_lowest_categories_names}")

        # Use the helper function to get product IDs by category names
        # Filtering by group (level 0 = Відділ)
        specific_product_ids = get_products_by_category_names(selected_lowest_categories_names, target_level=0)

        if not specific_product_ids:
            my_logger.warning(f"No products found for the selected category names: {selected_lowest_categories_names}. Returning empty plan.")
            return pd.DataFrame()
        my_logger.info(f"Found {len(specific_product_ids)} products for the selected category names.")

    # Call the core redistribution logic
    redistribution_plan_df = redistribution_plan_generator(
        date_start=date_start,
        date_finish=date_finish,
        days_of_analysis=days_of_analysis,
        min_surplus_coefficient=min_surplus_coefficient,
        donor_markets_ids=donor_markets_ids,
        recipient_markets_ids=recipient_markets_ids,
        specific_product_ids=specific_product_ids,
        today_stocs_mode=today_stocs_mode
    )

    if redistribution_plan_df.empty:
        my_logger.warning("No redistribution plan generated.")
        return pd.DataFrame()
    
    my_logger.info("Redistribution plan generated successfully by core logic.")
    return redistribution_plan_df
