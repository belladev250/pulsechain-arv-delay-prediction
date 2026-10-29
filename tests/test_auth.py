"""Unit tests for passwords, signed tokens, role scoping and the login rate limiter (standard library only)."""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import auth  # noqa: E402


class PasswordTests(unittest.TestCase):
    def test_hash_is_not_the_password_and_verifies(self):
        digest, salt = auth.hash_password("Correct#2026")
        self.assertNotIn("Correct", digest)
        self.assertTrue(auth.verify_password("Correct#2026", digest, salt))

    def test_wrong_password_is_rejected(self):
        digest, salt = auth.hash_password("Correct#2026")
        self.assertFalse(auth.verify_password("correct#2026", digest, salt))

    def test_same_password_gets_a_different_salt_and_hash(self):
        first, second = auth.hash_password("Same#2026"), auth.hash_password("Same#2026")
        self.assertNotEqual(first[1], second[1])
        self.assertNotEqual(first[0], second[0])


class TokenTests(unittest.TestCase):
    SECRET = b"unit-test-secret"

    def test_valid_token_returns_user_id(self):
        self.assertEqual(auth.read_token(auth.make_token(7, self.SECRET), self.SECRET), 7)

    def test_edited_token_is_rejected(self):
        payload, signature = auth.make_token(7, self.SECRET).split(".")
        forged = auth.make_token(1, self.SECRET).split(".")[0] + "." + signature
        self.assertIsNone(auth.read_token(forged, self.SECRET))
        self.assertIsNone(auth.read_token(payload + ".bad", self.SECRET))

    def test_token_signed_with_another_secret_is_rejected(self):
        self.assertIsNone(auth.read_token(auth.make_token(7, b"other"), self.SECRET))

    def test_expired_token_is_rejected(self):
        self.assertIsNone(auth.read_token(auth.make_token(7, self.SECRET, hours=-1), self.SECRET))

    def test_garbage_is_rejected(self):
        for bad in ("", "abc", "a.b.c", None):
            self.assertIsNone(auth.read_token(bad, self.SECRET))


class ScopeTests(unittest.TestCase):
    ADMIN = {"role": "admin", "country": None, "district": None}
    MANAGER = {"role": "country", "country": "Rwanda", "district": None}
    OFFICER = {"role": "district", "country": "Rwanda", "district": "Gasabo"}

    def test_admin_sees_everything(self):
        self.assertTrue(auth.in_scope(self.ADMIN, "Uganda", "Kampala"))

    def test_country_manager_sees_own_country_only(self):
        self.assertTrue(auth.in_scope(self.MANAGER, "Rwanda", "Huye"))
        self.assertFalse(auth.in_scope(self.MANAGER, "Uganda", "Kampala"))

    def test_district_officer_sees_own_district_only(self):
        self.assertTrue(auth.in_scope(self.OFFICER, "Rwanda", "Gasabo"))
        self.assertFalse(auth.in_scope(self.OFFICER, "Rwanda", "Huye"))
        self.assertFalse(auth.in_scope(self.OFFICER, "Uganda", "Gasabo"))

    def test_matching_ignores_case_and_spaces(self):
        self.assertTrue(auth.in_scope(self.OFFICER, " rwanda ", "GASABO"))

    def test_sql_fragment_matches_the_role(self):
        self.assertEqual(auth.scope_sql(self.ADMIN), ("1=1", []))
        self.assertEqual(auth.scope_sql(self.MANAGER)[1], ["Rwanda"])
        self.assertEqual(auth.scope_sql(self.OFFICER)[1], ["Rwanda", "Gasabo"])


class LoginLimiterTests(unittest.TestCase):
    def test_blocks_after_five_failures_and_resets(self):
        limiter = auth.LoginLimiter(attempts=5, window=60)
        for _ in range(4):
            limiter.fail("a@x.org")
        self.assertFalse(limiter.blocked("a@x.org"))
        limiter.fail("a@x.org")
        self.assertTrue(limiter.blocked("a@x.org"))
        self.assertFalse(limiter.blocked("b@x.org"))
        limiter.reset("a@x.org")
        self.assertFalse(limiter.blocked("a@x.org"))

    def test_block_expires_after_the_window(self):
        limiter = auth.LoginLimiter(attempts=2, window=0.05)
        limiter.fail("a@x.org")
        limiter.fail("a@x.org")
        self.assertTrue(limiter.blocked("a@x.org"))
        time.sleep(0.08)
        self.assertFalse(limiter.blocked("a@x.org"))


if __name__ == "__main__":
    unittest.main()
