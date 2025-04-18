from datetime import date, timedelta, datetime, time
import time as dt
import datetime
from datetime import datetime as dt_class

import numpy as np
from autoorder.connections import matrix, product, season_names, stoks, store_dataframe_orders, store_order, delete_store_orders_by_date, warehouse_id, warehouses_smal
import pandas as pd
from autoorder_m.helpers.category_maker import create_groups_list
from autoorder.connections import warehouse_id
from api.helpers.loger import my_logger
from autoorder.connections import shop_name, incoming_products, warehouse_id
from autoorder_m.helpers.calculating_order import calculate_order_stage_1, calculate_order_stage_2
from autoorder.analysis import abc_analysis_vectorized, future_promo, sdp



def custom_rounding(row):
    numb_pack_val = row['numb_pack']
    if numb_pack_val == 0:
        numb_pack_val = 1
    
    if (row['pure_need_items_insure'] % numb_pack_val) > (numb_pack_val / 2):
        return np.ceil(row['pure_need_items_insure'] / numb_pack_val) * numb_pack_val
    else:
        return np.floor(row['pure_need_items_insure'] / numb_pack_val) * numb_pack_val

def base_table_creation(date_start=None, date_finish=None, days_of_order=None,groups=None, markets=None, today_stocs_mode = False):
    this_day = date.today()
    if today_stocs_mode == False:
        today = date.today() - timedelta(days=1)
    else:
        today = this_day
        

    my_logger.debug(f"Starting create_matrix_season_groups with parameters: {date_start}, {date_finish}, {days_of_order}, {groups}")
    print(f"Starting create_matrix_season_groups with parameters: {date_start}, {date_finish}, {days_of_order}, {groups}")
    
    group_list= create_groups_list()
    groupe_for_table = group_list.copy()
    group_list_for_managers_table = groupe_for_table[['category_id','group', 'subgroup', 'subsubgroup', 'subsubsubgroup', 'subsubsubgroups']].drop_duplicates()
    group_list_for_managers_table = group_list_for_managers_table.rename(columns={'category_id': 'category_id_merged'})
    
    groupes_with_id = group_list[['category_id', 'group']].drop_duplicates()
    
    shops = shop_name()
    shops_names = shops.copy()

    id_markets = shops_names[shops_names['name'].isin(markets)]['id'].tolist()
    
    matrix_df = matrix(1)
    
    matrix_markets = matrix_df[matrix_df['shop_id'].isin(id_markets)]
    products = product(True)
    products= products.rename(columns={'id': 'product_id'})
    season = season_names()
    season = season.rename(columns={'name': 'season_name'})
    
    products_with_season = pd.merge( products, season,
                                    left_on = "season",
                                    right_on = "id",
                                    how = "left").fillna(date(1970,1,1))
    products_with_season_groups_name = pd.merge(products_with_season, groupes_with_id,
                                    left_on = "category_id",
                                    right_on = "category_id",
                                    how = "left").fillna(0)
    filtered_result = products_with_season_groups_name[products_with_season_groups_name['group'].isin(groups)]
    filtered_result_matrix = pd.merge(matrix_markets, filtered_result,
                                    left_on = "product_id",
                                    right_on = "product_id",
                                    how = "left").fillna(0)

    filtered_result_matrix['date_begin'] = pd.to_datetime(filtered_result_matrix["date_begin"]).dt.date
    filtered_result_matrix['date_end'] = pd.to_datetime(filtered_result_matrix["date_end"]).dt.date
    mask_season = ((filtered_result_matrix['date_begin'] <= (date_finish+timedelta(days = days_of_order))) & (filtered_result_matrix['date_end'] >= date_finish))
    mask_not_season = filtered_result_matrix['date_begin'] == date(1970,1,1)
    is_season = mask_season | mask_not_season
    filtered_result_matrix['in_season'] = is_season.astype(int)

    filtered_result_matrix = filtered_result_matrix.rename(columns={'id':'id_season','name':'prod_name'})
    
    sdp_all, sales_all_sources = sdp(date_start, date_finish)
    

    for_abc_table = sales_all_sources[['shop_id', 'product_id', 'sales_qty']]
    for_abc_table = for_abc_table.rename(columns={'sales_qty':'sdp_no_promo'})
    
    abc_all = abc_analysis_vectorized(for_abc_table)

    sdp_all = sdp_all.rename(columns={'shop_id':'shops_idis', 'product_id':'id_products'})

    matrix_sdp_all = pd.merge(filtered_result_matrix, sdp_all,
                              left_on = ['product_id', 'shop_id'],
                              right_on = ['id_products', 'shops_idis'],
                              how = 'left' ).fillna(0)
    matrix_sdp_all = matrix_sdp_all.drop(columns=['id_products', 'shops_idis'])


    today_stocs = stoks(today,today)
    
    all_warehouses = [warehouse_id] + warehouses_smal
    market_stocs = today_stocs[~today_stocs['shop_id'].isin(all_warehouses)].copy()
    
    if not market_stocs.empty:
        stock_by_shop = market_stocs.groupby('shop_id')['qty'].sum().reset_index()
        stock_by_shop.columns = ['shop_id', 'total_stock']
        
        sales_by_shop = sales_all_sources.groupby('shop_id')['sales_qty'].sum().reset_index()
        sales_by_shop.columns = ['shop_id', 'total_sales']
        
        shop_check = pd.merge(stock_by_shop, sales_by_shop, on='shop_id', how='left')
        shop_check['total_sales'] = shop_check['total_sales'].fillna(0)
        
        problem_shops = shop_check[(shop_check['total_stock'] == 0) & (shop_check['total_sales'] > 0)]
        
        if not problem_shops.empty:
            problem_shops_list = problem_shops['shop_id'].tolist()
            error_message = (
                f"КРИТИЧНА ПОМИЛКА: Знайдено {len(problem_shops)} магазин(и/ів) з продажами, "
                f"але залишками = 0! Магазини: {problem_shops_list}. "
                f"Дата залишків: {today}. Можливо, залишки не встигли оновитися. "
                f"Виконання зупинено."
            )
            my_logger.error(error_message)
            raise Exception(error_message)
    
    warehouse_stocs = today_stocs.copy()
    warehouse_stocs = warehouse_stocs[warehouse_stocs['shop_id'] == warehouse_id]
    warehouse_stocs = warehouse_stocs[['shop_id', 'product_id', 'qty']]
    warehouse_stocs = warehouse_stocs.rename(columns={'shop_id':'warehouse_shop_id', 'product_id':'warehouse_product_id', 'qty':'warehouse_stocs_qty'})
    
    today_stocs=today_stocs.rename(columns={'shop_id':'stocs_shop_id', 'product_id':'stocs_product_id', 'qty':'stocs_qty'})
    today_stocs = today_stocs[['stocs_shop_id', 'stocs_product_id', 'stocs_qty']]
    matrix_sdp_stocs = pd.merge(matrix_sdp_all, today_stocs,
                                left_on = ['product_id', 'shop_id'],
                                right_on = ['stocs_product_id', 'stocs_shop_id'],
                                how = 'left' ).fillna(0)
    matrix_sdp_stocs= matrix_sdp_stocs.drop(columns=['stocs_product_id', 'stocs_shop_id'])
    matrix_sdp_stocs = matrix_sdp_stocs[matrix_sdp_stocs['prod_name'].notna() &(matrix_sdp_stocs['prod_name']!=0) & (matrix_sdp_stocs['prod_name']!= '')]
    feauture_promo_days = future_promo(date_start, days_of_order)
    feauture_promo_days = feauture_promo_days.rename(columns={'shop_id':'promo_shop_id', 'product_id':'promo_product_id'})
    feauture_promo_days =  feauture_promo_days[['promo_shop_id', 'promo_product_id', 'next_promo_days']]
    matrix_sdp_stocs_feaucher_promo = pd.merge(matrix_sdp_stocs, feauture_promo_days,
                                left_on = ['product_id', 'shop_id'],
                                right_on = ['promo_product_id', 'promo_shop_id'],
                                how = 'left' ).fillna(0)
    matrix_sdp_stocs_feaucher_promo = matrix_sdp_stocs_feaucher_promo.drop(columns=['promo_product_id', 'promo_shop_id'])

    
    matrix_sdp_stocs_feaucher_promo['next_nopromo_days'] = days_of_order - matrix_sdp_stocs_feaucher_promo['next_promo_days']

    incoming_products_df = incoming_products()
    incoming_products_df['date_income'] = pd.to_datetime(incoming_products_df['date_income']).dt.date
    
    incoming_products_df_filtered = incoming_products_df[(incoming_products_df['date_income'] >= date_finish) & (incoming_products_df['date_income'] <= date_finish + timedelta(days=days_of_order))]
    incoming_products_df_filtered = incoming_products_df_filtered.rename(columns={'product_id':'product_id_income', 'shop_id':'shop_id_income'})

    base_table = pd.merge(matrix_sdp_stocs_feaucher_promo, incoming_products_df_filtered,
                          left_on=['product_id', 'shop_id'],
                          right_on=['product_id_income', 'shop_id_income'],
                          how='left').fillna(0)
    base_table = base_table.drop(columns=['product_id_income', 'shop_id_income'])
    

    
    base_table['need_items'] = np.where(
        (base_table['days_no_promo'] + base_table['days_promo']) == 0,
        0,
        np.where(
            (base_table['sdp_no_promo'] == 0) & (base_table['sdp_promo'] == 0),
            base_table['insur_balance'],
            np.where(
                (base_table['days_no_promo'] + base_table['days_promo']) <= 2,
                base_table['insur_balance'] * 2,
                base_table['sdp_no_promo'] * base_table['next_nopromo_days'] + base_table['sdp_promo'] * base_table['next_promo_days']
            )
        )
    )
    

    mask_next_promo = np.where(base_table['next_promo_days'] > 0, base_table['sdp_promo'], base_table['sdp_no_promo'] )

    mask_stocs_income = np.where((base_table['stocs_qty'] + base_table['income_qty'] - mask_next_promo)>0, (base_table['stocs_qty'] + base_table['income_qty'] - mask_next_promo), 0)
    
    base_table['pure_need_items'] = np.where(base_table['need_items'] - mask_stocs_income >0,
                                             base_table['need_items'] - mask_stocs_income,
                                             0)
    
    base_table['pure_need_items_rounded'] = base_table['pure_need_items'].round(0)

    
    adjusted_total_demand = np.where(
        (base_table['need_items'] == base_table['insur_balance']) & 
        (base_table['sdp_no_promo'] == 0) & (base_table['sdp_promo'] == 0) &
        ((base_table['days_no_promo'] + base_table['days_promo']) > 0),
        base_table['insur_balance'],
        base_table['need_items'] + base_table['insur_balance']
    )
    base_table['pure_need_items_insure'] = np.maximum(0, adjusted_total_demand - (base_table['stocs_qty'] + base_table['income_qty']))
    base_table['pure_need_items_insure_rounded'] = base_table.apply(custom_rounding, axis=1).astype(int)


    
    total_need_per_product = base_table.groupby('product_id')['pure_need_items'].sum().reset_index()
    total_need_per_product = total_need_per_product.rename(columns={'pure_need_items':'total_pure_need_items', 'product_id':'total_product_id'})
    

    base_table = pd.merge(base_table, total_need_per_product,
                          left_on='product_id',
                          right_on='total_product_id',
                          how='left').fillna(0)
    
    base_table['total_pure_need_items_insure'] = base_table.groupby('product_id')['pure_need_items_insure'].transform('sum')

    
    

    

    base_table['total_pure_need_items_insure_rounded'] = base_table.groupby('product_id')['pure_need_items_insure_rounded'].transform('sum')
    
    base_table['pure_need_items_insure_matematik_rounded'] = base_table['pure_need_items_insure'].round(0)
    base_table['total_pure_need_items_insure_matematik_rounded'] = base_table.groupby('product_id')['pure_need_items_insure_matematik_rounded'].transform('sum')

    base_table['pure_need_items_%'] = np.where(base_table['pure_need_items_insure_rounded']!=0,base_table['pure_need_items_insure_rounded'] / base_table['total_pure_need_items_insure_rounded'],0)
    base_table = base_table.drop(columns=['total_product_id', 'total_pure_need_items'])
    base_table = base_table.drop(columns=['total_pure_need_items_insure'])
    base_table = pd.merge(base_table, warehouse_stocs,
                          left_on=['product_id'],
                          right_on=['warehouse_product_id'],
                          how='left').fillna(0)
    
    base_table = base_table.drop(columns=['warehouse_product_id', 'warehouse_shop_id'])
    
    
    
    base_table['order_stage_1'] = base_table.apply(calculate_order_stage_1, axis=1)

    
    final_table_stage_2 = calculate_order_stage_2(base_table)

    final_table = final_table_stage_2.copy()

    final_table['final_order'] = final_table['order_stage_1'] + final_table['order_stage_2']

    final_table['sales_all_period']  = final_table['sales_promo'] * final_table['days_promo'] + final_table['sales_no_promo'] * final_table['days_no_promo']
    final_table['sales_all_period'] = final_table['sales_all_period'].round(0)
    final_table = pd.merge(final_table, abc_all[['abc']], 
                       left_on=['product_id', 'shop_id'],
                       right_on=['product_id', 'shop_id'],
                       how='left')

    final_table['abc'] = final_table['abc'].fillna('X')
    final_table = pd.merge(final_table, shops,
                       left_on='shop_id',
                       right_on='id',
                       how='left').fillna('')
    final_table = final_table.drop(columns=['id'])
    final_table = final_table.rename(columns={'name':'shop_name'})
    final_table = pd.merge(final_table, group_list_for_managers_table,
                          left_on='category_id',
                          right_on='category_id_merged',
                          how='left').fillna('')    
    my_logger.debug(f"Дублікати в (product_id, shop_id) парах у matrix_markets: {matrix_markets.duplicated(subset=['product_id', 'shop_id']).sum()}")
    
   

    clumns_for_managers = final_table[['product_id',  'group_y', 'subgroup', 'subsubgroup', 'subsubsubgroup', 'subsubsubgroups','prod_name', 'abc','shop_id', 'shop_name','sales_all_period','stocs_qty', 'sdp_no_promo', 'need_items','final_order', ]]
    clumns_for_managers = clumns_for_managers.rename(columns={'product_id':'Код товару', 'group_y':'Група', 'subgroup':'Підгрупа', 'subsubgroup':'Категорія', 'subsubsubgroup':'Підкатегорія', 'subsubsubgroups':'Підпідкатегорія', 'prod_name':'Назва товару', 'abc':'ABC аналіз', 'shop_id':'Код магазину', 'shop_name':'Назва магазину','sales_all_period':'Продажі за період, шт.', 'stocs_qty':'Сьогоднішні залишки, шт.', 'sdp_no_promo':'СДП без промо, шт.', 'need_items':'Потреба, шт.', 'final_order':'Замовлення, шт.'})


    df_for_sql = final_table[['shop_id', 'product_id', 'final_order']]

    df_for_sql = df_for_sql.rename(columns={'shop_id': 'shop_destination', 'final_order': 'qty'})
    df_for_sql['status'] = 1
    df_for_sql['shop_source'] = warehouse_id
    
    
    current_time = dt_class.now()
    this_day = date.today()
    etalon_time = time(9, 30, 0)

    if current_time.time() <= etalon_time:
        date_for_sql = this_day
    else:
        date_for_sql = this_day + timedelta(days=1)
        
    df_for_sql['date'] = date_for_sql
    print(f"markets_id for sql: {id_markets}")
    store_order_from_base = store_order(date_for_sql, id_markets)
    
    print(f"store_order_from_base: {store_order_from_base.head()}")
    print(f"df_for_sql: {df_for_sql.head()}")
    
    mask_for_diff_table = ["shop_source", "shop_destination", "date", "product_id"]
    combinet_df = pd.concat([store_order_from_base, df_for_sql], ignore_index=True).copy()
    combinet_df['qty'] = combinet_df['qty'].replace('', np.nan)
    combinet_df['qty'] = combinet_df['qty'].fillna(0)
    
    df_for_sql_push = combinet_df.drop_duplicates(subset=mask_for_diff_table, keep='last')
    filtererd_df_for_sql_push = df_for_sql_push[df_for_sql_push['qty'] != 0]
    filtererd_df_for_sql_push.replace({np.nan: None}, inplace=True)
    filtererd_df_for_sql_push_no_id = filtererd_df_for_sql_push.drop(columns=['id'])

    try:
       
        delete_store_orders_by_date(date_for_sql)

        store_dataframe_orders(filtererd_df_for_sql_push_no_id)
        my_logger.info(f"Orders for date {date_for_sql} stored successfully.")
        return clumns_for_managers, final_table_stage_2, {"status": "success", "message": "Дані успішно записано в базу даних."}
    
    except Exception as e:
        my_logger.error(f"Error storing orders for date {date_for_sql}: {str(e)}")