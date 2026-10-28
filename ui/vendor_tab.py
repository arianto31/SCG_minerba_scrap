"""'Vendors' page: puts all vendor UI sections together."""
import re

import pandas as pd
import streamlit as st

from core.filtering import filter_dataframe
from core.phone import with_whatsapp_links
from core.validation import ValidationSettings, validate_vendors
from core.vendor_status import (
    STATUS_ATTENTION, STATUS_NOT_FOUND, STATUS_VERIFIED, is_not_found, is_valid, needs_attention, summarize,
)
from repositories import vendor_repository
from services.excel_export import build_excel
from ui import state, theme
from ui.sections import document_upload, editor, excel_upload, settings_panel, table_selector
from ui.styles import build_vendor_column_config, style_rows, table_height, with_status_column

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FILTER_ALL = "all"
_FILTER_OPTIONS = {
    _FILTER_ALL: "All",
    STATUS_VERIFIED: "Verified",
    STATUS_NOT_FOUND: "Not found",
    STATUS_ATTENTION: "Expiring",
}


def render(df_minerba: pd.DataFrame) -> None:
    theme.page_header(
        "Procurement",
        "Vendors",
        "Keep every vendor's permits in one place and check each IUP against the official MinerbaOne database.",
    )
    if not _schema_ready():
        return
    flash = state.pop_flash()
    if flash:
        st.success(flash, icon=":material/check_circle:")
    if df_minerba.empty:
        st.info(
            "The MinerbaOne database is empty, so vendors can't be verified yet. "
            "Open **MinerbaOne database** in the menu and click **Refresh data**.",
            icon=":material/info:",
        )

    list_col, new_col, rules_col, _ = st.columns([2.6, 1, 1.2, 2.4], vertical_alignment="bottom")
    table = table_selector.render(list_col, new_col)
    _reset_when_table_changes(table)
    with rules_col:
        cfg = settings_panel.render(df_minerba)
    _load_data_once(table, df_minerba, cfg)

    ctx = state.VendorContext(
        table=table,
        df_minerba=df_minerba,
        cfg=cfg,
        saved_df=validate_vendors(st.session_state[state.KEY_SAVED_DF], df_minerba, cfg),
        working_df=st.session_state[state.KEY_WORKING_DF],
    )

    _render_summary(ctx.saved_df)
    _render_vendor_table(ctx)

    theme.section("Add or update vendors", "Choose the method that suits you. Each one checks MinerbaOne for you.")
    edit_tab, excel_tab, scan_tab = st.tabs([
        ":material/edit_note: Type or edit",
        ":material/upload_file: Import from Excel",
        ":material/document_scanner: Scan a document (AI)",
    ])
    with edit_tab:
        editor.render(ctx)
    with excel_tab:
        excel_upload.render(ctx)
    with scan_tab:
        document_upload.render(ctx)


# ------------------------------------------------------------------ setup
def _schema_ready() -> bool:
    """Make sure the `kategori` and `golongan` columns exist; if not, show the SQL to run."""
    if state.KEY_SCHEMA_OK not in st.session_state:
        st.session_state[state.KEY_SCHEMA_OK] = vendor_repository.schema_ready()
    if st.session_state[state.KEY_SCHEMA_OK]:
        return True

    st.error(
        "The `vendor_procurement` table is missing new columns (`kategori` for multiple lists, `golongan`). "
        "Run the SQL below in Supabase (SQL Editor; safe to run again), then click the button.",
        icon=":material/database:",
    )
    st.code(vendor_repository.schema_migration_sql(), language="sql")
    if st.button("I ran it, check again", icon=":material/refresh:", type="primary"):
        st.session_state.pop(state.KEY_SCHEMA_OK, None)
        st.rerun()
    return False


def _reset_when_table_changes(table: str) -> None:
    if st.session_state.get(state.KEY_LOADED_TABLE) != table:
        state.invalidate_vendor_data()
        st.session_state[state.KEY_LOADED_TABLE] = table


def _load_data_once(table: str, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> None:
    """Load the vendor data from the database into session_state (working copy + saved copy)."""
    if state.KEY_WORKING_DF in st.session_state:
        return
    with st.spinner("Loading vendors…"):
        base = validate_vendors(vendor_repository.fetch_vendors(table), df_minerba, cfg)
    st.session_state[state.KEY_WORKING_DF] = base
    st.session_state[state.KEY_SAVED_DF] = base
    st.session_state[state.KEY_EDITOR_VER] = 0


# ------------------------------------------------------------------ display
def _render_summary(saved_df: pd.DataFrame) -> None:
    s = summarize(saved_df)

    def share(part: int) -> str:
        return f"{part / s.total:.0%} found in MinerbaOne" if s.total else "no vendors yet"

    theme.kpi_cards([
        theme.Kpi("Total vendors", theme.fmt_int(s.total), "with an IUP holder name", theme.INDIGO),
        theme.Kpi("Verified", theme.fmt_int(s.verified), share(s.verified), theme.GREEN),
        theme.Kpi("Not found", theme.fmt_int(s.not_found), "IUP holder missing in MinerbaOne", theme.RED),
        theme.Kpi("Needs attention", theme.fmt_int(s.attention), "IUP expiring soon or expired", theme.AMBER),
    ])


def _render_vendor_table(ctx: state.VendorContext) -> None:
    theme.section("Vendor table", "Saved vendors in this list. Colors update after you save changes.")
    saved = ctx.saved_df
    if saved.empty:
        theme.empty_state(
            "📋", "This list has no vendors yet",
            "Add your first vendor below: type it in, import an Excel file, or scan a permit document with AI.",
        )
        return

    search_col, filter_col, download_col = st.columns([3, 2.4, 1.3], vertical_alignment="bottom")
    query = search_col.text_input(
        "Search vendors", key=state.KEY_VENDOR_SEARCH, icon=":material/search:",
        placeholder="Search by vendor, PIC, IUP holder, number…", label_visibility="collapsed",
    )
    with filter_col:
        status_filter = st.segmented_control(
            "Show", list(_FILTER_OPTIONS), format_func=_FILTER_OPTIONS.get, default=_FILTER_ALL,
            key=state.KEY_VENDOR_STATUS, label_visibility="collapsed",
        ) or _FILTER_ALL
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ctx.table).strip("_").lower() or "vendor"
    download_col.download_button(
        label="Download Excel", icon=":material/download:",
        data=build_excel(saved, ctx.table), file_name=f"vendor_data_{slug}.xlsx", mime=_MIME_XLSX, width="stretch",
    )

    shown = _apply_filters(saved, query, status_filter)
    theme.legend([("Verified in MinerbaOne", theme.GREEN), ("IUP holder not found", theme.RED),
                  ("IUP expiring or expired", theme.AMBER)])
    if shown.empty:
        st.info("No vendors match this search or filter.", icon=":material/search_off:")
        return
    if len(shown) != len(saved):
        st.caption(f"Showing **{len(shown)}** of {len(saved)} vendors")
    st.dataframe(style_rows(with_status_column(with_whatsapp_links(shown))), width="stretch", height=table_height(len(shown)),
                 column_config=build_vendor_column_config(whatsapp_links=True, status_column=True))


def _apply_filters(df: pd.DataFrame, query: str, status_filter: str) -> pd.DataFrame:
    """Search text + status filter. The status masks are the same ones behind the summary cards."""
    shown = filter_dataframe(df, query)
    masks = {STATUS_VERIFIED: is_valid, STATUS_NOT_FOUND: is_not_found, STATUS_ATTENTION: needs_attention}
    if status_filter not in masks or shown.empty:
        return shown
    return shown[masks[status_filter](shown)]
