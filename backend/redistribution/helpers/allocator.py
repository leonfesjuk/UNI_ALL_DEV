import pandas as pd
import numpy as np

from api.helpers.loger import init_logger
from .calculator import custom_rounding_to_numb_pack

my_logger = init_logger()

def allocate_redistribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Implements the core redistribution allocation logic.

    Args:
        df (pd.DataFrame): Merged DataFrame containing 'product_id', 'shop_id', 'is_donor',
                           'is_recipient', 'needed_qty_recipient_rounded', 'surplus_qty_donor_rounded',
                           'numb_pack', and other relevant info.

    Returns:
        pd.DataFrame: A DataFrame with the final redistribution plan, including 'transfer_qty'.
                      Each row represents a transfer from a donor shop to a recipient shop for a product.
    """
    my_logger.info("Starting redistribution allocation.")

    # Filter for potential donors and recipients
    donors_df = df[df['is_donor'] == 1].copy()
    recipients_df = df[df['is_recipient'] == 1].copy()

    # We only care about product-shop combinations where there's actual surplus/need
    donors_with_surplus = donors_df[donors_df['surplus_qty_donor_rounded'] > 0]
    recipients_with_need = recipients_df[recipients_df['needed_qty_recipient_rounded'] > 0]

    if donors_with_surplus.empty or recipients_with_need.empty:
        my_logger.info("No donors with surplus or no recipients with need. No redistribution possible.")
        return pd.DataFrame()

    # Create a unique list of products that have both surplus and need
    products_with_potential = pd.Series(list(set(donors_with_surplus['product_id']).intersection(recipients_with_need['product_id'])))

    if products_with_potential.empty:
        my_logger.info("No products found that have both surplus and need. No redistribution possible.")
        return pd.DataFrame()

    # Initialize mutable quantities for allocation
    # Use dictionary for faster lookup/update during iteration
    current_surplus = donors_with_surplus.set_index(['product_id', 'shop_id'])['surplus_qty_donor_rounded'].to_dict()
    current_need = recipients_with_need.set_index(['product_id', 'shop_id'])['needed_qty_recipient_rounded'].to_dict()

    redistribution_plan_records = []

    # Iterate product by product
    for product_id in products_with_potential:
        my_logger.debug(f"Allocating for product_id: {product_id}")

        # Get relevant donors and recipients for this product
        product_donors = donors_with_surplus[donors_with_surplus['product_id'] == product_id].copy()
        product_recipients = recipients_with_need[recipients_with_need['product_id'] == product_id].copy()

        if product_donors.empty or product_recipients.empty:
            continue

        # Get the numb_pack for this product (assuming it's consistent across shops for a product)
        # It's safer to get numb_pack from the original df filtered by product_id
        numb_pack_val = df[df['product_id'] == product_id]['numb_pack'].iloc[0] # Get any numb_pack for this product

        # Create all possible (donor, recipient) pairs for this product
        potential_transfers = pd.merge(
            product_recipients[['shop_id', 'product_id']].rename(columns={'shop_id': 'recipient_shop_id'}),
            product_donors[['shop_id', 'product_id']].rename(columns={'shop_id': 'donor_shop_id'}),
            on='product_id',
            how='inner'
        )
        
        # Filter out self-transfers (where donor and recipient are the same shop)
        potential_transfers = potential_transfers[
            potential_transfers['donor_shop_id'] != potential_transfers['recipient_shop_id']
        ].copy()
        
        # Add current surplus/need values from the mutable dictionaries for sorting
        potential_transfers['current_unmet_need'] = potential_transfers.apply(
            lambda row: current_need.get((row['product_id'], row['recipient_shop_id']), 0), axis=1
        )
        potential_transfers['current_available_surplus'] = potential_transfers.apply(
            lambda row: current_surplus.get((row['product_id'], row['donor_shop_id']), 0), axis=1
        )

        # Filter out pairs where either need or surplus is already 0 (could happen due to previous product allocation)
        potential_transfers = potential_transfers[
            (potential_transfers['current_unmet_need'] > 0) & 
            (potential_transfers['current_available_surplus'] > 0)
        ].copy()

        if potential_transfers.empty:
            continue

        # Sort potential transfers based on priority:
        # 1. Recipient's unmet need (descending)
        # 2. Donor's available surplus (descending)
        # This sorting is refreshed after each allocation to allow multiple donors per recipient
        potential_transfers = potential_transfers.sort_values(
            by=['current_unmet_need', 'current_available_surplus'],
            ascending=[False, False]
        )

        # Perform allocation with dynamic re-sorting
        # Keep allocating until all recipients' needs are met or all donors are exhausted
        max_iterations = len(potential_transfers) * 2  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Re-calculate current need/surplus for sorting (values change after each allocation)
            potential_transfers['current_unmet_need'] = potential_transfers.apply(
                lambda row: current_need.get((row['product_id'], row['recipient_shop_id']), 0), axis=1
            )
            potential_transfers['current_available_surplus'] = potential_transfers.apply(
                lambda row: current_surplus.get((row['product_id'], row['donor_shop_id']), 0), axis=1
            )
            
            # Filter out pairs where either need or surplus is already 0
            potential_transfers = potential_transfers[
                (potential_transfers['current_unmet_need'] > 0) &
                (potential_transfers['current_available_surplus'] > 0)
            ].copy()
            
            if potential_transfers.empty:
                break
            
            # Re-sort to prioritize recipients with highest remaining need
            potential_transfers = potential_transfers.sort_values(
                by=['current_unmet_need', 'current_available_surplus'],
                ascending=[False, False]
            )
            
            # Get the top transfer candidate
            transfer_candidate = potential_transfers.iloc[0]
            
            prod_id = transfer_candidate['product_id']
            rec_shop_id = transfer_candidate['recipient_shop_id']
            don_shop_id = transfer_candidate['donor_shop_id']

            # Re-check if there's still need and surplus for this specific product-shop combination
            if current_need.get((prod_id, rec_shop_id), 0) <= 0 or \
               current_surplus.get((prod_id, don_shop_id), 0) <= 0:
                # Remove this pair and continue
                potential_transfers = potential_transfers[1:]
                continue

            available_from_donor = current_surplus.get((prod_id, don_shop_id), 0)
            needed_by_recipient = current_need.get((prod_id, rec_shop_id), 0)

            transfer_qty_raw = min(available_from_donor, needed_by_recipient)

            transfer_qty = custom_rounding_to_numb_pack(transfer_qty_raw, numb_pack_val)

            if transfer_qty > 0:
                # Add to plan
                redistribution_plan_records.append({
                    'product_id': prod_id,
                    'donor_shop_id': don_shop_id,
                    'recipient_shop_id': rec_shop_id,
                    'transfer_qty': transfer_qty,
                    'packing_multiplicity': numb_pack_val
                })

                # Update mutable quantities
                current_surplus[(prod_id, don_shop_id)] -= transfer_qty
                current_need[(prod_id, rec_shop_id)] -= transfer_qty

                my_logger.debug(f"Iteration {iteration}: Allocated {transfer_qty} of {prod_id} from {don_shop_id} to {rec_shop_id}. Donor surplus remaining: {current_surplus[(prod_id, don_shop_id)]}, Recipient need remaining: {current_need[(prod_id, rec_shop_id)]}")
            
            # Remove this pair from the list (will be re-added if still has surplus)
            potential_transfers = potential_transfers[1:]

    # Convert records to DataFrame
    if not redistribution_plan_records:
        return pd.DataFrame()

    redistribution_df = pd.DataFrame(redistribution_plan_records)

    # Merge back additional details for the report (product name, shop names, prices, categories etc.)
    # from the original df
    
    # Prepare donor and recipient info for merging
    # Select unique product_id and shop_id for donors and recipients from original df
    
    donor_shops_data = df[df['is_donor'] == 1].set_index(['product_id', 'shop_id']).drop_duplicates()
    recipient_shops_data = df[df['is_recipient'] == 1].set_index(['product_id', 'shop_id']).drop_duplicates()


    # Merge donor info
    redistribution_df = pd.merge(
        redistribution_df,
        donor_shops_data[['product_name', 'shop_name', 'current_stocks_qty', 'incoming_qty',
                          'surplus_qty_donor_rounded',
                          'suppliers_name', 'group', 'subgroup', 'subsubgroup', 'subsubsubgroup', 'subsubsubgroups']],
        left_on=['product_id', 'donor_shop_id'],
        right_index=True,
        how='left'
    ).rename(columns={
        'shop_name': 'donor_shop_name',
        'current_stocks_qty': 'current_stock_donor',
        'incoming_qty': 'incoming_qty_donor',
        'surplus_qty_donor_rounded': 'surplus_qty_donor_calculated',
        'group': 'department',
        'subgroup': 'category',
        'subsubgroup': 'subcategory',
        'subsubsubgroup': 'subsubcategory',
        'subsubsubgroups': 'group_hierarchy'
    })

    # Merge recipient info
    redistribution_df = pd.merge(
        redistribution_df,
        recipient_shops_data[['shop_name', 'current_stocks_qty', 'incoming_qty', 'needed_qty_recipient_rounded', 'sdp_no_promo']],
        left_on=['product_id', 'recipient_shop_id'],
        right_index=True,
        how='left'
    ).rename(columns={
        'shop_name': 'recipient_shop_name',
        'current_stocks_qty': 'current_stock_recipient',
        'incoming_qty': 'incoming_qty_recipient',
        'needed_qty_recipient_rounded': 'needed_qty_recipient_calculated',
        'sdp_no_promo': 'sdp_no_promo_recipient'
    })

    my_logger.info("Finished redistribution allocation. Resulting DataFrame head:")
    my_logger.info(redistribution_df.head())

    return redistribution_df
