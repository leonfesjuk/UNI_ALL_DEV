from fastapi.responses import JSONResponse
import pandas as pd
from autoorder.connections import product_choose, retry_on_operational_error, category
from autoorder.analysis import abc_analysis_all, sdp, promotions
from api.helpers.loger import init_logger

my_logger = init_logger()


def add_category_hierarchy(df_products: pd.DataFrame, df_categories: pd.DataFrame) -> pd.DataFrame:
    """
    Adds category hierarchy columns (group, subgroup, etc.) to a product DataFrame based on
    category IDs and a category hierarchy DataFrame.

    Args:
        df_products: DataFrame with product information, including 'id', 'name', 'status', 'category_id'.
        df_categories: DataFrame with category hierarchy information, including 'id', 'name', 'parent_id'.

    Returns:
        DataFrame with the original product information and added category hierarchy columns
        ('group', 'subgroup', 'subsubgroup', 'subsubsubgroup').
        Returns the original df_products if df_categories is empty or None.
        Returns the original df_products if df_products is empty or None.
    """
    if df_categories is None or df_categories.empty:
        my_logger.warning("df_categories is empty or None. Returning original df_products.")
        return df_products

    if df_products is None or df_products.empty:
        my_logger.warning("df_products is empty or None. Returning original df_products.")
        return df_products

    category_dict = df_categories.set_index('id').to_dict('index')

    def get_category_hierarchy(category_id):
        hierarchy = []
        current_id = category_id
        while current_id is not None and current_id in category_dict:
            hierarchy.insert(0, category_dict[current_id]['name'])
            current_id = category_dict[current_id]['parent_id']
        return hierarchy

    df_products['category_hierarchy'] = df_products['category_id'].apply(get_category_hierarchy)

    df_products['group'] = df_products['category_hierarchy'].apply(lambda x: x[0] if len(x) > 0 else None)
    df_products['subgroup'] = df_products['category_hierarchy'].apply(lambda x: x[1] if len(x) > 1 else None)
    df_products['subsubgroup'] = df_products['category_hierarchy'].apply(lambda x: x[2] if len(x) > 2 else None)
    df_products['subsubsubgroup'] = df_products['category_hierarchy'].apply(lambda x: x[3] if len(x) > 3 else None)
    df_products['subsubsubgroups'] = df_products['category_hierarchy'].apply(lambda x: x[4] if len(x) > 4 else None)

    df_products = df_products.drop('category_hierarchy', axis=1)

    return df_products