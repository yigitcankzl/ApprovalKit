#!/usr/bin/env python3
"""
FGA Setup Script — ApprovalKit
-------------------------------
Bu script:
1. FGA store'unda authorization modelini oluşturur
2. Demo approvers + workspace için FGA tuple'larını yazar
3. .env dosyasına FGA_STORE_ID ve FGA_MODEL_ID'yi kaydeder

Kullanım:
  python scripts/setup_fga.py

.env'de şunların dolu olması gerekiyor:
  FGA_API_URL=https://api.us1.fga.dev
  FGA_STORE_ID=<fga.dev dashboard'dan>
  FGA_CLIENT_ID=<fga.dev dashboard → Credentials'dan>
  FGA_CLIENT_SECRET=<fga.dev dashboard → Credentials'dan>
"""

import asyncio
import os
import re
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

FGA_API_URL   = os.environ.get("FGA_API_URL", "https://api.us1.fga.dev")
FGA_STORE_ID  = os.environ.get("FGA_STORE_ID", "")
FGA_CLIENT_ID = os.environ.get("FGA_CLIENT_ID", "")
FGA_CLIENT_SECRET = os.environ.get("FGA_CLIENT_SECRET", "")

# Auth0 domain — FGA token audience için kullanılıyor
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")

# ──────────────────────────────────────────────────────────
# Authorization Model (DSL formatı)
# ──────────────────────────────────────────────────────────
AUTHORIZATION_MODEL = {
    "schema_version": "1.1",
    "type_definitions": [
        {
            "type": "user",
            "relations": {},
            "metadata": None,
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
                }
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
                }
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
                }
            },
        },
    ],
}


# ──────────────────────────────────────────────────────────
# Token alma
# ──────────────────────────────────────────────────────────
async def get_fga_token(client: httpx.AsyncClient) -> str:
    """FGA client credentials flow ile access token al."""
    if not FGA_CLIENT_ID or not FGA_CLIENT_SECRET:
        print("⚠  FGA_CLIENT_ID / FGA_CLIENT_SECRET boş — token'sız devam ediliyor")
        return ""

    # FGA token endpoint: Auth0 domain veya fga.dev
    token_url = f"https://fga.us.auth0.com/oauth/token"
    resp = await client.post(token_url, json={
        "client_id": FGA_CLIENT_ID,
        "client_secret": FGA_CLIENT_SECRET,
        "audience": "https://api.us1.fga.dev/",
        "grant_type": "client_credentials",
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print("✓ FGA access token alındı")
    return token


# ──────────────────────────────────────────────────────────
# Model oluşturma
# ──────────────────────────────────────────────────────────
async def create_model(client: httpx.AsyncClient, token: str) -> str:
    url = f"{FGA_API_URL}/stores/{FGA_STORE_ID}/authorization-models"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = await client.post(url, json=AUTHORIZATION_MODEL, headers=headers)

    if resp.status_code not in (200, 201):
        print(f"✗ Model oluşturulamadı: {resp.status_code} {resp.text}")
        sys.exit(1)

    model_id = resp.json()["authorization_model_id"]
    print(f"✓ Authorization model oluşturuldu: {model_id}")
    return model_id


# ──────────────────────────────────────────────────────────
# Tuple'ları yaz — seed data'daki workspace + approver'lar
# ──────────────────────────────────────────────────────────
async def write_initial_tuples(client: httpx.AsyncClient, token: str, model_id: str):
    """
    DB'deki workspace ve approver'lar için FGA tuple'larını oluştur.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://approvalkit:approvalkit@localhost:5432/approvalkit",
    )
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    tuples = []

    async with session_factory() as session:
        workspaces = (await session.execute(text("SELECT id FROM workspaces"))).fetchall()
        approvers  = (await session.execute(text("SELECT id, auth0_user_id FROM approvers"))).fetchall()
        rules      = (await session.execute(text("SELECT id, workspace_id FROM rules"))).fetchall()

        for (ws_id,) in workspaces:
            # Her approver → workspace'te approver rolü
            for (ap_id, auth0_uid) in approvers:
                user_fga = f"user:{auth0_uid}"
                tuples.append({"user": user_fga, "relation": "approver", "object": f"workspace:{ws_id}"})

            # İlk approver (CFO) → workspace admin
            if approvers:
                first_uid = approvers[0][1]
                tuples.append({"user": f"user:{first_uid}", "relation": "admin", "object": f"workspace:{ws_id}"})

        # Her rule → workspace bağlantısı
        for (rule_id, ws_id) in rules:
            tuples.append({"user": f"workspace:{ws_id}", "relation": "workspace", "object": f"rule:{rule_id}"})

    await engine.dispose()

    if not tuples:
        print("⚠  Veritabanında workspace/approver bulunamadı, tuple yazılmadı")
        return

    url = f"{FGA_API_URL}/stores/{FGA_STORE_ID}/write"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # FGA max 10 tuple/request — chunk'lara böl
    chunk_size = 10
    written = 0
    for i in range(0, len(tuples), chunk_size):
        chunk = tuples[i:i + chunk_size]
        resp = await client.post(url, json={
            "writes": {"tuple_keys": chunk},
            "authorization_model_id": model_id,
        }, headers=headers)
        if resp.status_code not in (200, 201):
            print(f"  ⚠  Tuple yazma hatası (chunk {i}): {resp.status_code} {resp.text}")
        else:
            written += len(chunk)

    print(f"✓ {written} FGA tuple yazıldı")


# ──────────────────────────────────────────────────────────
# .env güncelleme
# ──────────────────────────────────────────────────────────
def update_env(model_id: str):
    with open(ENV_FILE, "r") as f:
        content = f.read()

    def set_var(text, key, value):
        pattern = rf"^{key}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, text, re.MULTILINE):
            return re.sub(pattern, replacement, text, flags=re.MULTILINE)
        return text + f"\n{replacement}"

    content = set_var(content, "FGA_STORE_ID", FGA_STORE_ID)
    content = set_var(content, "FGA_MODEL_ID", model_id)

    with open(ENV_FILE, "w") as f:
        f.write(content)

    print(f"✓ .env güncellendi (FGA_STORE_ID + FGA_MODEL_ID)")


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────
async def main():
    print("\n── ApprovalKit FGA Setup ──\n")

    if not FGA_STORE_ID:
        print("✗ FGA_STORE_ID .env'de boş!")
        print("  → https://dashboard.fga.dev adresinde bir store oluştur")
        print("  → Store ID'yi .env'e FGA_STORE_ID=... olarak ekle")
        sys.exit(1)

    print(f"  Store  : {FGA_STORE_ID}")
    print(f"  API URL: {FGA_API_URL}\n")

    async with httpx.AsyncClient(timeout=30) as client:
        token = await get_fga_token(client)
        model_id = await create_model(client, token)
        await write_initial_tuples(client, token, model_id)

    update_env(model_id)

    print(f"\n✓ Setup tamamlandı!")
    print(f"  FGA_STORE_ID={FGA_STORE_ID}")
    print(f"  FGA_MODEL_ID={model_id}")
    print(f"\n  Şimdi 'docker compose restart api worker' çalıştır.\n")


if __name__ == "__main__":
    asyncio.run(main())
