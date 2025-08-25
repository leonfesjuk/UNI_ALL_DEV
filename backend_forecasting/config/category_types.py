import pandas as pd


def build_category_mappings(categories_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """
    Build static mapping dicts for each hierarchy level from a flat
    category DataFrame (id, name, parent_id).

    Returns:
      {"group": {"Продовольчі товари": 1, ...},
       "subgroup": {...},
       "subsubgroup": {...},
       "subsubsubgroup": {...},
       "subsubsubgroups": {...}}
    """
    if categories_df.empty:
        return {}

    cat_dict = categories_df.set_index('id').to_dict('index')

    def _walk(cat_id):
        path = []
        cid = cat_id
        while cid is not None and cid in cat_dict:
            path.insert(0, cat_dict[cid]['name'])
            cid = cat_dict[cid].get('parent_id')
        return path

    level_names = ['group', 'subgroup', 'subsubgroup', 'subsubsubgroup', 'subsubsubgroups']
    all_level_values: dict[str, set[str]] = {lvl: set() for lvl in level_names}

    for cid in cat_dict:
        path = _walk(cid)
        for i, lvl in enumerate(level_names):
            if i < len(path):
                all_level_values[lvl].add(path[i])

    mappings: dict[str, dict[str, int]] = {}
    for lvl in level_names:
        sorted_vals = sorted(all_level_values[lvl])
        mappings[lvl] = {val: idx + 1 for idx, val in enumerate(sorted_vals)}

    return mappings


CATEGORY_GROUP: dict[str, int] = {}
CATEGORY_SUBGROUP: dict[str, int] = {}
CATEGORY_SUBSUBGROUP: dict[str, int] = {}
CATEGORY_SUBSUBSUBGROUP: dict[str, int] = {}
CATEGORY_SUBSUBSUBGROUPS: dict[str, int] = {}

HIERARCHY_LEVELS: list[tuple[str, dict[str, int]]] = [
    ('group', CATEGORY_GROUP),
    ('subgroup', CATEGORY_SUBGROUP),
    ('subsubgroup', CATEGORY_SUBSUBGROUP),
    ('subsubsubgroup', CATEGORY_SUBSUBSUBGROUP),
    ('subsubsubgroups', CATEGORY_SUBSUBSUBGROUPS),
]


LEVEL_NAMES: list[str] = ['subsubsubgroups', 'subsubsubgroup', 'subsubgroup', 'subgroup', 'group']

LEVEL_COLUMNS: list[str] = [f'{name}_id' for name in LEVEL_NAMES]


def ensure_mappings(categories_df: pd.DataFrame) -> None:
    mappings = build_category_mappings(categories_df)
    CATEGORY_GROUP.update(mappings.get('group', {}))
    CATEGORY_SUBGROUP.update(mappings.get('subgroup', {}))
    CATEGORY_SUBSUBGROUP.update(mappings.get('subsubgroup', {}))
    CATEGORY_SUBSUBSUBGROUP.update(mappings.get('subsubsubgroup', {}))
    CATEGORY_SUBSUBSUBGROUPS.update(mappings.get('subsubsubgroups', {}))


import json as _json

_CATEGORY_MAP: dict[str, dict[str, int]] | None = None

def load_category_map(path: str = "data/demo/category_map.json") -> dict[str, dict[str, int]]:
    global _CATEGORY_MAP
    if _CATEGORY_MAP is None:
        try:
            with open(path) as f:
                _CATEGORY_MAP = _json.load(f)
        except Exception:
            _CATEGORY_MAP = {}
    return _CATEGORY_MAP

def resolve_category_id(category_id: str) -> tuple[int, int]:
    m = load_category_map()
    entry = m.get(category_id)
    if entry is None:
        raise ValueError(f"Unknown category_id: {category_id}")
    return int(entry["level"]), int(entry["level_id"])
