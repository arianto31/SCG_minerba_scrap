"""Halaman login: seluruh aplikasi disembunyikan sampai username dan password benar."""
import functools
import math

import streamlit as st

import config
from core.auth import AuthConfigError, LoginThrottle, hash_password, parse_users, verify_password
from ui import state

_THROTTLE = LoginThrottle()   # dipakai bersama semua sesi di proses server yang sama


@functools.lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash palsu agar username yang tidak ada tetap memakan waktu sama (tidak bisa ditebak dari kecepatan)."""
    return hash_password("tidak-dipakai")


def require_login() -> str:
    """
    Pasang di awal aplikasi. Jika belum login: tampilkan form dan HENTIKAN skrip (data belum disentuh).
    Jika sudah: kembalikan username. Gagal-tertutup: tanpa konfigurasi pengguna, aplikasi tidak bisa dibuka.
    """
    user = st.session_state.get(state.KEY_AUTH_USER)
    if user:
        return user

    try:
        users = parse_users(config.AUTH_USERS)
    except AuthConfigError as exc:
        st.error(f"Login belum dikonfigurasi: {exc}")
        st.markdown(
            "Buat pengguna dengan `python -m tools.hash_password`, lalu isi `AUTH_USERS` di file `.env` "
            "dan jalankan ulang aplikasi."
        )
        st.stop()

    _render_form(users)
    st.stop()


def render_user_bar(user: str) -> None:
    """Nama pengguna + tombol keluar (letakkan di pojok kanan atas)."""
    st.caption(f"👤 {user}")
    st.button("Keluar", on_click=logout, key="logout_button")


def logout() -> None:
    """Hapus seluruh data sesi (termasuk data vendor yang sempat dimuat)."""
    st.session_state.clear()


# ------------------------------------------------------------------ internal
def _render_form(users: dict) -> None:
    _, middle, _ = st.columns([1, 1, 1])
    with middle:
        st.markdown("### 🔒 Masuk")
        st.caption("Procurement Vendor Checker")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk")
        if submitted:
            _attempt_login(users, username, password)


def _attempt_login(users: dict, username: str, password: str) -> None:
    key = username.strip().lower()

    locked_for = _THROTTLE.remaining_lock(key)
    if locked_for > 0:
        st.error(f"Terlalu banyak percobaan gagal. Coba lagi dalam {math.ceil(locked_for)} detik.")
        return

    # Selalu hitung hash (walau username tidak ada) agar waktu respons sama; pesan error pun sama.
    password_ok = verify_password(password, users.get(key) or _dummy_hash())
    if password_ok and key in users:
        _THROTTLE.record_success(key)
        st.session_state[state.KEY_AUTH_USER] = key
        st.rerun()

    _THROTTLE.record_failure(key)
    st.error("Username atau password salah.")
