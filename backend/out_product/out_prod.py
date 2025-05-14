
from datetime import date, timedelta
from fastapi.responses import JSONResponse
import pandas as pd
from autoorder.conections import product_choose, retry_on_operational_error, category, productprices, shop_name
from autoorder.analysis import abc_analysis_all, sdp, promotions
from api.helpers.loger import init_logger
from api.helpers.categoey_column_maker import add_category_hierarchy

my_logger = init_logger()
start_total_promo_day = date(2022,1,1)

today = date.today() - timedelta(days=1)
today_date = today
yesterday = today.strftime("%Y-%m-%d")


def analyze_out_products(date_start, date_finish, products_status: list = ["Вивести"]) -> pd.DataFrame:

     #promotions name
    try:

        promo = promotions(start_date=start_total_promo_day)
        if promo is None or promo.empty:
            my_logger.error("promo порожній!")
            columns = ['shop_id', 'product_id', 'name', 'dt_from', 'dt_to']
            promo = pd.DataFrame(columns=columns)
            my_logger.error("promo порожній!")
            raise Exception("Немає даних про promo!")
        
        # filter date
        promo = promo[(promo['dt_from'] <= date_finish) & (promo['dt_to'] >= date_finish)]
        promo = promo.drop(columns=['dt_from', 'dt_to'])
        
        #grouping product_id and counting markets woth promo
        promo = promo.groupby('product_id').agg(
            name = ('name', 'first'),
            shop_id = ('shop_id', 'nunique')
        ).reset_index()
        promo = promo.rename(columns={'shop_id': 'Магазинів з промо', 'name': 'Назва акції'})
        
        print(f"promo created with {promo.head()} rows")
        my_logger.info(f"promo created with {promo.head()} rows")
        
           
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних promo: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
    
        
    
    # Dataframe with products status = "Вивести"
    try:
        sdp_all, sales_stocs_all = sdp(start_date=date_start, end_date=date_finish)
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних sdp_all, sales_stocs_all: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
    
    if sdp_all is None or sdp_all.empty:
        my_logger.error("sdp_all порожній!")
        raise Exception("Немає даних про sdp_all !")
    if sales_stocs_all is None or sales_stocs_all.empty:
        my_logger.error("sales_stocs_all порожній!")
        raise Exception("Немає даних про sdp_sales_stocs_all!")
    
    #kreating stocs per market
    stocs_per_market_df = sales_stocs_all.copy()
    stocs_per_market_df = stocs_per_market_df[['shop_id', 'product_id', 'stocs_qty', 'date']]
    stocs_per_market_df = stocs_per_market_df[stocs_per_market_df['date'] == date_finish]
    market_names = shop_name()
    stocs_per_market_df = pd.merge(stocs_per_market_df, market_names, left_on='shop_id', right_on='id', how='left')
    stocs_per_market_df = stocs_per_market_df.pivot(
        index='product_id',
        columns='name',
        values='stocs_qty'
    ).reset_index()
    print(stocs_per_market_df.head())
    
    try:
        my_logger.info(f"starting product_choose with parameters {products_status} ")
        df_product_out = product_choose(statuses=products_status)
        my_logger.info(f"analyze_out_products date_start: {date_start}, date_finish: {date_finish}, products_status: {products_status} created")
    
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних про товари: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
    
    if df_product_out is None or df_product_out.empty:
        my_logger.error("df_product_out порожній!")
        raise Exception("Немає даних про товари для виведення!")
    #df with products status = "Вивести"
    df_product_out = df_product_out.drop(['supplier_id', 'season'], axis=1)    
    
    try:
        categories = category()
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних categories: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
    if categories is None or categories.empty:
        my_logger.error("categories порожній!")
        raise Exception("Немає даних про categories!")

    

    
    try:
        abc = abc_analysis_all(sdp_all)
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних abc: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e    
    if abc is None or abc.empty:
        my_logger.error("abc порожній!")
        raise Exception("Немає даних про abc !")
    

    try:
        df_product_out_hierarchy = add_category_hierarchy(df_product_out, categories)
        if df_product_out_hierarchy is None or df_product_out_hierarchy.empty:
            my_logger.error("df_product_out_hierarchy порожній!")
            raise Exception("Немає даних про df_product_out_hierarchy !")
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних df_product_out_hierarchy: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e

    #building final dataframe
    try:
        columns_from_abc = ['product_id', 'abc']
        for col in columns_from_abc:
            if col not in abc.columns:
                my_logger.error(f"Column '{col}' not found in 'abc' DataFrame.")
                raise Exception(f"Column '{col}' not found in 'abc' DataFrame.")
        product_out_hierarchy_abc = pd.merge(df_product_out_hierarchy, abc,
                                         left_on=['id'],
                                         right_on=['product_id'],
                                         how='left')
        product_out_hierarchy_abc_cleaned = product_out_hierarchy_abc.drop(columns=['product_id'])

    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних df_product_out_hierarchy: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
    
    # adding sdp
    try:
        columns_from_sdp = ['product_id', 'sales_no_promo', 'sdp_no_promo', 'days_promo', 'sales_promo', 'sdp_promo']

        for col in columns_from_sdp:
            if col not in sdp_all.columns:
                my_logger.error(f"Column '{col}' not found in 'sdp' DataFrame.")
                raise Exception(f"Column '{col}' not found in 'sdp' DataFrame.")
        sdp_drop_cols = sdp_all[columns_from_sdp]
            
        sdp_grouped = sdp_drop_cols.groupby(['product_id']).agg('sum').fillna(0).reset_index()
        


    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних sdp for final table: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e
            

    #sales and stocs

    try:
        prices = productprices(yesterday=yesterday)
        prices_columns = ['product_id', 'price_incoming', 'price_retail']
        
        for col in prices_columns:
            if col not in prices:
                my_logger.error(f"Column '{col}' not found in 'prices' DataFrame.")
                raise Exception(f"Column '{col}' not found in 'prices' DataFrame.")
        prices = prices[prices_columns]
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних prices: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e



    try:
        colums_from_sales_stocs_all = ['product_id', 'date', 'sales_qty', 'stocs_qty']
        for col in colums_from_sales_stocs_all:
            if col not in sales_stocs_all.columns:
                my_logger.error(f"Column '{col}' not found in 'sales_stocs_all' DataFrame.")
                raise Exception(f"Column '{col}' not found in 'sdsales_stocs_allp' DataFrame.")
        sales_stocs_all_drop_markets = sales_stocs_all.drop(columns=['shop_id'])
        #sales for all period
        sales_sales_column = sales_stocs_all_drop_markets[['product_id', 'sales_qty']]
        sales_all_period = sales_sales_column.groupby('product_id').agg('sum').fillna(0).reset_index() 

        df_on_date_finish_filtered = sales_stocs_all_drop_markets[sales_stocs_all_drop_markets['date'] == date_finish]
        if df_on_date_finish_filtered.empty:
            my_logger.error(f"No data found for date {df_on_date_finish_filtered}")
            raise Exception(f"No data found for date {df_on_date_finish_filtered}")
        else:
            stocs_on_date_finish_filtered = df_on_date_finish_filtered[['product_id', 'stocs_qty']]
            stocs_on_date_finish_filtered_grouped = stocs_on_date_finish_filtered.groupby('product_id').agg('sum').fillna(0).reset_index()
            my_logger.info('stocs_on_date_finish_filtered_grouped created')
    except Exception as e:
        my_logger.error(f"Помилка при отриманні даних colums_from_sales_stocs_all for final table: {e}")
        raise Exception(f"Помилка бази даних: {e}") from e           
    
    #promo check
    is_promo_column = sdp_grouped [['product_id', 'days_promo']]
    is_promo_groupby = is_promo_column.groupby('product_id').agg('sum').fillna(0).reset_index()
    is_promo_groupby['promotion_in_period'] = is_promo_groupby['days_promo'].apply(lambda x: "Промо" if x > 0 else None)
    is_promo_bool = is_promo_groupby.drop(columns=['days_promo'])

    


    # df with abc, stocs, sales , promo 
    product_out_hierarchy_abc_stocs = pd.merge(product_out_hierarchy_abc_cleaned, stocs_on_date_finish_filtered_grouped, 
                                               left_on=['id'], right_on=['product_id'], how='left' ).fillna(0)
    my_logger.info(f"product_out_hierarchy_abc_stocs created sucesfully")
    product_out_hierarchy_abc_stocs_sales = pd.merge(product_out_hierarchy_abc_stocs, sales_all_period,
                                                     left_on=['id'],
                                                     right_on=['product_id'],
                                                     how='left').fillna(0)
    product_out_hierarchy_abc_stocs_sales = product_out_hierarchy_abc_stocs_sales.drop(columns=['product_id_x', 'product_id_y'])
    my_logger.info(f"product_out_hierarchy_abc_stocs_sales created sucesfully")
    product_out_hierarchy_abc_stocs_sales_promo = pd.merge(product_out_hierarchy_abc_stocs_sales,is_promo_bool,
                                                           left_on=['id'],
                                                           right_on=['product_id'],
                                                           how="left")
    
    product_out_hierarchy_abc_stocs_sales_promo = product_out_hierarchy_abc_stocs_sales_promo.drop(columns=['product_id'])

    #add prices
   
    product_out_hierarchy_abc_stocs_sales_promo_prices = pd.merge(product_out_hierarchy_abc_stocs_sales_promo, prices,
                                                                  left_on=['id'],
                                                                  right_on=['product_id'],
                                                                  how='left').fillna(0)
    
    product_out_hierarchy_abc_stocs_sales_promo_prices = product_out_hierarchy_abc_stocs_sales_promo_prices.drop(columns=['product_id'])
    #add promos

    product_out_hierarchy_abc_stocs_sales_promo_prices = pd.merge(product_out_hierarchy_abc_stocs_sales_promo_prices, promo,
                                                                    left_on=['id'],
                                                                    right_on=['product_id'],
                                                                    how='left').fillna(0)
    product_out_hierarchy_abc_stocs_sales_promo_prices = product_out_hierarchy_abc_stocs_sales_promo_prices.drop(columns=['product_id'])

    
    my_logger.info(f"product_out_hierarchy_abc_stocs_sales_promo_prices created sucesfully")

    #renaming columns

    new_names = {
        'id': 'Код товару',
        'name': 'Назва товару',
        'category_id': 'Код категорії',
        'group': 'Назва категорії',
        'abc': 'ABC',
        'stocs_qty': 'Залишок на вчора загальний',
        'sales_qty': 'Продажі за період',
        'promotion_in_period': 'Промо в періоді',
        'price_incoming': 'Ціна закупки',
        'price_retail': 'Ціна продажу',
        'status': 'Статус',
        }
    product_out_hierarchy_abc_stocs_sales_promo_prices.rename(columns=new_names, inplace=True)
    my_logger.info(f"product_out_hierarchy_abc_stocs_sales_promo_prices renamed")
    new_direction = ['Код категорії', 'Назва категорії',  'subgroup', 'subsubgroup', 'subsubsubgroup', 'Код товару', 'Назва товару' , 'Статус', 'Ціна закупки',  'Ціна продажу', 'ABC',  'Залишок на вчора загальний', 'Продажі за період', 'Назва акції', 'Магазинів з промо']
    product_out_hierarchy_abc_stocs_sales_promo_prices = product_out_hierarchy_abc_stocs_sales_promo_prices[new_direction]
    product_out_hierarchy_abc_stocs_sales_promo_prices = pd.merge(product_out_hierarchy_abc_stocs_sales_promo_prices, stocs_per_market_df,
                                                                    left_on=['Код товару'],
                                                                    right_on=['product_id'],
                                                                    how='left').fillna(0)
    product_out_hierarchy_abc_stocs_sales_promo_prices = product_out_hierarchy_abc_stocs_sales_promo_prices.drop(columns=['product_id'])
    product_out_hierarchy_abc_stocs_sales_promo_prices = product_out_hierarchy_abc_stocs_sales_promo_prices.drop_duplicates(subset=['Код товару'], keep='first')
    return  product_out_hierarchy_abc_stocs_sales_promo_prices
    


   
