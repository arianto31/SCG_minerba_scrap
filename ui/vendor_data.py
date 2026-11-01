"""Small write operations used by the popups: update every row of one IUP holder, add one record."""
from typing import List, Mapping

import pandas as pd
import streamlit as st

from core import material_groups
from core.frames import frames_equal
from core.schema import DB_COLS
from core.text_utils import normalize_name
from repositories import vendor_repository
from ui import state


def current_saved(ctx: state.VendorContext) -> pd.DataFrame:
    """Saved rows, validated with the current settings. Read from session_state so popups never see stale data."""
    return ctx.validate(st.session_state[state.KEY_SAVED_DF])


def _has_unsaved_edits(ctx: state.VendorContext) -> bool:
    return not frames_equal(st.session_state[state.KEY_WORKING_DF], current_saved(ctx))


def holder_mask(df: pd.DataFrame, holder_key: str) -> pd.Series:
    return df["iup_nama"].map(normalize_name) == holder_key


def update_holder(ctx: state.VendorContext, holder_key: str, updates: Mapping[str, str]) -> pd.DataFrame:
    """
    Set `updates` on every saved row of this IUP holder, save the list, and return the new saved rows.
    Unsaved edits in the editor are kept: the same change is applied to the editor copy too.
    """
    saved = current_saved(ctx)
    mask = holder_mask(saved, holder_key)
    if not mask.any():
        raise ValueError("This IUP holder is no longer in the saved list.")
    changed = saved.copy()
    for column, value in updates.items():
        changed.loc[mask, column] = value
    changed = ctx.validate(changed)

    with st.spinner("Saving…"):
        vendor_repository.save_records(vendor_repository.records_from_df(changed, ctx.table), ctx.table, replace=True)

    working = st.session_state[state.KEY_WORKING_DF].copy()
    unsaved = not frames_equal(working, saved)
    if unsaved:
        working_mask = holder_mask(working, holder_key)
        for column, value in updates.items():
            working.loc[working_mask, column] = value
        working = ctx.validate(working)
    else:
        working = changed
    st.session_state[state.KEY_SAVED_DF] = changed
    st.session_state[state.KEY_WORKING_DF] = working
    st.session_state[state.KEY_EDITOR_VER] = st.session_state.get(state.KEY_EDITOR_VER, 0) + 1
    return changed


def add_record(ctx: state.VendorContext, values: Mapping[str, str]) -> None:
    """Insert one new record into the active list (other rows are not touched)."""
    row = pd.DataFrame([{column: str(values.get(column, "") or "").strip() for column in DB_COLS}])
    checked = ctx.validate(row)
    records = vendor_repository.records_from_df(checked, ctx.table)
    if not records:
        raise ValueError("The record is empty.")
    unsaved = _has_unsaved_edits(ctx)
    with st.spinner("Saving…"):
        vendor_repository.save_records(records, ctx.table, replace=False)

    if not unsaved:
        state.invalidate_vendor_data()   # reload from the database on the next run
        return
    # Keep the unsaved editor edits: append the new record to both copies.
    for key in (state.KEY_SAVED_DF, state.KEY_WORKING_DF):
        df = st.session_state[key]
        new = checked.copy()
        try:
            next_no = int(pd.to_numeric(pd.Series(df.index)).max()) + 1 if len(df) else 1
        except (TypeError, ValueError):
            next_no = len(df) + 1
        new.index = [next_no]
        new.index.name = df.index.name or "NO"
        st.session_state[key] = pd.concat([df, new])
    st.session_state[state.KEY_EDITOR_VER] = st.session_state.get(state.KEY_EDITOR_VER, 0) + 1


def material_group_options(ctx: state.VendorContext) -> List[str]:
    """Batuan, Pasir, Fly Ash + every group used in any list + groups added in this session."""
    if state.KEY_GROUPS_DB not in st.session_state:
        try:
            st.session_state[state.KEY_GROUPS_DB] = vendor_repository.fetch_material_groups()
        except Exception:  # noqa: BLE001 - the dropdown still works with the other sources
            st.session_state[state.KEY_GROUPS_DB] = []
    return material_groups.build_options(
        st.session_state[state.KEY_GROUPS_DB],
        st.session_state[state.KEY_SAVED_DF]["golongan"] if state.KEY_SAVED_DF in st.session_state else [],
        st.session_state[state.KEY_WORKING_DF]["golongan"] if state.KEY_WORKING_DF in st.session_state else [],
        st.session_state.get(state.KEY_GROUPS_NEW, []),
    )


def remember_new_group(ctx: state.VendorContext, name: str) -> str:
    """Add a group to this session's dropdowns (it is stored for good once a record using it is saved)."""
    options = material_group_options(ctx)
    name = material_groups.canonical(name, options)
    if name and name not in options:
        st.session_state.setdefault(state.KEY_GROUPS_NEW, []).append(name)
    return name
