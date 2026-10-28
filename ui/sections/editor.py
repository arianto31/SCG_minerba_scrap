"""'Type or edit' tab: add / change / delete vendors in an editable table, then save to the database."""
import streamlit as st

from core.frames import frames_equal
from repositories import vendor_repository
from ui import state, theme
from ui.styles import build_vendor_column_config

_TIPS = (
    "- **Edit:** click a cell and type. **Add:** type in the empty row at the bottom (or use **+** in the table toolbar). "
    "**Delete:** tick the row on the left, then press the bin icon or **Delete**.\n"
    "- Fill in **IUP · Holder Name** — the MinerbaOne status and IUP details are filled in for you.\n"
    "- Greyed-out columns are calculated by the app.\n"
    "- Nothing is stored until you click **Save changes**."
)


def render(ctx: state.VendorContext) -> None:
    theme.steps(["Edit the table", "Check the auto-filled fields", "Save changes"])
    with st.expander("Tips for editing", icon=":material/lightbulb:"):
        st.markdown(_TIPS)

    edited_df = _render_editor(ctx)

    unsaved = ctx.has_unsaved_edits
    if unsaved:
        st.warning("You have unsaved changes. Save them, or discard to go back to the saved data.",
                   icon=":material/edit_note:")
    save_col, discard_col, _ = st.columns([1.3, 1.3, 4])
    if save_col.button("Save changes", type="primary", icon=":material/save:", disabled=not unsaved,
                       width="stretch", key="editor_save"):
        _save(ctx, edited_df)
    discard_col.button("Discard changes", icon=":material/undo:", disabled=not unsaved, width="stretch",
                       on_click=state.discard_edits, key="editor_discard")


def _render_editor(ctx: state.VendorContext):
    version = st.session_state[state.KEY_EDITOR_VER]
    edited_raw = st.data_editor(
        ctx.working_df,
        num_rows="dynamic",
        width="stretch",
        height=440,
        column_config=build_vendor_column_config(),
        key=f"vendor_editor_{ctx.table}_{version}",
    )
    # Recalculate the automatic columns from the edits; if anything changed, reload the table
    edited_df = ctx.validate(edited_raw.fillna("").astype(str))
    if not frames_equal(edited_df, ctx.working_df):
        st.session_state[state.KEY_WORKING_DF] = edited_df
        st.session_state[state.KEY_EDITOR_VER] += 1
        st.rerun()
    return edited_df


def _save(ctx: state.VendorContext, edited_df) -> None:
    with st.spinner("Saving to the cloud database…"):
        records = vendor_repository.records_from_df(edited_df, ctx.table)
        vendor_repository.save_records(records, ctx.table, replace=True)
    state.invalidate_vendor_data()
    state.set_flash(f"Saved {len(records)} vendor{'s' if len(records) != 1 else ''} to the list '{ctx.table}'.")
    st.rerun()
