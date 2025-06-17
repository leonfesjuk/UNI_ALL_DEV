import pandas as pd
import numpy as np
from datetime import date, timedelta

#from api.helpers.loger import init_logger # Not strictly needed here, will use logger from main
#my_logger = init_logger()

def custom_rounding_to_numb_pack(qty: float, numb_pack: int) -> int:
    """
    Rounds a given quantity to the nearest multiple of numb_pack.
    This function exactly replicates the custom_rounding logic from autoorder_m/base_table.py.
    
    Args:
        qty: Quantity to round
        numb_pack: Packing multiplicity
    
    Returns:
        Rounded quantity to nearest multiple of numb_pack
    """
    if numb_pack <= 0:
        numb_pack = 1  # Avoid division by zero

    if qty <= 0:
        return 0

    # Replicate exact logic from autoorder_m/base_table.py (lines 23-26)
    # If remainder > half of pack, round up (ceil)
    # Otherwise round down (floor)
    if (qty % numb_pack) > (numb_pack / 2):
        return int(np.ceil(qty / numb_pack) * numb_pack)
    else:
        return int(np.floor(qty / numb_pack) * numb_pack)


def calculate_recipient_need(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the 'needed_qty_recipient' for recipient shops based on autoorder_m logic.
    This function precisely replicates the logic for 'pure_need_items_insure' from base_table.py.

    Args:
        df (pd.DataFrame): Merged DataFrame containing relevant data for recipient shops.
                           Must include 'sdp_no_promo', 'sdp_promo', 'next_promo_days',
                           'next_no_promo_days', 'insur_balance', 'current_stocks_qty',
                           'incoming_qty', 'numb_pack', 'days_no_promo', 'days_promo'.

    Returns:
        pd.DataFrame: DataFrame with 'needed_qty_recipient' and 'needed_qty_recipient_rounded' columns added.
    """
    # Ensure relevant columns are numeric, filling any unexpected NaNs with 0
    for col in ['sdp_no_promo', 'sdp_promo', 'next_promo_days', 'next_no_promo_days',
                'insur_balance', 'current_stocks_qty', 'incoming_qty', 'numb_pack',
                'days_no_promo', 'days_promo']:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate projected demand from SDPs and future days
    df['projected_demand_from_sdp'] = (df['sdp_no_promo'] * df['next_no_promo_days']) + \
                                      (df['sdp_promo'] * df['next_promo_days'])

    # Replicate 'need_items' logic exactly from base_table.py (line 139-150)
    df['total_historical_sdp_days'] = df['days_no_promo'] + df['days_promo']

    df['need_items'] = np.where(
        df['total_historical_sdp_days'] == 0,
        0,
        np.where(
            (df['sdp_no_promo'] == 0) & (df['sdp_promo'] == 0),
            df['insur_balance'],
            np.where(
                df['total_historical_sdp_days'] <= 2,
                df['insur_balance'] * 2,
                df['sdp_no_promo'] * df['next_no_promo_days'] + df['sdp_promo'] * df['next_promo_days']
            )
        )
    )

    # Replicate 'mask_next_promo' logic from base_table.py (line 154)
    # This determines which SDP to use for current stock consideration
    df['mask_next_promo'] = np.where(df['next_promo_days'] > 0, 
                                     df['sdp_promo'], 
                                     df['sdp_no_promo'])

    # Replicate 'mask_stocs_income' logic from base_table.py (line 156-157)
    # This adjusts current stock by subtracting expected promo sales
    df['mask_stocs_income'] = np.where(
        (df['current_stocks_qty'] + df['incoming_qty'] - df['mask_next_promo']) > 0,
        (df['current_stocks_qty'] + df['incoming_qty'] - df['mask_next_promo']),
        0
    )

    # Replicate 'pure_need_items' logic from base_table.py (line 158-160)
    df['pure_need_items'] = np.where(
        df['need_items'] - df['mask_stocs_income'] > 0,
        df['need_items'] - df['mask_stocs_income'],
        0
    )

    # Replicate 'adjusted_total_demand' logic exactly from base_table.py (line 165-171)
    df['adjusted_total_demand'] = np.where(
        (df['need_items'] == df['insur_balance']) &
        (df['sdp_no_promo'] == 0) & (df['sdp_promo'] == 0) &
        (df['total_historical_sdp_days'] > 0),
        df['insur_balance'],
        df['need_items'] + df['insur_balance']
    )

    # Final 'pure_need_items_insure' calculation exactly from base_table.py (line 172)
    # This is the final need calculation
    df['needed_qty_recipient'] = np.maximum(0, df['adjusted_total_demand'] - (df['current_stocks_qty'] + df['incoming_qty']))

    # Apply rounding
    df['needed_qty_recipient_rounded'] = df.apply(
        lambda row: custom_rounding_to_numb_pack(row['needed_qty_recipient'], row['numb_pack']), axis=1
    )
    df['needed_qty_recipient_rounded'] = df['needed_qty_recipient_rounded'].astype(int)

    return df


def calculate_donor_surplus(df: pd.DataFrame, min_surplus_coefficient: float) -> pd.DataFrame:
    """
    Calculates the 'surplus_qty_donor' for donor shops.

    Args:
        df (pd.DataFrame): Merged DataFrame containing relevant data for donor shops.
                           Must include 'sdp_no_promo', 'sdp_promo', 'next_promo_days',
                           'next_no_promo_days', 'insur_balance', 'current_stocks_qty',
                           'incoming_qty', 'numb_pack'.
        min_surplus_coefficient (float): Multiplier for required stock to define actual surplus.

    Returns:
        pd.DataFrame: DataFrame with 'surplus_qty_donor' and 'surplus_qty_donor_rounded' columns added.
    """
    # Ensure relevant columns are numeric, filling any unexpected NaNs with 0
    for col in ['sdp_no_promo', 'sdp_promo', 'next_promo_days', 'next_no_promo_days', 
                'insur_balance', 'current_stocks_qty', 'incoming_qty', 'numb_pack']:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Calculate forecasted sales for the analysis period
    # Use next_no_promo_days for sdp_no_promo and next_promo_days for sdp_promo
    df['forecasted_sales_donor'] = (df['sdp_no_promo'] * df['next_no_promo_days']) + \
                                   (df['sdp_promo'] * df['next_promo_days'])

    # Required stock for the period including safety stock
    df['required_stock_donor'] = df['forecasted_sales_donor'] + df['insur_balance']
    df['required_stock_donor'] = df['required_stock_donor'].clip(lower=0)

    # Current total available stock
    df['current_total_available_donor'] = df['current_stocks_qty'] + df['incoming_qty']

    # Apply min_surplus_coefficient to determine actual available surplus for redistribution
    # A product is considered surplus if potential_surplus > 0 AND
    # current_total_available_donor > (required_stock_donor * min_surplus_coefficient)
    
    # Calculate the threshold for considering stock as surplus
    df['surplus_threshold'] = df['required_stock_donor'] * min_surplus_coefficient
    
    df['surplus_qty_donor'] = np.where(
        (df['current_total_available_donor'] > df['surplus_threshold']),
        df['current_total_available_donor'] - df['surplus_threshold'], # Surplus is the amount *above* the threshold
        0
    )
    df['surplus_qty_donor'] = df['surplus_qty_donor'].clip(lower=0) # Ensure no negative surplus

    # Apply rounding for the final order, but the base surplus is float
    df['surplus_qty_donor_rounded'] = df.apply(
        lambda row: custom_rounding_to_numb_pack(row['surplus_qty_donor'], row['numb_pack']), axis=1
    )
    df['surplus_qty_donor_rounded'] = df['surplus_qty_donor_rounded'].astype(int)

    return df
