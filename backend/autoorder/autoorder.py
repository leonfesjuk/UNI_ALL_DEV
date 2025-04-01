
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np
import os
from api.helpers.categoey_column_maker import add_category_hierarchy
#from .conections import shop_name, warhause_id, incoming_products, standart_promo_gain, product, category,productprices
from autoorder.conections import shop_name, warhause_id, incoming_products, standart_promo_gain, product, category,productprices

from autoorder.analysis import  sdp,  matrix, stoks, future_promo,abc_analysis_all, season_names,categories, suplaer_id, promotions, change_columns_direction

def auto_order_w_start(date_start=None, date_finish=None, days_of_order = None):
    print(f"auto_order_w_start {date_start},{date_finish},{days_of_order}")
    today = date.today() - timedelta(days=1)
    today_date = today
    #today = today.strftime("%Y-%m-%d")
    
    # Check if date is

    if date_finish is None:
        return "date_finish is None"
    if date_start is None:
        return "date_fstart is None"
    if days_of_order is None:
        return "days_of_order is None"

    print(f"Start auto_order_w_start with parameters:  today = {today}, date_start ={date_start}, date_finish = {date_finish}, days_of_order = {days_of_order}")

    #create datasets
    print(f"Prepairing to foo sdp_all")
 
    sdp_all, sales_all_sources = sdp(date_start, date_finish)
    print(f"Start sdp_all with {date_start} , {date_finish}")
    print(sdp_all.head(n=2))
    
    
    mtrx = matrix(1)
    
    print(mtrx.head(n=2))

    season = season_names()

    print(season.head(n=2))
    #season = season.rename(columns = {"date_bedin":"date_begin_season", "date_end":"date_end_season"})
    #season['date_begin'] = pd.to_datetime(season['date_begin']).dt.date
    #season['date_end'] = pd.to_datetime(season['date_end']).dt.date
    wh_matix = matrix(0)
    print(wh_matix.head(n=2))
    product_status = product()

    print(product_status.head(n=2))
    product_status = product_status.rename(columns={"id" : "product_id"})
    product_status = pd.merge(product_status, season,
                              left_on="season",
                              right_on="id",
                              how="left").fillna(date(1970,1,1))
    product_status=product_status.rename(columns={'name_y':'Сезон'})                          
   
    product_status['date_begin'] = pd.to_datetime(product_status['date_begin']).dt.date
    product_status['date_end'] = pd.to_datetime(product_status['date_end']).dt.date
    #product_status = product_status.drop(['id_x', 'id_y'], axis=1)


    mask_season = ((product_status['date_begin'] <= (date_finish+timedelta(days = days_of_order))) & (product_status['date_end'] >= date_finish))
    mask_not_season = product_status['date_begin'] == date(1970,1,1)
    is_season = mask_season | mask_not_season
    product_status['in_season'] = is_season.astype(int)
    
    product_status = product_status.drop(['date_end', 'date_begin'],axis=1)
    
    today_stocs = stoks(today,today)

    #create stocs for final tab
    today_stocs_for_pivot = today_stocs.copy()

    #create dataset with all stoks yesterdey
    stocs_all_source = today_stocs.copy()
    stocs_all_source = stocs_all_source.groupby('product_id', as_index=False)['qty'].sum()
    print("////////////////////////////////////////////////////////////////")
    print(stocs_all_source.head())


    #clear table
    today_stocs_for_pivot = today_stocs_for_pivot.drop(columns=['id', 'dt', 'date'])
    today_stocs_for_pivot = today_stocs_for_pivot.rename(columns={'shop_id' :'shops', 'product_id': 'id_prod'})
    #create and add to stocs - names of marckets
    shops = shop_name()
    today_stocs_for_pivot = pd.merge(today_stocs_for_pivot, shops,
                                     left_on=['shops'],
                                     right_on=['id']).fillna(0)
    today_stocs_pivot = today_stocs_for_pivot.pivot(index='id_prod', columns='name', values=['qty']).fillna(0)
    today_stocs_pivot.columns = today_stocs_pivot.columns.droplevel(0)  # Видаляємо верхній рівень 'qty'
    today_stocs_pivot = today_stocs_pivot.reset_index() # повертаємо id_prod в колонку
    print(f"{today_stocs_pivot.head()}")

    print(today_stocs_for_pivot.head())
    print(f"Start today_stocs with {today} , {today}")
    incoming_product = incoming_products()
    

    print(incoming_product.head(n=2))
    abc = abc_analysis_all(sdp_all)
  
    feauture_promo_days = future_promo(date_start, days_of_order)

    

    print(feauture_promo_days.head(n=2))

     #filter promos that actual yesterday
    
    
    

    feauture_promo_days = feauture_promo_days.drop(['dt_from', 'dt_to', 'dt_from_number', 'dt_to_number'], axis = 1)
    
    #merge datasets in basic dataset
        #merge today stocs to sdp dataset
    #
    merged_df = pd.merge(mtrx,sdp_all,
                        left_on= ['product_id', 'shop_id'],
                        right_on= ['product_id', 'shop_id'],
                        how = 'left').fillna(0)
    merged_df = pd.merge(merged_df,today_stocs,
                         left_on = ['product_id', 'shop_id'],
                         right_on= ['product_id', 'shop_id'],
                         how = 'left').fillna(0)
    merged_df = merged_df.rename(columns={'qty':'today_stocs'})
    merged_df = merged_df.drop(['id','dt', 'date'], axis=1)

    #merge info for future promos
    merged_df = pd.merge(merged_df, feauture_promo_days,
                         left_on=['shop_id', 'product_id'],
                         right_on=['shop_id', 'product_id'],
                         how='left').fillna(0)
    # create column with info about days without promo in future
    merged_df['next_no_promo_days'] = days_of_order - merged_df['next_promo_days']
    dtypes_dict = {'next_no_promo_days': int, 'next_promo_days': int}
    merged_df = merged_df.astype(dtypes_dict)

    # count neded items for period
      
    #created warhause_df without markets///
    warhause_df = wh_matix[wh_matix['shop_id'] == warhause_id]

    warhause_df = pd.merge(warhause_df, today_stocs,
                           left_on = ['product_id', 'shop_id'],
                           right_on= ['product_id', 'shop_id'],
                           how = 'left').fillna(0)
    
    warhause_df = warhause_df.rename(columns={'qty':'today_stocs'})

   
    warhause_df = pd.merge(warhause_df, incoming_product,
                         left_on=['shop_id','product_id'],
                         right_on=['shop_id','product_id'],
                         how = 'left').fillna(0)
    # filtered df without warhause
    
    merged_df = merged_df[merged_df['shop_id']!= warhause_id]

    

    merged_df = pd.merge(merged_df, incoming_product,
                         left_on=['shop_id','product_id'],
                         right_on=['shop_id','product_id'],
                         how = 'left').fillna(0)
    
    
    
    merged_df = merged_df.drop(columns=['date_income'])

    #mask_need = (merged_df['next_promo_days'] * merged_df['sdp_promo'] + merged_df['next_no_promo_days']
        # * merged_df['sdp_no_promo']+merged_df['insur_balance']).where(merged_df['sdp_promo'] <=0, merged_df['sdp_no_promo'] * standart_promo_gain)
    stoc_mask = (merged_df['today_stocs']+merged_df['income_qty'])
    mask = merged_df['sdp_promo'] <=0
    sdp_promo_adjusted = np.where(mask, merged_df['sdp_no_promo'] * standart_promo_gain, merged_df['sdp_promo'])
    mask_need = sdp_promo_adjusted * merged_df['next_promo_days'] + merged_df['next_no_promo_days'] * merged_df['sdp_no_promo'] + merged_df['insur_balance']


    
    merged_df['neded_items_order_period'] = np.where(mask_need > stoc_mask, mask_need - stoc_mask,0)
    
    
    #test excell for debuging!!!!!!!!!!!!!!!
    
    
    test_table = merged_df

    total_quantity_per_product = merged_df.groupby('product_id')['neded_items_order_period'].sum()

    total_quantity_per_product = pd.merge(product_status, total_quantity_per_product,
                                          left_on = ["product_id"],
                                          right_on = ["product_id"],
                                          how="left").fillna(0)
    
    
    warhause_df = pd.merge(warhause_df, product_status[['product_id', 'in_season']],
                            left_on=['product_id'],
                            right_on=['product_id'],
                            how = 'left').fillna(0)
    
    warhause_df = warhause_df[warhause_df['in_season'] == 1]
    warhause_df = warhause_df.drop(columns=['in_season'])

    warhause_need = pd.merge(total_quantity_per_product, warhause_df, 
                             left_on=['product_id'],
                             right_on=['product_id'],
                             how = 'outer').fillna(0)
    warhause_need['numb_pack'] = warhause_need['numb_pack'].replace(0,1)
   #warhause_need = warhause_need.rename(columns={'in_season_y':'in_season'})
    #warhause_need.to_excel('warhause_need.xlsx')
   
    #warhause_need = warhause_need.drop(columns=['matrix_active','days_no_promo', 'sales_no_promo','sdp_no_promo', 'days_promo', 'sales_promo', 'sdp_promo', 'next_no_promo_days', 'next_promo_days'])
    # якщо сезон 1 ( в тому числі несезонний товар) то отримуєм результат маски, якщо 0 ( не сезон) - отримаєм результат 0
    warhause_need_mask = warhause_need['neded_items_order_period'] + warhause_need['insur_balance']
    warhause_stoc_mask = warhause_need['today_stocs'] + warhause_need['income_qty']

    warhause_need['warhause_order'] = np.where(warhause_need['in_season'] ==1,
                                               warhause_need_mask.sub(warhause_stoc_mask).clip(lower=0),
                                               0)
    merge_need_abc = pd.merge(warhause_need, abc, how='left').fillna('X')
   
   #roundin with numb_puck
    def custom_round(x, base):
    
        return base * np.floor(x / base + 0.5)

    merge_need_abc['rounded_order'] = np.where(
    merge_need_abc['warhause_order'] <= merge_need_abc['numb_pack'] * 0.5,
    0,
    np.where(
        merge_need_abc['abc'] == 'A',
        custom_round(merge_need_abc['warhause_order'], merge_need_abc['numb_pack']),
        np.where(merge_need_abc['numb_pack'] != 0,
                 custom_round(merge_need_abc['warhause_order'], merge_need_abc['numb_pack']),
                 np.nan)))

    ## BEAUTIFICATION OF DATASET FOR MANAGERS

    category_naes = category()

   
    

    print("added paren element:\n")
    
    print(merge_need_abc.head())

    prices = productprices(today)
    prices = prices.drop(['id','date'], axis=1)
    prices = prices.drop_duplicates(subset=['product_id'], keep='first')
    merge_need_abc = pd.merge(merge_need_abc, prices,
                              left_on=['product_id'],
                              right_on=['product_id'],
                              how='left').fillna(0)
    
    supliers = suplaer_id()
    supliers=supliers.drop(['supplier_id'],axis=1)
    
 

    supliers=supliers.groupby('product_id')['suppliers_name'].apply(lambda x: '/'.join(x)).reset_index()
    
    merge_need_abc = pd.merge(merge_need_abc,supliers,
                              left_on = ['product_id'],
                              right_on=['product_id'],
                              how='left').fillna(0)
   
    #adding Today promo

    promotion_today=promotions(date_start)

    promotion_today=promotion_today[(promotion_today['dt_from'] <= today_date) & (promotion_today['dt_to']>=today_date)]
    promotion_today=promotion_today.drop(['shop_id','dt_from', 'dt_to'], axis=1)
    promotion_today = promotion_today.rename(columns={'name':'Акція'})
    promotion_today = promotion_today.drop_duplicates(subset=['product_id'], keep ='first')
    print("Promotion_today")
    print(promotion_today.head())


    #category hyerarhy
    categories = category()
    prods = product()

    print(prods.head())
    category_hyerarhy = add_category_hierarchy(prods, categories)
    
    
    category_hyerarhy=category_hyerarhy.rename(columns={'group':'Відділ','subgroup':'Категорія', 'subsubgroup':'Підкатегорія', 'subsubsubgroup':'Група', 'subsubsubgroups':'Підгрупа'})
    
    #Clearin droping thrash columns
    

   
    
    merge_need_abc['Сезон'] = merge_need_abc['Сезон'].replace(date(1970,1,1), '0')

    merge_need_abc = merge_need_abc.rename(columns={'product_id':'Код_товару', 'product_name':'Найменування', 'status':'Статус','price_incoming':'Ціна прихідна','price_retail':'Роздрібна ціна','suppliers_name':'Постачальник'})
    
    merge_need_abc = pd.merge(merge_need_abc, promotion_today,
                              left_on=['Код_товару'],
                              right_on=['product_id'],
                              how="left").fillna(0)

    merge_need_abc=merge_need_abc.drop(['today_stocs','product_id'], axis=1)
  
    
    merge_need_abc=merge_need_abc.rename(columns={'rounded_order':'Потреба розрахунок'})
    category_hyerarhy= category_hyerarhy.rename(columns={'id':'id_products'})
    merge_need_abc = pd.merge(merge_need_abc, category_hyerarhy,
                              left_on=['Код_товару'],
                              right_on=['id_products'], how='left').fillna(0)
    
    merge_need_abc["productcategory_id_x"] = merge_need_abc["productcategory_id_x"].replace('180ddb06-c260-11ed-a3e3-d4f9a95cd002','★')
    merge_need_abc["productcategory_id_x"] = merge_need_abc["productcategory_id_x"].replace(0,'')
    

    merge_need_abc = merge_need_abc.rename(columns={'name_x':'Найменування','supplier_id':'Код постачальника', 'neded_items_order_period':'Потреба', 'income_qty':'Товари в дорозі', "productcategory_id_x":"Ядро"})
    
   
    new_order=['Відділ', 'Підкатегорія',  'Категорія','Група', 'Підгрупа','Код_товару', 'Найменування', 'Статус', 'Постачальник', 'Ціна прихідна', 'Роздрібна ціна', 'Акція','Сезон', 'Потреба розрахунок','abc',"Ядро",'Товари в дорозі']
    
    merge_need_abc = merge_need_abc[new_order]
    merge_need_abc = pd.merge(merge_need_abc, today_stocs_pivot,
                              left_on=['Код_товару'],
                              right_on=['id_prod'],
                              how='left').fillna(0)
                     
    
    merge_need_abc = pd.merge(merge_need_abc, stocs_all_source, left_on = ['Код_товару'], right_on=['product_id'], how='left').fillna(0)
    
    merge_need_abc = merge_need_abc.rename(columns={'qty':'Залишки складу та магазинів'})
    merge_need_abc = merge_need_abc.drop(['id_prod', 'product_id'], axis=1)

    #add sales all_sources
    sales_all_sources = sales_all_sources.groupby('product_id', as_index=False)['sales_qty'].sum()
    
    merge_need_abc = pd.merge(merge_need_abc, sales_all_sources,
                              left_on=['Код_товару'],
                              right_on=['product_id'],
                              how='left').fillna(0)
    merge_need_abc=merge_need_abc.rename(columns={'sales_qty':'Сумарні продажі'})
    merge_need_abc=merge_need_abc.drop(['product_id'], axis=1)

    columns_to_move = ['Залишки складу та магазинів','Сумарні продажі','Потреба розрахунок']
    merge_need_abc = change_columns_direction(merge_need_abc, columns_to_move)
    
   
    print("AUTOORDER FINISH")
    print(merge_need_abc.head())
    
    return merge_need_abc, test_table, 



#################################################################################################
#x,y = auto_order_w_start(date_start=date(2025,1,1), date_finish=date(2025,1,10), days_of_order=7)
#x.to_excel('tests.xlsx')