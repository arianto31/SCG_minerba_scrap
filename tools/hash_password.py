"""Create an AUTH_USERS entry for the .env file.

Run from the project folder:
    python -m tools.hash_password          # hidden password input
    python -m tools.hash_password --show   # password visible while typing
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
        print("The username must not be empty and must not contain ':' or ';'.")
        return 1

    password = _ask("Password: ", show)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"The password needs at least {MIN_PASSWORD_LENGTH} characters (got {len(password)}).")
        return 1
    confirm = _ask("Repeat password: ", show)
    if password != confirm:
        print(f"The passwords do not match (got {len(password)} and {len(confirm)} characters).")
        return 1

    print("\nAdd this to the .env file (separate several users with semicolons, keep the single quotes):\n")
    print(f"AUTH_USERS='{username}:{hash_password(password)}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
