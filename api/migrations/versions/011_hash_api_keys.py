"""Hash existing plaintext API keys (workspace + agent).

Revision ID: 011
Revises: 010
"""
import hashlib
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def upgrade():
    conn = op.get_bind()

    # Hash workspace API keys
    rows = conn.execute(sa.text("SELECT id, api_key FROM workspaces WHERE api_key IS NOT NULL"))
    for row in rows:
        ws_id, key = row
        if key and len(key) != 64:  # Not already a SHA256 hash
            hashed = _hash(key)
            conn.execute(
                sa.text("UPDATE workspaces SET api_key = :h WHERE id = :id"),
                {"h": hashed, "id": ws_id},
            )

    # Hash agent API keys
    rows = conn.execute(sa.text("SELECT id, api_key FROM registered_agents WHERE api_key IS NOT NULL"))
    for row in rows:
        agent_id, key = row
        if key and len(key) != 64:  # Not already a SHA256 hash
            hashed = _hash(key)
            conn.execute(
                sa.text("UPDATE registered_agents SET api_key = :h WHERE id = :id"),
                {"h": hashed, "id": agent_id},
            )


def downgrade():
    pass  # Cannot reverse a hash — keys must be regenerated
