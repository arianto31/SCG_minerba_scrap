"""Utilitas teks, tanggal, dan angka (murni Python/pandas, tanpa Streamlit atau database)."""
import re
from datetime import date, datetime

import pandas as pd

LEGAL_ENTITY_TOKENS = {"pt", "cv", "ud", "tbk"}

# Nilai (huruf kecil) yang dianggap "kosong".
EMPTY_MARKERS = {"", "-", "nan", "none", "null", "nat"}

ID_MONTHS = {
    "januari": "january", "februari": "february", "maret": "march", "mei": "may",
    "juni": "june", "juli": "july", "agustus": "august", "oktober": "october",
    "desember": "december",
}


def is_blank(value) -> bool:
    """True untuk None/NaN, teks kosong, atau penanda kosong seperti '-'."""
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
    """Huruf kecil, hapus tanda baca & badan hukum (PT/CV/UD/TBK) agar perbandingan nama adil."""
    if name is None or (not isinstance(name, str) and pd.isna(name)):
        return ""
    text = re.sub(r"[^a-z0-9\s]", " ", str(name).lower())
    return " ".join(t for t in text.split() if t not in LEGAL_ENTITY_TOKENS)


def parse_date(value):
    """Baca tanggal dari berbagai format (ISO, dd/mm/yyyy, nama bulan Indonesia). Gagal -> NaT."""
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
    """Ubah tanggal ke 'YYYY-MM-DD'. Jika tidak terbaca, kembalikan teks aslinya."""
    parsed = parse_date(value)
    return parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else str(value).strip()


def to_int_str(value) -> str:
    """'5.116' -> '5', '5,6' -> '6'. Teks non-angka dikembalikan apa adanya."""
    try:
        return str(int(round(float(str(value).replace(",", ".")))))
    except (ValueError, TypeError):
        return value


def clean_key(value) -> str:
    """Bersihkan header: huruf kecil, buang isi kurung, buang semua selain huruf/angka."""
    text = re.sub(r"\(.*?\)", "", str(value).lower())
    return re.sub(r"[^a-z0-9]", "", text)
