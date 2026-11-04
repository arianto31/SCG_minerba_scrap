"""Sign-in page: the whole app stays hidden until the username and password are correct."""
import functools
import math
import time
from typing import Optional

import streamlit as st

import config
from core.auth import AuthConfigError, LoginThrottle, hash_password, parse_users, verify_password
from ui import appearance, state, theme

_THROTTLE = LoginThrottle()   # shared by every session in the same server process

MSG_WRONG_CREDENTIALS = "Incorrect username or password."
MSG_MISSING_FIELDS = "Enter your username and password."

_USER_KEY = "login_username"
_PASS_KEY = "login_password"

# Shows the "Signing you in…" screen the moment Sign in is pressed (or Enter in a field), before the server
# answers, so the form never sits there half-faded. Every fresh render of the form removes it again (wrong
# password -> the form is back with the message). The run number makes the script run on every render.
_SIGNING_IN_JS = """
<script>/* run %(run)s */
(function () {
  document.body.classList.remove('q-signing-in');
  if (window.__qLoginHook) return;
  window.__qLoginHook = true;
  var start = function () { document.body.classList.add('q-signing-in'); };
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('.st-key-login_submit button')) start();
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.closest && e.target.closest('.st-key-q_login input')) start();
  }, true);
})();
</script>
"""


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
    """Clear all session data (including any vendor data that was loaded). The light/dark choice is kept."""
    mode = st.session_state.get(state.KEY_THEME_MODE)
    st.session_state.clear()
    if mode:
        st.session_state[state.KEY_THEME_MODE] = mode


# ------------------------------------------------------------------ internal
def _render_form(users: dict) -> None:
    with st.container(key="q_login_theme"):
        appearance.icon_toggle("login_theme_toggle")

    _, middle, _ = st.columns([1, 1.1, 1])
    with middle, st.container(key="q_login"):
        theme.login_hero()
        with st.form("login_form"):
            st.text_input("Username", key=_USER_KEY, placeholder="Enter your username", autocomplete="username")
            st.text_input("Password", key=_PASS_KEY, type="password", placeholder="Enter your password",
                          autocomplete="current-password")
            st.form_submit_button("Sign in", type="primary", icon=":material/login:", width="stretch",
                                  key="login_submit", on_click=_on_submit, args=(users,))
        error = st.session_state.pop(state.KEY_LOGIN_ERROR, None)
        if error:
            st.error(error, icon=":material/error:")
        theme.login_footer()

    st.html(theme.splash_html("Signing you in…", "Checking your account", "is-login")
            + _SIGNING_IN_JS % {"run": time.time_ns()}, unsafe_allow_javascript=True)


def _on_submit(users: dict) -> None:
    """Sign-in button callback. Runs before the page is drawn, so on success the form is never shown again."""
    error = _attempt_login(users, st.session_state.get(_USER_KEY, ""), st.session_state.get(_PASS_KEY, ""))
    if error:
        st.session_state[state.KEY_LOGIN_ERROR] = error
        st.session_state[_PASS_KEY] = ""      # clear the password field for the next try


def _attempt_login(users: dict, username: str, password: str) -> Optional[str]:
    """Check the credentials. Success: mark the session signed in and return None. Failure: the message to show."""
    key = (username or "").strip().lower()
    if not key or not password:
        return MSG_MISSING_FIELDS

    locked_for = _THROTTLE.remaining_lock(key)
    if locked_for > 0:
        return f"Too many failed attempts. Please try again in {math.ceil(locked_for)} seconds."

    # Always compute a hash (even for unknown usernames) so response time is identical; same message too.
    password_ok = verify_password(password, users.get(key) or _dummy_hash())
    if password_ok and key in users:
        _THROTTLE.record_success(key)
        st.session_state[state.KEY_AUTH_USER] = key
        st.session_state[state.KEY_JUST_SIGNED_IN] = True
        st.session_state.pop(_PASS_KEY, None)
        return None

    _THROTTLE.record_failure(key)
    return MSG_WRONG_CREDENTIALS
