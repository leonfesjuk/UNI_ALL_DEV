from dataclasses import dataclass


@dataclass(frozen=True)
class ShopId:
    value: int


@dataclass(frozen=True)
class ProductId:
    value: int


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "UAH"
