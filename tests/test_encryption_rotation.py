"""Tests for api/services/encryption.py — Fernet + key rotation."""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["HMAC_SECRET"] = "a-hmac-secret"
os.environ["CREDENTIALS_KEY"] = "key-one"
os.environ["CREDENTIALS_KEY_PREVIOUS"] = ""
os.environ["ENVIRONMENT"] = "production"

from api.config import get_settings
from api.services import encryption


def _reload(env: dict):
    for k, v in env.items():
        os.environ[k] = v
    get_settings.cache_clear()
    importlib.reload(encryption)


class TestEncryptDecryptRoundtrip:
    def setup_method(self):
        _reload({"CREDENTIALS_KEY": "key-one", "CREDENTIALS_KEY_PREVIOUS": ""})

    def test_encrypt_then_decrypt(self):
        ct = encryption.encrypt_secret("hello world")
        assert ct is not None and ct != "hello world"
        assert encryption.decrypt_secret(ct) == "hello world"

    def test_empty_values_passthrough(self):
        assert encryption.encrypt_secret("") == ""
        assert encryption.encrypt_secret(None) is None
        assert encryption.decrypt_secret("") == ""
        assert encryption.decrypt_secret(None) is None

    def test_different_plaintexts_different_ciphertexts(self):
        a = encryption.encrypt_secret("alpha")
        b = encryption.encrypt_secret("beta")
        assert a != b

    def test_fernet_nonce_makes_each_encryption_unique(self):
        a = encryption.encrypt_secret("same")
        b = encryption.encrypt_secret("same")
        assert a != b  # Fernet includes a timestamp + random IV


class TestKeyRotation:
    def test_previous_key_decrypts_old_ciphertext(self):
        _reload({"CREDENTIALS_KEY": "old-key", "CREDENTIALS_KEY_PREVIOUS": ""})
        ct_old = encryption.encrypt_secret("payload")
        assert encryption.decrypt_secret(ct_old) == "payload"

        # Rotate: new key primary, old key as previous.
        _reload({"CREDENTIALS_KEY": "new-key", "CREDENTIALS_KEY_PREVIOUS": "old-key"})
        # Old ciphertext still decrypts.
        assert encryption.decrypt_secret(ct_old) == "payload"
        # New ciphertext also works.
        ct_new = encryption.encrypt_secret("payload")
        assert encryption.decrypt_secret(ct_new) == "payload"
        # New ciphertext differs from old (different key).
        assert ct_new != ct_old

    def test_wrong_key_without_previous_returns_none(self):
        _reload({"CREDENTIALS_KEY": "old-key", "CREDENTIALS_KEY_PREVIOUS": ""})
        ct = encryption.encrypt_secret("payload")
        _reload({"CREDENTIALS_KEY": "new-key", "CREDENTIALS_KEY_PREVIOUS": ""})
        # Legacy plaintext fallback path — InvalidToken returns value as-is.
        # That's the documented behaviour (treats tamper as legacy plaintext).
        result = encryption.decrypt_secret(ct)
        assert result == ct  # returned unchanged, not decrypted


class TestFailSoft:
    def test_unexpected_error_returns_none(self):
        _reload({"CREDENTIALS_KEY": "key", "CREDENTIALS_KEY_PREVIOUS": ""})
        # Monkey-patch fernet to raise an unexpected exception.
        original = encryption._get_fernet

        class BadFernet:
            def decrypt(self, *_args, **_kwargs):
                raise RuntimeError("disk on fire")

        encryption._get_fernet = lambda: BadFernet()  # type: ignore[assignment]
        try:
            assert encryption.decrypt_secret("anyvalue") is None
        finally:
            encryption._get_fernet = original

    def test_strict_variant_raises(self):
        _reload({"CREDENTIALS_KEY": "k", "CREDENTIALS_KEY_PREVIOUS": ""})
        # Invalid ciphertext → strict raises.
        with pytest.raises(Exception):
            encryption.decrypt_secret_strict("not-fernet-ciphertext-zzzzz")


class TestProductionSafety:
    def test_encrypt_without_key_raises_in_prod(self):
        _reload({
            "CREDENTIALS_KEY": "",
            "HMAC_SECRET": "",
            "CREDENTIALS_KEY_PREVIOUS": "",
            "ENVIRONMENT": "production",
        })
        with pytest.raises(RuntimeError, match="production"):
            encryption.encrypt_secret("secret")
        # Restore
        _reload({
            "CREDENTIALS_KEY": "key-one",
            "HMAC_SECRET": "a-hmac-secret",
            "ENVIRONMENT": "production",
        })

    def test_encrypt_without_key_allowed_in_dev(self):
        _reload({
            "CREDENTIALS_KEY": "",
            "HMAC_SECRET": "",
            "CREDENTIALS_KEY_PREVIOUS": "",
            "ENVIRONMENT": "development",
        })
        # Should not raise, returns plaintext with warning.
        assert encryption.encrypt_secret("secret") == "secret"
        _reload({
            "CREDENTIALS_KEY": "key-one",
            "HMAC_SECRET": "a-hmac-secret",
            "ENVIRONMENT": "production",
        })
