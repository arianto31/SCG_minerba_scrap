"""Bagian UI: tambah / ubah / hapus data vendor lewat tabel editor, lalu simpan ke database."""
import time

import streamlit as st

from core.frames import frames_equal
from repositories import vendor_repository
from ui import state
from ui.styles import build_vendor_column_config


def render(ctx: state.VendorContext) -> None:
    title = "✏️ Tambah / Edit Data Vendor" + (" — ada perubahan belum disimpan" if ctx.has_unsaved_edits else "")
    with st.expander(title):
        st.caption(
            "Klik **+** di bawah tabel untuk menambah baris, atau pilih baris lalu tekan **Delete** untuk menghapus. "
            "Kolom **IUP NAMA** tetap terlihat saat tabel digeser ke kanan. "
            "MINERBAONE dan data IUP terisi otomatis begitu IUP NAMA diisi. "
            "Klik **Simpan Perubahan** agar tersimpan dan tabel berwarna di atas ikut diperbarui."
        )
        edited_df = _render_editor(ctx)
        if st.button("💾 Simpan Perubahan", type="primary"):
            _save(ctx, edited_df)


def _render_editor(ctx: state.VendorContext):
    version = st.session_state[state.KEY_EDITOR_VER]
    edited_raw = st.data_editor(
        ctx.working_df,
        num_rows="dynamic",
        use_container_width=True,
        height=460,
        column_config=build_vendor_column_config(),
        key=f"vendor_editor_{ctx.table}_{version}",
    )
    # Hitung ulang kolom otomatis dari hasil edit; jika ada perubahan, muat ulang tabel
    edited_df = ctx.validate(edited_raw.fillna("").astype(str))
    if not frames_equal(edited_df, ctx.working_df):
        st.session_state[state.KEY_WORKING_DF] = edited_df
        st.session_state[state.KEY_EDITOR_VER] += 1
        st.rerun()
    return edited_df


def _save(ctx: state.VendorContext, edited_df) -> None:
    with st.spinner("Menyimpan ke Cloud Database..."):
        records = vendor_repository.records_from_df(edited_df, ctx.table)
        vendor_repository.save_records(records, ctx.table, replace=True)
        state.invalidate_vendor_data()
        st.success(f"Berhasil menyimpan {len(records)} baris ke tabel '{ctx.table}'!")
        time.sleep(1)
        st.rerun()
