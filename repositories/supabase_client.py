"""Koneksi Supabase (singleton) dan helper query umum."""
from typing import Iterator, List, Optional, Sequence, Tuple

from supabase import Client, create_client

import config

_client: Optional[Client] = None


def get_client() -> Client:
    """Klien Supabase tunggal (dibuat saat pertama dipakai)."""
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL dan SUPABASE_KEY belum diatur di file .env")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def fetch_all(
    table: str,
    columns: str = "*",
    order_col: Optional[str] = None,
    eq: Optional[Tuple[str, str]] = None,
    page_size: int = 1000,
) -> List[dict]:
    """Ambil seluruh baris. Supabase membatasi 1000 baris per permintaan, jadi diambil per halaman."""
    rows: List[dict] = []
    start = 0
    while True:
        query = get_client().table(table).select(columns)
        if eq:
            query = query.eq(eq[0], eq[1])
        if order_col:
            query = query.order(order_col)
        page = query.range(start, start + page_size - 1).execute().data or []
        rows.extend(page)
        if len(page) < page_size:
            return rows
        start += page_size


def chunks(items: Sequence, size: int) -> Iterator[Sequence]:
    for i in range(0, len(items), size):
        yield items[i:i + size]
