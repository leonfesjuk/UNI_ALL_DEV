from autoorder.conections import category, product
from api.helpers.categoey_column_maker import add_category_hierarchy
from api.helpers.loger import init_logger
from autoorder.conections import stoks, productprices
import datetime
import pandas as pd

yesterday_date = datetime.date.today() - datetime.timedelta(days=1)


def market_down_products_generate():
    my_logger = init_logger()

    try:
        categories = category()
        products = product(status_exceptions=True)
        hierarhy = add_category_hierarchy(products, categories)
        my_logger.info(f"Product hierarchy created with 'Вивести' status products included.")
    except Exception as e:
        my_logger.error(f"Exception {e}")
        raise

    filter_mask = (
        hierarhy['group'].str.contains('УЦІНКА', case=False, na=False) |
        hierarhy['subgroup'].str.contains('УЦІНКА', case=False, na=False) |
        hierarhy['subsubgroup'].str.contains('УЦІНКА', case=False, na=False) |
        hierarhy['subsubsubgroup'].str.contains('УЦІНКА', case=False, na=False) |
        hierarhy['subsubsubgroups'].str.contains('УЦІНКА', case=False, na=False)
    )
    market_down_products = hierarhy[filter_mask]


    if market_down_products.empty:
        my_logger.warning(f"market_down_products is empty")
        return market_down_products

    stocs_all_products = stoks(yesterday_date, yesterday_date)
    stocs_all_products = stocs_all_products.groupby('product_id')['qty'].sum().reset_index()

    market_down_products_stocs = pd.merge(market_down_products, stocs_all_products,
                                          left_on='id',
                                          right_on='product_id',
                                          how='left').fillna(0)
    

    price = productprices(yesterday=yesterday_date)
    price = price[['product_id', 'price_incoming']]
    market_down_products_stocs = pd.merge(market_down_products_stocs,
                                          price,
                                          left_on=['id'],
                                          right_on=['product_id'],
                                          how='left').fillna(0)
    market_down_products_stocs['total_price'] = market_down_products_stocs['price_incoming'] * market_down_products_stocs['qty']

    # Drop unnecessary columns as requested by the user
    cols_to_drop = [
        'season', 'category_id', 'product_id_x', 'product_id_y', 'product_id',
        'supplier_id', 'productcategory_id'
    ]
    market_down_products_stocs = market_down_products_stocs.drop(columns=cols_to_drop, errors='ignore')

    # Rename columns to Ukrainian
    rename_map = {
        'id': 'Код товару',
        'name': 'Назва товару',
        'status': 'Статус',
        'qty': 'Залишок',
        'price_incoming': 'Ціна закупки',
        'total_price': 'Сума закупки',
        'group': 'Відділ',
        'subgroup': 'Категорія',
        'subsubgroup': 'Підкатегорія',
        'subsubsubgroup': 'Група',
        'subsubsubgroups': 'Підгрупа'
    }
    market_down_products_stocs = market_down_products_stocs.rename(columns=rename_map)

    return market_down_products_stocs








