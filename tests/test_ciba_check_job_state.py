"""Tests for CIBAService._check_job_state.

Covers:
 - Invalid UUID → None
 - Job not found → None
 - Job in non-terminal state → None
 - Job in terminal state → returns state value string
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("HMAC_SECRET", "ciba-test")

from unittest.mock import AsyncMock, MagicMock, patch

from api.services.ciba import CIBAService, ciba_service


class TestCheckJobState:
    def test_invalid_uuid_returns_none(self):
        result = asyncio.run(ciba_service._check_job_state("not-a-uuid"))
        assert result is None

    def test_empty_string_returns_none(self):
        result = asyncio.run(ciba_service._check_job_state(""))
        assert result is None

    def test_none_returns_none(self):
        # None is an invalid job_id — UUID(None) raises, handled as ValueError.
        result = asyncio.run(ciba_service._check_job_state(None))  # type: ignore
        assert result is None

    def test_job_not_found_returns_none(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine):
            with patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_factory):
                result = asyncio.run(
                    ciba_service._check_job_state(str(uuid.uuid4()))
                )
        assert result is None

    def test_terminal_state_returns_value(self):
        from api.models.approval_job import JobState

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = JobState.APPROVED

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine):
            with patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_factory):
                result = asyncio.run(
                    ciba_service._check_job_state(str(uuid.uuid4()))
                )
        assert result == "approved"
        mock_engine.dispose.assert_awaited_once()

    def test_pending_state_returns_none(self):
        from api.models.approval_job import JobState

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = JobState.PENDING

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        mock_factory = MagicMock(return_value=mock_session)

        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine):
            with patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_factory):
                result = asyncio.run(
                    ciba_service._check_job_state(str(uuid.uuid4()))
                )
        assert result is None
