from datetime import date

import numpy as np
from insurance_balance.insure_balance_class import Insure_Balance
from autoorder.analysis import sdp
from api.helpers.loger import my_logger
import pandas as pd
from autoorder.conections import matrix, product,  warhause_id, shop_name, season_names, category
from api.helpers.categoey_column_maker import add_category_hierarchy


def insure_balance_builder(date_start: date, date_end:date):
    base_column_names=['insurance_no_promo', 'insurance_promo']
    coefficients = {
        'z_90' : 1.28,
        'z_95' : 1.645,
        'z_99' : 2.33
    }
    
    L = 3 # time betwin orders in days
    # Get SDP data
    df_sdp, x, df_daily_sales = sdp(date_start, date_end, detailed=True)
    my_logger.info(f"SDP and daily sales data fetched successfully.{df_sdp.head()}, {df_daily_sales.head()}")
    print(f"Кількість NaN у 'shop_id' (df_sdp): {df_sdp['shop_id'].isnull().sum()}")
    print(f"Кількість NaN у 'shop_id' (df_daily_sales): {df_daily_sales['shop_id'].isnull().sum()}")

    
    
    try:
        base_data = Insure_Balance(df_sdp, df_daily_sales)
        base_data.merge_sales_sdp()
    
        merged_sdp_day_sales = base_data.df_daily_sales
        my_logger.info(f"DataFrame 'test' має {merged_sdp_day_sales.shape[0]} рядків.")
        my_logger.info(f"Приклад перших 5 рядків: {merged_sdp_day_sales.head().to_string()}")
        
        condition_no_promo = (merged_sdp_day_sales['is_stoc'] > 0) & (merged_sdp_day_sales['is_promo'] == 0)
        condition_promo = (merged_sdp_day_sales['is_stoc'] > 0) & (merged_sdp_day_sales['is_promo'] > 0)
        merged_sdp_day_sales['average_minus_sdp_nopromo'] = np.where(
            condition_no_promo,
            (merged_sdp_day_sales['sales_qty'] - merged_sdp_day_sales['sdp_no_promo']) ** 2,
            0)       
        merged_sdp_day_sales['average_minus_sdp_promo'] = np.where(
            condition_promo,
            (merged_sdp_day_sales['sales_qty'] - merged_sdp_day_sales['sdp_promo']) ** 2,
            0)
        
        mean = merged_sdp_day_sales.groupby(['shop_id', 'product_id'])[['average_minus_sdp_nopromo', 'average_minus_sdp_promo']].mean().reset_index()
        mean['stdev_nopromo_np'] = np.sqrt(mean['average_minus_sdp_nopromo'])
        mean['stdev_promo_np'] = np.sqrt(mean['average_minus_sdp_promo'])
        
        #final counting insurance balance
        for base_name in base_column_names:
            stdev_column_name = 'stdev_nopromo_np' if 'no_promo' in base_name else 'stdev_promo_np'
            for key, value in coefficients.items():
                new_column_name = f"{base_name}_{key}"
                mean[new_column_name] = (mean[stdev_column_name] * value * (L ** 0.5))
                mean[new_column_name] = mean[new_column_name].round(0)
        
        mean = mean.round({
            'stdev_nopromo_np': 1,
            'stdev_promo_np': 1,
            'average_minus_sdp_nopromo': 1,
            'average_minus_sdp_promo': 1
        })

        #adding sdp for managers
        sdp_copy = merged_sdp_day_sales[['shop_id','product_id','sdp_promo','sdp_no_promo']]
        sdp_copy = sdp_copy.drop_duplicates(subset=['shop_id','product_id'])
        sdp_copy = sdp_copy.round({'sdp_promo': 1, 'sdp_no_promo': 1})
        
        result_table = pd.merge(mean, sdp_copy, on=['shop_id','product_id'], how='left').fillna(0)
        
        
        
    except Exception as e:
        my_logger.error(f"Error in insure_balance_builder: {e}")
        raise e
    
    try:
        matrix_all = matrix(1)
        my_logger.info(f"Matrix data fetched successfully.{matrix_all.head()}")
    except Exception as e:
        my_logger.error(f"Error fetching matrix data: {e}")
        raise e
    #formatting table for managers
    
    matrix_formatted = matrix_all[['product_id','shop_id', 'insur_balance']]
    
    try:
        product_name = product(status_exceptions=False)
        categories = category()

        hierarhy = add_category_hierarchy(product_name, categories)
        hierarhy = hierarhy[['id', 'group']]
        


        categories = categories[['id', 'name']]
        categories = categories.rename(columns = {'id':'categories_id' , 'name':'Категорія'})

              

        product_name["productcategory_id"] = product_name["productcategory_id"].replace('180ddb06-c260-11ed-a3e3-d4f9a95cd002','★')
        
        names_season = season_names()
        names_season = names_season[['id', 'name']]
        names_season = names_season.rename(columns = {'id':'season_id', 'name':'Сезон'})
        
        product_name = pd.merge(product_name, names_season,
                                left_on= 'season',
                                right_on= 'season_id',
                                how='left').fillna(0)
      
        product_name = pd.merge(product_name, categories,
                                left_on='category_id',
                                right_on='categories_id',
                                how='left')
       
        my_logger.info(f"Product data fetched successfully.{product_name.head()}")
    except Exception as e:
        my_logger.error(f"Error fetching product data: {e}")
        raise e 
    
    matrix_name = product_name[['id', 'name', 'productcategory_id', 'Сезон', 'Категорія']]
    
    result_table = pd.merge(result_table, matrix_formatted,
                            left_on=['product_id','shop_id'],
                            right_on=['product_id','shop_id'],
                            how='left').fillna(0)
    result_table = pd.merge(result_table, matrix_name,
                            left_on='product_id',
                            right_on='id',
                            how='left').fillna(0)
    

    result_table = result_table[result_table['shop_id'] != warhause_id]
    shops = shop_name()
    shops = shops.rename(columns={'name':'shop_name'})
    result_table = pd.merge(result_table, shops,
                            left_on="shop_id",
                            right_on= "id",
                            how="left").fillna(0)
    result_table = pd.merge(result_table, hierarhy,
                            left_on="product_id",
                            right_on="id",
                            how="left").fillna(0)
    
    table_direction = ['shop_id', 'shop_name', 'product_id', 'name', 'Категорія', 'group', 'productcategory_id', 'Сезон', 'sdp_no_promo', 'sdp_promo',
                       'stdev_nopromo_np', 'stdev_promo_np', 'insur_balance',
                       'insurance_no_promo_z_90', 'insurance_no_promo_z_95', 'insurance_no_promo_z_99',
                       'insurance_promo_z_90', 'insurance_promo_z_95', 'insurance_promo_z_99']
    result_table = result_table[table_direction]
    
    result_table.rename(columns={'shop_id':'Номер магазину', 'shop_name':'Магазин', 'group':'Група', 'product_id':'Код товару', 'name':'Назва товару', 'productcategory_id':'Ядро','sdp_no_promo':'СДП не акція',
                             'sdp_promo':'СДП акція', 'stdev_nopromo_np': 'Стандартне відхиилення акційне',
                             'stdev_promo_np':'Стандартне відхилення неакційне', 'insur_balance':'Страхові з матриці',
                             'insurance_no_promo_z_90':'Неакційні страхові покриття 90%',
                             'insurance_no_promo_z_95':'Неакцйні страхові покриття 95%',
                             'insurance_no_promo_z_99':'Неакційні страхові покриття 99%',
                             'insurance_promo_z_90':'Акційні страхові покриття 90%',
                             'insurance_promo_z_95':'Акційні страхові покриття 95%',
                             'insurance_promo_z_99':'Акційні страхові покриття 99%'},
                             inplace=True)
    
    result_table = result_table[result_table['Назва товару'] != 0]
    return result_table
