"""Pick the active vendor list, or create a new one (e.g. Vendor Pasir, Vendor Batu)."""
import streamlit as st

from repositories import vendor_repository
from ui import state


def render(select_col, create_col) -> str:
    """Show the list picker (in `select_col`) and the "New list" button (in `create_col`). Returns the active list."""
    if state.KEY_TABLE_NAMES not in st.session_state:
        st.session_state[state.KEY_TABLE_NAMES] = vendor_repository.list_table_names()
    names = st.session_state[state.KEY_TABLE_NAMES]
    if st.session_state.get(state.KEY_ACTIVE_TABLE) not in names:
        st.session_state[state.KEY_ACTIVE_TABLE] = names[0]

    with select_col:
        active = st.selectbox(
            "Vendor list", names, key=state.KEY_ACTIVE_TABLE,
            help="Each list keeps its own vendors, for example one list per material (Pasir, Batu…).",
        )
    with create_col:
        with st.popover("New list", icon=":material/add:", width="stretch"):
            st.markdown("**Create a vendor list**")
            st.text_input("List name", key=state.KEY_NEW_TABLE_NAME, placeholder="e.g. Vendor Pasir")
            st.button("Create list", on_click=_create_table, type="primary", icon=":material/check:",
                      width="stretch")
    return active


def _create_table() -> None:
    """'Create list' callback (runs before the rerun, so it may change widget state)."""
    name = st.session_state.get(state.KEY_NEW_TABLE_NAME, "").strip()
    names = st.session_state[state.KEY_TABLE_NAMES]

    if not name:
        st.toast("Please type a name for the new list.", icon="⚠️")
        return
    existing = next((n for n in names if n.lower() == name.lower()), None)
    if existing:
        st.session_state[state.KEY_ACTIVE_TABLE] = existing
        st.toast(f"The list '{existing}' already exists, so it was opened.", icon="ℹ️")
        return

    vendor_repository.register_table(name)
    names.append(name)
    st.session_state[state.KEY_ACTIVE_TABLE] = name
    st.session_state[state.KEY_NEW_TABLE_NAME] = ""
    st.toast(f"List '{name}' created.", icon="✅")
