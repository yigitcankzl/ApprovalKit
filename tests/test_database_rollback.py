"""Tests for api/database.py get_db() rollback behaviour.

Covers:
 - Exception inside the session → rollback is called
 - rollback itself raises → suppressed, original exception propagates
 - Normal path (no exception) → no rollback, session closed
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "db-test")

from unittest.mock import AsyncMock, MagicMock, patch


def _make_session():
    session = AsyncMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_session_factory(session):
    """Return an async context manager that yields the given session."""
    class FakeCtx:
        async def __aenter__(self):
            return session
        async def __aexit__(self, *args):
            pass
    factory = MagicMock(return_value=FakeCtx())
    return factory


class TestGetDbRollback:
    def test_exception_triggers_rollback(self):
        session = _make_session()
        with patch("api.database.async_session", _make_session_factory(session)):
            from api.database import get_db

            async def _run():
                gen = get_db()
                s = await gen.__anext__()
                assert s is session
                # Simulate an exception in the caller.
                with pytest.raises(ValueError, match="boom"):
                    await gen.athrow(ValueError("boom"))

            asyncio.run(_run())
        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()

    def test_rollback_failure_suppressed_original_propagates(self):
        session = _make_session()
        session.rollback = AsyncMock(side_effect=RuntimeError("rollback failed"))
        with patch("api.database.async_session", _make_session_factory(session)):
            from api.database import get_db

            async def _run():
                gen = get_db()
                await gen.__anext__()
                # The original ValueError must propagate, not the rollback RuntimeError.
                with pytest.raises(ValueError, match="original"):
                    await gen.athrow(ValueError("original"))

            asyncio.run(_run())
        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()

    def test_normal_path_no_rollback(self):
        session = _make_session()
        with patch("api.database.async_session", _make_session_factory(session)):
            from api.database import get_db

            async def _run():
                gen = get_db()
                s = await gen.__anext__()
                assert s is session
                # Normal completion — send None to finish the generator.
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass

            asyncio.run(_run())
        session.rollback.assert_not_awaited()
        session.close.assert_awaited_once()
