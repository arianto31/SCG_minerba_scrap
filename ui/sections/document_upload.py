"""Bagian UI: upload foto/PDF dokumen (IUP, NIB, Surat Dukungan) -> ekstraksi Gemini -> isi tabel vendor."""
import mimetypes
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

import config
from core.schema import pretty_label
from repositories import vendor_repository
from services.document_ai import (
    ALLOWED_MIME_TYPES,
    DOCUMENT_TYPE_LABELS,
    FILLABLE_COLUMNS,
    DocumentType,
    ExtractionError,
    UploadedDocument,
    create_extractor,
    merge_values,
    new_vendor_row,
    normalize_values,
    to_vendor_values,
)
from ui import state
from ui.styles import build_vendor_column_config, style_rows

_TARGET_NEW = "➕ Buat baris baru"
_TARGET_EXISTING = "📝 Isi ke baris yang sudah ada"
_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "webp"]
_MAX_PREVIEW_IMAGES = 4


@dataclass
class _SaveTarget:
    """Ke mana hasil ekstraksi akan disimpan."""
    preview: pd.DataFrame   # baris yang ditampilkan pada pratinjau
    rows: pd.DataFrame      # DataFrame yang disimpan ke database
    replace: bool           # True = ganti seluruh isi tabel (mode 'isi baris yang sudah ada')
    button_label: str


def render(ctx: state.VendorContext) -> None:
    with st.expander("🤖 Upload Dokumen IUP / Data Tambang (Foto atau PDF) — ekstrak dengan AI"):
        if not config.GEMINI_API_KEY:
            st.info("Isi `GEMINI_API_KEY` di file `.env`, lalu jalankan ulang aplikasi untuk memakai fitur ini.")
            return

        documents = _render_uploader(ctx.table)
        if documents:
            _render_extract_button(documents)

        result = st.session_state.get(state.KEY_DOC_RESULT)
        if result:
            _render_review(ctx, result)


# ------------------------------------------------------------------ 1. upload & ekstraksi
def _render_uploader(table: str) -> List[UploadedDocument]:
    version = st.session_state.setdefault(state.KEY_DOC_UPLOAD_VER, 0)
    files = st.file_uploader(
        "Pilih foto (JPG/PNG/WEBP) atau PDF. Beberapa foto/halaman dari SATU dokumen boleh dipilih sekaligus.",
        type=_FILE_TYPES,
        accept_multiple_files=True,
        key=f"doc_upload_{table}_{version}",
    )
    documents = [
        UploadedDocument(name=f.name, data=f.getvalue(), mime_type=_mime_type(f)) for f in (files or [])
    ]
    _render_previews(documents)
    return documents


def _mime_type(uploaded_file) -> str:
    return uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"


def _render_previews(documents: List[UploadedDocument]) -> None:
    images = [d for d in documents if d.mime_type.startswith("image/")]
    for column, image in zip(st.columns(_MAX_PREVIEW_IMAGES), images[:_MAX_PREVIEW_IMAGES]):
        column.image(image.data, caption=image.name, width="stretch")
    pdfs = [d.name for d in documents if d.mime_type == "application/pdf"]
    if pdfs:
        st.caption("📄 PDF: " + ", ".join(pdfs))


def _render_extract_button(documents: List[UploadedDocument]) -> None:
    if not st.button("🔍 Ekstrak dengan Gemini", type="primary", key="doc_extract"):
        return
    try:
        with st.spinner("Gemini sedang membaca dokumen..."):
            document = create_extractor().extract(documents)
    except ExtractionError as exc:
        st.error(str(exc))
        return

    counter = st.session_state.get(state.KEY_DOC_COUNTER, 0) + 1
    st.session_state[state.KEY_DOC_COUNTER] = counter
    st.session_state[state.KEY_DOC_RESULT] = {
        "version": counter,  # dipakai sebagai bagian key editor agar tabel koreksi ter-reset
        "type": DocumentType(document.document_type),
        "notes": document.catatan,
        "values": to_vendor_values(document),
    }


