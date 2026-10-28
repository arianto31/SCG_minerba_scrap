"""Sign-in page: the whole app stays hidden until the username and password are correct."""
import functools
import math

import streamlit as st

import config
from core.auth import AuthConfigError, LoginThrottle, hash_password, parse_users, verify_password
from ui import state, theme

_THROTTLE = LoginThrottle()   # shared by every session in the same server process

MSG_WRONG_CREDENTIALS = "Incorrect username or password."


@functools.lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Fake hash so unknown usernames take the same time (they cannot be guessed from response speed)."""
    return hash_password("not-used")


def require_login() -> str:
    """
    Call at the top of the app. Not signed in: show the form and STOP the script (no data touched yet).
    Signed in: return the username. Fails closed: without a user configuration the app cannot be opened.
    """
    user = st.session_state.get(state.KEY_AUTH_USER)
    if user:
        return user

    try:
        users = parse_users(config.AUTH_USERS)
    except AuthConfigError as exc:
        st.error(f"Sign-in is not configured yet: {exc}")
        st.markdown(
            "Create a user with `python -m tools.hash_password`, put the result in `AUTH_USERS` in the "
            "`.env` file, and restart the app."
        )
        st.stop()

    _render_form(users)
    st.stop()


def render_user_bar(user: str) -> None:
    """User card + sign-out button (placed at the bottom of the sidebar)."""
    theme.user_card(user)
    st.button("Sign out", on_click=logout, key="logout_button", icon=":material/logout:", width="stretch")


def logout() -> None:
    """Clear all session data (including any vendor data that was loaded)."""
    st.session_state.clear()


# ------------------------------------------------------------------ internal
def _render_form(users: dict) -> None:
    _, middle, _ = st.columns([1, 1.1, 1])
    with middle:
        theme.login_hero()
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username", autocomplete="username")
            password = st.text_input("Password", type="password", placeholder="Enter your password",
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", icon=":material/login:",
                                              width="stretch")
        if submitted:
            _attempt_login(users, username, password)
        theme.login_footer()


def _attempt_login(users: dict, username: str, password: str) -> None:
    key = username.strip().lower()

    locked_for = _THROTTLE.remaining_lock(key)
    if locked_for > 0:
        st.error(f"Too many failed attempts. Please try again in {math.ceil(locked_for)} seconds.")
        return

    # Always compute a hash (even for unknown usernames) so response time is identical; same message too.
    password_ok = verify_password(password, users.get(key) or _dummy_hash())
    if password_ok and key in users:
        _THROTTLE.record_success(key)
        st.session_state[state.KEY_AUTH_USER] = key
        st.rerun()

    _THROTTLE.record_failure(key)
    st.error(MSG_WRONG_CREDENTIALS)
