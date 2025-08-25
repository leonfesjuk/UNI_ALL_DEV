from dataclasses import dataclass
from datetime import date

from core.domain.value_objects import Money, ProductId, ShopId


@dataclass
class PromoScenario:
    shop_id: ShopId
    product_id: ProductId
    promo_type_id: int
    date_start: date
    date_end: date
    expected_price: Money


@dataclass
class ForecastResult:
    product_id: ProductId
    date: date
    sales_qty: float


@dataclass
class Comparison:
    product_id: ProductId
    with_promo: float
    without_promo: float
    uplift_qty: float
    cannibalized_products: list[str]
