"""App entry point: run with `streamlit run app.py`."""
import streamlit as st

from ui import appearance, login, minerba_tab, state, theme, vendor_tab
from ui.cache import load_minerba_data

_GUIDE = [
    "Pick a vendor list (or create one) on the Vendors page.",
    "Add vendors: type them in, import an Excel file, or scan a permit with AI.",
    "Each IUP holder name is checked against MinerbaOne automatically.",
    "Red rows need fixing, amber rows expire soon. Save, then download Excel.",
]


def _vendors_page() -> None:
    vendor_tab.render(load_minerba_data())


def _minerba_page() -> None:
    minerba_tab.render(load_minerba_data())


def _sidebar(pages, user: str) -> None:
    with st.sidebar:
        theme.brand()
        theme.nav_label("Menu")
        for page in pages:
            st.page_link(page, width="stretch")
        st.divider()
        with st.expander("How it works", icon=":material/help:"):
            theme.guide(_GUIDE)
        if appearance.available():
            theme.nav_label("Appearance")
            appearance.sidebar_picker()
        login.render_user_bar(user)


def _welcome_screen(user: str):
    """Right after signing in: cover the page while the first load runs (removed when the page is ready)."""
    if not st.session_state.pop(state.KEY_JUST_SIGNED_IN, False):
        return None
    slot = st.empty()
    slot.html(theme.splash_html(f"Welcome, {user}", "Loading your workspace…"))
    return slot


def main() -> None:
    st.set_page_config(page_title=theme.APP_NAME, page_icon="⛰️", layout="wide",
                       initial_sidebar_state="expanded")
    appearance.init()
    theme.inject(appearance.current())
    appearance.remember()
    user = login.require_login()  # stops here until signed in; no data has been fetched yet
    splash = _welcome_screen(user)

    pages = [
        st.Page(_vendors_page, title="Vendors", icon=":material/storefront:", url_path="vendors", default=True),
        st.Page(_minerba_page, title="MinerbaOne database", icon=":material/travel_explore:", url_path="minerba"),
    ]
    current = st.navigation(pages, position="hidden")
    try:
        _sidebar(pages, user)
        current.run()
    finally:
        if splash is not None:
            splash.empty()


main()
