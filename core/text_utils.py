"""Text, date and number helpers (pure Python/pandas, no Streamlit or database)."""
import re
from datetime import date, datetime

import pandas as pd

LEGAL_ENTITY_TOKENS = {"pt", "cv", "ud", "tbk"}

# Values (lower-case) treated as "empty".
EMPTY_MARKERS = {"", "-", "nan", "none", "null", "nat"}

# Indonesian month names -> English, so dates written in Indonesian documents can be parsed.
ID_MONTHS = {
    "januari": "january", "februari": "february", "maret": "march", "mei": "may",
    "juni": "june", "juli": "july", "agustus": "august", "oktober": "october",
    "desember": "december",
}


def is_blank(value) -> bool:
    """True for None/NaN, empty text, or empty markers such as '-'."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in EMPTY_MARKERS
    if isinstance(value, (datetime, date)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_name(name) -> str:
    """Lower-case and strip punctuation & legal entity tokens (PT/CV/UD/TBK) so names compare fairly."""
    if name is None or (not isinstance(name, str) and pd.isna(name)):
        return ""
    text = re.sub(r"[^a-z0-9\s]", " ", str(name).lower())
    return " ".join(t for t in text.split() if t not in LEGAL_ENTITY_TOKENS)


def parse_date(value):
    """Parse a date from many formats (ISO, dd/mm/yyyy, Indonesian month names). Failure -> NaT."""
    if is_blank(value):
        return pd.NaT
    if isinstance(value, (datetime, date)):
        return pd.Timestamp(value)
    text = str(value).strip().lower()
    for indonesian, english in ID_MONTHS.items():
        text = text.replace(indonesian, english)
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return pd.to_datetime(text[:10], format="%Y-%m-%d", errors="coerce")
    return pd.to_datetime(text, dayfirst=True, errors="coerce")


def to_iso_date(value) -> str:
    """Convert a date to 'YYYY-MM-DD'. If it cannot be parsed, return the original text."""
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else str(value).strip()


def to_int_str(value) -> str:
    """'5.116' -> '5', '5,6' -> '6'. Non-numeric text is returned unchanged."""
    try:
        return str(int(round(float(str(value).replace(",", ".")))))
    except (ValueError, TypeError):
        return value


def clean_key(value) -> str:
    """Clean a header: lower-case, drop text in brackets, keep only letters/digits."""
    text = re.sub(r"\(.*?\)", "", str(value).lower())
    return re.sub(r"[^a-z0-9]", "", text)
