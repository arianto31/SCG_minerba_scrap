"""Filter DataFrame: pencarian umum + filter per kolom (tidak peka huruf besar/kecil)."""
from typing import Mapping, Optional

import pandas as pd


def _contains(series: pd.Series, text: str) -> pd.Series:
    # regex=False: tanda seperti ( . + diperlakukan sebagai teks biasa; case=False: abaikan kapital
    return series.astype(str).str.contains(text, case=False, regex=False, na=False)


def filter_dataframe(
    df: pd.DataFrame,
    query: str = "",
    column_queries: Optional[Mapping[str, str]] = None,
) -> pd.DataFrame:
    """
    Baris lolos jika memenuhi SEMUA kondisi: setiap kolom berisi teks filternya, dan (jika ada)
    salah satu kolom berisi kata kunci pencarian umum.
    """
    mask = pd.Series(True, index=df.index)
    for column, text in (column_queries or {}).items():
        text = (text or "").strip()
        if text and column in df.columns:
            mask &= _contains(df[column], text)

    query = (query or "").strip()
    if query and not df.empty:
        mask &= df.apply(lambda column: _contains(column, query)).any(axis=1)
    return df[mask]
