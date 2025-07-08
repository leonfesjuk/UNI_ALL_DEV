from autoorder.analysis import sdp, promotions, prices_daily
import pandas as pd
import numpy as np 
from autoorder.conections import matrix, warhause_id, warhauses_smal, productprices, product, season_names, shop_name
from autoorder_m.healpers.category_maker import create_groups_list

def sales_loose_analysis(start_date, end_date):

    daily_price = prices_daily(start_date, end_date)
    daily_price = daily_price[['price', 'qty', 'product_id', 'date', 'shop_id']]

    daily_price['date'] = pd.to_datetime(daily_price['date'], errors='coerce').dt.date
    
    daily_price['line_item_total_price'] = daily_price['price'] * daily_price['qty']
    
    
    sdp_counted, sdp_all = sdp(
        start_date=start_date,
        end_date=end_date)
    promo = promotions(start_date)
    promo = promo[['shop_id', 'product_id', 'dt_from', 'dt_to']]
    promo  = promo.rename(columns={
        'dt_from': 'promo_start',
        'dt_to': 'promo_end',
        'shop_id': 'shop_id_promo',
        'product_id': 'product_id_promo'
    })
    loosing_days_promo = pd.merge(sdp_all, promo,
                                  left_on=['shop_id', 'product_id'],
                                  right_on=['shop_id_promo', 'product_id_promo'],
                                  how='left').fillna(0)
    
    
    matrix_active = matrix(1)
    matrix_active = matrix_active[['shop_id', 'product_id']]
    all_warehouses_to_exclude = [warhause_id] + warhauses_smal

    matrix_active = matrix_active[~matrix_active['shop_id'].isin(all_warehouses_to_exclude)]
    
    feucher_dates = pd.date_range(start = start_date, end =  end_date)
    multi_index =pd.MultiIndex.from_product([matrix_active['shop_id'].unique(), matrix_active['product_id'].unique(), feucher_dates], names=['shop_id', 'product_id', 'date_temp'])    
    df_feucher_dates_matrix = pd.DataFrame(index=multi_index).reset_index()
    df_feucher_dates_matrix['date_temp'] = df_feucher_dates_matrix['date_temp'].dt.date 
    daily_sales_and_stock = pd.merge(df_feucher_dates_matrix, loosing_days_promo,
                                     left_on=['shop_id', 'product_id', 'date_temp'],
                                     right_on=['shop_id', 'product_id', 'date'],
                                     how='left').fillna(0)
    daily_sales_and_stock = daily_sales_and_stock.drop(columns = ['date', 'shop_id_promo', 'product_id_promo'], axis = 1)
    daily_sales_and_stock['date_temp'] = pd.to_datetime(daily_sales_and_stock['date_temp']).dt.date
    daily_sales_and_stock['promo_start'] = pd.to_datetime(daily_sales_and_stock['promo_start'], errors='coerce').dt.date
    daily_sales_and_stock['promo_end'] = pd.to_datetime(daily_sales_and_stock['promo_end'], errors='coerce').dt.date

    promo_condition = (
        (daily_sales_and_stock['date_temp'] >= daily_sales_and_stock['promo_start']) & 
        (daily_sales_and_stock['date_temp'] <= daily_sales_and_stock['promo_end'])
    )
    daily_sales_and_stock['is_promo'] = np.where(promo_condition, 1, 0)
    daily_sales_and_stock = daily_sales_and_stock.drop(columns = ['promo_start', 'promo_end'], axis = 1 )


    daily_sales_and_stock['is_active'] = np.where(
        (daily_sales_and_stock['stocs_qty'] > 0) | (daily_sales_and_stock['sales_qty'] > 0), 1, 0)

    daily_sales_and_stock['promo_sales'] = np.where(
        daily_sales_and_stock['is_promo'] ==1, daily_sales_and_stock['sales_qty'], 0)

    daily_sales_and_stock['non_promo_sales'] = np.where(
        daily_sales_and_stock['is_promo'] == 0, daily_sales_and_stock['sales_qty'], 0
    )
    daily_sales_and_stock['active_promo_days'] = np.where(
        daily_sales_and_stock['is_promo'] == 1, daily_sales_and_stock['is_active'], 0
    )
        
    daily_sales_and_stock['active_non_promo_days'] = np.where(
        daily_sales_and_stock['is_promo'] == 0, daily_sales_and_stock['is_active'], 0
    )

    daily_sales_and_stock['out_of_stock_days_non_promo'] = np.where(
        (daily_sales_and_stock['is_promo'] == 0) & (daily_sales_and_stock['is_active'] == 0 ), 1, 0 
    )
    
    daily_sales_and_stock['out_of_stock_days_promo'] = np.where(
        (daily_sales_and_stock['is_promo'] == 1) & (daily_sales_and_stock['is_active'] == 0 ), 1, 0 
    )
    
    prices_for_merge = daily_price[['shop_id', 'product_id', 'date', 'price' ]]
    prices_for_merge = prices_for_merge.rename(columns={'date': 'date_close'})

    daily_price_promo_non_promo = pd.merge(daily_sales_and_stock, prices_for_merge,
                           left_on=['shop_id', 'product_id', 'date_temp'],
                           right_on=['shop_id', 'product_id', 'date_close'],
                           how='left').fillna(0)
    price = productprices(end_date)
    price = price[['product_id', 'price_retail', 'date']]
    # Convert 'date' column to date objects to match the type of 'date_temp' for merging
    price['date'] = pd.to_datetime(price['date']).dt.date
    daily_price_promo_non_promo = pd.merge(daily_price_promo_non_promo, price,
                                           left_on=['product_id', 'date_temp'],
                                           right_on=['product_id', 'date'],
                                           how='left').fillna(0)

    # Use np.nan to correctly calculate the mean, ignoring days without sales
    daily_price_promo_non_promo['promo_price'] = np.where(
        (daily_price_promo_non_promo['is_promo'] == 1) & (daily_price_promo_non_promo['price'] > 0),
        daily_price_promo_non_promo['price'],
        np.nan  # Use nan so mean() ignores it
    )

    daily_price_promo_non_promo['non_promo_price'] = np.where(
        (daily_price_promo_non_promo['is_promo'] == 0) & (daily_price_promo_non_promo['price'] > 0),
        daily_price_promo_non_promo['price'],
        np.nan  # Use nan so mean() ignores it
    )
    
    # Also replace 0 in price_retail with nan
    daily_price_promo_non_promo['price_retail'] = daily_price_promo_non_promo['price_retail'].replace(0, np.nan)

    # Calculate average for all three price types
    avg_prices = daily_price_promo_non_promo.groupby(['shop_id', 'product_id']).agg(
        avg_promo_price=('promo_price', 'mean'),
        avg_non_promo_price=('non_promo_price', 'mean'),
        avg_pricelist_price=('price_retail', 'mean') # Add pricelist price to the aggregation
    ).reset_index().fillna(0)
    
   


    grouped_df_sales_stocs_promo = daily_sales_and_stock.groupby(['shop_id', 'product_id']).agg(
        sales_non_promo = ('non_promo_sales', 'sum'),
        sales_promo = ('promo_sales', 'sum'),
        non_promo_days = ('active_non_promo_days', 'sum'),
        promo_days = ('active_promo_days', 'sum'),
        out_of_stock_days_non_promo = ('out_of_stock_days_non_promo', 'sum'),
        out_of_stock_days_promo = ('out_of_stock_days_promo', 'sum'),
        total_active_days = ('is_active', 'sum')

    ).reset_index()

    sdp_looses = grouped_df_sales_stocs_promo.assign(
        sdp_non_promo = np.where((grouped_df_sales_stocs_promo['non_promo_days'] <= 0) | (grouped_df_sales_stocs_promo['total_active_days'] <= 3), 0, (grouped_df_sales_stocs_promo['sales_non_promo'] / grouped_df_sales_stocs_promo['non_promo_days']).round(2)),
        sdp_promo = np.where((grouped_df_sales_stocs_promo['promo_days'] <= 0) | (grouped_df_sales_stocs_promo['total_active_days'] <= 3), 0, (grouped_df_sales_stocs_promo['sales_promo'] / grouped_df_sales_stocs_promo['promo_days']).round(2)),
        total_out_of_stock_days = grouped_df_sales_stocs_promo['out_of_stock_days_promo'] + grouped_df_sales_stocs_promo['out_of_stock_days_non_promo']
    )
    
    sdp_looses['loose_none_promo_sales_qty'] = (sdp_looses['sdp_non_promo'] * sdp_looses['out_of_stock_days_non_promo']).round(2)
    sdp_looses['loose_promo_sales_qty'] = (sdp_looses['sdp_promo'] * sdp_looses['out_of_stock_days_promo']).round(2)
    sdp_looses['loose_all_sales_qty'] = sdp_looses['loose_none_promo_sales_qty'] + sdp_looses['loose_promo_sales_qty']

    # --- New logic for calculating lost revenue ---
    # Merge sdp_looses with avg_prices to have all data in one place
    sdp_looses = pd.merge(sdp_looses, avg_prices, on=['shop_id', 'product_id'], how='left').fillna(0)

    # Simplified cascade logic as per your request
    sdp_looses['effective_price_non_promo'] = np.where(
        sdp_looses['avg_non_promo_price'] > 0,
        sdp_looses['avg_non_promo_price'],
        sdp_looses['avg_pricelist_price'] # Fallback to pricelist price
    )

    # Simplified cascade logic as per your request
    sdp_looses['effective_price_promo'] = np.where(
        sdp_looses['avg_promo_price'] > 0,
        sdp_looses['avg_promo_price'],
        sdp_looses['avg_pricelist_price'] # Fallback to pricelist price
    )

    # Calculate final lost revenue
    sdp_looses['loose_none_promo_revenue'] = (sdp_looses['loose_none_promo_sales_qty'] * sdp_looses['effective_price_non_promo']).round(2)
    sdp_looses['loose_promo_revenue'] = (sdp_looses['loose_promo_sales_qty'] * sdp_looses['effective_price_promo']).round(2)
    sdp_looses['loose_all_revenue'] = sdp_looses['loose_none_promo_revenue'] + sdp_looses['loose_promo_revenue']

    prod = product(True)
    prod = prod[["id", "name", "status", "season", "category_id"]]
    
    # Convert merge keys to string type as requested by the user
    sdp_looses['product_id'] = sdp_looses['product_id'].astype(str)
    prod['id'] = prod['id'].astype(str)

    sdp_looses = pd.merge(sdp_looses, prod,
                          left_on='product_id',
                          right_on='id',
                          how='left').fillna(0)

    sdp_looses_filtered = sdp_looses[sdp_looses['id'] != 0]
    category_names = create_groups_list()
    category_names = category_names[['id', 'group']]
    sdp_looses_filtered = pd.merge(sdp_looses_filtered, category_names,
                                   left_on='product_id',
                                   right_on='id',
                                   how='left').fillna(0)
    
    stocs = sdp_all.copy()
    target_ids = [warhause_id, warhauses_smal]
    stocs_warhauses = stocs[(stocs['shop_id'].isin(target_ids) &
    (stocs['date'] == end_date))]
    stocs_markets = stocs[((~stocs['shop_id'].isin(target_ids)) &
    (stocs['date'] == end_date))]

    stocs_warhauses_sum = stocs_warhauses.groupby("product_id")["stocs_qty"].sum().reset_index().rename(
    columns={'stocs_qty': 'stocs_qty_warehouse'})
    stocs_markets_sum = stocs_markets.groupby("product_id")["stocs_qty"].sum().reset_index().rename(
        columns={'stocs_qty': 'stocs_qty_market'}
    )
    
    sdp_looses_filtered = pd.merge(sdp_looses_filtered,stocs_warhauses_sum,
                                   left_on='product_id',
                                   right_on='product_id',
                                   how='left').fillna(0)
    
    sdp_looses_filtered = pd.merge(sdp_looses_filtered,stocs_markets_sum,
                                   left_on='product_id',
                                   right_on='product_id',
                                   how='left').fillna(0)
    season_names_df = season_names()
    season_names_df = season_names_df[['id', 'name']]
    season_names_df = season_names_df.rename(columns = {'id':'season_id', 'name':'season_name'})
    sdp_looses_filtered = pd.merge(sdp_looses_filtered, season_names_df,
                                   left_on='season',
                                   right_on='season_id',
                                   how='left').fillna(0)
    markets_name = shop_name()
    markets_name = markets_name.rename(columns={'id':'id_market', 'name':'market_name'})
    sdp_looses_filtered = pd.merge(sdp_looses_filtered, markets_name,
                                   left_on='shop_id',
                                   right_on='id_market',
                                   how='left').fillna(0)


    new_column_direction = ['shop_id', 'market_name', 'name', 'product_id', 'group', 'status', 'season_name', 'sales_non_promo', 'sales_promo', 'non_promo_days',
                            'promo_days', 'out_of_stock_days_non_promo', 'out_of_stock_days_promo', 'sdp_non_promo',
                            'sdp_promo', 'total_out_of_stock_days', 'loose_none_promo_sales_qty', 'loose_promo_sales_qty',
                            'loose_all_sales_qty', 'avg_promo_price', 'avg_non_promo_price', 'avg_pricelist_price'
                            , 'loose_none_promo_revenue', 'loose_promo_revenue',
                            'loose_all_revenue', 'stocs_qty_warehouse', 'stocs_qty_market']
    
    sdp_looses_filtered = sdp_looses_filtered[new_column_direction]

    sdp_looses_filtered = sdp_looses_filtered.rename(columns = {'shop_id':'Код товару', 'market_name':'Назва магазину','name':'Назва товару','group':'Група товарів','status':'Статус товару',
                                                                  'season_name':'Сезон', 'sales_non_promo':'Продажі неакційні', 'sales_promo':'Продажі акційні',
                                                                  'non_promo_days':'Неакційні дні', 'promo_days':'Акційні дні', 'out_of_stock_days_non_promo':'Неакційні дні відсутності товару',
                                                                  'out_of_stock_days_promo':'Акційні дні відсутності товару', 'sdp_non_promo':'Сдп неакційне','sdp_promo':'Сдп акційне',
                                                                  'total_out_of_stock_days':'Загальна кількість днів відсутності товару', 'loose_none_promo_sales_qty':'Втрачені неакційні продажі шт.',
                                                                  'loose_promo_sales_qty':'Втрачені акційні продажі шт.', 'loose_all_sales_qty':'Загалом втрачені продажі шт.', 'avg_promo_price':'Середня акційна ціна грн.',
                                                                  'avg_non_promo_price':'Середня неакційна ціна грн.', 'avg_pricelist_price':'Середня ціна прайсова грн.', 'loose_none_promo_revenue':'Втрачені неакційні продажі грн.',
                                                                   'loose_promo_revenue':'Втрачені акційні продажі в грн.', 'loose_all_revenue':'Загальні втрачені продажі грн.',
                                                                    'stocs_qty_warehouse':'Залишки всіх складів шт.', 'stocs_qty_market':'Залишки всіх магазинів шт.' })

    return sdp_looses_filtered