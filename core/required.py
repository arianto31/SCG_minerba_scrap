"""Fields every NEW vendor record must have (helps avoid duplicates and half-filled records)."""
from typing import List

import pandas as pd

from core.schema import APP_ONLY_COLS, AUTO_COLS, DB_COLS, DISPLAY_LABELS
from core.text_utils import is_blank, normalize_name

REQUIRED_NEW_COLS = ("iup_nama", "vendor", "nama_pic", "golongan")
REQUIRED_LABELS = {
    "iup_nama": "Holder Name",
    "vendor": "Vendor",
    "nama_pic": "PIC Name",
    "golongan": "Material Group",
}
MISSING_COLUMN = "missing"
# Columns a user types in (same rule as saving: rows without any of these are empty and never saved).
_MANUAL_COLS = [c for c in DB_COLS if c not in AUTO_COLS + APP_ONLY_COLS + ["remark"]]


def required_text() -> str:
    """'Holder Name, Vendor, PIC Name and Material Group' (for messages)."""
    labels = [REQUIRED_LABELS[c] for c in REQUIRED_NEW_COLS]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def missing_fields(values) -> List[str]:
    """Labels of the required fields that are empty in one row / dict."""
    return [REQUIRED_LABELS.get(c, DISPLAY_LABELS.get(c, c)) for c in REQUIRED_NEW_COLS if is_blank(values.get(c, ""))]


def _has_input(row) -> bool:
    return any(not is_blank(row.get(c, "")) for c in _MANUAL_COLS)


def incomplete_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows (with some input) missing a required field, plus a `missing` column listing what is missing."""
    labels, missing = [], []
    for label, row in df.iterrows():
        gaps = missing_fields(row)
        if gaps and _has_input(row):
            labels.append(label)
            missing.append(", ".join(gaps))
    out = df.loc[labels].copy()
    out[MISSING_COLUMN] = missing
    return out


def new_rows(edited: pd.DataFrame, saved: pd.DataFrame) -> pd.DataFrame:
    """
    Rows of the edited table that are new: their vendor + holder pair is not in the saved data
    (added rows, or rows whose vendor / holder was renamed). Rows only edited elsewhere are not new.
    """
    def keys(df):
        return [(normalize_name(v), normalize_name(h)) for v, h in zip(df["vendor"], df["iup_nama"])]

    existing = set(keys(saved))
    keep = [key not in existing for key in keys(edited)]
    return edited[keep]
