from api.helpers.loger import init_logger
from autoorder.conections import *

#from .conections import check, product, receipt, matrix, stoks, promo, promo_items, season_names, supplierproductm2m, supplier_name, cat_man_name, category_manager, retry_on_operational_error
import pandas as pd
from datetime import date, datetime, timedelta, time
import numpy as np
from sqlalchemy import  exc

my_logger = init_logger()
my_logger.debug("Логер ініціалізований у analysis.py")
#create dataframe with product_id, syppliers_id, suppliers_name
"""
def suppliers():
  suplier_names = supplier_name()
 

  supplier_product = product()
  supplier_product = supplier_product.drop(['name','status', 'season', 'category_id'], axis=1)
  supplier_product = supplier_product.rename(columns={'id':'product_id'})
 
 
  
  suppliers = pd.merge(supplier_product, suplier_names,
                       left_on = ['supplier_id'],
                       right_on= ['id'],
                       how = 'inner').fillna(0)
  suppliers = suppliers.drop(['id'], axis=1)
  print("suppliers:")
  print(suppliers.head(n=2))
  return suppliers
"""

#create dataframe with categories and managers

def categories():
  my_logger.debug("Starting categories")
  category_name = cat_man_name()
  categori_and_managers = category_manager()
  result = pd.merge(categori_and_managers, category_name,
                    left_on=['manager_id'],
                    right_on=['id'],
                    how='left').fillna(0)
  result = result.drop(['manager_id', 'id'], axis=1)
  my_logger.debug("Finishing categories")
  my_logger.debug(result.head(n=2))
 
  return result

#create df with supliers

def suplaer_id():
  
  suplaer_id = product()
  suplaer_id = suplaer_id.drop(['name','status', 'season', 'category_id'], axis=1)
  suplaer_id = suplaer_id.rename(columns={'id':'product_id'})
  
  suplaer_name = supplier_name()

  suplier_df = pd.merge(suplaer_id, suplaer_name,left_on=['supplier_id'], right_on=['id'], how='inner').fillna(0)
  suplier_df = suplier_df.drop(['id'], axis =1)
  suplier_df = suplier_df.rename(columns={'name':'suppliers_name'})
  print("suplaer_id:")
  print(suplier_df.head(n=2))
 
  return suplier_df


def prices_daily(start_date, end_date):
  try:
    check_data = check(start_date, end_date, prices=True)
    if check_data is None:
      my_logger.warning("check_data is None")
      return None
  except Exception as e:
    my_logger.error(f"Error in check: {e}")
    return None
  
  try:
  # Call the receipt function from conections module
    receipt_data = receipt(start_date=start_date, end_date=end_date)
    if receipt_data is None:
      my_logger.warning("receipt_data is None")
      return None
  except Exception as e:
    my_logger.error(f"Error in receipt: {e}")
    return None
  
  check_df = pd.merge(check_data, receipt_data,  # Use receipt_data instead of receipt
      left_on = ['receipt_id'],
      right_on = ['id'],how = 'left')
  
  return check_df


  

#dataframe prices

def day_sales_stocs(start_date, end_date):
  try:
    check_data = check(start_date, end_date)  # Assuming check returns data
    if check_data is None:
      my_logger.warning("check_data is None")
      return None
  except Exception as e:
    my_logger.error(f"Error in check: {e}")
    return None

  try:
  # Call the receipt function from conections module
    receipt_data = receipt(start_date=start_date, end_date=end_date)
    if receipt_data is None:
      my_logger.warning("receipt_data is None")
      return None
  except Exception as e:
    my_logger.error(f"Error in receipt: {e}")
    return None
  
  try:
    stocs =  stoks(start_date, end_date)
    if stocs is None:
      my_logger.warning("stocs is None")
      return None
  except Exception as e:
    my_logger.error(f"Error in stocs: {e}")
    return None

  check_df = pd.merge(check_data, receipt_data,  # Use receipt_data instead of receipt
      left_on = ['receipt_id'],
      right_on = ['id'],how = 'left')
  check_df = check_df.drop(['receipt_closed_at', 'id', 'closed_at', 'date_close'], axis=1)
  result_df = check_df.groupby(['shop_id', 'product_id','date']).agg({'qty': 'sum'}).reset_index()
 
  result_df = result_df.rename(columns={'qty':'sales_qty'})
  day_sales_stocs = pd.merge(result_df, stocs,
                             left_on = ['shop_id', 'product_id', 'date'],
                             right_on = ['shop_id','product_id', 'date'],
                             how = 'outer')
  day_sales_stocs = day_sales_stocs.drop(['id','dt'], axis = 1)
  day_sales_stocs = day_sales_stocs.rename(columns={'qty':'stocs_qty'})
  day_sales_stocs = day_sales_stocs.fillna(0)
  day_sales_stocs[['sales_qty', 'stocs_qty']] = day_sales_stocs[['sales_qty', 'stocs_qty']].clip(lower=0)
  print("day_sales_stocs:")
  print(day_sales_stocs.head(n=2))
  return day_sales_stocs


