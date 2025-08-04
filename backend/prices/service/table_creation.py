from datetime import date, timedelta
import pandas as pd



from autoorder.conections import stoks, product, productprices





def prices_with_stocks():

    yesterday =  date.today() - timedelta(days=1)

    stocks_all = stoks(yesterday, yesterday)

    valid_product_ids = stocks_all[stocks_all['qty'] > 0][['product_id']].drop_duplicates().reset_index(drop=True)

    # Отримуємо всі товари окрім "Архівний" (включаючи "Вивести")
    products_names = product(status_exceptions=True, archive_products=False)
    products_names = products_names[["id", "name"]]

    products_with_names = pd.merge(valid_product_ids, products_names,
                                   left_on="product_id",
                                   right_on="id",
                                   how="left").fillna(0)

    product_prices = productprices(yesterday)
    product_prices = product_prices[["product_id", "price_incoming", "price_retail"]]

    products_with_names_prices = pd.merge(products_with_names, product_prices,
                                          left_on="product_id",
                                           right_on="product_id",
                                           how="left").fillna(0)

    products_with_names_prices = products_with_names_prices.drop(columns=["id"])

    products_with_names_prices = products_with_names_prices.rename(columns={
    'product_id': 'Код товару',
    'name': 'Назва',
    'price_incoming': 'Прихідна ціна',
    'price_retail': 'Роздрібна ціна'
})

    return products_with_names_prices

