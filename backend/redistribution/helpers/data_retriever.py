
import pandas as pd
from datetime import date, timedelta

# Import necessary functions from existing modules
from api.helpers.loger import init_logger
from autoorder.conections import (
    matrix, product, season_names, stoks, shop_name,
    incoming_products, category, productprices, warhause_id, warhauses_smal
)
from autoorder.analysis import sdp, future_promo, suplaer_id
from api.helpers.categoey_column_maker import add_category_hierarchy

my_logger = init_logger()

def get_all_base_data(analysis_start_date: date, analysis_end_date: date, projection_days: int, today_stocs_mode: bool) -> dict:
    """
    Retrieves all necessary base data from the database using existing autoorder functions.

    Args:
        analysis_start_date (date): Start date for historical sales analysis.
        analysis_end_date (date): End date for historical sales analysis.
        projection_days (int): Number of days for future demand projection.
        today_stocs_mode (bool): If True, uses today's stock for current levels; otherwise, uses yesterday's.

    Returns:
        dict: A dictionary containing various DataFrames:
              'shops', 'products_full', 'categories_hierarchy', 'matrix', 'sdp_data',
              'future_promo', 'stocks', 'incoming_products', 'prices', 'suppliers',
              'current_stock_date' (the date for which current stocks were fetched).
    """
    my_logger.info(f"Starting data retrieval for redistribution. Analysis Period: {analysis_start_date}-{analysis_end_date}, Projection Days: {projection_days}, Today Stock Mode: {today_stocs_mode}")

    # Determine the specific date for fetching current stocks (yesterday or today)
    system_today = date.today()
    if today_stocs_mode:
        current_stock_date = system_today
    else:
        current_stock_date = system_today - timedelta(days=1)
    my_logger.info(f"Using {current_stock_date} for current stock data.")

    # Shops and categories
    shops = shop_name()
    all_warehouses_to_exclude = [warhause_id] + warhauses_smal
    shops = shops[~shops['id'].isin(all_warehouses_to_exclude)]
    products_full = product(status_exceptions=False)
    categories = category()
    categories_hierarchy = add_category_hierarchy(products_full, categories)

    # Matrix data (all active products in matrix)
    matrix_data = matrix(1)

    # SDP data (historical sales analysis period)
    sdp_data, _ = sdp(analysis_start_date, analysis_end_date)

    # Future promotions (projection period, starting from analysis_start_date to capture all relevant active promos)
    future_promos_data = future_promo(analysis_start_date, projection_days)

    # Stocks (fetch *only* for current_stock_date)
    stocks = stoks(current_stock_date, current_stock_date)

    # Incoming products (fetch for the projection period, starting from analysis_end_date to match autoorder_m)
    # This range goes from analysis_end_date up to analysis_end_date + projection_days
    raw_incoming_products_data = incoming_products()

    # Ensure the date_income column is in datetime format before using .dt accessor
    raw_incoming_products_data['date_income'] = pd.to_datetime(raw_incoming_products_data['date_income'])

    incoming_products_data = raw_incoming_products_data[
        (raw_incoming_products_data['date_income'].dt.date >= analysis_end_date) &
        (raw_incoming_products_data['date_income'].dt.date <= (analysis_end_date + timedelta(days=projection_days)))
    ].copy()

    # Prices (using current_stock_date, similar to how autoorder.py would get latest for 'yesterday')
    prices = productprices(current_stock_date)

    # Suppliers
    suppliers = suplaer_id()

    my_logger.info("Finished base data retrieval.")

    return {
        'shops': shops,
        'products_full': products_full,
        'categories_hierarchy': categories_hierarchy,
        'matrix': matrix_data,
        'sdp_data': sdp_data,
        'future_promo': future_promos_data,
        'stocks': stocks,
        'incoming_products': incoming_products_data,
        'prices': prices,
        'suppliers': suppliers,
        'current_stock_date': current_stock_date # Return this date for filter_and_merge_base_data
    }