# ------------------------------------------------------------------ 2. tinjau, koreksi, simpan
def _render_review(ctx: state.VendorContext, result: dict) -> None:
    st.divider()
    st.markdown(f"**Jenis dokumen terdeteksi:** {DOCUMENT_TYPE_LABELS[result['type']]}")
    if result["notes"]:
        st.warning(f"Catatan AI: {result['notes']}")
    st.caption("Periksa dan koreksi hasil ekstraksi sebelum disimpan. AI bisa salah baca, terutama pada foto buram.")

    values = _render_value_editor(result)
    if not values:
        st.info("Tidak ada data yang berhasil dibaca. Coba foto yang lebih jelas, atau isi manual pada tabel di atas.")
        return

    target = _choose_target(ctx, values)
    if target is None:
        return

    st.markdown("**Pratinjau hasil (sudah dicek ke Minerba):**")
    st.dataframe(style_rows(target.preview), width="stretch", hide_index=True,
                 column_config=build_vendor_column_config())

    if ctx.has_unsaved_edits:
        st.warning("Ada perubahan di tabel editor yang belum disimpan. Simpan dulu agar tidak hilang.")
    if st.button(target.button_label, type="primary", disabled=ctx.has_unsaved_edits, key="doc_apply"):
        _apply(ctx, target)


def _render_value_editor(result: dict) -> Dict[str, str]:
    """Tabel dua kolom (kolom vendor, nilai) yang bisa dikoreksi user. Mengembalikan nilai yang terisi."""
    rows = [{"Kolom": pretty_label(c), "Nilai": result["values"].get(c, "")} for c in FILLABLE_COLUMNS]
    edited = st.data_editor(
        pd.DataFrame(rows),
        hide_index=True,
        disabled=["Kolom"],
        width="stretch",
        column_config={
            "Kolom": st.column_config.TextColumn(width="medium"),
            "Nilai": st.column_config.TextColumn(width="large"),
        },
        key=f"doc_values_{result['version']}",
    )
    return normalize_values(dict(zip(FILLABLE_COLUMNS, edited["Nilai"].tolist())))


def _choose_target(ctx: state.VendorContext, values: Dict[str, str]) -> Optional[_SaveTarget]:
    mode = st.radio("Simpan sebagai", [_TARGET_NEW, _TARGET_EXISTING], horizontal=True, key="doc_target")
    if mode == _TARGET_NEW:
        return _new_row_target(ctx, values)
    return _existing_row_target(ctx, values)


def _new_row_target(ctx: state.VendorContext, values: Dict[str, str]) -> _SaveTarget:
    row = ctx.validate(pd.DataFrame([new_vendor_row(values)]))
    return _SaveTarget(preview=row, rows=row, replace=False,
                       button_label=f"💾 Simpan sebagai baris baru di '{ctx.table}'")


def _existing_row_target(ctx: state.VendorContext, values: Dict[str, str]) -> Optional[_SaveTarget]:
    if ctx.saved_df.empty:
        st.info("Tabel ini masih kosong, belum ada baris yang bisa diisi. Pilih 'Buat baris baru'.")
        return None

    position = st.selectbox(
        "Pilih baris yang akan diisi", range(len(ctx.saved_df)),
        format_func=lambda i: _row_label(ctx.saved_df, i), key="doc_existing_row",
    )
    overwrite = st.checkbox("Timpa kolom yang sudah terisi (bawaan: hanya isi yang masih kosong)",
                            value=False, key="doc_overwrite")

    merged = merge_values(ctx.saved_df.iloc[position].to_dict(), values, overwrite)
    updated = ctx.saved_df.copy()
    updated.loc[updated.index[position], list(merged)] = list(merged.values())
    updated = ctx.validate(updated)
    return _SaveTarget(preview=updated.iloc[[position]], rows=updated, replace=True,
                       button_label=f"💾 Simpan ke baris terpilih di '{ctx.table}'")


def _row_label(df: pd.DataFrame, position: int) -> str:
    row = df.iloc[position]
    return f"{position + 1} · {str(row['vendor']).strip() or '-'} · {str(row['iup_nama']).strip() or '-'}"


def _apply(ctx: state.VendorContext, target: _SaveTarget) -> None:
    records = vendor_repository.records_from_df(target.rows, ctx.table)
    if not records:
        st.error("Tidak ada data yang bisa disimpan.")
        return
    with st.spinner("Menyimpan ke Cloud Database..."):
        vendor_repository.save_records(records, ctx.table, replace=target.replace)

    st.session_state.pop(state.KEY_DOC_RESULT, None)
    st.session_state[state.KEY_DOC_UPLOAD_VER] += 1
    state.invalidate_vendor_data()
    state.set_flash(f"Data dokumen berhasil disimpan ke tabel '{ctx.table}'.")
    st.rerun()
