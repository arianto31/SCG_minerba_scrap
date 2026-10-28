"""'MinerbaOne database' page: browse, search, filter per column, download, and refresh the scraped ESDM data."""
import io
import logging
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

from core.filtering import filter_dataframe
from minerba_scraper import MinerbaScraper
from repositories.supabase_client import get_client
from ui import state, theme
from ui.scrape_progress import ScrapeProgressView, show_summary
from ui.styles import minerba_label, pretty_minerba_config

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_GLOBAL_QUERY_KEY = "esdm_query"
_COLUMN_FILTER_PREFIX = "esdm_filter_"
_FILTERS_PER_ROW = 4


def render(df_minerba: pd.DataFrame) -> None:
    theme.page_header(
        "Reference data",
        "MinerbaOne database",
        "Official mining permits published by the Ministry of Energy and Mineral Resources (ESDM). "
        "Every vendor IUP is verified against this list.",
    )

    _render_stats(df_minerba)
    refresh_clicked = _render_actions(df_minerba)
    progress_slot = st.empty()   # the progress card appears under the buttons

    if refresh_clicked:
        _refresh(progress_slot)  # ends with st.rerun()
    else:
        _show_last_summary(progress_slot)

    if df_minerba.empty:
        theme.empty_state(
            "🛰️", "No permit data yet",
            "Click “Refresh data” above to download the latest permits from MinerbaOne. "
            "It takes a few minutes; afterwards vendors can be verified automatically.",
        )
        return

    theme.section("Browse permits", "Type to search every column, or narrow down per column.")
    query, column_queries = _render_filters(list(df_minerba.columns))
    shown = filter_dataframe(df_minerba, query, column_queries)
    active = sum(bool(v.strip()) for v in column_queries.values()) + bool(query.strip())
    st.caption(f"Showing **{len(shown):,}** of {len(df_minerba):,} permits"
               + (f" · {active} filter{'s' if active != 1 else ''} active" if active else ""))

    if shown.empty:
        st.info("No permits match your search. Try fewer words or clear the filters.", icon=":material/search_off:")
        return
    shown = shown.reset_index(drop=True)
    shown.index = shown.index + 1
    shown.index.name = "NO"
    st.dataframe(shown, width="stretch", height=560, column_config=pretty_minerba_config(shown))


# ------------------------------------------------------------------ header area
def _render_stats(df: pd.DataFrame) -> None:
    summary = st.session_state.get(state.KEY_SCRAPE_SUMMARY)
    refreshed, refreshed_note = (summary[1], "source: minerbaone.esdm.go.id") if summary else (
        "—", "not refreshed in this session")
    companies = df["nama_badan_usaha"].nunique() if "nama_badan_usaha" in df.columns else 0
    commodities = df["komoditas"].replace("-", pd.NA).nunique() if "komoditas" in df.columns else 0
    theme.kpi_cards([
        theme.Kpi("Permits", theme.fmt_int(len(df)), "rows in the database", theme.INDIGO),
        theme.Kpi("Companies", theme.fmt_int(companies), "unique permit holders", theme.CYAN),
        theme.Kpi("Commodities", theme.fmt_int(commodities), "different materials", theme.GREEN),
        theme.Kpi("Last refresh", refreshed, refreshed_note, theme.SLATE),
    ])


def _render_actions(df: pd.DataFrame) -> bool:
    """Refresh (with a short confirmation) and download buttons. Returns True when a refresh was started."""
    refresh_col, download_col, _ = st.columns([1.3, 1.6, 4], vertical_alignment="center")
    with refresh_col:
        with st.popover("Refresh data", icon=":material/sync:", width="stretch"):
            st.markdown("**Download the latest data from MinerbaOne?**")
            st.caption(
                "This usually takes a few minutes. Keep this page open until it finishes. "
                "Your current data stays in place if anything goes wrong."
            )
            clicked = st.button("Start refresh", type="primary", icon=":material/play_arrow:", width="stretch")
    with download_col:
        st.download_button(
            label="Download Excel",
            icon=":material/download:",
            data=_to_excel(df) if not df.empty else b"",
            file_name="minerbaone_esdm_database.xlsx",
            mime=_MIME_XLSX,
            disabled=df.empty,
            width="stretch",
        )
    return clicked


# ------------------------------------------------------------------ per-column filters
def _render_filters(columns: List[str]):
    """One global search box + a collapsible grid with one text box per column. Case is ignored."""
    query = st.text_input(
        "Search", key=_GLOBAL_QUERY_KEY, placeholder="Search company, permit number, commodity, location…",
        icon=":material/search:", label_visibility="collapsed",
    )
    column_queries: Dict[str, str] = {}
    with st.expander("Filter by column", icon=":material/filter_list:"):
        st.caption("Each box keeps only rows containing that text. Press Enter to apply.")
        for start in range(0, len(columns), _FILTERS_PER_ROW):
            row = columns[start:start + _FILTERS_PER_ROW]
            for slot, name in zip(st.columns(_FILTERS_PER_ROW), row):
                column_queries[name] = slot.text_input(
                    minerba_label(name), key=_COLUMN_FILTER_PREFIX + name, placeholder="Type to filter…"
                )
        st.button("Clear all filters", on_click=_reset_filters, args=(columns,), icon=":material/filter_alt_off:")
    return query, column_queries


def _reset_filters(columns: List[str]) -> None:
    """Reset button callback (runs before the rerun, so it may change widget state)."""
    st.session_state[_GLOBAL_QUERY_KEY] = ""
    for name in columns:
        st.session_state[_COLUMN_FILTER_PREFIX + name] = ""


# ------------------------------------------------------------------ refresh
def _refresh(slot) -> None:
    view = ScrapeProgressView(slot)
    try:
        MinerbaScraper(supabase_client=get_client(), on_progress=view.update).run_pipeline()
    except Exception as exc:  # noqa: BLE001 - show a friendly message; details are in the log
        logging.exception("Scraping failed")
        view.fail(str(exc))
        return

    st.cache_data.clear()
    st.session_state[state.KEY_SCRAPE_SUMMARY] = (view.last, datetime.now().strftime("%d/%m/%Y %H:%M"))
    st.rerun()


def _show_last_summary(slot) -> None:
    summary = st.session_state.get(state.KEY_SCRAPE_SUMMARY)
    if summary:
        progress, finished_at = summary
        show_summary(slot, progress, caption=f"updated {finished_at}")


def _to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.rename(columns=minerba_label).to_excel(writer, index=False, sheet_name="ESDM Data")
    return buffer.getvalue()
