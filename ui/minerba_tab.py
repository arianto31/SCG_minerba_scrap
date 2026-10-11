"""Tab 'Minerba Website (ESDM)': lihat, cari, unduh, dan refresh data hasil scraping."""
import io
import time

import pandas as pd
import streamlit as st

from minerba_scraper import MinerbaScraper
from repositories.supabase_client import get_client
from ui.styles import pretty_minerba_config

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render(df_minerba: pd.DataFrame) -> None:
    st.subheader("Database Perizinan Minerba (ESDM)")

    refresh_col, download_col = st.columns([1, 3])
    with refresh_col:
        if st.button("🔄 Refresh Data ESDM"):
            _refresh()
    with download_col:
        if not df_minerba.empty:
            st.download_button(
                label="📥 Download Data ESDM (.xlsx)",
                data=_to_excel(df_minerba),
                file_name="database_esdm_terbaru.xlsx",
                mime=_MIME_XLSX,
            )

    if df_minerba.empty:
        st.warning("Data masih kosong. Silakan klik 'Refresh Data ESDM' untuk memulai scraping.")
        return

    query = st.text_input("🔎 Cari data (nama badan usaha, lokasi, dll.)", placeholder="Ketik kata kunci...")
    shown = _filter(df_minerba, query)
    st.caption(f"Menampilkan {len(shown):,} dari {len(df_minerba):,} baris")

    shown = shown.reset_index(drop=True)
    shown.index = shown.index + 1
    shown.index.name = "NO"
    st.dataframe(shown, use_container_width=True, height=560, column_config=pretty_minerba_config(shown))


def _refresh() -> None:
    with st.spinner("Update Data... Please wait..."):
        MinerbaScraper(supabase_client=get_client()).run_pipeline()
        st.cache_data.clear()
    st.success("Update Done!!")
    time.sleep(2)
    st.rerun()


def _to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data ESDM")
    return buffer.getvalue()


def _filter(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return df
    mask = df.apply(lambda column: column.str.contains(query, case=False, na=False)).any(axis=1)
    return df[mask]
