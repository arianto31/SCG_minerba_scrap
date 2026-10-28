"""Turn extraction results into vendor column values (and merge them into existing rows)."""
from typing import Dict, Mapping

import pandas as pd

from core.schema import DATE_COLS, DB_COLS, INT_COLS
from core.text_utils import is_blank, to_int_str, to_iso_date

from .models import FILLABLE_COLUMNS, ExtractedDocument


def normalize_values(raw: Mapping[str, object]) -> Dict[str, str]:
    """Clean raw values (from the AI or user corrections): filled columns only, ISO dates, whole numbers."""
    values: Dict[str, str] = {}
    for column in FILLABLE_COLUMNS:
        value = raw.get(column)
        if is_blank(value):
            continue
        text = str(value).strip()
        if column in DATE_COLS:
            text = to_iso_date(text)
        elif column in INT_COLS:
            text = to_int_str(text)
        if text:
            values[column] = text
    return values


def to_vendor_values(document: ExtractedDocument) -> Dict[str, str]:
    return normalize_values(document.model_dump())


def new_vendor_row(values: Mapping[str, str]) -> Dict[str, str]:
    """A new vendor row: every column empty except those filled from the document."""
    row = {column: "" for column in DB_COLS}
    row.update(values)
    return row


def merge_values(existing: Mapping[str, object], values: Mapping[str, str], overwrite: bool) -> Dict[str, str]:
    """
    Merge document values into an existing row.
    overwrite=False: only fill empty columns; True: also replace columns that already have a value.
    """
    merged = {
        column: "" if pd.isna(existing.get(column, "")) else str(existing.get(column, ""))
        for column in DB_COLS
    }
    for column, value in values.items():
        if overwrite or is_blank(merged[column]):
            merged[column] = value
    return merged
