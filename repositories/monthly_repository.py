"""Monthly price per MT and density per (IUP holder, vendor), stored in the `vendor_monthly` table."""
from datetime import datetime, timezone
from typing import Dict, List

from repositories.supabase_client import chunks, fetch_all, get_client

MONTHLY_TABLE = "vendor_monthly"
_CONFLICT = "kategori,holder_key,vendor_key,year,month"

MIGRATION_SQL = """-- Monthly price per MT and density for each IUP holder + vendor. Safe to run again.
CREATE TABLE IF NOT EXISTS vendor_monthly (
  id           bigserial PRIMARY KEY,
  kategori     text    NOT NULL,
  holder_key   text    NOT NULL,
  vendor_key   text    NOT NULL,
  holder       text,
  vendor       text,
  year         integer NOT NULL,
  month        integer NOT NULL CHECK (month BETWEEN 1 AND 12),
  price_per_mt numeric,
  density      numeric,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (kategori, holder_key, vendor_key, year, month)
);
ALTER TABLE vendor_monthly DISABLE ROW LEVEL SECURITY;"""


def table_ready() -> bool:
    try:
        get_client().table(MONTHLY_TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def fetch(table: str) -> List[Dict]:
    """Every monthly record of one vendor list."""
    return fetch_all(MONTHLY_TABLE, order_col="id", eq=("kategori", table))


def upsert(records: List[Dict], table: str) -> None:
    """Insert or update records (one per holder + vendor + month). Only the fields present are changed."""
    if not records:
        return
    stamp = datetime.now(timezone.utc).isoformat()
    payload = [{**record, "kategori": table, "updated_at": stamp} for record in records]
    for part in chunks(payload, 500):
        get_client().table(MONTHLY_TABLE).upsert(list(part), on_conflict=_CONFLICT).execute()