def day_sales_stocs_by_shop(start_date, end_date, shop_ids):
    try:
        check_data = check(start_date, end_date)
        if check_data is None:
            my_logger.warning("check_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in check: {e}")
        return None

    try:
        receipt_data = receipt(start_date=start_date, end_date=end_date)
        if receipt_data is None:
            my_logger.warning("receipt_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in receipt: {e}")
        return None

    try:
        stocs_data = stoks(start_date, end_date)
        if stocs_data is None:
            my_logger.warning("stocs is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in stocs: {e}")
        return None

    receipt_data = receipt_data[receipt_data["shop_id"].isin(shop_ids)]

    check_df = pd.merge(check_data, receipt_data,
        left_on=["receipt_id"],
        right_on=["id"], how="inner")
    check_df = check_df.drop(["receipt_closed_at", "id", "closed_at", "date_close"], axis=1)
    result_df = check_df.groupby(["shop_id", "product_id", "date"]).agg({"qty": "sum"}).reset_index()
    result_df = result_df.rename(columns={"qty": "sales_qty"})

    stocs_data = stocs_data[stocs_data["shop_id"].isin(shop_ids)]

    df = pd.merge(result_df, stocs_data,
        left_on=["shop_id", "product_id", "date"],
        right_on=["shop_id", "product_id", "date"],
        how="outer")
    df = df.drop(["id", "dt"], axis=1)
    df = df.rename(columns={"qty": "stocs_qty"})
    df = df.fillna(0)
    df[["sales_qty", "stocs_qty"]] = df[["sales_qty", "stocs_qty"]].clip(lower=0)
    print("day_sales_stocs_by_shop:")
    print(df.head(n=2))
    return df


def prices_daily_by_shop(start_date, end_date, shop_ids):
    try:
        check_data = check(start_date, end_date, prices=True)
        if check_data is None:
            my_logger.warning("check_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in check: {e}")
        return None

    try:
        receipt_data = receipt(start_date=start_date, end_date=end_date)
        if receipt_data is None:
            my_logger.warning("receipt_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in receipt: {e}")
        return None

    receipt_data = receipt_data[receipt_data["shop_id"].isin(shop_ids)]

    check_df = pd.merge(check_data, receipt_data,
        left_on=["receipt_id"],
        right_on=["id"], how="inner")
    return check_df


def stoc_today():
  #today = date.today() 
  today = date(2024,9,22)# temp simulation today 
  stocs_today = stoks(today,today)
  print("stoc_today:")
  print(stocs_today.head(n=2))
  return stocs_today

#merge promos, result -> promo code, day, market

  

def promotions(start_date):
  try:
    promos = promo(start_date - timedelta(days=90)) # береться додатково період 15 днів, на випадок, якщо акція була запущена раніше і активна
    if promos is None:
      my_logger.warning("promos is None")
      return None
    
    
    
    promo_item = promo_items()
    if promo_item is None:
      my_logger.warning("promo_item is None")
      return None
  
  
  
    promo_item = promo_item.drop(['id'], axis = 1) 
    promotions = pd.merge(promo_item, promos,
                          left_on=['promo_id'],
                          right_on=['id'],
                          how='inner')
    promos = promotions.drop(['id', 'promo_id'], axis = 1)
    
    
    #duplicates = promos.duplicated()
    #print(duplicates.sum())
      
    promos['dt_from'] = pd.to_datetime(promos['date_from']).dt.date
    promos['dt_to'] = pd.to_datetime(promos['date_to']).dt.date
    promos = promos.drop(['date_from', 'date_to'], axis = 1)
    print("promotions:")
    print(promos.head(n=2))

    return promos
  except Exception as e:
    my_logger.error(f"Error in promotions: {e}")
    return None
    


