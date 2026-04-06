"""Tests for api/main.py value_error_handler — info disclosure.

Covers:
 - production → generic "Invalid request value" message
 - non-production → full str(exc) returned
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "ve-test")

from unittest.mock import MagicMock

from api.config import get_settings


def _get_handler(env: str):
    os.environ["ENVIRONMENT"] = env
    get_settings.cache_clear()
    from api import main
    importlib.reload(main)
    handler = main.app.exception_handlers.get(ValueError)
    if not handler:
        raise RuntimeError("ValueError handler not registered")
    return handler


class TestValueErrorHandler:
    def test_production_generic_message(self):
        import asyncio
        handler = _get_handler("production")
        req = MagicMock()
        req.url = MagicMock()
        req.url.path = "/test"
        resp = asyncio.run(handler(req, ValueError("secret internal detail")))
        import json
        body = json.loads(resp.body)
        assert body["detail"] == "Invalid request value"
        assert "secret" not in body["detail"]
        assert resp.status_code == 400

    def test_dev_full_message(self):
        import asyncio
        handler = _get_handler("development")
        req = MagicMock()
        req.url = MagicMock()
        req.url.path = "/test"
        resp = asyncio.run(handler(req, ValueError("badly formatted UUID")))
        import json
        body = json.loads(resp.body)
        assert "badly formatted UUID" in body["detail"]
        assert resp.status_code == 400
        # Restore
        os.environ["ENVIRONMENT"] = "production"
        get_settings.cache_clear()
