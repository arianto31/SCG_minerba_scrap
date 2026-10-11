"""Akses data vendor di Supabase. Satu tabel vendor = satu nilai pada kolom `kategori`."""
from pathlib import Path
from typing import Dict, List

import pandas as pd

from core.schema import AUTO_COLS, DB_COLS, DEFAULT_TABLE, INT_COLS
from core.text_utils import to_int_str
from repositories.supabase_client import chunks, fetch_all, get_client

VENDOR_TABLE = "vendor_procurement"
REGISTRY_TABLE = "vendor_tables"
_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


# ------------------------------------------------------------------ skema & daftar tabel
def schema_ready() -> bool:
    """True jika kolom `kategori` sudah ada."""
    try:
        get_client().table(VENDOR_TABLE).select("kategori").limit(1).execute()
        return True
    except Exception:
        return False


def schema_migration_sql() -> str:
    return _SCHEMA_FILE.read_text(encoding="utf-8")


def list_table_names() -> List[str]:
    """Nama tabel vendor: dari daftar `vendor_tables` (jika ada) + nilai `kategori` yang dipakai."""
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
    """Catat nama tabel baru (opsional; gagal diabaikan karena tabel tetap muncul setelah berisi data)."""
    try:
        get_client().table(REGISTRY_TABLE).insert({"nama": name}).execute()
    except Exception:
        pass


# ------------------------------------------------------------------ baca / tulis vendor
def fetch_vendors(table: str) -> pd.DataFrame:
    """Data vendor satu tabel sebagai DataFrame teks (kolom = DB_COLS, indeks = NO)."""
    rows = fetch_all(VENDOR_TABLE, order_col="id", eq=("kategori", table))
    # dtype=object menjaga angka bulat tetap "5" (bukan "5.0") saat ada nilai NULL
    df = pd.DataFrame(rows, dtype=object) if rows else pd.DataFrame(columns=DB_COLS)
    for column in DB_COLS:
        if column not in df.columns:
            df[column] = ""
    df = df[DB_COLS].fillna("").astype(str)
    df.index = df.index + 1
    df.index.name = "NO"
    return df


def records_from_df(df: pd.DataFrame, table: str) -> List[Dict[str, object]]:
    """DataFrame -> daftar record Supabase. Sel kosong menjadi NULL; baris tanpa isian manual dilewati."""
    manual_cols = [c for c in DB_COLS if c not in AUTO_COLS + ["remark"]]
    records = []
    for _, row in df.iterrows():
        record = {}
        for column in DB_COLS:
            value = row.get(column, "")
            value = "" if pd.isna(value) else str(value).strip()
            if column in INT_COLS and value:
                value = to_int_str(value)  # kolom integer menolak desimal seperti "5.116"
            record[column] = value if value != "" else None  # kolom angka/tanggal menolak ""
        if any(record[c] for c in manual_cols):
            record["kategori"] = table
            records.append(record)
    return records


def save_records(records: List[dict], table: str, replace: bool) -> None:
    """
    Simpan record ke satu tabel vendor.
    replace=True: data lama dihapus SETELAH data baru berhasil dimasukkan (aman jika insert gagal).
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
