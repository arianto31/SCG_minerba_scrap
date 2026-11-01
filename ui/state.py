"""session_state keys and the shared context passed between vendor UI sections."""
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import streamlit as st

from core.frames import frames_equal
from core.validation import ValidationSettings, validate_vendors

# ---- session_state keys (one place, easy to trace) ----
KEY_AUTH_USER = "auth_user"        # username currently signed in
KEY_SCHEMA_OK = "schema_ok"
KEY_FLASH = "flash"
KEY_TABLE_NAMES = "table_names"
KEY_ACTIVE_TABLE = "active_table"
KEY_LOADED_TABLE = "loaded_table"
KEY_NEW_TABLE_NAME = "new_table_name"
KEY_WORKING_DF = "vendor_df"      # working copy (editor content)
KEY_SAVED_DF = "saved_df"         # data already saved (colored table)
KEY_EDITOR_VER = "editor_ver"
KEY_EXCEL_UPLOAD_VER = "upload_ver"
KEY_DOC_UPLOAD_VER = "doc_upload_ver"
KEY_DOC_RESULT = "doc_result"
KEY_DOC_COUNTER = "doc_counter"
KEY_SCRAPE_SUMMARY = "scrape_summary"   # summary of the last ESDM refresh
KEY_VENDOR_SEARCH = "vendor_search"
KEY_VENDOR_STATUS = "vendor_status_filter"   # KPI card picked to show the table (None = table hidden)
KEY_TABLE_VER = "vendor_table_ver"           # bumped to clear the table's cell selection
KEY_DETAIL = "vendor_detail"                 # what the details popup shows: {"kind", "key", "row", "history"}
KEY_ADD_PENDING = "quick_add_pending"        # quick-add values waiting for "Save anyway" (duplicate check)
KEY_EDITOR_CONFIRM = "editor_confirm_dup"    # editor save waiting for "Save anyway" (duplicate check)
KEY_GROUPS_DB = "material_groups_db"         # material groups used in the database (all lists), cached
KEY_GROUPS_NEW = "material_groups_new"       # groups added in this session that no saved record uses yet


@dataclass
class VendorContext:
    """Data every vendor UI section needs, built once per rerun."""
    table: str
    df_minerba: pd.DataFrame
    cfg: ValidationSettings
    saved_df: pd.DataFrame      # already validated
    working_df: pd.DataFrame    # editor content (may hold unsaved changes)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        return validate_vendors(df, self.df_minerba, self.cfg)

    @property
    def has_unsaved_edits(self) -> bool:
        return not frames_equal(self.working_df, self.saved_df)


def set_flash(message: str) -> None:
    """Success message shown once on the next render (survives st.rerun)."""
    st.session_state[KEY_FLASH] = message


def pop_flash() -> Optional[str]:
    return st.session_state.pop(KEY_FLASH, None)


def invalidate_vendor_data() -> None:
    """Force the vendor data to be reloaded from the database on the next render."""
    st.session_state.pop(KEY_WORKING_DF, None)
    st.session_state.pop(KEY_SAVED_DF, None)
    st.session_state.pop(KEY_GROUPS_DB, None)


def discard_edits() -> None:
    """Button callback: throw away unsaved editor changes and show the saved data again."""
    if KEY_SAVED_DF in st.session_state:
        st.session_state[KEY_WORKING_DF] = st.session_state[KEY_SAVED_DF]
        st.session_state[KEY_EDITOR_VER] = st.session_state.get(KEY_EDITOR_VER, 0) + 1
