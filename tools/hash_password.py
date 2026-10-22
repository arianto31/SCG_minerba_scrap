"""Buat entri AUTH_USERS untuk file .env.

Jalankan dari folder proyek:
    python -m tools.hash_password          # password tersembunyi
    python -m tools.hash_password --show   # password terlihat saat diketik
"""
import getpass
import sys

from core.auth import MIN_PASSWORD_LENGTH, hash_password


def _ask(prompt: str, show: bool) -> str:
    return input(prompt) if show else getpass.getpass(prompt)


def main() -> int:
    show = "--show" in sys.argv
    username = input("Username: ").strip().lower()
    if not username or ":" in username or ";" in username:
        print("Username tidak boleh kosong dan tidak boleh berisi ':' atau ';'.")
        return 1

    password = _ask("Password: ", show)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password minimal {MIN_PASSWORD_LENGTH} karakter (terbaca {len(password)}).")
        return 1
    confirm = _ask("Ulangi password: ", show)
    if password != confirm:
        print(f"Password tidak sama (terbaca {len(password)} dan {len(confirm)} karakter).")
        return 1

    print("\nTambahkan ke file .env (beberapa pengguna dipisah titik koma, pakai tanda kutip tunggal):\n")
    print(f"AUTH_USERS='{username}:{hash_password(password)}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())