PROMO_TYPES: dict[str, int] = {
    "Знижкова": 1,
    "ОдинОдинТри": 2,
    "Подарункова": 3,
}

PROMO_TYPE_NAMES: dict[int, str] = {v: k for k, v in PROMO_TYPES.items()}
