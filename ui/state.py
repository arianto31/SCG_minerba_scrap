"""Kunci session_state dan konteks bersama antar bagian UI vendor."""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

from core.frames import frames_equal
from core.validation import ValidationSettings, validate_vendors

# ---- kunci session_state (satu tempat agar mudah dilacak) ----
KEY_SCHEMA_OK = "schema_ok"
KEY_FLASH = "flash"
KEY_TABLE_NAMES = "table_names"
KEY_ACTIVE_TABLE = "active_table"
KEY_LOADED_TABLE = "loaded_table"
KEY_NEW_TABLE_NAME = "new_table_name"
KEY_WORKING_DF = "vendor_df"      # salinan kerja (isi editor)
KEY_SAVED_DF = "saved_df"         # data yang sudah tersimpan (tabel berwarna)
KEY_EDITOR_VER = "editor_ver"
KEY_EXCEL_UPLOAD_VER = "upload_ver"
KEY_DOC_UPLOAD_VER = "doc_upload_ver"
KEY_DOC_RESULT = "doc_result"
KEY_DOC_COUNTER = "doc_counter"


@dataclass
class VendorContext:
    """Data yang dibutuhkan setiap bagian UI vendor, dibuat sekali per rerun."""
    table: str
    df_minerba: pd.DataFrame
    cfg: ValidationSettings
    saved_df: pd.DataFrame      # sudah divalidasi
    working_df: pd.DataFrame    # isi editor (bisa berisi perubahan yang belum disimpan)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_vendors(df, self.df_minerba, self.cfg)

    @property
    def has_unsaved_edits(self) -> bool:
        return not frames_equal(self.working_df, self.saved_df)


def set_flash(message: str) -> None:
    """Pesan sukses yang ditampilkan sekali pada render berikutnya (bertahan melewati st.rerun)."""
    st.session_state[KEY_FLASH] = message


def pop_flash() -> Optional[str]:
    return st.session_state.pop(KEY_FLASH, None)


def invalidate_vendor_data() -> None:
    """Paksa data vendor dimuat ulang dari database pada render berikutnya."""
    st.session_state.pop(KEY_WORKING_DF, None)
    st.session_state.pop(KEY_SAVED_DF, None)
