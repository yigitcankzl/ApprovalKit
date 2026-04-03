"""Tests for startup migration runner (idempotent ADD COLUMN IF NOT EXISTS)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch


def run(coro):
    return asyncio.run(coro)


class TestMigrationRunner:

    def test_migrations_list_not_empty(self):
        from api.migrations import MIGRATIONS
        assert len(MIGRATIONS) > 0

    def test_all_migrations_are_tuples(self):
        from api.migrations import MIGRATIONS
        for m in MIGRATIONS:
            assert isinstance(m, tuple), f"Migration {m} should be a tuple"
            assert len(m) == 2, "Each migration should be (name, sql)"

    def test_migration_names_unique(self):
        from api.migrations import MIGRATIONS
        names = [m[0] for m in MIGRATIONS]
        assert len(names) == len(set(names)), "Migration names must be unique"

    def test_all_sqls_are_alter_table(self):
        from api.migrations import MIGRATIONS
        for name, sql in MIGRATIONS:
            assert "ALTER TABLE" in sql.upper(), f"Migration '{name}' should use ALTER TABLE"

    def test_all_sqls_have_if_not_exists(self):
        from api.migrations import MIGRATIONS
        for name, sql in MIGRATIONS:
            assert "IF NOT EXISTS" in sql.upper(), f"Migration '{name}' should use IF NOT EXISTS"

    def test_risk_score_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("risk_score" in sql for sql in sqls)

    def test_risk_level_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("risk_level" in sql for sql in sqls)

    def test_trust_score_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("trust_score" in sql for sql in sqls)

    def test_trust_history_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("trust_history" in sql for sql in sqls)

    def test_rejection_reason_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("rejection_reason" in sql for sql in sqls)

    def test_risk_auto_approve_threshold_migration_exists(self):
        from api.migrations import MIGRATIONS
        sqls = [sql for _, sql in MIGRATIONS]
        assert any("risk_auto_approve_threshold" in sql for sql in sqls)

    def test_run_migrations_executes_all_statements(self):
        from api.migrations import MIGRATIONS, run_migrations
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        run(run_migrations(db))
        assert db.execute.call_count == len(MIGRATIONS)
        db.commit.assert_awaited_once()

    def test_run_migrations_continues_on_error(self):
        """If one migration fails, the runner should continue."""
        from api.migrations import run_migrations
        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("column already exists")
            return MagicMock()

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=execute_side_effect)
        db.commit = AsyncMock()

        from api.migrations import MIGRATIONS
        run(run_migrations(db))
        # Commit still called at the end
        db.commit.assert_awaited_once()

    def test_migration_sql_targets_correct_tables(self):
        from api.migrations import MIGRATIONS
        tables = {name.split(".")[0] for name, _ in MIGRATIONS}
        assert "approval_jobs" in tables
        assert "registered_agents" in tables
        assert "rules" in tables
