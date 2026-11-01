"""Vendor data access in Supabase. One vendor list = one value of the `kategori` column."""
from pathlib import Path
from typing import Dict, List

import pandas as pd

from core.schema import APP_ONLY_COLS, AUTO_COLS, DB_COLS, DEFAULT_TABLE, INT_COLS
from core.text_utils import to_int_str
from repositories.supabase_client import chunks, fetch_all, get_client

VENDOR_TABLE = "vendor_procurement"
REGISTRY_TABLE = "vendor_tables"
_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


# ------------------------------------------------------------------ schema & list names
def schema_ready() -> bool:
    """True when every column the app needs exists (`kategori`, `golongan`, `lokasi_maps`, `iup_renewal`)."""
    try:
        get_client().table(VENDOR_TABLE).select("kategori,golongan,lokasi_maps,iup_renewal").limit(1).execute()
        return True
    except Exception:
        return False


def schema_migration_sql() -> str:
    return _SCHEMA_FILE.read_text(encoding="utf-8")


def list_table_names() -> List[str]:
    """Vendor list names: from the `vendor_tables` registry (if any) + `kategori` values in use."""
    names: List[str] = []
    try:
        names += [r["nama"] for r in fetch_all(REGISTRY_TABLE, order_col="nama")]
    except Exception:
        pass
    try:
        names += [r["kategori"] for r in fetch_all(VENDOR_TABLE, columns="kategori", order_col="id")
                  if r.get("kategori")]
    except Exception:
        pass

    seen, unique = set(), []
    for name in (str(n).strip() for n in names):
        if name and name.lower() not in seen:
            seen.add(name.lower())
            unique.append(name)
    return unique or [DEFAULT_TABLE]


def register_table(name: str) -> None:
    """Register a new list name (optional; failures are ignored because a list appears once it has data)."""
    try:
        get_client().table(REGISTRY_TABLE).insert({"nama": name}).execute()
    except Exception:
        pass


def fetch_material_groups() -> List[str]:
    """Every material group (golongan) used in any vendor list."""
    rows = fetch_all(VENDOR_TABLE, columns="golongan", order_col="id")
    return [str(r["golongan"]) for r in rows if r.get("golongan")]


# ------------------------------------------------------------------ read / write vendors
def fetch_vendors(table: str) -> pd.DataFrame:
    """One vendor list as a text DataFrame (columns = DB_COLS, index = NO)."""
    rows = fetch_all(VENDOR_TABLE, order_col="id", eq=("kategori", table))
    # dtype=object keeps whole numbers as "5" (not "5.0") when there are NULL values
    df = pd.DataFrame(rows, dtype=object) if rows else pd.DataFrame(columns=DB_COLS)
    for column in DB_COLS:
        if column not in df.columns:
            df[column] = ""
    df = df[DB_COLS].fillna("").astype(str)
    df.index = df.index + 1
    df.index.name = "NO"
    return df


def records_from_df(df: pd.DataFrame, table: str) -> List[Dict[str, object]]:
    """DataFrame -> Supabase records. Empty cells become NULL; rows without any manual input are skipped."""
    manual_cols = [c for c in DB_COLS if c not in AUTO_COLS + APP_ONLY_COLS + ["remark"]]
    records = []
    for _, row in df.iterrows():
        record = {}
        for column in DB_COLS:
            value = row.get(column, "")
            value = "" if pd.isna(value) else str(value).strip()
            if column in INT_COLS and value:
                value = to_int_str(value)  # integer columns reject decimals such as "5.116"
            record[column] = value if value != "" else None  # number/date columns reject ""
        if any(record[c] for c in manual_cols):
            record["kategori"] = table
            records.append(record)
    return records


def save_records(records: List[dict], table: str, replace: bool) -> None:
    """
    Save records into one vendor list.
    replace=True: old rows are deleted AFTER the new rows were inserted (safe if the insert fails).
    """
    client = get_client()
    old_ids = []
    if replace:
        old_ids = [r["id"] for r in fetch_all(VENDOR_TABLE, columns="id", order_col="id",
                                              eq=("kategori", table))]
    for part in chunks(records, 500):
        client.table(VENDOR_TABLE).insert(list(part)).execute()
    for part in chunks(old_ids, 100):
        client.table(VENDOR_TABLE).delete().in_("id", list(part)).execute()
