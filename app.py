"""Titik masuk aplikasi: jalankan dengan `streamlit run app.py`."""
import streamlit as st

from ui import minerba_tab, vendor_tab
from ui.cache import cached_minerba_data


def main() -> None:
    st.set_page_config(page_title="Procurement Matcher", page_icon="🏢", layout="wide")
    st.title("🏢 QUICK Andesit")
    st.text("Quarry Information Checklist")

    vendor, minerba = st.tabs(["📋 Vendor (Procurement)", "🌐 Minerba Website (ESDM)"])
    df_minerba = cached_minerba_data()

    with minerba:
        minerba_tab.render(df_minerba)
    with vendor:
        vendor_tab.render(df_minerba)


main()
