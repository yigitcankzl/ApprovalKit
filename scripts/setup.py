#!/usr/bin/env python3
"""
ApprovalKit — One-shot Setup Script
=====================================
Reads credentials from .env, then automatically:
  1. Validates Auth0 connection (domain, client ID/secret, CIBA grant)
  2. Creates FGA store (if FGA_STORE_ID is empty)
  3. Pushes the authorization model to FGA
  4. Seeds workspace + approver tuples from the database
  5. Generates a cryptographically secure HMAC_SECRET (if missing)
  6. Writes FGA_STORE_ID, FGA_MODEL_ID, HMAC_SECRET back to .env
  7. Prints a final status report

What you need to fill in .env BEFORE running this script:
  AUTH0_DOMAIN         e.g. dev-xxxx.us.auth0.com
  AUTH0_CLIENT_ID      M2M application client ID
  AUTH0_CLIENT_SECRET  M2M application client secret
  AUTH0_MGMT_API_AUDIENCE  https://<domain>/api/v2/
  FGA_CLIENT_ID        from dashboard.fga.dev → Store → Credentials
  FGA_CLIENT_SECRET    from dashboard.fga.dev → Store → Credentials
  FGA_STORE_ID         (optional — script creates one if empty)

Usage:
  # Inside container:
  docker compose exec api python scripts/setup.py

  # On host (needs httpx, sqlalchemy, python-dotenv):
  pip install httpx sqlalchemy asyncpg python-dotenv
  python scripts/setup.py
"""

import asyncio
import os
import re
import secrets
import sys
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE  = REPO_ROOT / ".env"

# ---------------------------------------------------------------------------
# Load .env manually (avoid importing api.config so this runs standalone)
# ---------------------------------------------------------------------------
def load_env(path: Path) -> dict:
    env: dict = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env

def write_env_var(path: Path, key: str, value: str):
    """Update or append a single key=value in .env (never logs the value)."""
    content = path.read_text() if path.exists() else ""
    pattern = rf"^{re.escape(key)}=.*$"
    replacement = f"{key}={value}"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{replacement}\n"
    path.write_text(content)


ENV = load_env(ENV_FILE)

