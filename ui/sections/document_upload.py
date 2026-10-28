"""'Scan a document (AI)' tab: upload photos/PDF (IUP, NIB, support letter) -> Gemini extraction -> vendor table."""
import mimetypes
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

import config
from core.schema import pretty_label
from repositories import vendor_repository
from services.document_ai import (
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
from services.document_ai.models import MAX_TOTAL_BYTES
from ui import state, theme
from ui.styles import build_vendor_column_config, style_rows, with_status_column

_TARGET_NEW = "Add as a new vendor"
_TARGET_EXISTING = "Fill in an existing vendor"
_FILE_TYPES = ["pdf", "png", "jpg", "jpeg", "webp"]
_MAX_PREVIEW_IMAGES = 4
_FIELD, _VALUE = "Field", "Value"


@dataclass
class _SaveTarget:
    """Where the extraction result will be saved."""
    preview: pd.DataFrame   # rows shown in the preview
    rows: pd.DataFrame      # DataFrame written to the database
    replace: bool           # True = replace the whole list (the 'fill in an existing vendor' mode)
    button_label: str


def render(ctx: state.VendorContext) -> None:
    theme.steps(["Upload photos or a PDF", "Let AI read it", "Check & save"])
    if not config.GEMINI_API_KEY:
        st.info("To use this feature, set `GEMINI_API_KEY` in the `.env` file and restart the app.",
                icon=":material/key:")
        return

    documents = _render_uploader(ctx.table)
    if documents:
        _render_extract_button(documents)

    result = st.session_state.get(state.KEY_DOC_RESULT)
    if result:
        _render_review(ctx, result)


# ------------------------------------------------------------------ 1. upload & extract
def _render_uploader(table: str) -> List[UploadedDocument]:
    version = st.session_state.setdefault(state.KEY_DOC_UPLOAD_VER, 0)
    files = st.file_uploader(
        "Permit document (IUP, NIB or support letter)",
        type=_FILE_TYPES,
        accept_multiple_files=True,
        key=f"doc_upload_{table}_{version}",
        help="You can select several photos or pages at once, as long as they belong to ONE document.",
    )
    st.caption(f"JPG, PNG, WEBP or PDF · several pages of one document are fine · "
               f"up to {MAX_TOTAL_BYTES // 1024 // 1024} MB in total")
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
    if not st.button("Read document with AI", type="primary", icon=":material/auto_awesome:", key="doc_extract"):
        return
    try:
        with st.spinner("Gemini is reading the document… this usually takes 10–30 seconds."):
            document = create_extractor().extract(documents)
    except ExtractionError as exc:
        st.error(str(exc), icon=":material/error:")
        return

    counter = st.session_state.get(state.KEY_DOC_COUNTER, 0) + 1
    st.session_state[state.KEY_DOC_COUNTER] = counter
    st.session_state[state.KEY_DOC_RESULT] = {
        "version": counter,  # part of the editor key so the correction table resets
        "type": DocumentType(document.document_type),
        "notes": document.notes,
        "values": to_vendor_values(document),
    }


def _discard_result() -> None:
    st.session_state.pop(state.KEY_DOC_RESULT, None)


# ------------------------------------------------------------------ 2. review, correct, save
def _render_review(ctx: state.VendorContext, result: dict) -> None:
    st.divider()
    head_col, discard_col = st.columns([4, 1.2], vertical_alignment="center")
    head_col.markdown(f"#### Review the result · {DOCUMENT_TYPE_LABELS[result['type']]}")
    discard_col.button("Discard result", icon=":material/close:", on_click=_discard_result, key="doc_discard",
                       width="stretch")
    if result["notes"]:
        st.warning(f"Note from the AI: {result['notes']}", icon=":material/smart_toy:")
    st.caption("AI can misread text, especially in blurry photos. Check every value and correct it in the table "
               "before saving.")

    values = _render_value_editor(result)
    if not values:
        st.info("Nothing could be read from this document. Try a sharper photo, or type the data in the "
                "“Type or edit” tab.", icon=":material/visibility_off:")
        return

    target = _choose_target(ctx, values)
    if target is None:
        return

    st.markdown("**Preview (already checked against MinerbaOne)**")
    st.dataframe(style_rows(with_status_column(target.preview)), width="stretch", hide_index=True,
                 column_config=build_vendor_column_config(status_column=True))

    if ctx.has_unsaved_edits:
        st.warning("You have unsaved changes in the “Type or edit” tab. Save or discard them first so they "
                   "aren't lost.", icon=":material/edit_note:")
    if st.button(target.button_label, type="primary", icon=":material/save:", disabled=ctx.has_unsaved_edits,
                 key="doc_apply"):
        _apply(ctx, target)


def _render_value_editor(result: dict) -> Dict[str, str]:
    """Two-column table (field, value) the user can correct. Returns the filled-in values."""
    rows = [{_FIELD: pretty_label(c), _VALUE: result["values"].get(c, "")} for c in FILLABLE_COLUMNS]
    edited = st.data_editor(
        pd.DataFrame(rows),
        hide_index=True,
        disabled=[_FIELD],
        width="stretch",
        column_config={
            _FIELD: st.column_config.TextColumn(width="medium"),
            _VALUE: st.column_config.TextColumn(width="large", help="Click to correct the value."),
        },
        key=f"doc_values_{result['version']}",
    )
    return normalize_values(dict(zip(FILLABLE_COLUMNS, edited[_VALUE].tolist())))


def _choose_target(ctx: state.VendorContext, values: Dict[str, str]) -> Optional[_SaveTarget]:
    mode = st.radio("Save as", [_TARGET_NEW, _TARGET_EXISTING], horizontal=True, key="doc_target")
    if mode == _TARGET_NEW:
        return _new_row_target(ctx, values)
    return _existing_row_target(ctx, values)


def _new_row_target(ctx: state.VendorContext, values: Dict[str, str]) -> _SaveTarget:
    row = ctx.validate(pd.DataFrame([new_vendor_row(values)]))
    return _SaveTarget(preview=row, rows=row, replace=False,
                       button_label=f"Save as a new vendor in '{ctx.table}'")


def _existing_row_target(ctx: state.VendorContext, values: Dict[str, str]) -> Optional[_SaveTarget]:
    if ctx.saved_df.empty:
        st.info("This list is still empty, so there is no vendor to fill in. Choose “Add as a new vendor”.",
                icon=":material/info:")
        return None

    position = st.selectbox(
        "Which vendor should be filled in?", range(len(ctx.saved_df)),
        format_func=lambda i: _row_label(ctx.saved_df, i), key="doc_existing_row",
    )
    overwrite = st.checkbox("Also overwrite fields that already have a value (default: only fill empty fields)",
                            value=False, key="doc_overwrite")

    merged = merge_values(ctx.saved_df.iloc[position].to_dict(), values, overwrite)
    updated = ctx.saved_df.copy()
    updated.loc[updated.index[position], list(merged)] = list(merged.values())
    updated = ctx.validate(updated)
    return _SaveTarget(preview=updated.iloc[[position]], rows=updated, replace=True,
                       button_label=f"Save to the selected vendor in '{ctx.table}'")


def _row_label(df: pd.DataFrame, position: int) -> str:
    row = df.iloc[position]
    return f"{position + 1} · {str(row['vendor']).strip() or '-'} · {str(row['iup_nama']).strip() or '-'}"


def _apply(ctx: state.VendorContext, target: _SaveTarget) -> None:
    records = vendor_repository.records_from_df(target.rows, ctx.table)
    if not records:
        st.error("There is nothing to save.", icon=":material/error:")
        return
    with st.spinner("Saving to the cloud database…"):
        vendor_repository.save_records(records, ctx.table, replace=target.replace)

    st.session_state.pop(state.KEY_DOC_RESULT, None)
    st.session_state[state.KEY_DOC_UPLOAD_VER] += 1
    state.invalidate_vendor_data()
    state.set_flash(f"The document data was saved to the list '{ctx.table}'.")
    st.rerun()
