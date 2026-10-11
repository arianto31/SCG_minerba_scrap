"""Pilih tabel vendor aktif atau buat tabel vendor baru (mis. Vendor Pasir, Vendor Batu)."""
import streamlit as st

from repositories import vendor_repository
from ui import state


def render() -> str:
    """Tampilkan pemilih tabel dan kembalikan nama tabel aktif."""
    if state.KEY_TABLE_NAMES not in st.session_state:
        st.session_state[state.KEY_TABLE_NAMES] = vendor_repository.list_table_names()
    names = st.session_state[state.KEY_TABLE_NAMES]
    if st.session_state.get(state.KEY_ACTIVE_TABLE) not in names:
        st.session_state[state.KEY_ACTIVE_TABLE] = names[0]

    select_col, create_col = st.columns([2, 3])
    with select_col:
        active = st.selectbox("📁 Tabel vendor", names, key=state.KEY_ACTIVE_TABLE)
    with create_col:
        with st.expander("➕ Buat tabel vendor baru"):
            st.text_input("Nama tabel (contoh: Vendor Pasir, Vendor Batu)", key=state.KEY_NEW_TABLE_NAME)
            st.button("Buat tabel", on_click=_create_table)
    return active


def _create_table() -> None:
    """Callback tombol 'Buat tabel' (berjalan sebelum rerun, jadi boleh mengubah state widget)."""
    name = st.session_state.get(state.KEY_NEW_TABLE_NAME, "").strip()
    names = st.session_state[state.KEY_TABLE_NAMES]

    if not name:
        st.toast("Nama tabel tidak boleh kosong.", icon="⚠️")
        return
    existing = next((n for n in names if n.lower() == name.lower()), None)
    if existing:
        st.session_state[state.KEY_ACTIVE_TABLE] = existing
        st.toast(f"Tabel '{existing}' sudah ada, dipilih.", icon="ℹ️")
        return

    vendor_repository.register_table(name)
    names.append(name)
    st.session_state[state.KEY_ACTIVE_TABLE] = name
    st.session_state[state.KEY_NEW_TABLE_NAME] = ""
    st.toast(f"Tabel '{name}' dibuat.", icon="✅")
