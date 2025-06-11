import pandas as pd
from typing import List, Dict, Optional

from api.helpers.loger import init_logger
from autoorder.conections import category, product

my_logger = init_logger()


def get_category_hierarchy_tree(target_level: int = 1) -> List[Dict]:
    """
    Retrieves the category hierarchy for frontend display.
    Returns ONLY unique groups (Відділи) - same as autoorder_m approach.

    Args:
        target_level (int): Not used, kept for API compatibility.
                           Always returns unique groups (level 0 = Відділ).

    Returns:
        List[Dict]: List of dictionaries containing unique group names.
    """
    my_logger.info(f"Fetching category hierarchy (unique groups only).")

    try:
        categories_df = category()

        if categories_df is None or categories_df.empty:
            my_logger.warning("No category data returned.")
            return []

        # Get products and build hierarchy using add_category_hierarchy (same as autoorder_m)
        products_df = product(status_exceptions=False)

        if products_df.empty:
            my_logger.warning("No products found.")
            return []

        # Use add_category_hierarchy to build hierarchy (same as autoorder_m)
        from api.helpers.categoey_column_maker import add_category_hierarchy
        categories_hierarchy = add_category_hierarchy(products_df, categories_df)

        # Filter out products without valid group
        categories_hierarchy = categories_hierarchy[
            categories_hierarchy['group'].notna() & 
            (categories_hierarchy['group'] != '')
        ].copy()

        if categories_hierarchy.empty:
            my_logger.warning("No products with valid category hierarchy found.")
            return []

        # Get unique groups (Відділи) - EXACTLY like autoorder_m
        # drop_duplicates by category_id first, then by group
        unique_groups_df = categories_hierarchy[['category_id', 'group']].drop_duplicates(subset=['category_id'])
        unique_groups_df = unique_groups_df[['group']].drop_duplicates(subset=['group'])
        unique_groups_df = unique_groups_df.sort_values('group').reset_index(drop=True)

        # Build result - each unique group with its own category_id as filtering_id
        hierarchy_records = []
        for _, row in unique_groups_df.iterrows():
            # Find the category_id for this group (first one encountered)
            group_category_id = categories_hierarchy[
                categories_hierarchy['group'] == row['group']
            ]['category_id'].iloc[0]
            
            hierarchy_records.append({
                'group': row['group'],
                'subgroup': '',
                'subsubgroup': '',
                'subsubsubgroup': '',
                'subsubsubgroups': '',
                'filtering_id': group_category_id,
            })

        my_logger.info(f"Successfully retrieved {len(hierarchy_records)} unique groups (Відділи).")
        return hierarchy_records

    except Exception as e:
        my_logger.error(f"Error fetching category hierarchy: {str(e)}")
        raise


def get_products_by_category_names(category_names: List[str], target_level: int = 1) -> List[str]:
    """
    Get product IDs filtered by category names at specified hierarchy level.
    
    Args:
        category_names (List[str]): List of category names to filter by.
        target_level (int): The hierarchy level to filter by.
                           0 = group (Відділ), 1 = subgroup (Категорія), 
                           2 = subsubgroup (Підкатегорія), etc.
                           Default is 1 (subgroup = 2nd level = Категорія).
    
    Returns:
        List[str]: List of product IDs that belong to the specified categories.
    """
    my_logger.info(f"Filtering products by category names at level {target_level}: {category_names}")
    
    try:
        products_full = product(status_exceptions=False)
        categories = category()
        
        if products_full.empty:
            my_logger.warning("No products found.")
            return []
        
        # Build category hierarchy
        from api.helpers.categoey_column_maker import add_category_hierarchy
        categories_hierarchy = add_category_hierarchy(products_full, categories)
        
        # Map target_level to column name
        level_columns = {
            0: 'group',        # Відділ
            1: 'subgroup',     # Категорія (2nd level)
            2: 'subsubgroup',  # Підкатегорія (3rd level)
            3: 'subsubsubgroup',  # 4th level
            4: 'subsubsubgroups'  # 5th level
        }
        
        filter_column = level_columns.get(target_level, 'subgroup')
        
        # Filter by specified level name
        filtered_products = categories_hierarchy[
            categories_hierarchy[filter_column].isin(category_names)
        ]
        
        specific_product_ids = filtered_products['id'].unique().tolist()
        
        my_logger.info(f"Found {len(specific_product_ids)} products for the specified categories at level {target_level} ({filter_column}).")
        return specific_product_ids
    
    except Exception as e:
        my_logger.error(f"Error filtering products by category names: {str(e)}")
        raise
