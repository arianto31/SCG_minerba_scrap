"""Titik masuk aplikasi: jalankan dengan `streamlit run app.py`."""
import streamlit as st

from ui import login, minerba_tab, vendor_tab
from ui.cache import cached_minerba_data


def main() -> None:
    st.set_page_config(page_title="Procurement Matcher", page_icon="🏢", layout="wide")
    user = login.require_login()  # berhenti di sini sampai login berhasil; belum ada data yang diambil

    title_col, user_col = st.columns([5, 1])
    title_col.title("🏢 QUICK Andesit")
    title_col.caption("Quarry Information Checklist")
    with user_col:
        login.render_user_bar(user)

    vendor, minerba = st.tabs(["📋 Vendor (Procurement)", "🌐 Minerba Website (ESDM)"])
    df_minerba = cached_minerba_data()

    with minerba:
        minerba_tab.render(df_minerba)
    with vendor:
        vendor_tab.render(df_minerba)


main()