def sdp(start_date, end_date, detailed = False):
  my_logger.debug(f"sdp -> start: start_date={start_date}, end_date={end_date}")
  try:
    my_logger.debug("sdp -> calling day_sales_stocs") 
    sales_stocs = day_sales_stocs(start_date, end_date)
    my_logger.debug("sdp -> day_sales_stocs finished")
  except exc.OperationalError as e:
        my_logger.error(f"Error in day_sales_stocs: {e}")
        return None, None
  if sales_stocs is None:
    my_logger.warning("sales_stocs is None")
    return None, None
  
  sales_all_sources = sales_stocs.copy()
  try:
    my_logger.debug("sdp -> calling promotions")
    promo = promotions(start_date)
    
    my_logger.debug("sdp -> promotions returned")
    
  except exc.OperationalError as e:
    my_logger.error(f"Error in promotions: {e}")
    return None, None
  if promo is None:
    my_logger.warning("promo is None")
    return None, None
    
  my_logger.debug("sdp -> merging sales_stocs and promo")
  try:
    merged_df = pd.merge(sales_stocs, promo,              
                  left_on = ['product_id', 'shop_id'],
                  right_on = ['product_id', 'shop_id'],
                  how = 'left' )
    my_logger.debug("sdp -> fillna completed")
  except:
    my_logger.error(f"Error in fillna: {e}")
    return None, None
      
  
  try:
    merged_df['dt_from'] = merged_df['dt_from'].fillna(pd.Timestamp('1000-01-01').date())
    merged_df['dt_to'] = merged_df['dt_to'].fillna(pd.Timestamp('1000-01-01').date())
    my_logger.debug("sdp -> fillna completed")
  except Exception as e:
    my_logger.error(f"Error in fillna: {e}")
    return None, None
  
  try:
    merged_df = merged_df.fillna(0)
    my_logger.debug("sdp -> fillna(0) completed")
  except Exception as e:
    my_logger.error(f"Error in fillna(0): {e}")
    return None, None

  #create column with boolean promo or not
  try:
    merged_df['is_promo'] = ((merged_df['date'] >= merged_df['dt_from']) & (merged_df['date'] <= merged_df['dt_to'])).astype(int)
    my_logger.debug("sdp -> is_promo completed")
  except Exception as e:
        my_logger.error(f"Error in days_qty_no_promo: {e}")
        return None, None
  #create is stoc - boolean that means stocs in each day

  merged_df['is_stoc'] = ((merged_df['sales_qty'] > 0) | (merged_df['stocs_qty'] > 0)).astype(int)
  #count days for promo and no prommo
  days_qty_no_promo = merged_df[merged_df['is_promo'] == 0].groupby(['product_id', 'shop_id']).agg(days_no_promo=('is_stoc', 'sum'), sales_no_promo=('sales_qty', 'sum')).reset_index()
  
  days_qty_no_promo['sdp_no_promo'] = np.where(days_qty_no_promo['days_no_promo'] != 0, days_qty_no_promo['sales_no_promo'] / days_qty_no_promo['days_no_promo'], 0)

  days_qty_promo = merged_df[merged_df['is_promo'] == 1].groupby(['product_id', 'shop_id']).agg(
    days_promo=('is_stoc', 'sum'),
    sales_promo=('sales_qty', 'sum')
    ).reset_index()
  days_qty_promo['sdp_promo'] = np.where(days_qty_promo['days_promo'] != 0, days_qty_promo['sales_promo'] / days_qty_promo['days_promo'], 0)
  
  sdp_all = pd.merge(days_qty_no_promo, days_qty_promo,
                     left_on = ['product_id', 'shop_id'],
                     right_on = ['product_id', 'shop_id'],
                     how = 'outer').fillna(0)
  print("sdp -> finish:")
  print(sdp_all.head(n=2))

  if detailed:
    return  sdp_all, sales_all_sources, merged_df
  
  return sdp_all, sales_all_sources

today = date.today() 

def future_promo(date_start,  days_of_order):
  print("future_promo -> start:")
  today = date.today() 
  today = today.timetuple().tm_yday
  #days_of_order = days_of_order.timetuple().tm_yday
  #invert date to numbers for numpy
  next_promo = promotions(date_start)
   
  next_promo['dt_from'] = pd.to_datetime(next_promo['dt_from'])
  
  next_promo['dt_from_number'] = next_promo['dt_from'].dt.dayofyear
  next_promo['dt_to'] = pd.to_datetime(next_promo['dt_to'])
  next_promo['dt_to_number'] = next_promo['dt_to'].dt.dayofyear
  
  #create fucher date
  dates_range = np.arange(today,  today + days_of_order)



  # Створимо матрицю, де кожен рядок - це товар, а кожен стовпець - день
# 1 означає, що товар в акції в цей день
  is_on_sale = (
    (next_promo['dt_from_number'].values[:, np.newaxis] <= dates_range) &
    (dates_range <= next_promo['dt_to_number'].values[:, np.newaxis])
  )
#count days inn promo and without promo
  next_promo['next_promo_days'] = is_on_sale.sum(axis=1)
  #next_promo['next_no_promo_days'] = days_of_order# - next_promo['next_promo_days']
  result = pd.DataFrame(next_promo)
  final_result = next_promo[next_promo['next_promo_days'] > 0].copy()
  print("future_promo -> finish:")
  print(result.head(n=2))
  return final_result
   
  


#ABC analis by sdp_no_promo

