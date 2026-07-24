import time
import unittest

from app.security import jwt_hs256
from app.security.auth import hash_password, verify_password
from app.security.rate_limit import RateLimiter
from app.security.rbac import has_permission
from app.security.uploads import UploadValidationError, validate_upload

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class TestJWT(unittest.TestCase):
    SECRET = "unit-test-secret-key-0123456789abcdef"

    def test_roundtrip(self):
        token = jwt_hs256.encode({"sub": "u1", "tenant_id": "t1"}, self.SECRET)
        claims = jwt_hs256.decode(token, self.SECRET)
        self.assertEqual(claims["sub"], "u1")
        self.assertEqual(claims["tenant_id"], "t1")

    def test_tampered_token_rejected(self):
        token = jwt_hs256.encode({"sub": "u1"}, self.SECRET)
        header, payload, sig = token.split(".")
        tampered = ".".join([header, payload[:-2] + "xx", sig])
        with self.assertRaises(jwt_hs256.JWTError):
            jwt_hs256.decode(tampered, self.SECRET)

    def test_wrong_secret_rejected(self):
        token = jwt_hs256.encode({"sub": "u1"}, self.SECRET)
        with self.assertRaises(jwt_hs256.JWTError):
            jwt_hs256.decode(token, "another-secret")

    def test_expired_token_rejected(self):
        token = jwt_hs256.encode({"sub": "u1", "exp": int(time.time()) - 10}, self.SECRET)
        with self.assertRaises(jwt_hs256.JWTError):
            jwt_hs256.decode(token, self.SECRET)


class TestPasswords(unittest.TestCase):
    def test_hash_and_verify(self):
        stored = hash_password("s3cret-pass")
        self.assertTrue(verify_password("s3cret-pass", stored))
        self.assertFalse(verify_password("wrong", stored))
        self.assertNotIn("s3cret-pass", stored)


class TestRBAC(unittest.TestCase):
    def test_admin_has_governance_export(self):
        self.assertTrue(has_permission(["admin"], "governance:export"))

    def test_viewer_cannot_assess(self):
        self.assertFalse(has_permission(["viewer"], "assess:run"))

    def test_engineer_cannot_export_rules(self):
        self.assertFalse(has_permission(["engineer"], "governance:export"))


class TestUploadValidation(unittest.TestCase):
    def test_valid_pdf_accepted(self):
        meta = validate_upload("plan.pdf", PDF_BYTES)
        self.assertEqual(meta["extension"], ".pdf")
        self.assertNotEqual(meta["storage_name"], "plan.pdf")

    def test_valid_png_accepted(self):
        meta = validate_upload("site.png", PNG_BYTES)
        self.assertEqual(meta["extension"], ".png")

    def test_path_traversal_rejected(self):
        for name in ("../../etc/passwd.pdf", "..\\evil.pdf", "a/b.pdf", "a\\b.pdf"):
            with self.assertRaises(UploadValidationError, msg=name):
                validate_upload(name, PDF_BYTES)

    def test_dangerous_filenames_rejected(self):
        for name in ("con.pdf", ".hidden.pdf", "file\x00name.pdf", "trailing..", "x" * 300 + ".pdf"):
            with self.assertRaises(UploadValidationError, msg=repr(name)):
                validate_upload(name, PDF_BYTES)

    def test_disallowed_extension_rejected(self):
        with self.assertRaises(UploadValidationError):
            validate_upload("malware.exe", b"MZ\x90\x00")

    def test_magic_byte_mismatch_rejected(self):
        with self.assertRaises(UploadValidationError):
            validate_upload("fake.pdf", b"MZ\x90\x00 this is not a pdf")

    def test_empty_file_rejected(self):
        with self.assertRaises(UploadValidationError):
            validate_upload("empty.pdf", b"")

    def test_oversize_rejected(self):
        from app.config import settings

        oversized = b"%PDF-" + b"0" * (settings.max_upload_mb * 1024 * 1024 + 1)
        with self.assertRaises(UploadValidationError):
            validate_upload("big.pdf", oversized)


class TestRateLimiter(unittest.TestCase):
    def test_limit_enforced(self):
        limiter = RateLimiter(limit_per_minute=3)
        results = [limiter.allow("client-a") for _ in range(5)]
        self.assertEqual(results, [True, True, True, False, False])

    def test_keys_isolated(self):
        limiter = RateLimiter(limit_per_minute=1)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_zero_limit_disables(self):
        limiter = RateLimiter(limit_per_minute=0)
        self.assertTrue(all(limiter.allow("x") for _ in range(100)))


if __name__ == "__main__":
    unittest.main()
