"""Bagian UI: upload Excel data vendor, pratinjau pengecekan ke Minerba, lalu impor ke database."""
import pandas as pd
import streamlit as st

from core.schema import DB_COLS, pretty_label
from core.text_utils import normalize_name
from repositories import vendor_repository
from services.excel_export import build_excel
from services.excel_import import ImportResult, parse_vendor_excel
from ui import state
from ui.styles import build_vendor_column_config, style_rows

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MODE_APPEND = "➕ Tambahkan ke data yang sudah ada"
_MODE_REPLACE = "♻️ Ganti seluruh data tabel ini"


@st.cache_data(show_spinner=False)
def _parse_cached(data: bytes) -> ImportResult:
    return parse_vendor_excel(data)


def render(ctx: state.VendorContext) -> None:
    with st.expander("📤 Upload Excel Data Vendor"):
        st.caption(
            "Upload file Excel berisi data vendor. Sistem membaca header otomatis (header 1 baris seperti "
            "`NIB NOMOR` maupun header 2 tingkat), lalu langsung mengecek IUP NAMA ke tabel Minerba."
        )
        st.download_button(
            label="📄 Download template kosong",
            data=build_excel(pd.DataFrame(columns=DB_COLS), ctx.table),
            file_name="template_data_vendor.xlsx",
            mime=_MIME_XLSX,
            key="dl_template",
        )
        version = st.session_state.setdefault(state.KEY_EXCEL_UPLOAD_VER, 0)
        uploaded = st.file_uploader("Pilih file Excel (.xlsx)", type=["xlsx"], key=f"upload_{ctx.table}_{version}")
        if uploaded is None:
            return

        try:
            result = _parse_cached(uploaded.getvalue())
        except Exception as exc:  # noqa: BLE001 - file user bisa rusak dengan banyak cara
            st.error(f"Gagal membaca file: {exc}")
            return
        if result.data.empty:
            st.warning("Tidak ada baris data yang terbaca (kolom VENDOR dan IUP NAMA kosong semua).")
            return
        _render_preview_and_import(ctx, result)


def _render_preview_and_import(ctx: state.VendorContext, result: ImportResult) -> None:
    checked = ctx.validate(result.data)
    found = int((checked["minerbaone"] == "Valid").sum())
    total_col, valid_col, missing_col = st.columns(3)
    total_col.metric("Baris terbaca", len(checked))
    valid_col.metric("Valid di Minerba", found)
    missing_col.metric("Tidak ditemukan", len(checked) - found)

    with st.expander("Lihat pemetaan kolom"):
        st.write(", ".join(f"**{label}** → {pretty_label(db)}" for label, db in result.mapped))
        if result.unmapped:
            st.warning("Kolom berikut tidak dikenali dan diabaikan: " + ", ".join(result.unmapped))
    st.dataframe(style_rows(checked), use_container_width=True, height=300,
                 column_config=build_vendor_column_config())

    mode = st.radio("Cara impor", [_MODE_APPEND, _MODE_REPLACE], key=f"import_mode_{ctx.table}")
    replace = mode == _MODE_REPLACE
    to_save = checked
    if replace:
        st.warning(f"Seluruh data di tabel '{ctx.table}' akan diganti dengan isi file ini.")
    elif st.checkbox("Lewati baris yang sudah ada (VENDOR & IUP NAMA sama)", value=True,
                     key=f"skip_dup_{ctx.table}"):
        to_save, skipped = _drop_existing(checked, ctx.saved_df)
        if skipped:
            st.info(f"{skipped} baris dilewati karena sudah ada.")

    if st.button(f"✅ Impor {len(to_save)} baris ke tabel '{ctx.table}'", type="primary",
                 disabled=len(to_save) == 0):
        with st.spinner("Mengimpor ke Cloud Database..."):
            records = vendor_repository.records_from_df(to_save, ctx.table)
            vendor_repository.save_records(records, ctx.table, replace=replace)
        st.session_state[state.KEY_EXCEL_UPLOAD_VER] += 1
        state.invalidate_vendor_data()
        state.set_flash(f"Berhasil mengimpor {len(records)} baris ke tabel '{ctx.table}'.")
        st.rerun()


def _row_keys(df: pd.DataFrame):
    return [(normalize_name(v), normalize_name(i)) for v, i in zip(df["vendor"], df["iup_nama"])]


def _drop_existing(new_rows: pd.DataFrame, saved: pd.DataFrame):
    """Buang baris yang VENDOR & IUP NAMA-nya sudah ada di data tersimpan. Mengembalikan (sisa, jumlah dilewati)."""
    existing = set(_row_keys(saved))
    keep = [key not in existing for key in _row_keys(new_rows)]
    return new_rows[keep], len(keep) - sum(keep)
