"""Monthly price per MT and material density for each (IUP holder, vendor) pair.

One stored record = one holder + one vendor + one month, with `price_per_mt` and/or `density`.
The popups show the data as a grid: one row per month, one column per vendor (holder view) or per
holder (vendor view).
"""
import math
from datetime import date
from typing import Dict, Iterable, List, Mapping, Optional

import pandas as pd

FIELD_PRICE = "price_per_mt"
FIELD_DENSITY = "density"
FIELDS = (FIELD_PRICE, FIELD_DENSITY)

HOLDER_KEY = "holder_key"
VENDOR_KEY = "vendor_key"

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTH_INDEX_NAME = "Month"


# ------------------------------------------------------------------ which months / years to show
def visible_months(year: int, today: Optional[date] = None) -> List[int]:
    """Past year -> all 12 months. Current year -> January up to last month. Future year -> none."""
    today = today or date.today()
    if year < today.year:
        return list(range(1, 13))
    if year == today.year:
        return list(range(1, today.month))
    return []


def year_options(years_with_data: Iterable, today: Optional[date] = None) -> List[int]:
    """Years to offer, newest first: every year that has data, plus this year and last year."""
    today = today or date.today()
    years = {today.year, today.year - 1}
    for year in years_with_data:
        try:
            year = int(year)
        except (TypeError, ValueError):
            continue
        if 1990 <= year <= today.year:
            years.add(year)
    return sorted(years, reverse=True)


# ------------------------------------------------------------------ records <-> grid
def to_number(value) -> float:
    """Database / editor value -> float (NaN when empty or not a number)."""
    if value is None:
        return math.nan
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def build_grid(records: Iterable[Mapping], field: str, axis_key: str, columns: Mapping[str, str],
               fixed: Mapping[str, str], year: int, months: List[int]) -> pd.DataFrame:
    """
    Grid of one field (price or density): index = month names, one column per entry of `columns`.
    columns: {normalized key on `axis_key`: column label}. fixed: the other key, e.g. {HOLDER_KEY: "abc"}.
    """
    grid = pd.DataFrame(math.nan, index=[MONTH_NAMES[m - 1] for m in months],
                        columns=list(columns.values()), dtype=float)
    grid.index.name = MONTH_INDEX_NAME
    for record in records:
        if _int(record.get("year")) != year or _int(record.get("month")) not in months:
            continue
        if any(record.get(k) != v for k, v in fixed.items()):
            continue
        label = columns.get(record.get(axis_key))
        if label is not None:
            grid.at[MONTH_NAMES[_int(record["month"]) - 1], label] = to_number(record.get(field))
    return grid


def grid_changes(before: pd.DataFrame, after: pd.DataFrame, field: str, axis_key: str,
                 columns: Mapping[str, str], fixed: Mapping[str, str], names: Mapping[str, str],
                 year: int) -> List[Dict[str, object]]:
    """
    Cells that changed between the stored grid and the edited grid -> records to upsert.
    names: {HOLDER_KEY / VENDOR_KEY value: display text} for every key involved (stored for readability).
    A cleared cell gives a record with the field set to None.
    """
    month_numbers = {name: i + 1 for i, name in enumerate(MONTH_NAMES)}
    records = []
    for key, label in columns.items():
        if label not in after.columns:
            continue
        for month_name in after.index:
            old = to_number(before.at[month_name, label]) if month_name in before.index else math.nan
            new = to_number(after.at[month_name, label])
            if _same(old, new):
                continue
            keys = {**fixed, axis_key: key}
            records.append({
                **keys,
                "holder": names.get(keys[HOLDER_KEY], ""),
                "vendor": names.get(keys[VENDOR_KEY], ""),
                "year": year,
                "month": month_numbers[month_name],
                field: None if math.isnan(new) else new,
            })
    return records


def column_averages(grid: pd.DataFrame) -> Dict[str, float]:
    """Average of the filled months per column (columns without any value are left out)."""
    means = grid.apply(pd.to_numeric, errors="coerce").mean(skipna=True)
    return {column: float(value) for column, value in means.items() if pd.notna(value)}


def _same(old: float, new: float) -> bool:
    if math.isnan(old) and math.isnan(new):
        return True
    return not math.isnan(old) and not math.isnan(new) and abs(old - new) < 1e-9


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
