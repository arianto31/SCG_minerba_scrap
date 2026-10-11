"""Cache Streamlit untuk data yang mahal diambil."""
import pandas as pd
import streamlit as st

from repositories import minerba_repository


@st.cache_data(show_spinner=False)
def cached_minerba_data() -> pd.DataFrame:
    return minerba_repository.fetch_minerba_data()
