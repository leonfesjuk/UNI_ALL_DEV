from api.helpers.loger import my_logger
from autoorder.analysis import abc_analysis_all
from autoorder_m.healpers.base_table import base_table_creation


def auto_order_markets_start(date_start = None, date_finish = None, days_of_order = None, groups = None, markets = None, today_stocs_mode = False):
    """
    Функція для автоматичного замовлення товарів на ринку.
    
    :param date_start: Дата початку замовлення (формат: YYYY-MM-DD).
    :param date_finish: Дата закінчення замовлення (формат: YYYY-MM-DD).
    :param days_of_order: Кількість днів для замовлення.
    :param groups: Список груп товарів для замовлення.
    :return: JSONResponse з результатами замовлення.
    """

    
    clumns_for_managers, final_table_stage_2, db_status = base_table_creation(
        date_start=date_start,
        date_finish=date_finish,
        days_of_order=days_of_order,
        groups=groups,
        markets = markets,
        today_stocs_mode = today_stocs_mode
    )

    

    return clumns_for_managers, final_table_stage_2, db_status