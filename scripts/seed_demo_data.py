#!/usr/bin/env python3
"""
Seed demo data into the database for demonstration purposes.
Run after: alembic upgrade head
"""

import asyncio
import uuid
import secrets
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

import os
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://approvalkit:approvalkit@postgres:5432/approvalkit")


async def seed():
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    async with session_factory() as session:
        async with session.begin():
            workspace_id = uuid.uuid4()
            api_key = secrets.token_hex(32)
            hmac_secret = secrets.token_hex(64)

            # Workspace
            await session.execute(text("""
                INSERT INTO workspaces (id, name, auth0_tenant, api_key, hmac_secret)
                VALUES (:id, :name, :tenant, :api_key, :hmac_secret)
            """), {
                "id": workspace_id, "name": "Demo Workspace",
                "tenant": "demo.auth0.com", "api_key": api_key, "hmac_secret": hmac_secret,
            })

            # Approvers
            approvers = [
                {"name": "CFO", "email": "cfo@company.com", "auth0_user_id": "auth0|cfo001"},
                {"name": "CEO", "email": "ceo@company.com", "auth0_user_id": "auth0|ceo001"},
                {"name": "CS Lead", "email": "cs@company.com", "auth0_user_id": "auth0|cs001"},
                {"name": "Lead Dev", "email": "lead@company.com", "auth0_user_id": "auth0|dev001"},
                {"name": "Maintainer A", "email": "maint-a@company.com", "auth0_user_id": "auth0|maint001"},
            ]
            approver_ids = []
            for a in approvers:
                aid = uuid.uuid4()
                approver_ids.append(aid)
                await session.execute(text("""
                    INSERT INTO approvers (id, workspace_id, name, email, auth0_user_id)
                    VALUES (:id, :ws, :name, :email, :auth0)
                """), {"id": aid, "ws": workspace_id, "name": a["name"], "email": a["email"], "auth0": a["auth0_user_id"]})

            cfo_id, ceo_id, cs_id, lead_id, maint_id = approver_ids

            # Connections
            for conn in [
                {"name": "Stripe Production", "service": "stripe", "vault_id": "tv_stripe_prod"},
                {"name": "GitHub Main", "service": "github", "vault_id": "tv_github_main"},
            ]:
                await session.execute(text("""
                    INSERT INTO connections (id, workspace_id, name, service, token_vault_connection_id, actions)
                    VALUES (:id, :ws, :name, :service, :vault_id, :actions)
                """), {
                    "id": uuid.uuid4(), "ws": workspace_id,
                    "name": conn["name"], "service": conn["service"], "vault_id": conn["vault_id"],
                    "actions": '["charge", "refund", "payout"]' if conn["service"] == "stripe" else '["deploy", "rollback", "merge_pr"]',
                })

            # Rules
            # Rule 1: Stripe charge > $100 — sequential CS → CFO
            rule1_id = uuid.uuid4()
            await session.execute(text("""
                INSERT INTO rules (id, workspace_id, name, connection, action, conditions, model, timeout_seconds, on_timeout, escalate_to, context_template, partial_approval, priority)
                VALUES (:id, :ws, :name, :conn, :action, :cond, 'sequential', 300, 'escalate', :esc, :tmpl, true, 10)
            """), {
                "id": rule1_id, "ws": workspace_id,
                "name": "High-value Stripe charges",
                "conn": "stripe-prod", "action": "charge",
                "cond": '[{"field":"amount","operator":"gt","value":100}]',
                "esc": ceo_id,
                "tmpl": "Charge of ${{amount}} for {{customer}}",
            })
            for i, aid in enumerate([cs_id, cfo_id]):
                await session.execute(text("""
                    INSERT INTO rule_approvers (id, rule_id, approver_id, "order")
                    VALUES (:id, :rule, :approver, :ord)
                """), {"id": uuid.uuid4(), "rule": rule1_id, "approver": aid, "ord": i})

            # Rule 2: Production deploy — any-one
            rule2_id = uuid.uuid4()
            await session.execute(text("""
                INSERT INTO rules (id, workspace_id, name, connection, action, conditions, model, timeout_seconds, on_timeout, blackout_start, blackout_end, cooldown_max, context_template, priority)
                VALUES (:id, :ws, :name, :conn, :action, :cond, 'any_one', 120, 'block', '23:00', '06:00', 5, :tmpl, 5)
            """), {
                "id": rule2_id, "ws": workspace_id,
                "name": "Production deployments",
                "conn": "github-main", "action": "deploy",
                "cond": '[{"field":"env","operator":"eq","value":"production"}]',
                "tmpl": "Deploy {{branch}} to {{env}}",
            })
            for aid in [lead_id, maint_id]:
                await session.execute(text("""
                    INSERT INTO rule_approvers (id, rule_id, approver_id, "order")
                    VALUES (:id, :rule, :approver, 0)
                """), {"id": uuid.uuid4(), "rule": rule2_id, "approver": aid})

            # Rule 3: Rollback — specific lead only
            rule3_id = uuid.uuid4()
            await session.execute(text("""
                INSERT INTO rules (id, workspace_id, name, connection, action, conditions, model, timeout_seconds, on_timeout, context_template, priority)
                VALUES (:id, :ws, :name, :conn, :action, :cond, 'specific', 120, 'block', :tmpl, 8)
            """), {
                "id": rule3_id, "ws": workspace_id,
                "name": "Production rollback",
                "conn": "github-main", "action": "rollback",
                "cond": '[{"field":"env","operator":"eq","value":"production"}]',
                "tmpl": "Rollback {{env}} to {{version}}",
            })
            await session.execute(text("""
                INSERT INTO rule_approvers (id, rule_id, approver_id, "order")
                VALUES (:id, :rule, :approver, 0)
            """), {"id": uuid.uuid4(), "rule": rule3_id, "approver": lead_id})

        print(f"Demo data seeded successfully!")
        print(f"  Workspace ID: {workspace_id}")
        print(f"  API Key:      {api_key}")
        print(f"  HMAC Secret:  {hmac_secret}")
        print(f"  Approvers:    CFO, CEO, CS Lead, Lead Dev, Maintainer A")
        print(f"  Rules:        3 (Stripe charge, Prod deploy, Prod rollback)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
