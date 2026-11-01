"""'Vendors' page: puts all vendor UI sections together."""
import re

import pandas as pd
import streamlit as st

from core.filtering import filter_dataframe
from core.phone import with_whatsapp_links
from core.schema import RENEWAL_COL
from core.validation import ValidationSettings, validate_vendors
from core.vendor_status import (
    STATUS_ATTENTION, STATUS_NOT_FOUND, STATUS_VERIFIED, is_not_found, is_valid, needs_attention, summarize,
)
from repositories import vendor_repository
from services.excel_export import build_excel
from ui import state, theme
from ui.sections import details, document_upload, editor, excel_upload, quick_add, settings_panel, table_selector
from ui.styles import CLICKABLE_COLUMNS, COMPACT_COLUMNS, build_compact_column_config, style_rows, table_height

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_FILTER_ALL = "all"
_FILTER_OPTIONS = {
    _FILTER_ALL: "All",
    STATUS_VERIFIED: "Verified",
    STATUS_NOT_FOUND: "Not found",
    STATUS_ATTENTION: "Needs attention",
}
_FILTER_TITLES = {
    _FILTER_ALL: "All vendors",
    STATUS_VERIFIED: "Verified vendors",
    STATUS_NOT_FOUND: "IUP holder not found in MinerbaOne",
    STATUS_ATTENTION: "IUP needs attention (expiring or expired)",
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

    list_col, new_col, rules_col, _, add_col = st.columns([2.6, 1, 1.2, 1.2, 1.3], vertical_alignment="bottom")
    table = table_selector.render(list_col, new_col)
    _reset_when_table_changes(table)
    with rules_col:
        cfg = settings_panel.render(df_minerba)
    add_clicked = add_col.button("Add vendor", type="primary", icon=":material/add:", width="stretch",
                                 key="open_quick_add", help="Add one record with a short form (checks for duplicates).")
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
    if add_clicked:
        st.session_state.pop(state.KEY_ADD_PENDING, None)
        quick_add.show(ctx)

    theme.section("More ways to add or update",
                  "Edit many rows at once, import an Excel file, or scan a permit. Each one checks MinerbaOne for you.")
    edit_tab, excel_tab, scan_tab = st.tabs([
        ":material/edit_note: Edit the full table",
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
        "The `vendor_procurement` table is missing new columns (`kategori` for multiple lists, `golongan`, "
        "`lokasi_maps` for the Google Maps link, `iup_renewal` for the IUP renewal tracker). "
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
def _toggle_card(key: str) -> None:
    """KPI card callback: show the vendors behind this card, or hide the table when it is clicked again."""
    current = st.session_state.get(state.KEY_VENDOR_STATUS)
    st.session_state[state.KEY_VENDOR_STATUS] = None if current == key else key
    _clear_table_selection()


def _clear_table_selection() -> None:
    st.session_state[state.KEY_TABLE_VER] = st.session_state.get(state.KEY_TABLE_VER, 0) + 1


def _render_summary(saved_df: pd.DataFrame) -> None:
    s = summarize(saved_df)

    def share(part: int) -> str:
        return f"{part / s.total:.0%} found in MinerbaOne" if s.total else "no vendors yet"

    active = st.session_state.get(state.KEY_VENDOR_STATUS)
    if active not in _FILTER_OPTIONS:
        active = st.session_state[state.KEY_VENDOR_STATUS] = None
    theme.clickable_kpi_cards([
        (_FILTER_ALL, theme.Kpi("Total vendors", theme.fmt_int(s.total), "with an IUP holder name", theme.INDIGO)),
        (STATUS_VERIFIED, theme.Kpi("Verified", theme.fmt_int(s.verified), share(s.verified), theme.GREEN)),
        (STATUS_NOT_FOUND, theme.Kpi("Not found", theme.fmt_int(s.not_found), "IUP holder missing in MinerbaOne",
                                     theme.RED)),
        (STATUS_ATTENTION, theme.Kpi("Needs attention", theme.fmt_int(s.attention), "IUP expiring soon or expired",
                                     theme.AMBER)),
    ], active, _toggle_card)


def _render_vendor_table(ctx: state.VendorContext) -> None:
    saved = ctx.saved_df
    if saved.empty:
        theme.empty_state(
            "📋", "This list has no vendors yet",
            "Click “Add vendor” at the top, or import an Excel file / scan a permit document below.",
        )
        return

    active = st.session_state.get(state.KEY_VENDOR_STATUS)
    search_col, download_col = st.columns([4.4, 1.3], vertical_alignment="bottom")
    query = search_col.text_input(
        "Search vendors", key=state.KEY_VENDOR_SEARCH, icon=":material/search:",
        placeholder="Search by vendor, PIC, IUP holder, number…", label_visibility="collapsed",
        on_change=_clear_table_selection,
    )
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ctx.table).strip("_").lower() or "vendor"
    download_col.download_button(
        label="Download Excel", icon=":material/download:",
        data=build_excel(saved, ctx.table), file_name=f"vendor_data_{slug}.xlsx", mime=_MIME_XLSX, width="stretch",
    )

    if active is None and not query.strip():
        theme.empty_state("👆", "Click a card above to see its vendors",
                          "For example, click “Needs attention” to list only the IUPs that expire soon. "
                          "You can also type in the search box.")
        return

    shown = _apply_filters(saved, query, active or _FILTER_ALL)
    title = _FILTER_TITLES.get(active or _FILTER_ALL)
    theme.section(title, "Click a Holder Name or Vendor to open its details. Click a contact number to chat on WhatsApp.")
    theme.legend([("Verified", theme.GREEN), ("IUP holder not found", theme.RED),
                  ("IUP expiring or expired", theme.AMBER)])
    if shown.empty:
        st.info("No vendors match this search or card.", icon=":material/search_off:")
        return
    st.caption(f"Showing **{len(shown)}** of {len(saved)} records")

    compact = with_whatsapp_links(shown[[column for column, _, _ in COMPACT_COLUMNS]])
    event = st.dataframe(
        style_rows(compact, status_source=shown), width="stretch", height=table_height(len(shown), 520),
        column_config=build_compact_column_config(), on_select="rerun", selection_mode="single-cell",
        key=f"vendor_table_{ctx.table}_{st.session_state.get(state.KEY_TABLE_VER, 0)}",
    )
    _open_clicked_cell(ctx, event, compact)


def _open_clicked_cell(ctx: state.VendorContext, event, compact: pd.DataFrame) -> None:
    """A click on a Holder Name / Vendor cell opens the details popup (inside the app, no new tab)."""
    cells = event.selection.cells if event is not None else []
    if not cells:
        return
    position, column = cells[0]
    if column not in CLICKABLE_COLUMNS or not (0 <= position < len(compact)):
        return
    _clear_table_selection()   # so the popup does not open again on the next rerun
    kind = details.KIND_HOLDER if column == "iup_nama" else details.KIND_VENDOR
    if details.open_details(kind, ctx.saved_df, compact.index[position]):
        details.show(ctx)
    else:
        st.toast("This cell is empty, so there are no details to show.", icon="ℹ️")


def _apply_filters(df: pd.DataFrame, query: str, status_filter: str) -> pd.DataFrame:
    """Search text + card filter. The status masks are the same ones behind the summary cards."""
    searchable = df.drop(columns=[RENEWAL_COL], errors="ignore")   # don't search inside the tracker JSON
    shown = df.loc[filter_dataframe(searchable, query).index]
    masks = {STATUS_VERIFIED: is_valid, STATUS_NOT_FOUND: is_not_found, STATUS_ATTENTION: needs_attention}
    if status_filter not in masks or shown.empty:
        return shown
    return shown[masks[status_filter](shown)]
