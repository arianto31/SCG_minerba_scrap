"""Access to the scraped Minerba (ESDM) data."""
import pandas as pd

from repositories.supabase_client import fetch_all

TABLE = "data_tambang"


def fetch_minerba_data() -> pd.DataFrame:
    """All ESDM data as text. The `id` column (if any) is dropped."""
    try:
        rows = fetch_all(TABLE, order_col="id")
    except Exception:  # the ESDM table may not have an id column
        rows = fetch_all(TABLE)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    return df.fillna("-").astype(str)
