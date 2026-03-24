"""
Connections management routes
==============================
Manage ServiceConnections and their encrypted credentials.

POST /api/v1/connections/{id}/credentials  — store encrypted credentials
GET  /api/v1/connections                   — list connections (no creds exposed)
GET  /api/v1/connections/{id}              — single connection detail
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.connection import ServiceConnection
from api.services.token_vault import encrypt_credentials, decrypt_credentials

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


class StoreCredentialsRequest(BaseModel):
    credentials: dict


def _conn_to_dict(c: ServiceConnection) -> dict:
    return {
        "id":              str(c.id),
        "name":            c.name,
        "slug":            c.slug,
        "service":         c.service,
        "actions":         c.actions or [],
        "has_credentials": c.credentials_enc is not None,
        "is_active":       c.is_active,
        "created_at":      c.created_at.isoformat(),
    }


@router.get("")
async def list_connections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.is_active.is_(True))
        .order_by(ServiceConnection.name)
    )
    return [_conn_to_dict(c) for c in result.scalars().all()]


@router.get("/{connection_id}")
async def get_connection(connection_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _conn_to_dict(conn)


@router.post("/{connection_id}/credentials", status_code=200)
async def store_credentials(
    connection_id: str,
    body: StoreCredentialsRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Encrypt and store credentials for a connection.
    Credentials never returned in any response — write-only.

    Example body for Stripe:
        {"credentials": {"api_key": "sk_test_..."}}

    Example body for GitHub:
        {"credentials": {"token": "ghp_...", "owner": "myorg", "repo": "myrepo"}}
    """
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.credentials_enc = encrypt_credentials(body.credentials)
    await db.commit()

    return {
        "status":  "stored",
        "connection": conn.name,
        "service":    conn.service,
        "keys":    list(body.credentials.keys()),  # confirm what was stored, never values
    }


@router.delete("/{connection_id}/credentials", status_code=200)
async def delete_credentials(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.credentials_enc = None
    await db.commit()
    return {"status": "cleared", "connection": conn.name}
