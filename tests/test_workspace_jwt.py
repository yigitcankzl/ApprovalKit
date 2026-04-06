"""Tests for api/middleware/workspace.py JWT verification.

Generates ephemeral RSA keys, signs tokens, patches the JWKS client
to return the matching public key, then verifies the middleware's
decisions.
"""
import asyncio
import importlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "workspace-test")
os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
os.environ["AUTH0_AUDIENCE"] = "https://api.approvalkit.example/"
os.environ["AUTH0_CLIENT_ID"] = "m2m-client-id"
os.environ["AUTH0_WEB_CLIENT_ID"] = "web-client-id"
os.environ["ENVIRONMENT"] = "production"

from unittest.mock import MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.config import get_settings


def _reload_workspace_module():
    get_settings.cache_clear()
    from api.middleware import workspace as wsmod
    importlib.reload(wsmod)
    return wsmod


_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_priv_pem = _rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
_pub_key = _rsa_key.public_key()


def _issue_token(
    *,
    sub="user|42",
    aud="https://api.approvalkit.example/",
    iss="https://tenant.us.auth0.com/",
    exp_in=300,
    algorithm="RS256",
):
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_in,
    }
    return jwt.encode(claims, _priv_pem, algorithm=algorithm)


def _patch_jwks(wsmod):
    """Replace the JWKS client with one that returns our local public key."""
    signing_key = MagicMock()
    signing_key.key = _pub_key
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    return patch.object(wsmod, "_jwks_client", return_value=client)


class TestVerifyAuth0Token:
    def setup_method(self):
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        os.environ["AUTH0_AUDIENCE"] = "https://api.approvalkit.example/"
        os.environ["AUTH0_CLIENT_ID"] = "m2m-client-id"
        os.environ["AUTH0_WEB_CLIENT_ID"] = "web-client-id"
        os.environ["ENVIRONMENT"] = "production"

    def test_valid_token_accepted(self):
        ws = _reload_workspace_module()
        token = _issue_token()
        with _patch_jwks(ws):
            claims = ws._verify_auth0_token(token, "tenant.us.auth0.com")
        assert claims is not None
        assert claims["sub"] == "user|42"

    def test_expired_token_rejected(self):
        ws = _reload_workspace_module()
        token = _issue_token(exp_in=-100)
        with _patch_jwks(ws):
            assert ws._verify_auth0_token(token, "tenant.us.auth0.com") is None

    def test_wrong_issuer_rejected(self):
        ws = _reload_workspace_module()
        token = _issue_token(iss="https://evil.example.com/")
        with _patch_jwks(ws):
            assert ws._verify_auth0_token(token, "tenant.us.auth0.com") is None

    def test_wrong_audience_rejected(self):
        ws = _reload_workspace_module()
        token = _issue_token(aud="https://different-api.example/")
        with _patch_jwks(ws):
            assert ws._verify_auth0_token(token, "tenant.us.auth0.com") is None

    def test_id_token_with_client_id_aud_rejected(self):
        """Access tokens are issued for API audiences. ID tokens have
        aud == client_id and must be rejected."""
        ws = _reload_workspace_module()
        # ID token: aud = Auth0 client_id. PyJWT's aud check passes
        # only if one of the allowed auds matches, so we need to add
        # the client_id to the allowed list to get past PyJWT — then
        # the extra guard should still reject it.
        token = _issue_token(aud="https://api.approvalkit.example/")
        # Tamper to make aud == client_id at the claim level by issuing
        # with that audience in the allowed list.
        os.environ["AUTH0_AUDIENCE"] = "m2m-client-id"
        ws = _reload_workspace_module()
        token = _issue_token(aud="m2m-client-id")
        with _patch_jwks(ws):
            result = ws._verify_auth0_token(token, "tenant.us.auth0.com")
        assert result is None
        # Restore
        os.environ["AUTH0_AUDIENCE"] = "https://api.approvalkit.example/"
        _reload_workspace_module()

    def test_bad_signature_rejected(self):
        ws = _reload_workspace_module()
        # Sign with a DIFFERENT key but return our local public key.
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        claims = {
            "sub": "u|1",
            "aud": "https://api.approvalkit.example/",
            "iss": "https://tenant.us.auth0.com/",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        }
        token = jwt.encode(claims, other_pem, algorithm="RS256")
        with _patch_jwks(ws):
            assert ws._verify_auth0_token(token, "tenant.us.auth0.com") is None

    def test_hs256_token_rejected(self):
        """Algorithm confusion: an HS256 token must not be accepted when
        the verifier is configured for RS256."""
        ws = _reload_workspace_module()
        claims = {
            "sub": "u|1",
            "aud": "https://api.approvalkit.example/",
            "iss": "https://tenant.us.auth0.com/",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        }
        bad_token = jwt.encode(claims, "symmetric-secret", algorithm="HS256")
        with _patch_jwks(ws):
            assert ws._verify_auth0_token(bad_token, "tenant.us.auth0.com") is None


class TestJwtEnforcementToggle:
    def test_enforced_in_prod_with_auth0_domain(self):
        os.environ["ENVIRONMENT"] = "production"
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        ws = _reload_workspace_module()
        assert ws._jwt_enforcement_enabled() is True

    def test_not_enforced_in_dev(self):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        ws = _reload_workspace_module()
        assert ws._jwt_enforcement_enabled() is False

    def test_not_enforced_without_auth0_domain(self):
        os.environ["ENVIRONMENT"] = "production"
        os.environ["AUTH0_DOMAIN"] = ""
        ws = _reload_workspace_module()
        assert ws._jwt_enforcement_enabled() is False
        # Restore
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        _reload_workspace_module()


class TestJwksCache:
    def test_cache_bounded(self):
        os.environ["AUTH0_DOMAIN"] = "tenant.us.auth0.com"
        ws = _reload_workspace_module()
        ws._jwks_clients.clear()
        # Don't actually hit the network — stub PyJWKClient.
        with patch.object(ws, "PyJWKClient", return_value=MagicMock()):
            for i in range(ws._JWKS_CACHE_MAX + 10):
                ws._jwks_client(f"tenant{i}.us.auth0.com")
        assert len(ws._jwks_clients) == ws._JWKS_CACHE_MAX
