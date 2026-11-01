"""'Type or edit' tab: add / change / delete vendors in an editable table, then save to the database."""
import pandas as pd
import streamlit as st

from core import duplicates, required
from core.frames import frames_equal
from repositories import vendor_repository
from ui import state, theme
from ui.styles import build_vendor_column_config
from ui.vendor_data import material_group_options, remember_new_group

_TIPS = (
    "- **Edit:** click a cell and type. **Add:** type in the empty row at the bottom (or use **+** in the table toolbar). "
    "**Delete:** click the small box at the left edge of the row (it turns red), then click the bin icon that "
    "appears above the table on the right, or press **Delete**. Then click **Save changes**.\n"
    "- New rows need **IUP · Holder Name**, **Vendor**, **PIC Name** and **Material Group**. "
    "The MinerbaOne status and IUP details are filled in for you.\n"
    "- Greyed-out columns are calculated by the app.\n"
    "- Nothing is stored until you click **Save changes**."
)


def render(ctx: state.VendorContext) -> None:
    theme.steps(["Edit the table", "Check the auto-filled fields", "Save changes"])
    tips_col, group_col = st.columns([4, 1.4], vertical_alignment="top")
    with tips_col.expander("Tips for editing", icon=":material/lightbulb:"):
        st.markdown(_TIPS)
    with group_col.popover("New material group", icon=":material/add:", width="stretch"):
        _new_group_form(ctx)

    edited_df = _render_editor(ctx)

    unsaved = ctx.has_unsaved_edits
    if unsaved:
        st.warning("You have unsaved changes. Save them, or discard to go back to the saved data.",
                   icon=":material/edit_note:")
    save_col, discard_col, _ = st.columns([1.3, 1.3, 4])
    save_clicked = save_col.button("Save changes", type="primary", icon=":material/save:", disabled=not unsaved,
                                   width="stretch", key="editor_save")
    discard_col.button("Discard changes", icon=":material/undo:", disabled=not unsaved, width="stretch",
                       on_click=_discard, key="editor_discard")
    if save_clicked:
        # new records must have the required fields; then check for duplicates
        incomplete = required.incomplete_rows(required.new_rows(edited_df, ctx.saved_df))
        if not incomplete.empty:
            st.session_state.pop(state.KEY_EDITOR_CONFIRM, None)
            _show_incomplete(incomplete)
            return
        if duplicates.related_to_new_rows(edited_df, ctx.saved_df).empty:
            _save(ctx, edited_df)
        st.session_state[state.KEY_EDITOR_CONFIRM] = True

    if unsaved and st.session_state.get(state.KEY_EDITOR_CONFIRM):
        _duplicate_check(ctx, edited_df)


def _new_group_form(ctx: state.VendorContext) -> None:
    """Add a material group to the dropdown when none of the existing ones fits."""
    st.caption("Current groups: " + ", ".join(material_group_options(ctx)))
    with st.form("new_group_form", border=False, clear_on_submit=True):
        name = st.text_input("Group name", placeholder="e.g. Split, Abu Batu")
        added = st.form_submit_button("Add to the list", type="primary", icon=":material/add:")
    if added:
        before = material_group_options(ctx)
        name = remember_new_group(ctx, name)
        if not name:
            st.error("Type a group name first.")
        elif name in before:
            st.info(f"“{name}” is already in the list.")
        else:
            st.session_state[state.KEY_EDITOR_VER] += 1   # rebuild the table so the dropdown shows it
            st.rerun()


def _show_incomplete(incomplete: pd.DataFrame) -> None:
    """New rows must have the required fields; list the ones that don't (nothing is saved)."""
    count = len(incomplete)
    st.error(
        f"{count} new row{'s are' if count != 1 else ' is'} missing required fields. Every new record needs "
        f"{required.required_text()}. Fill them in, then click Save changes again.",
        icon=":material/assignment_late:",
    )
    st.dataframe(
        pd.DataFrame({
            "Missing": incomplete[required.MISSING_COLUMN], "Holder Name": incomplete["iup_nama"],
            "Vendor": incomplete["vendor"], "PIC": incomplete["nama_pic"], "Material Group": incomplete["golongan"],
        }, index=incomplete.index),
        width="stretch", height=min(320, 40 + 35 * count),
        column_config={"_index": st.column_config.TextColumn("No", width=55)},
    )


def _discard() -> None:
    st.session_state.pop(state.KEY_EDITOR_CONFIRM, None)
    state.discard_edits()


def _duplicate_check(ctx: state.VendorContext, edited_df) -> None:
    """Before saving: list saved records that look like the rows just added, and ask to confirm."""
    related = duplicates.related_to_new_rows(edited_df, ctx.saved_df)
    if related.empty:
        st.session_state.pop(state.KEY_EDITOR_CONFIRM, None)
        return
    st.warning(
        f"Some new rows look like **{len(related)}** record{'s' if len(related) != 1 else ''} already saved "
        "(same or similar vendor / IUP holder). Check them so you don't save the same data twice.",
        icon=":material/content_copy:",
    )
    st.dataframe(
        pd.DataFrame({
            "Match": related[duplicates.MATCH_COLUMN], "Holder Name": related["iup_nama"],
            "Vendor": related["vendor"], "PIC": related["nama_pic"], "Contact": related["no_kontak"],
        }, index=related.index),
        width="stretch", height=min(320, 40 + 35 * len(related)),
        column_config={"_index": st.column_config.TextColumn("No", width=55)},
    )
    save_col, cancel_col, _ = st.columns([1.3, 1.3, 4])
    if save_col.button("Save anyway", type="primary", icon=":material/save:", width="stretch",
                       key="editor_save_anyway"):
        _save(ctx, edited_df)
    if cancel_col.button("Keep editing", icon=":material/edit:", width="stretch", key="editor_keep_editing"):
        st.session_state.pop(state.KEY_EDITOR_CONFIRM, None)
        st.rerun()


def _render_editor(ctx: state.VendorContext):
    version = st.session_state[state.KEY_EDITOR_VER]
    edited_raw = st.data_editor(
        ctx.working_df,
        num_rows="dynamic",
        width="stretch",
        height=440,
        column_config=build_vendor_column_config(group_options=material_group_options(ctx)),
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
    st.session_state.pop(state.KEY_EDITOR_CONFIRM, None)
    incomplete = required.incomplete_rows(required.new_rows(edited_df, ctx.saved_df))
    if not incomplete.empty:   # also guards "Save anyway" after further edits
        _show_incomplete(incomplete)
        return
    with st.spinner("Saving to the cloud database…"):
        records = vendor_repository.records_from_df(edited_df, ctx.table)
        vendor_repository.save_records(records, ctx.table, replace=True)
    state.invalidate_vendor_data()
    state.set_flash(f"Saved {len(records)} vendor{'s' if len(records) != 1 else ''} to the list '{ctx.table}'.")
    st.rerun()