def filter_and_merge_base_data(
    base_data: dict,
    specific_product_ids: list[str],
    donor_markets_ids: list[str],
    recipient_markets_ids: list[str],
    analysis_start_date: date, # Used for logging/context
    analysis_end_date: date,   # Used for logging/context
    projection_days: int,      # Used for next_no_promo_days calculation
    current_stock_date: date   # The actual date for current stocks
) -> pd.DataFrame:
    """
    Filters and merges base data into a single DataFrame for further processing.

    Args:
        base_data (dict): Dictionary of raw DataFrames from get_all_base_data.
        specific_product_ids (list[str]): List of product IDs to filter by.
        donor_markets_ids (list[str]): List of donor shop IDs.
        recipient_markets_ids (list[str]): List of recipient shop IDs.
        analysis_start_date (date): Start date of the historical analysis period.
        analysis_end_date (date): End date of the historical analysis period.
        projection_days (int): Number of days for future demand projection.
        current_stock_date (date): The specific date for which current stocks were fetched.

    Returns:
        pd.DataFrame: Merged and filtered DataFrame containing all relevant information.
    """
    my_logger.info(f"Starting filtering and merging of base data for analysis {analysis_start_date}-{analysis_end_date}, projection {projection_days} days, current stock on {current_stock_date}.")

    shops = base_data['shops']
    products_full = base_data['products_full']
    categories_hierarchy = base_data['categories_hierarchy']
    matrix_data = base_data['matrix']
    sdp_data = base_data['sdp_data']
    future_promo_data = base_data['future_promo']
    stocks = base_data['stocks'] # Already filtered for current_stock_date
    incoming_products_data = base_data['incoming_products'] # Already filtered for projection period
    prices = base_data['prices']
    suppliers = base_data['suppliers']

    # --- Initial Filtering ---
    # Filter products
    if specific_product_ids:
        products_filtered = products_full[products_full['id'].isin(specific_product_ids)].copy()
    else:
        products_filtered = products_full.copy() 

    if products_filtered.empty:
        my_logger.warning("No products found after filtering. Returning empty DataFrame.")
        return pd.DataFrame()

    # Filter shops to only include donors and recipients
    all_target_shop_ids = list(set(donor_markets_ids + recipient_markets_ids))
    shops_filtered = shops[shops['id'].isin(all_target_shop_ids)].copy()
    if shops_filtered.empty:
        my_logger.warning("No shops found after filtering donors/recipients. Returning empty DataFrame.")
        return pd.DataFrame()

    # --- Merging Data ---
    products_filtered = products_filtered.rename(columns={'id': 'product_id'})

    base_df = pd.merge(
        matrix_data,
        products_filtered[['product_id', 'name', 'status', 'season', 'category_id', 'supplier_id', 'productcategory_id']],
        on='product_id',
        how='inner'
    )
    base_df = base_df.rename(columns={'name': 'product_name'})

    base_df = base_df[base_df['shop_id'].isin(all_target_shop_ids)].copy()
    if base_df.empty:
        my_logger.warning("No relevant product-shop combinations after filtering. Returning empty DataFrame.")
        return pd.DataFrame()

    base_df = pd.merge(base_df, shops_filtered[['id', 'name']], left_on='shop_id', right_on='id', how='left')
    base_df = base_df.drop(columns=['id']).rename(columns={'name': 'shop_name'})

    base_df = pd.merge(
        base_df,
        sdp_data,
        on=['product_id', 'shop_id'],
        how='left'
    ).fillna(0)


    # Merge future promos
    future_promos_agg = future_promo_data.groupby(['shop_id', 'product_id'])['next_promo_days'].sum().reset_index()
    base_df = pd.merge(
        base_df,
        future_promos_agg,
        on=['shop_id', 'product_id'],
        how='left'
    ).fillna(0)
    
    base_df['next_promo_days'] = base_df['next_promo_days'].astype(int)
    base_df['next_no_promo_days'] = projection_days - base_df['next_promo_days'] 
    base_df['next_no_promo_days'] = base_df['next_no_promo_days'].clip(lower=0).astype(int)

    # Merge stocks (stocks DF already contains only for current_stock_date)
    # Use 'dt' column from stocks which is the current_stock_date
    if stocks.empty:
        my_logger.warning(f"No current stocks found for date {current_stock_date}. Initializing 'current_stocks_qty' to 0.")
        base_df['current_stocks_qty'] = 0
    else:
        current_stocks_sum = stocks.groupby(['shop_id', 'product_id'])['qty'].sum().reset_index()
        base_df = pd.merge(
            base_df,
            current_stocks_sum.rename(columns={'qty': 'current_stocks_qty'}),
            on=['shop_id', 'product_id'],
            how='left'
        ).fillna(0)
    
    # Merge incoming products (incoming_products_data already filtered for projection period)
    if incoming_products_data.empty:
        my_logger.warning(f"No relevant incoming products found for projection period. Initializing 'incoming_qty' to 0.")
        base_df['incoming_qty'] = 0
    else:
        incoming_products_sum = incoming_products_data.groupby(['shop_id', 'product_id'])['income_qty'].sum().reset_index()
        base_df = pd.merge(
            base_df,
            incoming_products_sum,
            on=['shop_id', 'product_id'],
            how='left'
        ).fillna(0)

    # Prices (latest available price before or on current_stock_date)
    prices['date'] = pd.to_datetime(prices['date'])
    prices_latest = prices[prices['date'].dt.date <= current_stock_date].sort_values('date', ascending=False).drop_duplicates(subset=['product_id'], keep='first')
    base_df = pd.merge(
        base_df,
        prices_latest[['product_id', 'price_incoming', 'price_retail']],
        on='product_id',
        how='left'
    ).fillna(0)

    # Add suppliers
    suppliers_grouped = suppliers.groupby('product_id')['suppliers_name'].apply(lambda x: '/'.join(x)).reset_index()
    base_df = pd.merge(
        base_df,
        suppliers_grouped,
        on='product_id',
        how='left'
    ).fillna('')

    # Add category hierarchy
    categories_hierarchy_renamed = categories_hierarchy.rename(columns={'id': 'product_id'})
    hierarchy_cols = ['product_id', 'group', 'subgroup', 'subsubgroup', 'subsubsubgroup', 'subsubsubgroups']

    categories_hierarchy_filtered = categories_hierarchy_renamed[
        categories_hierarchy_renamed['product_id'].isin(base_df['product_id'].unique())
    ][hierarchy_cols].drop_duplicates(subset=['product_id'])

    base_df = pd.merge(
        base_df,
        categories_hierarchy_filtered,
        on='product_id',
        how='left'
    ).fillna('')

    base_df['is_donor'] = base_df['shop_id'].isin(donor_markets_ids).astype(int)
    base_df['is_recipient'] = base_df['shop_id'].isin(recipient_markets_ids).astype(int)
    
    my_logger.info("Finished filtering and merging base data. Resulting DataFrame head:")
    my_logger.info(base_df.head())
    my_logger.info(f"Resulting DataFrame shape: {base_df.shape}")

    return base_df
