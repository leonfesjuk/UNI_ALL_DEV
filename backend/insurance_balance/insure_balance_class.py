from datetime import date
import pandas as pd
import numpy as np
from autoorder.analysis import sdp
from api.helpers.loger import my_logger


class Insure_Balance:
    def __init__(self, df_sdp: pd.DataFrame, df_daily_sales: pd.DataFrame): #Need df "sdp, 1 and 3 variable with details = True"
        self.df_sdp = df_sdp
        self.df_daily_sales = df_daily_sales

        required_columns_sdp= ['product_id', 'shop_id', 'days_no_promo', 'sales_no_promo','sdp_no_promo', 'days_promo','sdp_promo', 'sales_promo']
        if not all(col in df_sdp.columns for col in required_columns_sdp):
                raise ValueError(f"DataFrame повинен містити наступні стовпці: {required_columns_sdp}")
        
        required_columns_daily_sales = ['shop_id', 'product_id', 'date', 'sales_qty', 'stocs_qty', 'is_promo', 'is_stoc']

        if not all(col in df_daily_sales.columns for col in required_columns_daily_sales):
                raise ValueError(f"DataFrame повинен містити наступні стовпці: {required_columns_daily_sales}")
        
        self.df_sdp = df_sdp.copy()
        self.df_daily_sales = df_daily_sales.copy()


        #metods
        
        #adding SDP promo - no promo to daily sales
    def merge_sales_sdp(self):
        sdp_data = self.df_sdp[['product_id', 'shop_id', 'sdp_no_promo', 'sdp_promo']].drop_duplicates()
        self.df_daily_sales = pd.merge(self.df_daily_sales, sdp_data, on=['product_id', 'shop_id'], how='left').fillna(0)
        self.df_daily_sales.drop(columns=['dt_from', 'dt_to', 'name'], inplace=True)
        my_logger.info(f"Merged SDP data into daily sales.{self.df_daily_sales.head()}")
                

        

        

