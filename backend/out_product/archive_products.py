from api.helpers.loger import init_logger
from autoorder.conections import product_choose, retry_on_operational_error, category, productprices, shop_name, stoks, product
from autoorder.analysis import abc_analysis_all, sdp, promotions
import pandas as pd

my_logger = init_logger()


def archive_products_analise(date_start, date_finish):
    my_logger.info(f"archive_products_analise() start with first date {date_start}, second date {date_finish}")
    
    # Define columns and fetch stock data
    stocs_columns = ['shop_id', 'product_id', 'qty']
    stocs_first_date = stoks(date_start=date_start, date_finish=date_start)
    stocs_first_date = stocs_first_date[stocs_columns]
    stocs_second_date = stoks(date_start=date_finish, date_finish=date_finish)
    stocs_second_date = stocs_second_date[stocs_columns]

    # Define new column names for quantities
    new_column_name_first_date = f"Залишок на {date_start}"
    new_column_name_second_date = f"Залишок на {date_finish}"

    # Rename qty columns before merging
    stocs_first_date = stocs_first_date.rename(columns={'qty': new_column_name_first_date})
    stocs_second_date = stocs_second_date.rename(columns={'qty': new_column_name_second_date})

    # Merge the two stock dataframes on product_id and shop_id
    merged_stocks = pd.merge(stocs_first_date, stocs_second_date,
                             on=['product_id', 'shop_id'],
                             how='outer').fillna(0)

    # Fetch products data
    products = product(status_exceptions=True, archive_products=True)
    products = products[['id', 'name', 'status', 'category_id']]

    # Merge products with the combined stock data
    merged_df = pd.merge(products, merged_stocks,
                         left_on='id',
                         right_on='product_id',
                         how='left').fillna(0)

    # Clean up the final dataframe
    merged_df = merged_df.drop('product_id', axis=1)
    condition = merged_df['shop_id'] != 0
    merged_df = merged_df[condition]
    merged_df = merged_df.rename(columns = {"id":"Код товару", "name":"Назва товару", "status":"Статус товару",  "category_id":"Код категорії", "shop_id":"Код магазину"})

    # Fetch and merge shop names
    shops = shop_name()
    merged_df = pd.merge(merged_df, shops, left_on='Код магазину', right_on='id', how='left')
    merged_df = merged_df.drop('id', axis=1) # drop the redundant id column from shops
    merged_df = merged_df.rename(columns={'name': 'Назва магазину'})

    # Reorder columns
    cols = merged_df.columns.tolist()
    shop_code_index = cols.index('Код магазину')
    cols.insert(shop_code_index + 1, cols.pop(cols.index('Назва магазину')))
    merged_df = merged_df[cols]

    # Fetch and merge category names
    categories_df = category()
    categories_df = categories_df.rename(columns={"id": "Код категорії", "name": "Назва категорії"})
    
    merged_df = pd.merge(merged_df, categories_df[['Код категорії', 'Назва категорії']], 
                         on='Код категорії', 
                         how='left')

    # Reorder columns to place "Назва категорії" after "Код категорії"
    cols = merged_df.columns.tolist()
    category_code_index = cols.index('Код категорії')
    cols.insert(category_code_index + 1, cols.pop(cols.index('Назва категорії')))
    merged_df = merged_df[cols]
    
    return merged_df