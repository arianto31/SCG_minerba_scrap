"""Tab 'Minerba Website (ESDM)': lihat, filter per kolom, unduh, dan refresh data hasil scraping."""
import io
import logging
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

from core.filtering import filter_dataframe
from minerba_scraper import MinerbaScraper
from repositories.supabase_client import get_client
from ui import state
from ui.scrape_progress import ScrapeProgressView, show_summary
from ui.styles import pretty_minerba_config

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_GLOBAL_QUERY_KEY = "esdm_query"
_COLUMN_FILTER_PREFIX = "esdm_filter_"
_FILTERS_PER_ROW = 5


def render(df_minerba: pd.DataFrame) -> None:
    st.subheader("Database Perizinan Minerba (ESDM)")

    refresh_col, download_col = st.columns([1, 3])
    progress_slot = st.empty()   # kartu progres tampil di bawah tombol
    with refresh_col:
        refresh_clicked = st.button("🔄 Refresh Data ESDM")
    with download_col:
        if not df_minerba.empty:
            st.download_button(
                label="📥 Download Data ESDM (.xlsx)",
                data=_to_excel(df_minerba),
                file_name="database_esdm_terbaru.xlsx",
                mime=_MIME_XLSX,
            )

    if refresh_clicked:
        _refresh(progress_slot)  # selesai dengan st.rerun()
    else:
        _show_last_summary(progress_slot)

    if df_minerba.empty:
        st.warning("Data masih kosong. Silakan klik 'Refresh Data ESDM' untuk memulai scraping.")
        return

    query, column_queries = _render_filters(list(df_minerba.columns))
    shown = filter_dataframe(df_minerba, query, column_queries)
    active = sum(bool(v.strip()) for v in column_queries.values()) + bool(query.strip())
    st.caption(f"Menampilkan {len(shown):,} dari {len(df_minerba):,} baris" + (f" · {active} filter aktif" if active else ""))

    shown = shown.reset_index(drop=True)
    shown.index = shown.index + 1
    shown.index.name = "NO"
    st.dataframe(shown, width="stretch", height=560, column_config=pretty_minerba_config(shown))


# ------------------------------------------------------------------ filter per kolom
def _render_filters(columns: List[str]):
    """Kotak pencarian umum + satu kotak ketik per kolom. Huruf besar/kecil diabaikan."""
    with st.expander("🔎 Filter per kolom (ketik lalu tekan Enter)", expanded=True):
        query = st.text_input("Cari di semua kolom", key=_GLOBAL_QUERY_KEY, placeholder="Ketik kata kunci...")
        column_queries: Dict[str, str] = {}
        for start in range(0, len(columns), _FILTERS_PER_ROW):
            row = columns[start:start + _FILTERS_PER_ROW]
            for slot, name in zip(st.columns(_FILTERS_PER_ROW), row):
                column_queries[name] = slot.text_input(
                    name.replace("_", " ").title(), key=_COLUMN_FILTER_PREFIX + name, placeholder="ketik..."
                )
        st.button("Reset filter", on_click=_reset_filters, args=(columns,))
    return query, column_queries


def _reset_filters(columns: List[str]) -> None:
    """Callback tombol reset (berjalan sebelum rerun sehingga boleh mengubah state widget)."""
    st.session_state[_GLOBAL_QUERY_KEY] = ""
    for name in columns:
        st.session_state[_COLUMN_FILTER_PREFIX + name] = ""


# ------------------------------------------------------------------ refresh data
def _refresh(slot) -> None:
    view = ScrapeProgressView(slot)
    try:
        MinerbaScraper(supabase_client=get_client(), on_progress=view.update).run_pipeline()
    except Exception as exc:  # noqa: BLE001 - tampilkan pesan ramah, detail ada di log
        logging.exception("Scraping gagal")
        view.fail(str(exc))
        return

    st.cache_data.clear()
    st.session_state[state.KEY_SCRAPE_SUMMARY] = (view.last, datetime.now().strftime("%d/%m/%Y %H:%M"))
    st.rerun()


def _show_last_summary(slot) -> None:
    summary = st.session_state.get(state.KEY_SCRAPE_SUMMARY)
    if summary:
        progress, finished_at = summary
        show_summary(slot, progress, caption=f"diperbarui {finished_at}")


def _to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data ESDM")
    return buffer.getvalue()
