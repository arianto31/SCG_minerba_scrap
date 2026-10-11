"""Utilitas perbandingan DataFrame."""
import pandas as pd


def frames_equal(first: pd.DataFrame, second: pd.DataFrame) -> bool:
    """Bandingkan isi dua DataFrame sebagai teks (abaikan tipe data dan label indeks)."""
    return (
        first.reset_index(drop=True).astype(str)
        .equals(second.reset_index(drop=True).astype(str))
    )
