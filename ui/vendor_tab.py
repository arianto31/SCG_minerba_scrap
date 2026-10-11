"""Tab 'Vendor (Procurement)': merangkai seluruh bagian UI vendor."""
import re

import pandas as pd
import streamlit as st

from core.schema import AUTO_TAG
from core.validation import ValidationSettings, validate_vendors
from repositories import vendor_repository
from services.excel_export import build_excel
from ui import state
from ui.sections import document_upload, editor, excel_upload, settings_panel, table_selector
from ui.styles import build_vendor_column_config, style_rows

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render(df_minerba: pd.DataFrame) -> None:
    st.subheader("Manajemen Data Vendor")

    if not _schema_ready():
        return
    flash = state.pop_flash()
    if flash:
        st.success(flash)

    table = table_selector.render()
    _reset_when_table_changes(table)
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
    _render_colored_table(ctx)
    excel_upload.render(ctx)
    document_upload.render(ctx)
    editor.render(ctx)


# ------------------------------------------------------------------ persiapan
def _schema_ready() -> bool:
    """Pastikan kolom `kategori` ada; jika belum, tampilkan SQL yang harus dijalankan."""
    if state.KEY_SCHEMA_OK not in st.session_state:
        st.session_state[state.KEY_SCHEMA_OK] = vendor_repository.schema_ready()
    if st.session_state[state.KEY_SCHEMA_OK]:
        return True

    st.error(
        "Fitur banyak tabel butuh kolom `kategori` di tabel `vendor_procurement`. "
        "Jalankan SQL berikut sekali di Supabase (SQL Editor), lalu klik tombol di bawah."
    )
    st.code(vendor_repository.schema_migration_sql(), language="sql")
    if st.button("🔁 Sudah dijalankan, cek lagi"):
        st.session_state.pop(state.KEY_SCHEMA_OK, None)
        st.rerun()
    return False


def _reset_when_table_changes(table: str) -> None:
    if st.session_state.get(state.KEY_LOADED_TABLE) != table:
        state.invalidate_vendor_data()
        st.session_state[state.KEY_LOADED_TABLE] = table


def _load_data_once(table: str, df_minerba: pd.DataFrame, cfg: ValidationSettings) -> None:
    """Muat data vendor dari database ke session_state (salinan kerja + salinan tersimpan)."""
    if state.KEY_WORKING_DF in st.session_state:
        return
    base = validate_vendors(vendor_repository.fetch_vendors(table), df_minerba, cfg)
    st.session_state[state.KEY_WORKING_DF] = base
    st.session_state[state.KEY_SAVED_DF] = base
    st.session_state[state.KEY_EDITOR_VER] = 0


# ------------------------------------------------------------------ tampilan
def _render_summary(saved_df: pd.DataFrame) -> None:
    total = int((saved_df["iup_nama"].astype(str).str.strip() != "").sum())
    valid = int((saved_df["minerbaone"] == "Valid").sum())
    invalid = int((saved_df["minerbaone"] == "-").sum())
    warned = int(saved_df["remark"].astype(str).str.contains(AUTO_TAG, regex=False).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Vendor", total)
    c2.metric("Valid di Minerba", valid)
    c3.metric("Belum Valid", invalid)
    c4.metric("IUP Perlu Perhatian", warned)

    st.caption(
        "🟥 Merah = IUP NAMA tidak ditemukan di tabel Minerba  ·  "
        "🟨 Kuning = IUP akan / sudah berakhir (ada peringatan). "
        "Warna muncul pada data yang **sudah disimpan**."
    )


def _render_colored_table(ctx: state.VendorContext) -> None:
    st.dataframe(style_rows(ctx.saved_df), use_container_width=True, height=460,
                 column_config=build_vendor_column_config())

    slug = re.sub(r"[^A-Za-z0-9]+", "_", ctx.table).strip("_").lower() or "vendor"
    st.download_button(
        label="📥 Download Excel Vendor (.xlsx)",
        data=build_excel(ctx.saved_df, ctx.table),
        file_name=f"data_vendor_{slug}.xlsx",
        mime=_MIME_XLSX,
    )
