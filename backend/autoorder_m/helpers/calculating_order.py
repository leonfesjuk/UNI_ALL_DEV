import math
import pandas as pd



def calculate_order_stage_1(row):
    if row['warehouse_stocs_qty'] <= 0:
        return 0
    elif (row['warehouse_stocs_qty'] >= row['total_pure_need_items_insure_rounded']):
        return row['pure_need_items_insure_rounded']
    elif (row['total_pure_need_items_insure_matematik_rounded'] <= row['warehouse_stocs_qty']) and (row['notmultiplicitypacking'] != 1) and (row['pure_need_items_insure_rounded'] >= 0):
        return row['pure_need_items_insure_matematik_rounded']
    elif (row['total_pure_need_items_insure_matematik_rounded'] >= row['warehouse_stocs_qty']) and (row['notmultiplicitypacking'] != 1):
        return int(row['warehouse_stocs_qty'] * row['pure_need_items_%'])
    elif (row['total_pure_need_items_insure_matematik_rounded'] <= row['warehouse_stocs_qty']) and (row['notmultiplicitypacking'] == 1):
        individual_need = row['total_pure_need_items_insure_matematik_rounded'] * row['pure_need_items_%']
        return math.floor(individual_need / row['numb_pack']) * row['numb_pack']
    
            

        
def calculate_order_stage_2(base_table):
    
    product_level_summary = base_table.groupby('product_id').agg(
        total_order_stage_1=('order_stage_1', 'sum'),
        original_warehouse_stocs_qty=('warehouse_stocs_qty', 'first'),
        total_pure_need_items_insure_rounded_per_product=('total_pure_need_items_insure_rounded', 'first')
        ).reset_index()
    product_level_summary['remaining_stock_after_stage1'] = \
    product_level_summary['original_warehouse_stocs_qty'] - product_level_summary['total_order_stage_1']

    products_for_stage2 = product_level_summary[
    (product_level_summary['original_warehouse_stocs_qty'] < product_level_summary['total_pure_need_items_insure_rounded_per_product']) &
    (product_level_summary['remaining_stock_after_stage1'] > 0)]

    base_table['order_stage_2'] = 0

    for _, product_row in products_for_stage2.iterrows():
        product_id = product_row['product_id']
        current_remaining_stock = product_row['remaining_stock_after_stage1']

        # Фільтруємо магазини для поточного товару, у яких pure_need_items_% > 0,
        # і сортуємо їх за pure_need_items_% за спаданням.
        # Отримуємо індекси рядків DataFrame для зручного оновлення за допомогою .loc
        relevant_shops_indices = base_table[(base_table['product_id'] == product_id) & (base_table['pure_need_items_%'] > 0)].sort_values(
            by='pure_need_items_%', ascending=False
        ).index.tolist()

        for shop_idx in relevant_shops_indices:
            if current_remaining_stock <= 0:
                break # Зупиняємо розподіл, якщо склад вичерпано

            # Розраховуємо залишкову потребу магазину після першого етапу
            order_stage_1_qty = base_table.loc[shop_idx, 'order_stage_1']
            shop_pure_need_insure_rounded = base_table.loc[shop_idx, 'pure_need_items_insure_rounded']
            remaining_need = shop_pure_need_insure_rounded - order_stage_1_qty
            
            if remaining_need <= 0:
                continue # Переходимо до наступного магазину, якщо потреба вже задоволена

            # Кількість, яку можна виділити поточному магазину:
            # це мінімум з поточного залишку на складі та залишкової потреби магазину
            allocatable_qty = min(current_remaining_stock, remaining_need)

            if allocatable_qty > 0: # Розподіляємо тільки якщо є що відвантажувати
                base_table.loc[shop_idx, 'order_stage_2'] += allocatable_qty
                current_remaining_stock -= allocatable_qty

    return base_table