def abc_analysis_vectorized(df):
  print("abc_analysis_vectorized -> start:")
  
  #group and count SDP
  grouped = df.groupby(['shop_id','product_id']).sum()
  # % sales
  grouped['sdp_no_promo_percentage'] = grouped.groupby(level=0)['sdp_no_promo'].transform(lambda x: x/x.sum())
  #sort by markets
  grouped = grouped.sort_values(['shop_id', 'sdp_no_promo_percentage'], ascending = False)
  #cumulatives
  grouped['cumsum'] = grouped.groupby(level=0)['sdp_no_promo_percentage'].cumsum()
  #categorythe
  grouped['abc'] = np.where(grouped['cumsum'] <= 0.8, 'A',
                            np.where(grouped['cumsum'] <= 0.9,
                                     'B',
                                     'C'))
  
  print("abc_analysis_vectorized -> finish:")
  print(grouped.head(n=2))
  return grouped

def abc_analysis_all(df):
  
  grouped = df.drop(['shop_id', 'days_no_promo', 'sales_no_promo', 'sales_promo', 'days_promo', 'sdp_promo'], axis = 1)
  grouped = grouped.groupby(['product_id']).sum()
  # Calculate percentage of total SDP
  grouped['sdp_no_promo_percentage'] = grouped['sdp_no_promo'] / grouped['sdp_no_promo'].sum()

    # Sort by percentage
  grouped = grouped.sort_values('sdp_no_promo_percentage', ascending=False)

    # Calculate cumulative percentage
  grouped['cumsum'] = grouped['sdp_no_promo_percentage'].cumsum()

    # Assign ABC categories
  grouped['abc'] = np.where(grouped['cumsum'] <= 0.8, 'A',
                              np.where(grouped['cumsum'] <= 0.9, 'B', 'C'))
  grouped = grouped.reset_index()
  grouped = grouped.drop(['sdp_no_promo', 'sdp_no_promo_percentage', 'cumsum'], axis = 1)
  
  print("abc_analysis_all -> finish:")
  print(grouped.head(n=2))
  return grouped
  

def change_columns_direction(df, columns_to_move):
  all_columns = list(df.columns)
  remaining_columns = [col for col in all_columns if col not in columns_to_move]
  new_column_order = remaining_columns + columns_to_move
  df = df[new_column_order]
  return df


#x , y = sdp(date(2024,11,1), date(2024,11,16))
#x.to_excel("daysqttpromo.xlsx")
#y.to_excel("salesallsources.xlsx")

#y= promotions(date(2024,9,3))
#y.to_excel("promo.xlsx")
#suplaer_id()

def prices_daily_by_shop_filtered(start_date, end_date, shop_ids):
    try:
        check_data = check_by_shop(start_date, end_date, shop_ids, prices=True)
        if check_data is None:
            my_logger.warning("check_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in check_by_shop: {e}")
        return None

    try:
        receipt_data = receipt_by_shop(start_date=start_date, end_date=end_date, shop_ids=shop_ids)
        if receipt_data is None:
            my_logger.warning("receipt_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in receipt_by_shop: {e}")
        return None

    check_df = pd.merge(check_data, receipt_data,
        left_on=["receipt_id"],
        right_on=["id"], how="inner")
    return check_df


def day_sales_stocs_by_shop_filtered(start_date, end_date, shop_ids):
    try:
        check_data = check_by_shop(start_date, end_date, shop_ids)
        if check_data is None:
            my_logger.warning("check_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in check_by_shop: {e}")
        return None

    try:
        receipt_data = receipt_by_shop(start_date=start_date, end_date=end_date, shop_ids=shop_ids)
        if receipt_data is None:
            my_logger.warning("receipt_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in receipt_by_shop: {e}")
        return None

    try:
        stocs_data = stoks_by_shop(start_date, end_date, shop_ids)
        if stocs_data is None:
            my_logger.warning("stocs_data is None")
            return None
    except Exception as e:
        my_logger.error(f"Error in stoks_by_shop: {e}")
        return None

    check_df = pd.merge(check_data, receipt_data,
        left_on=["receipt_id"],
        right_on=["id"], how="inner")
    check_df = check_df.drop(["receipt_closed_at", "id", "closed_at", "date_close"], axis=1)
    result_df = check_df.groupby(["shop_id", "product_id", "date"]).agg({"qty": "sum"}).reset_index()
    result_df = result_df.rename(columns={"qty": "sales_qty"})

    df = pd.merge(result_df, stocs_data,
        left_on=["shop_id", "product_id", "date"],
        right_on=["shop_id", "product_id", "date"],
        how="outer")
    df = df.drop(["id", "dt"], axis=1)
    df = df.rename(columns={"qty": "stocs_qty"})
    df = df.fillna(0)
    df[["sales_qty", "stocs_qty"]] = df[["sales_qty", "stocs_qty"]].clip(lower=0)
    print("day_sales_stocs_by_shop_filtered:")
    print(df.head(n=2))
    return df
