from autoorder.connections import category
from api.helpers.category_column_maker import add_category_hierarchy
from autoorder.connections import product

def create_groups_list():
    try:
        categories = category()
    except Exception as e:
        print(f"Error initializing category: {e}")
        return None
    try:
        products = product(True)  # Включає товари зі статусом "Вивести" для побудови ієрархії
    except Exception as e:
        print(f"Error initializing product: {e}")
        return None
    
    try:
        hyterarchy = add_category_hierarchy(products, categories)
    except Exception as e:
        print(f"Error initializing add_category_hierarchy: {e}")
        return None
    return hyterarchy

