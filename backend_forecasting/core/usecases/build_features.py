from datetime import date

import pandas as pd

from core.gateway.i_data_gateway import DataInputGateway
from config.promo_types import PROMO_TYPES


def build_feature_dataframe(start_date: date, end_date: date, gateway: DataInputGateway | None = None) -> pd.DataFrame:
    from adapters.secondary.data.erp_gateway import ErpDataInputGateway
    gw: DataInputGateway = gateway or ErpDataInputGateway(start_date, end_date)

    sales = gw.sales_stocks_daily()
    promo_defs = gw.promo()
    promo_links = gw.promo_links()
    prices = gw.daily_prices()
    weather = gw.weather()
    holidays = gw.holidays()
    cats = gw.category_hierarchy()

    promo_active = promo_links.merge(
        promo_defs[['id', 'type_id', 'date_from', 'date_to']],
        left_on='promo_id',
        right_on='id',
        how='inner'
    )

    promo_daily = promo_active.assign(
        date=promo_active.apply(
            lambda r: pd.date_range(r['date_from'], r['date_to'], freq='D'),
            axis=1
        )
    ).explode('date')
    promo_daily['date'] = pd.to_datetime(promo_daily['date']).dt.date
    promo_daily = promo_daily[['shop_id', 'product_id', 'date', 'type_id']].drop_duplicates()

    df = sales.merge(
        promo_daily,
        on=['shop_id', 'product_id', 'date'],
        how='left'
    )
    df['is_promo'] = df['type_id'].notna()
    df['promo_type_id'] = df['type_id'].map(PROMO_TYPES).fillna(0).astype(int)
    df = df.drop(columns=['type_id'])

    daily_price = prices.groupby(['shop_id', 'product_id', 'date'], as_index=False)['price'].mean()
    daily_price['price'] = daily_price['price'].round(1)

    df = df.merge(
        daily_price[['shop_id', 'product_id', 'date', 'price']],
        on=['shop_id', 'product_id', 'date'],
        how='left'
    )

    df = df.merge(weather, on='date', how='left')
    df = df.merge(holidays, on='date', how='left')
    df = df.merge(cats, on='product_id', how='left')

    df['has_stock'] = ((df['sales_qty'] > 0) | (df['stocs_qty'] > 0)).astype(bool)

    df['day_of_week'] = pd.to_datetime(df['date']).dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(bool)
    df['month'] = pd.to_datetime(df['date']).dt.month

    df = df.drop(columns=['stocs_qty'])

    return df
