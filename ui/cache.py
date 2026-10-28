"""Streamlit caching for data that is expensive to fetch."""
import logging

import pandas as pd
import streamlit as st

from repositories import minerba_repository


@st.cache_data(show_spinner=False)
def cached_minerba_data() -> pd.DataFrame:
    return minerba_repository.fetch_minerba_data()


def load_minerba_data() -> pd.DataFrame:
    """Cached ESDM data, with a loading indicator and a friendly message (instead of a crash) on failure."""
    try:
        with st.spinner("Loading the MinerbaOne database…"):
            return cached_minerba_data()
    except Exception as exc:  # noqa: BLE001 - show a readable message; details stay in the log
        logging.exception("Loading the Minerba data failed")
        st.error(
            "We couldn't load data from the database. Check your internet connection and the Supabase "
            "settings in `.env`, then reload the page.",
            icon=":material/cloud_off:",
        )
        with st.expander("Technical details"):
            st.code(str(exc))
        st.stop()
