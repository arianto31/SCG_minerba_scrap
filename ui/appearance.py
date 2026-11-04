"""
Light / dark mode, chosen per user.

Streamlit only has one app-wide theme (`.streamlit/config.toml`). To let every user pick their own,
we adjust the theme Streamlit sends to that user's browser at the start of each run. Native widgets
(tables, inputs, dialogs) and our own CSS (ui/theme.py) then switch together.
The choice is kept in a cookie so it survives a page reload.
"""
import logging

import streamlit as st

from ui import state

LIGHT = "light"
DARK = "dark"
DEFAULT_MODE = DARK
MODES = (LIGHT, DARK)

_COOKIE = "q_theme"
_WIDGET_KEY = "theme_mode_picker"
_CHANGED_KEY = "_theme_mode_changed"
_LOGGER = logging.getLogger(__name__)

# Streamlit theme colors per mode. Dark matches the [theme] section of .streamlit/config.toml
# (used as the fallback); fonts and corner radius always come from config.toml.
PALETTES = {
    DARK: {
        "base": DARK,
        "primary_color": "#6366F1",
        "background_color": "#080B14",
        "secondary_background_color": "#121A2C",
        "text_color": "#E6E9F2",
        "link_color": "#A5B4FC",
        "border_color": "#222B42",
        "sidebar": {"background_color": "#0A0F1D", "secondary_background_color": "#131B2E",
                    "border_color": "#1C2438"},
    },
    LIGHT: {
        "base": LIGHT,
        "primary_color": "#4F46E5",
        "background_color": "#F4F6FB",
        "secondary_background_color": "#E9EDF5",
        "text_color": "#0F172A",
        "link_color": "#4338CA",
        "border_color": "#D5DBE7",
        "sidebar": {"background_color": "#FFFFFF", "secondary_background_color": "#F1F4F9",
                    "border_color": "#E2E7F0"},
    },
}

_patch_ok = False


# ------------------------------------------------------------------ public
def current() -> str:
    mode = st.session_state.get(state.KEY_THEME_MODE)
    return mode if mode in MODES else DEFAULT_MODE


def init() -> None:
    """Call once per run, before anything is drawn. Restores the saved choice on a fresh session."""
    install()
    if state.KEY_THEME_MODE in st.session_state:
        return
    saved = _saved_mode()
    st.session_state[state.KEY_THEME_MODE] = saved
    if saved != DEFAULT_MODE and _patch_ok:
        st.rerun()   # this run already started with the default theme; restart with the saved one


def available() -> bool:
    """False when this Streamlit version could not be adjusted (the switch is then hidden)."""
    return _patch_ok


def sidebar_picker() -> None:
    """Light / Dark switch for the sidebar."""
    if not _patch_ok:
        return
    st.session_state.setdefault(_WIDGET_KEY, current())
    st.segmented_control(
        "Appearance", options=list(MODES), key=_WIDGET_KEY, on_change=_on_pick,
        format_func=lambda m: ":material/light_mode: Light" if m == LIGHT else ":material/dark_mode: Dark",
        label_visibility="collapsed", width="stretch",
    )
    _apply_change()


def icon_toggle(key: str) -> None:
    """Single icon button (login page): switches to the other mode."""
    if not _patch_ok:
        return
    to_light = current() == DARK
    if st.button("", key=key, icon=":material/light_mode:" if to_light else ":material/dark_mode:",
                 help="Switch to light mode" if to_light else "Switch to dark mode", type="tertiary"):
        _set(LIGHT if to_light else DARK)
        st.rerun()


def remember() -> None:
    """Store the current choice in a cookie (an invisible element; only re-sent when the choice changes)."""
    mode = current()
    with st.container(key="q_theme_store"):
        st.html(
            f"<script>document.cookie='{_COOKIE}={mode}; path=/; max-age=31536000; SameSite=Lax';</script>",
            unsafe_allow_javascript=True,
        )


# ------------------------------------------------------------------ internal
def _saved_mode() -> str:
    try:
        value = st.context.cookies.get(_COOKIE)
    except Exception:   # no browser context (tests, bare mode)
        value = None
    return value if value in MODES else DEFAULT_MODE


def _set(mode: str) -> None:
    st.session_state[state.KEY_THEME_MODE] = mode
    st.session_state[_WIDGET_KEY] = mode


def _on_pick() -> None:
    picked = st.session_state.get(_WIDGET_KEY)
    if picked not in MODES:          # clicking the selected option again clears it: keep the current mode
        st.session_state[_WIDGET_KEY] = current()
        return
    if picked != current():
        st.session_state[state.KEY_THEME_MODE] = picked
        st.session_state[_CHANGED_KEY] = True


def _apply_change() -> None:
    # The theme for a run is sent before callbacks run, so restart once to send the new one.
    if st.session_state.pop(_CHANGED_KEY, False):
        st.rerun()


def _fill(theme_msg, colors: dict) -> None:
    for name, value in colors.items():
        if name == "sidebar":
            _fill(theme_msg.sidebar, value)
        elif name == "base":
            theme_msg.base = theme_msg.BaseTheme.LIGHT if value == LIGHT else theme_msg.BaseTheme.DARK
        else:
            setattr(theme_msg, name, value)


def install() -> bool:
    """Wrap Streamlit's 'new session' message so each user gets the theme of their own choice (once)."""
    global _patch_ok
    if _patch_ok:
        return True
    try:
        from streamlit.runtime.app_session import AppSession

        original = AppSession._create_new_session_message
        if not getattr(original, "_q_theme", False):
            def create_new_session_message(self, *args, **kwargs):
                msg = original(self, *args, **kwargs)
                try:
                    session_state = self._session_state
                    mode = session_state[state.KEY_THEME_MODE] if state.KEY_THEME_MODE in session_state else None
                    theme_msg = msg.new_session.custom_theme
                    theme_msg.ClearField("light")    # one fixed theme per user, not the browser's own choice
                    theme_msg.ClearField("dark")
                    _fill(theme_msg, PALETTES.get(mode, PALETTES[DEFAULT_MODE]))
                except Exception:   # never break the app over colors
                    _LOGGER.exception("Could not apply the light/dark theme")
                return msg

            create_new_session_message._q_theme = True
            AppSession._create_new_session_message = create_new_session_message
        _patch_ok = True
    except Exception:
        _LOGGER.warning("Light/dark switch unavailable in this Streamlit version", exc_info=True)
        _patch_ok = False
    return _patch_ok
