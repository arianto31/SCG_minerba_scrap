"""Autentikasi sederhana: hash password (PBKDF2), daftar pengguna dari konfigurasi, dan pembatas percobaan login."""
import hashlib
import hmac
import secrets
import time
from typing import Callable, Dict, Optional

ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000   # rekomendasi OWASP untuk PBKDF2-HMAC-SHA256
MIN_PASSWORD_LENGTH = 8


class AuthConfigError(ValueError):
    """Konfigurasi pengguna (AUTH_USERS) tidak valid."""


# ------------------------------------------------------------------ password
def hash_password(password: str, iterations: int = DEFAULT_ITERATIONS, salt: Optional[bytes] = None) -> str:
    """Hasil: 'pbkdf2_sha256$<iterasi>$<salt hex>$<hash hex>' (salt acak per password)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Cocokkan password dengan hash tersimpan (perbandingan waktu-konstan). Hash rusak -> False."""
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(actual, expected)


# ------------------------------------------------------------------ daftar pengguna
def parse_users(raw: str) -> Dict[str, str]:
    """
    'user1:hash1;user2:hash2' -> {'user1': 'hash1', 'user2': 'hash2'} (username huruf kecil).
    Melempar AuthConfigError jika kosong/format salah/username ganda. Pesan error tidak memuat hash.
    """
    users: Dict[str, str] = {}
    entries = [e.strip() for e in (raw or "").split(";") if e.strip()]
    for number, entry in enumerate(entries, start=1):
        username, separator, stored = entry.partition(":")
        username = username.strip().lower()
        if not separator or not username or not stored.startswith(ALGORITHM + "$") or stored.count("$") != 3:
            raise AuthConfigError(f"Entri pengguna ke-{number} tidak valid. Format: username:hash")
        if username in users:
            raise AuthConfigError(f"Username ganda: '{username}'")
        users[username] = stored
    if not users:
        raise AuthConfigError("AUTH_USERS belum diatur.")
    return users


# ------------------------------------------------------------------ anti tebak-tebakan
class LoginThrottle:
    """Kunci sementara sebuah username setelah terlalu banyak percobaan gagal."""

    def __init__(self, max_attempts: int = 5, lock_seconds: float = 300, window_seconds: float = 900,
                 clock: Callable[[], float] = time.monotonic):
        self.max_attempts, self.lock_seconds, self.window_seconds, self._clock = (
            max_attempts, lock_seconds, window_seconds, clock)
        self._state: Dict[str, dict] = {}   # key -> {"count", "last", "locked_until"}

    def remaining_lock(self, key: str) -> float:
        """Sisa detik terkunci (0 jika tidak terkunci)."""
        entry = self._state.get(key)
        return max(0.0, entry["locked_until"] - self._clock()) if entry else 0.0

    def record_failure(self, key: str) -> None:
        now = self._clock()
        self._prune(now)
        entry = self._state.setdefault(key, {"count": 0, "last": now, "locked_until": 0.0})
        if now - entry["last"] > self.window_seconds:
            entry["count"] = 0
        entry["count"] += 1
        entry["last"] = now
        if entry["count"] >= self.max_attempts:
            entry["locked_until"] = now + self.lock_seconds
            entry["count"] = 0

    def record_success(self, key: str) -> None:
        self._state.pop(key, None)

    def _prune(self, now: float) -> None:
        """Buang catatan lama agar memori tidak membengkak oleh username acak."""
        if len(self._state) < 1000:
            return
        stale = [k for k, e in self._state.items()
                 if e["locked_until"] < now and now - e["last"] > self.window_seconds]
        for key in stale:
            del self._state[key]
