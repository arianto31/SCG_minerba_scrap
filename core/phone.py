"""Nomor kontak -> link WhatsApp (wa.me)."""
import re
from typing import Optional

import pandas as pd

from core.text_utils import is_blank

_MIN_DIGITS, _MAX_DIGITS = 9, 15


def to_whatsapp_url(value) -> Optional[str]:
    """
    '0812-3456-7890' / '+62 812 3456 7890' / '812...' -> 'https://wa.me/6281234567890'.
    Jika ada beberapa nomor dalam satu sel (dipisah koma, titik koma, garis miring, 'dan'), dipakai yang pertama.
    Mengembalikan None jika bukan nomor telepon yang valid.
    """
    if is_blank(value):
        return None
    first = re.split(r"[;,/\n]|\bdan\b", str(value), maxsplit=1)[0]
    digits = re.sub(r"\D", "", first)

    if digits.startswith("00"):          # 0062...
        digits = digits[2:]
    if digits.startswith("620"):         # 62 0812... (nol berlebih)
        digits = "62" + digits[3:]
    elif digits.startswith("0"):         # 0812... -> 62812...
        digits = "62" + digits[1:]
    elif digits.startswith("8"):         # 812... -> 62812...
        digits = "62" + digits

    if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
        return None
    return f"https://wa.me/{digits}"


def with_whatsapp_links(df: pd.DataFrame, column: str = "no_kontak") -> pd.DataFrame:
    """Salinan DataFrame (khusus tampilan) dengan kolom kontak diganti link WhatsApp; tidak valid -> kosong."""
    out = df.copy()
    out[column] = pd.Series([to_whatsapp_url(v) for v in out[column]], index=out.index, dtype=object)
    return out
