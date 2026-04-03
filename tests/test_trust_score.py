"""Tests for Agent Trust Score logic (Feature 8)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def run(coro):
    return asyncio.run(coro)


class TestTrustScoreHelpers:
    """Unit tests for _agent_to_dict trust score fields."""

    def _make_agent(self, trust_score=100, trust_history=None):
        agent = MagicMock()
        agent.id = "agent-uuid-1"
        agent.name = "test-agent"
        agent.description = "Test agent"
        agent.icon = "bot"
        agent.is_active = True
        agent.api_key = None
        agent.created_at = MagicMock()
        agent.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        agent.trust_score = trust_score
        agent.trust_history = trust_history or []
        agent.scenarios = []
        return agent

    def test_trust_score_in_dict(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=85)
        d = _agent_to_dict(agent)
        assert d["trust_score"] == 85

    def test_trust_level_high(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=90)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "high"

    def test_trust_level_medium(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=65)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "medium"

    def test_trust_level_low(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=30)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "low"

    def test_trust_level_boundary_80_is_high(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=80)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "high"

    def test_trust_level_boundary_50_is_medium(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=50)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "medium"

    def test_trust_level_49_is_low(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent(trust_score=49)
        d = _agent_to_dict(agent)
        assert d["trust_level"] == "low"

    def test_trust_score_defaults_100_when_none(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent()
        agent.trust_score = None
        d = _agent_to_dict(agent)
        assert d["trust_score"] == 100

    def test_trust_history_in_dict(self):
        from api.routes.agents import _agent_to_dict
        history = [{"decision": "approve", "delta": 2, "score": 100}]
        agent = self._make_agent(trust_history=history)
        d = _agent_to_dict(agent)
        assert d["trust_history"] == history

    def test_trust_history_defaults_empty_list(self):
        from api.routes.agents import _agent_to_dict
        agent = self._make_agent()
        agent.trust_history = None
        d = _agent_to_dict(agent)
        assert d["trust_history"] == []


class TestTrustScoreUpdateLogic:
    """Unit tests for trust score delta calculation."""

    def _delta(self, decision):
        return -5 if decision == "reject" else 2 if decision == "approve" else 0

    def test_approve_increases_by_2(self):
        assert self._delta("approve") == 2

    def test_reject_decreases_by_5(self):
        assert self._delta("reject") == -5

    def test_unknown_decision_no_change(self):
        assert self._delta("other") == 0

    def test_score_clamped_at_100(self):
        current = 99
        delta = 2
        assert min(100, max(0, current + delta)) == 100

    def test_score_clamped_at_0(self):
        current = 2
        delta = -5
        assert min(100, max(0, current + delta)) == 0

    def test_score_normal_increase(self):
        current = 80
        assert min(100, max(0, current + 2)) == 82

    def test_score_normal_decrease(self):
        current = 80
        assert min(100, max(0, current - 5)) == 75

    def test_history_capped_at_50_events(self):
        history = [{"decision": "approve", "delta": 2, "score": 100}] * 50
        # adding one more
        history.append({"decision": "reject", "delta": -5, "score": 95})
        history = history[-50:]
        assert len(history) == 50

    def test_history_entry_structure(self):
        from datetime import datetime
        entry = {
            "decision": "approve",
            "delta": 2,
            "ts": datetime.utcnow().isoformat(),
            "score": 100,
        }
        assert "decision" in entry
        assert "delta" in entry
        assert "ts" in entry
        assert "score" in entry


class TestUpdateTrustScoreFunction:
    """Test _update_trust_score async function."""

    def test_returns_early_if_agent_not_found(self):
        from api.routes.agents import _update_trust_score
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        # Should not raise
        run(_update_trust_score("unknown-agent", "ws-id", "approve", db))

    def test_approve_increases_score(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 90
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "approve", db))

        assert agent.trust_score == 92

    def test_reject_decreases_score(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 80
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "reject", db))

        assert agent.trust_score == 75

    def test_score_does_not_exceed_100(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 100
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "approve", db))

        assert agent.trust_score == 100

    def test_score_does_not_go_below_zero(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 2
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "reject", db))

        assert agent.trust_score == 0

    def test_history_entry_appended(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 80
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "approve", db))

        assert len(agent.trust_history) == 1
        assert agent.trust_history[0]["decision"] == "approve"
        assert agent.trust_history[0]["delta"] == 2

    def test_commit_called(self):
        from api.routes.agents import _update_trust_score
        agent = MagicMock()
        agent.trust_score = 80
        agent.trust_history = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=agent)))
        db.commit = AsyncMock()

        run(_update_trust_score("my-agent", "ws-id", "approve", db))

        db.commit.assert_awaited_once()
