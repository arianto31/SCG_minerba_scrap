import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.auth import (
    AuthConfigError, LoginThrottle, hash_password, parse_users, verify_password,
)
from ui import login, state


class StopApp(Exception):
    pass


class RerunApp(Exception):
    pass


FAST = 1000  # iterasi kecil agar tes cepat


class PasswordTest(unittest.TestCase):
    def test_round_trip_and_wrong_password(self):
        stored = hash_password("rahasia-123", iterations=FAST)
        self.assertTrue(stored.startswith("pbkdf2_sha256$1000$"))
        self.assertTrue(verify_password("rahasia-123", stored))
        self.assertFalse(verify_password("rahasia-124", stored))
        self.assertFalse(verify_password("", stored))

    def test_salt_is_random(self):
        self.assertNotEqual(hash_password("sama", iterations=FAST), hash_password("sama", iterations=FAST))

    def test_malformed_hash_never_matches(self):
        for stored in ("", "plain", "md5$1$aa$bb", "pbkdf2_sha256$x$aa$bb", "pbkdf2_sha256$1000$zz$bb",
                       "pbkdf2_sha256$1000$aa"):
            self.assertFalse(verify_password("apa saja", stored), stored)


class ParseUsersTest(unittest.TestCase):
    def setUp(self):
        self.h1, self.h2 = hash_password("satu-satu-1", iterations=FAST), hash_password("dua-dua-22", iterations=FAST)

    def test_parses_multiple_users_lowercased(self):
        users = parse_users(f" Admin:{self.h1} ; budi:{self.h2} ;")
        self.assertEqual(set(users), {"admin", "budi"})
        self.assertTrue(verify_password("dua-dua-22", users["budi"]))

    def test_rejects_bad_config_without_leaking_hash(self):
        for raw in ("", "   ", "admin", f"admin{self.h1}", f":{self.h1}", "admin:plaintext-password"):
            with self.assertRaises(AuthConfigError):
                parse_users(raw)
        with self.assertRaises(AuthConfigError) as ctx:
            parse_users(f"a:{self.h1};A:{self.h2}")
        self.assertNotIn(self.h1, str(ctx.exception))
        with self.assertRaises(AuthConfigError) as ctx:
            parse_users("admin:rahasia-asli")
        self.assertNotIn("rahasia-asli", str(ctx.exception))


class ThrottleTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.throttle = LoginThrottle(max_attempts=3, lock_seconds=60, window_seconds=120, clock=lambda: self.now)

    def test_locks_after_max_failures_then_expires(self):
        for _ in range(3):
            self.assertEqual(self.throttle.remaining_lock("a"), 0)
            self.throttle.record_failure("a")
        self.assertEqual(self.throttle.remaining_lock("a"), 60)
        self.assertEqual(self.throttle.remaining_lock("b"), 0)   # username lain tidak ikut terkunci
        self.now = 61
        self.assertEqual(self.throttle.remaining_lock("a"), 0)

    def test_success_resets_counter(self):
        self.throttle.record_failure("a"); self.throttle.record_failure("a")
        self.throttle.record_success("a")
        self.throttle.record_failure("a"); self.throttle.record_failure("a")
        self.assertEqual(self.throttle.remaining_lock("a"), 0)

    def test_old_failures_expire(self):
        self.throttle.record_failure("a"); self.throttle.record_failure("a")
        self.now = 500   # di luar jendela
        self.throttle.record_failure("a")
        self.assertEqual(self.throttle.remaining_lock("a"), 0)


class LoginFlowTest(unittest.TestCase):
    def setUp(self):
        self.users_raw = f"admin:{hash_password('benar-benar-1', iterations=FAST)}"
        self.errors = []

        def stop():
            raise StopApp

        def rerun():
            raise RerunApp

        self.fake_st = SimpleNamespace(
            session_state={}, error=self.errors.append, stop=stop, rerun=rerun,
            markdown=lambda *a, **k: None,
        )
        self.patches = [
            patch.object(login, "st", self.fake_st),
            patch.object(login.config, "AUTH_USERS", self.users_raw),
            patch.object(login, "_THROTTLE", LoginThrottle()),
            patch.object(login, "_render_form", lambda users: None),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.users = parse_users(self.users_raw)

    def test_correct_login_sets_session_and_reruns(self):
        with self.assertRaises(RerunApp):
            login._attempt_login(self.users, "  ADMIN ", "benar-benar-1")
        self.assertEqual(self.fake_st.session_state[state.KEY_AUTH_USER], "admin")

    def test_wrong_password_and_unknown_user_share_same_message(self):
        login._attempt_login(self.users, "admin", "salah")
        login._attempt_login(self.users, "tidak-ada", "benar-benar-1")
        self.assertEqual(self.errors, ["Username atau password salah."] * 2)
        self.assertNotIn(state.KEY_AUTH_USER, self.fake_st.session_state)

    def test_lockout_blocks_even_correct_password(self):
        for _ in range(5):
            login._attempt_login(self.users, "admin", "salah")
        login._attempt_login(self.users, "admin", "benar-benar-1")      # benar, tapi sedang terkunci
        self.assertIn("Terlalu banyak percobaan", self.errors[-1])
        self.assertNotIn(state.KEY_AUTH_USER, self.fake_st.session_state)

    def test_require_login_blocks_app_until_authenticated(self):
        with self.assertRaises(StopApp):
            login.require_login()
        self.fake_st.session_state[state.KEY_AUTH_USER] = "admin"
        self.assertEqual(login.require_login(), "admin")

    def test_fails_closed_without_configuration(self):
        with patch.object(login.config, "AUTH_USERS", ""):
            with self.assertRaises(StopApp):
                login.require_login()
        self.assertIn("Login belum dikonfigurasi", self.errors[-1])

    def test_logout_clears_all_session_data(self):
        self.fake_st.session_state.update({state.KEY_AUTH_USER: "admin", "vendor_df": object()})
        login.logout()
        self.assertEqual(self.fake_st.session_state, {})


if __name__ == "__main__":
    unittest.main()
