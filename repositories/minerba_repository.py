"""Akses data hasil scraping Minerba (ESDM)."""
import pandas as pd

from repositories.supabase_client import fetch_all

TABLE = "data_tambang"


def fetch_minerba_data() -> pd.DataFrame:
    """Seluruh data ESDM sebagai teks. Kolom `id` (jika ada) dibuang."""
    try:
        rows = fetch_all(TABLE, order_col="id")
    except Exception:  # tabel ESDM mungkin tidak punya kolom id
        rows = fetch_all(TABLE)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    return df.fillna("-").astype(str)