AUTH0_DOMAIN          = ENV.get("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID       = ENV.get("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET   = ENV.get("AUTH0_CLIENT_SECRET", "")
AUTH0_MGMT_AUDIENCE   = ENV.get("AUTH0_MGMT_API_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")
FGA_API_URL           = ENV.get("FGA_API_URL", "https://api.us1.fga.dev")
FGA_STORE_ID          = ENV.get("FGA_STORE_ID", "")
FGA_MODEL_ID          = ENV.get("FGA_MODEL_ID", "")
FGA_CLIENT_ID         = ENV.get("FGA_CLIENT_ID", "")
FGA_CLIENT_SECRET     = ENV.get("FGA_CLIENT_SECRET", "")
HMAC_SECRET           = ENV.get("HMAC_SECRET", "")
DATABASE_URL          = ENV.get("DATABASE_URL", "postgresql+asyncpg://approvalkit:approvalkit@postgres:5432/approvalkit")

# ---------------------------------------------------------------------------
# FGA authorization model (JSON format for the REST API)
# ---------------------------------------------------------------------------
FGA_MODEL_JSON = {
    "schema_version": "1.1",
    "type_definitions": [
        {
            "type": "user",
        },
        {
            "type": "workspace",
            "relations": {
                "admin":       {"this": {}},
                "approver":    {"this": {}},
                "agent_owner": {"this": {}},
                "viewer":      {"this": {}},
            },
            "metadata": {
                "relations": {
                    "admin":       {"directly_related_user_types": [{"type": "user"}]},
                    "approver":    {"directly_related_user_types": [{"type": "user"}]},
                    "agent_owner": {"directly_related_user_types": [{"type": "user"}]},
                    "viewer":      {"directly_related_user_types": [{"type": "user"}]},
                },
            },
        },
        {
            "type": "rule",
            "relations": {
                "workspace": {"this": {}},
                "can_read": {
                    "union": {
                        "child": [
                            {"tupleToUserset": {"tupleset": {"relation": "workspace"}, "computedUserset": {"relation": "admin"}}},
                            {"tupleToUserset": {"tupleset": {"relation": "workspace"}, "computedUserset": {"relation": "agent_owner"}}},
                        ]
                    }
                },
                "can_write": {
                    "tupleToUserset": {
                        "tupleset": {"relation": "workspace"},
                        "computedUserset": {"relation": "admin"},
                    }
                },
            },
            "metadata": {
                "relations": {
                    "workspace": {"directly_related_user_types": [{"type": "workspace"}]},
                    "can_read":  {"directly_related_user_types": []},
                    "can_write": {"directly_related_user_types": []},
                },
            },
        },
        {
            "type": "audit_log",
            "relations": {
                "workspace": {"this": {}},
                "owner":     {"this": {}},
                "agent":     {"this": {}},
                "can_read": {
                    "union": {
                        "child": [
                            {"tupleToUserset": {"tupleset": {"relation": "workspace"}, "computedUserset": {"relation": "admin"}}},
                            {"tupleToUserset": {"tupleset": {"relation": "workspace"}, "computedUserset": {"relation": "viewer"}}},
                            {
                                "intersection": {
                                    "child": [
                                        {"tupleToUserset": {"tupleset": {"relation": "workspace"}, "computedUserset": {"relation": "approver"}}},
                                        {"computedUserset": {"relation": "owner"}},
                                    ]
                                }
                            },
                        ]
                    }
                },
            },
            "metadata": {
                "relations": {
                    "workspace": {"directly_related_user_types": [{"type": "workspace"}]},
                    "owner":     {"directly_related_user_types": [{"type": "user"}]},
                    "agent":     {"directly_related_user_types": [{"type": "user"}]},
                    "can_read":  {"directly_related_user_types": []},
                },
            },
        },
    ],
}

# ---------------------------------------------------------------------------
# Status tracker
# ---------------------------------------------------------------------------
results: dict = {
    "auth0":      None,   # True / False
    "fga_store":  None,
    "fga_model":  None,
    "fga_tuples": None,
    "hmac":       None,
    "db":         None,
}

def ok(label: str):  print(f"  \033[32m✓\033[0m {label}")
def err(label: str): print(f"  \033[31m✗\033[0m {label}")
def info(label: str):print(f"  \033[33m·\033[0m {label}")


# ===========================================================================
# STEP 1 — Auth0 validation
# ===========================================================================
async def step_auth0(client: httpx.AsyncClient) -> str | None:
    """
    Get a Management API token using client credentials.
    Returns the token on success, None on failure.
    """
    print("\n[1/5] Auth0 connection")

    if not AUTH0_DOMAIN:
        err("AUTH0_DOMAIN is not set"); results["auth0"] = False; return None
    if not AUTH0_CLIENT_ID or not AUTH0_CLIENT_SECRET:
        err("AUTH0_CLIENT_ID / AUTH0_CLIENT_SECRET not set"); results["auth0"] = False; return None

    try:
        resp = await client.post(
            f"https://{AUTH0_DOMAIN}/oauth/token",
            json={
                "client_id":     AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "audience":      AUTH0_MGMT_AUDIENCE,
                "grant_type":    "client_credentials",
            },
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        ok(f"Management API token acquired  (domain: {AUTH0_DOMAIN})")
        results["auth0"] = True
        return token

    except httpx.HTTPStatusError as e:
        err(f"Auth0 token request failed: {e.response.status_code} {e.response.text[:120]}")
        results["auth0"] = False
        return None
    except Exception as e:
        err(f"Auth0 connection error: {e}")
        results["auth0"] = False
        return None


async def verify_ciba(client: httpx.AsyncClient, mgmt_token: str):
    """Check whether the M2M application has the CIBA grant type enabled."""
    try:
        resp = await client.get(
            f"https://{AUTH0_DOMAIN}/api/v2/clients/{AUTH0_CLIENT_ID}",
            headers={"Authorization": f"Bearer {mgmt_token}"},
        )
        resp.raise_for_status()
        grants = resp.json().get("grant_types", [])
        ciba_grant = "urn:openid:params:grant-type:ciba"
        if ciba_grant in grants:
            ok("CIBA grant type is enabled on the application")
        else:
            info("CIBA grant type NOT found — enabling it now...")
            await client.patch(
                f"https://{AUTH0_DOMAIN}/api/v2/clients/{AUTH0_CLIENT_ID}",
                headers={"Authorization": f"Bearer {mgmt_token}", "Content-Type": "application/json"},
                json={"grant_types": list(set(grants) | {ciba_grant})},
            )
            ok("CIBA grant type enabled")
    except Exception as e:
        info(f"Could not verify CIBA grant: {e}")


# ===========================================================================
# STEP 2 — FGA token
# ===========================================================================
async def get_fga_token(client: httpx.AsyncClient) -> str:
    if not FGA_CLIENT_ID or not FGA_CLIENT_SECRET:
        info("FGA_CLIENT_ID / FGA_CLIENT_SECRET not set — proceeding without auth token")
        return ""
    try:
        resp = await client.post(
            "https://fga.us.auth0.com/oauth/token",
            json={
                "client_id":     FGA_CLIENT_ID,
                "client_secret": FGA_CLIENT_SECRET,
                "audience":      "https://api.us1.fga.dev/",
                "grant_type":    "client_credentials",
            },
        )
        resp.raise_for_status()
        ok("FGA access token acquired")
        return resp.json()["access_token"]
    except Exception as e:
        err(f"FGA token error: {e}")
        return ""


# ===========================================================================
# STEP 3 — FGA store + model
# ===========================================================================
async def step_fga_store(client: httpx.AsyncClient, fga_token: str) -> str:
    """Create a new FGA store if FGA_STORE_ID is empty, otherwise verify it."""
    global FGA_STORE_ID
    print("\n[2/5] FGA store")

    headers = {"Authorization": f"Bearer {fga_token}"} if fga_token else {}

    if FGA_STORE_ID:
        # Verify the store exists
        try:
            resp = await client.get(f"{FGA_API_URL}/stores/{FGA_STORE_ID}", headers=headers)
            if resp.status_code == 200:
                ok(f"Existing store verified  (id: {FGA_STORE_ID})")
                results["fga_store"] = True
                return FGA_STORE_ID
            else:
                info(f"Store {FGA_STORE_ID} not reachable ({resp.status_code}) — creating a new one")
        except Exception:
            info("Could not reach FGA — creating a new store")

    # Create a new store
    try:
        resp = await client.post(
            f"{FGA_API_URL}/stores",
            json={"name": "ApprovalKit"},
            headers=headers,
        )
        resp.raise_for_status()
        store_id = resp.json()["id"]
        FGA_STORE_ID = store_id
        write_env_var(ENV_FILE, "FGA_STORE_ID", store_id)
        ok(f"New FGA store created and saved  (id: {store_id})")
        results["fga_store"] = True
        return store_id
    except Exception as e:
        err(f"Failed to create FGA store: {e}")
        results["fga_store"] = False
        return ""


async def step_fga_model(client: httpx.AsyncClient, fga_token: str, store_id: str) -> str:
    """Push the authorization model to FGA."""
    global FGA_MODEL_ID
    print("\n[3/5] FGA authorization model")

    if not store_id:
        err("No store ID — skipping model creation"); results["fga_model"] = False; return ""

    headers = {"Authorization": f"Bearer {fga_token}"} if fga_token else {}

    try:
        resp = await client.post(
            f"{FGA_API_URL}/stores/{store_id}/authorization-models",
            json=FGA_MODEL_JSON,
            headers=headers,
        )
        resp.raise_for_status()
        model_id = resp.json()["authorization_model_id"]
        FGA_MODEL_ID = model_id
        write_env_var(ENV_FILE, "FGA_MODEL_ID", model_id)
        ok(f"Authorization model created and saved  (id: {model_id})")
        results["fga_model"] = True
        return model_id
    except Exception as e:
        err(f"Failed to create model: {e}")
        results["fga_model"] = False
        return ""


# ===========================================================================
# STEP 4 — Seed FGA tuples from DB
# ===========================================================================
async def step_fga_tuples(client: httpx.AsyncClient, fga_token: str, store_id: str, model_id: str):
    print("\n[4/5] FGA relationship tuples")

    if not store_id or not model_id:
        err("Missing store/model — skipping tuples"); results["fga_tuples"] = False; return

    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import text

        engine = create_async_engine(DATABASE_URL)
        session_factory = async_sessionmaker(engine, class_=AsyncSession)

        tuples: list[dict] = []

        async with session_factory() as session:
            workspaces = (await session.execute(text("SELECT id FROM workspaces"))).fetchall()
            approvers  = (await session.execute(text("SELECT id, auth0_user_id FROM approvers"))).fetchall()
            rules      = (await session.execute(text("SELECT id, workspace_id FROM rules"))).fetchall()

        await engine.dispose()

        if not workspaces:
            info("No workspaces in DB — skipping tuples (run seed_demo_data.py first)")
            results["fga_tuples"] = False
            return

        for (ws_id,) in workspaces:
            ws_obj = f"workspace:{ws_id}"

            for i, (ap_id, auth0_uid) in enumerate(approvers):
                user_fga = f"user:{auth0_uid}"
                # All approvers get the 'approver' role in the workspace
                tuples.append({"user": user_fga, "relation": "approver", "object": ws_obj})
                # First approver is also admin
                if i == 0:
                    tuples.append({"user": user_fga, "relation": "admin", "object": ws_obj})

        for (rule_id, ws_id) in rules:
            tuples.append({"user": f"workspace:{ws_id}", "relation": "workspace", "object": f"rule:{rule_id}"})

        results["db"] = True
    except Exception as e:
        err(f"Database error while reading tuples: {e}")
        results["fga_tuples"] = False
        results["db"] = False
        return

    headers = {"Authorization": f"Bearer {fga_token}"} if fga_token else {}
    url = f"{FGA_API_URL}/stores/{store_id}/write"

    written = 0
    failed  = 0
    for i in range(0, len(tuples), 10):   # FGA accepts max 10 tuples per request
        chunk = tuples[i:i + 10]
        try:
            resp = await client.post(url, json={
                "writes": {"tuple_keys": chunk},
                "authorization_model_id": model_id,
            }, headers=headers)
            if resp.status_code in (200, 201):
                written += len(chunk)
            else:
                # 409 = already exists — not an error
                if resp.status_code == 409:
                    written += len(chunk)
                else:
                    failed += len(chunk)
        except Exception as e:
            failed += len(chunk)

    if failed == 0:
        ok(f"{written} tuples written  ({len(workspaces)} workspace, {len(approvers)} approvers, {len(rules)} rules)")
        results["fga_tuples"] = True
    else:
        info(f"{written} written, {failed} failed")
        results["fga_tuples"] = written > 0


# ===========================================================================
# STEP 5 — HMAC secret
# ===========================================================================
def step_hmac():
    global HMAC_SECRET
    print("\n[5/5] HMAC secret")

    if HMAC_SECRET and len(HMAC_SECRET) >= 32:
        ok(f"HMAC_SECRET already set  ({len(HMAC_SECRET)} chars)")
        results["hmac"] = True
        return

    HMAC_SECRET = secrets.token_hex(32)   # 256-bit
    write_env_var(ENV_FILE, "HMAC_SECRET", HMAC_SECRET)
    ok(f"Generated and saved a new 256-bit HMAC_SECRET")
    results["hmac"] = True


# ===========================================================================
# Final report
# ===========================================================================
def print_report():
    print("\n" + "=" * 52)
    print("  Setup Report")
    print("=" * 52)

    checks = [
        ("Auth0 connection",    results["auth0"]),
        ("FGA store",           results["fga_store"]),
        ("FGA model",           results["fga_model"]),
        ("FGA tuples",          results["fga_tuples"]),
        ("HMAC secret",         results["hmac"]),
        ("Database reachable",  results["db"]),
    ]
    all_ok = True
    for label, status in checks:
        if status is True:
            print(f"  \033[32m✓\033[0m  {label}")
        elif status is False:
            print(f"  \033[31m✗\033[0m  {label}")
            all_ok = False
        else:
            print(f"  \033[33m-\033[0m  {label}  (skipped)")

    print()
    if all_ok:
        print("  \033[32mAll checks passed.\033[0m")
        print("  Restart services:  docker compose restart api worker")
    else:
        print("  \033[33mSome steps need attention — see messages above.\033[0m")
        print()
        if not results["auth0"]:
            print("  Auth0 fix:")
            print("    • Verify AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET in .env")
            print(f"    • Open https://manage.auth0.com → Applications → find your M2M app")
        if not results["fga_store"] or not results["fga_model"]:
            print("  FGA fix:")
            print("    • Go to https://dashboard.fga.dev")
            print("    • Create a store called 'ApprovalKit'")
            print("    • Create Credentials (Client ID + Secret) under that store")
            print("    • Add FGA_STORE_ID, FGA_CLIENT_ID, FGA_CLIENT_SECRET to .env")
            print("    • Re-run this script")
    print()


# ===========================================================================
# Entry point
# ===========================================================================
async def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║   ApprovalKit — Setup                        ║")
    print("╚══════════════════════════════════════════════╝")

    async with httpx.AsyncClient(timeout=20) as client:
        mgmt_token = await step_auth0(client)
        if mgmt_token:
            await verify_ciba(client, mgmt_token)

        fga_token = await get_fga_token(client)
        store_id  = await step_fga_store(client, fga_token)
        model_id  = await step_fga_model(client, fga_token, store_id)
        await step_fga_tuples(client, fga_token, store_id, model_id)

    step_hmac()
    print_report()


if __name__ == "__main__":
    asyncio.run(main())
