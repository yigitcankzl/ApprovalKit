"""Tests for PII masking utility (api/services/pii.py)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.services.pii import _mask_email, _mask_string, mask_text, mask_params


class TestMaskEmail:
    def test_basic_email(self):
        assert _mask_email("alice@example.com") == "a***@e***.com"

    def test_short_local(self):
        result = _mask_email("a@example.com")
        assert "@" in result
        assert "alice" not in result

    def test_no_at_returns_original(self):
        assert _mask_email("noemail") == "noemail"

    def test_subdomain_email(self):
        result = _mask_email("user@mail.company.co.uk")
        assert result.startswith("u***@")
        assert "user" not in result

    def test_empty_local(self):
        result = _mask_email("@example.com")
        assert "***" in result


class TestMaskString:
    def test_normal_string(self):
        assert _mask_string("Alice") == "Al***e"

    def test_short_string(self):
        result = _mask_string("Al")
        assert result.startswith("A")
        assert "***" in result

    def test_single_char(self):
        result = _mask_string("X")
        assert result.startswith("X")

    def test_exact_3_chars(self):
        result = _mask_string("abc")
        assert result == "a***"

    def test_long_string(self):
        result = _mask_string("VeryLongName")
        assert result == "Ve***e"
        assert "VeryLongName" not in result

    def test_empty_string(self):
        result = _mask_string("")
        assert result == "***"


class TestMaskText:
    def test_masks_email_in_text(self):
        text = "Contact alice@example.com for details"
        result = mask_text(text)
        assert "alice@example.com" not in result
        assert "a***@e***.com" in result

    def test_masks_multiple_emails(self):
        text = "From alice@foo.com to bob@bar.org"
        result = mask_text(text)
        assert "alice@foo.com" not in result
        assert "bob@bar.org" not in result

    def test_no_email_unchanged(self):
        text = "No email here, just text"
        assert mask_text(text) == text

    def test_empty_string(self):
        assert mask_text("") == ""


class TestMaskParams:
    def test_masks_email_field(self):
        params = {"email": "alice@example.com", "amount": 500}
        result = mask_params(params)
        assert result["email"] == "a***@e***.com"
        assert result["amount"] == 500

    def test_masks_name_field(self):
        params = {"name": "Alice Johnson", "status": "active"}
        result = mask_params(params)
        assert "Alice Johnson" not in result["name"]
        assert result["status"] == "active"

    def test_masks_multiple_pii_fields(self):
        params = {
            "customer": "Bob Smith",
            "recipient": "charlie@test.com",
            "phone": "555-1234",
            "amount": 100,
        }
        result = mask_params(params)
        assert "Bob Smith" not in result["customer"]
        assert "charlie@test.com" not in result["recipient"]
        assert "555-1234" not in result["phone"]
        assert result["amount"] == 100

    def test_none_params(self):
        assert mask_params(None) is None

    def test_empty_params(self):
        assert mask_params({}) == {}

    def test_non_string_pii_value_unchanged(self):
        params = {"email": 12345}
        result = mask_params(params)
        assert result["email"] == 12345

    def test_original_untouched(self):
        params = {"email": "alice@example.com"}
        result = mask_params(params)
        assert params["email"] == "alice@example.com"
        assert result is not params

    def test_case_insensitive_keys(self):
        # keys are lowercased in the check
        params = {"Email": "alice@example.com"}
        result = mask_params(params)
        # PII check uses k.lower(), so "Email" → "email" matches
        assert "alice@example.com" not in result.get("Email", "")

    def test_username_masked(self):
        params = {"username": "admin_user"}
        result = mask_params(params)
        assert "admin_user" not in result["username"]

    def test_non_pii_key_preserved(self):
        params = {"transaction_id": "tx-12345", "currency": "USD"}
        result = mask_params(params)
        assert result["transaction_id"] == "tx-12345"
        assert result["currency"] == "USD"
