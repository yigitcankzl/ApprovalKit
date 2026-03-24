"""
Token Vault Service
===================
Manages per-connection credentials (Fernet-encrypted) and executes
downstream API calls after an approval is granted.

Credential storage
------------------
Credentials are stored as Fernet-encrypted JSON in `connections.credentials_enc`.
The encryption key is taken from CREDENTIALS_KEY env var, or derived from
HMAC_SECRET using HKDF-SHA256 when the env var is absent.

Supported service handlers
---------------------------
  stripe  — charge, refund, payout   (Stripe REST API)
  github  — deploy, rollback         (GitHub Actions / Repos API)
"""
import base64
import json
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from loguru import logger

from api.config import get_settings

settings = get_settings()


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _derive_fernet_key() -> bytes:
    """Return a 32-byte Fernet key from CREDENTIALS_KEY or HMAC_SECRET."""
    raw = settings.CREDENTIALS_KEY or settings.HMAC_SECRET
    if not raw:
        raise RuntimeError("Neither CREDENTIALS_KEY nor HMAC_SECRET is set")

    # If the value is already a valid Fernet key (44-char base64), use it directly
    if len(raw) == 44:
        try:
            base64.urlsafe_b64decode(raw + "==")
            return raw.encode()
        except Exception:
            pass

    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"approvalkit-credentials-v1",
        info=b"fernet",
    ).derive(raw.encode())
    return base64.urlsafe_b64encode(derived)


def encrypt_credentials(creds: dict) -> str:
    key = _derive_fernet_key()
    return Fernet(key).encrypt(json.dumps(creds).encode()).decode()


def decrypt_credentials(enc: str) -> dict:
    key = _derive_fernet_key()
    try:
        raw = Fernet(key).decrypt(enc.encode())
        return json.loads(raw)
    except InvalidToken:
        raise ValueError("Invalid or tampered credentials blob")


# ---------------------------------------------------------------------------
# Service connectors
# ---------------------------------------------------------------------------

async def _execute_stripe(action: str, params: dict, creds: dict) -> dict:
    """
    Stripe REST API connector.
    creds: {"api_key": "sk_test_..."}
    """
    api_key = creds.get("api_key", "")
    if not api_key:
        raise ValueError("Stripe api_key not configured for this connection")

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(base_url="https://api.stripe.com", timeout=30) as c:
        if action == "charge":
            # Create a PaymentIntent in test mode
            amount_cents = int(float(params.get("amount", 0)) * 100)
            currency    = params.get("currency", "usd")
            description = params.get("description", f"Charge for {params.get('customer', 'unknown')}")

            r = await c.post("/v1/payment_intents", headers=headers, data={
                "amount":              str(amount_cents),
                "currency":            currency,
                "description":         description,
                "payment_method_data[type]": "card",
                "payment_method_data[card][token]": "tok_visa",
                "confirm":             "true",
                "automatic_payment_methods[enabled]": "false",
            })
            data = r.json()
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Stripe charge failed: {data.get('error', {}).get('message', r.text)}")
            return {
                "success":  True,
                "action":   "charge",
                "id":       data.get("id"),
                "status":   data.get("status"),
                "amount":   data.get("amount"),
                "currency": data.get("currency"),
            }

        elif action == "refund":
            charge_id = params.get("charge_id") or params.get("payment_intent")
            if not charge_id:
                raise ValueError("refund requires 'charge_id' or 'payment_intent' param")
            r = await c.post("/v1/refunds", headers=headers, data={"payment_intent": charge_id})
            data = r.json()
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Stripe refund failed: {data.get('error', {}).get('message', r.text)}")
            return {"success": True, "action": "refund", "id": data.get("id"), "status": data.get("status")}

        elif action == "payout":
            amount_cents = int(float(params.get("amount", 0)) * 100)
            currency     = params.get("currency", "usd")
            r = await c.post("/v1/payouts", headers=headers, data={
                "amount":   str(amount_cents),
                "currency": currency,
            })
            data = r.json()
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Stripe payout failed: {data.get('error', {}).get('message', r.text)}")
            return {"success": True, "action": "payout", "id": data.get("id"), "status": data.get("status")}

        else:
            raise ValueError(f"Unsupported Stripe action: {action}")


async def _execute_github(action: str, params: dict, creds: dict) -> dict:
    """
    GitHub API connector.
    creds: {"token": "ghp_...", "owner": "myorg", "repo": "myrepo"}
    """
    token = creds.get("token", "")
    owner = creds.get("owner", params.get("owner", ""))
    repo  = creds.get("repo",  params.get("repo", ""))

    if not token or not owner or not repo:
        raise ValueError("GitHub credentials incomplete: need token, owner, repo")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(base_url="https://api.github.com", timeout=30) as c:
        if action == "deploy":
            workflow = params.get("workflow", "deploy.yml")
            ref      = params.get("ref", params.get("branch", "main"))
            inputs   = params.get("inputs", {})

            r = await c.post(
                f"/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
                headers=headers,
                json={"ref": ref, "inputs": inputs},
            )
            if r.status_code == 404:
                # Fallback: create a deployment
                r2 = await c.post(f"/repos/{owner}/{repo}/deployments", headers=headers, json={
                    "ref":         ref,
                    "description": f"Deployment approved via ApprovalKit",
                    "auto_merge":  False,
                    "required_contexts": [],
                })
                data = r2.json()
                return {"success": r2.status_code in (200, 201, 202), "action": "deploy",
                        "id": data.get("id"), "ref": ref}
            return {"success": r.status_code in (200, 204), "action": "deploy",
                    "workflow": workflow, "ref": ref}

        elif action == "rollback":
            ref = params.get("ref", params.get("tag", ""))
            if not ref:
                raise ValueError("rollback requires 'ref' or 'tag' param")

            r = await c.post(f"/repos/{owner}/{repo}/deployments", headers=headers, json={
                "ref":         ref,
                "description": "Rollback approved via ApprovalKit",
                "auto_merge":  False,
                "required_contexts": [],
            })
            data = r.json()
            if r.status_code not in (200, 201):
                raise RuntimeError(f"GitHub rollback failed: {data.get('message', r.text)}")
            return {"success": True, "action": "rollback",
                    "deployment_id": data.get("id"), "ref": ref}

        elif action == "merge_pr":
            pr_number = params.get("pr_number") or params.get("number")
            if not pr_number:
                raise ValueError("merge_pr requires 'pr_number' param")
            r = await c.put(f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", headers=headers, json={
                "merge_method": params.get("merge_method", "squash"),
            })
            data = r.json()
            if r.status_code not in (200, 201):
                raise RuntimeError(f"GitHub merge failed: {data.get('message', r.text)}")
            return {"success": True, "action": "merge_pr", "sha": data.get("sha")}

        else:
            raise ValueError(f"Unsupported GitHub action: {action}")


_SERVICE_HANDLERS = {
    "stripe": _execute_stripe,
    "github": _execute_github,
}


# ---------------------------------------------------------------------------
# TokenVaultService
# ---------------------------------------------------------------------------

class TokenVaultService:
    def __init__(self):
        self.domain        = settings.AUTH0_DOMAIN
        self.client_id     = settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_CLIENT_SECRET

    # ---- Credential management ----

    @staticmethod
    def encrypt_credentials(creds: dict) -> str:
        return encrypt_credentials(creds)

    @staticmethod
    def decrypt_credentials(enc: str) -> dict:
        return decrypt_credentials(enc)

    async def store_credentials(self, connection_id: str, creds: dict, db) -> None:
        """Encrypt and persist credentials for a connection."""
        from sqlalchemy import select
        from api.models.connection import ServiceConnection

        enc = encrypt_credentials(creds)
        result = await db.execute(select(ServiceConnection).where(ServiceConnection.id == connection_id))
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError(f"Connection {connection_id} not found")
        conn.credentials_enc = enc
        await db.commit()
        logger.info(f"Credentials stored for connection {conn.name}")

    # ---- Action execution ----

    async def execute_action(
        self,
        connection: str,
        action: str,
        params: dict,
        workspace_id: str | None = None,
        db: Any = None,
    ) -> dict:
        """
        Execute a downstream action after approval.
        Looks up the ServiceConnection by slug name, decrypts credentials,
        routes to the appropriate service handler.
        """
        creds: dict | None = None
        service: str | None = None

        if db is not None:
            from sqlalchemy import select, or_
            from api.models.connection import ServiceConnection

            # Try exact slug match first, then fuzzy name match
            result = await db.execute(
                select(ServiceConnection).where(
                    or_(
                        ServiceConnection.slug == connection,
                        ServiceConnection.name.ilike(f"%{connection}%"),
                    ),
                    ServiceConnection.is_active.is_(True),
                ).order_by(
                    # Prefer exact slug match
                    (ServiceConnection.slug == connection).desc()
                )
            )
            conn_obj = result.scalars().first()

            if conn_obj:
                service = conn_obj.service.lower()
                if conn_obj.credentials_enc:
                    try:
                        creds = decrypt_credentials(conn_obj.credentials_enc)
                    except Exception as e:
                        logger.error(f"Failed to decrypt credentials for {conn_obj.name}: {e}")

        if creds is None:
            logger.warning(
                f"No credentials configured for connection '{connection}' "
                f"(service={service}) — logging action without executing"
            )
            return {
                "success": False,
                "skipped": True,
                "reason": "no_credentials",
                "connection": connection,
                "action": action,
                "params": params,
            }

        handler = _SERVICE_HANDLERS.get(service)
        if handler is None:
            logger.warning(f"No handler for service '{service}'")
            return {"success": False, "reason": f"unsupported_service:{service}"}

        try:
            result = await handler(action, params, creds)
            logger.info(f"Executed {service}/{action}: {result}")
            return result
        except Exception as e:
            logger.error(f"Execution failed for {service}/{action}: {e}")
            return {"success": False, "error": str(e), "connection": connection, "action": action}

    # ---- Auth0 Management API helpers (kept for Token Vault list/revoke) ----

    async def get_management_token(self) -> str | None:
        if not self.domain:
            return None
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/oauth/token",
                json={
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                    "audience":      settings.AUTH0_MGMT_API_AUDIENCE,
                    "grant_type":    "client_credentials",
                },
            )
            response.raise_for_status()
            return response.json().get("access_token")

    async def list_connections(self) -> list[dict]:
        token = await self.get_management_token()
        if not token:
            return []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{self.domain}/api/v2/connections",
                headers={"Authorization": f"Bearer {token}"},
                params={"strategy": "oauth2"},
            )
            response.raise_for_status()
            return response.json()

    async def revoke_connection(self, connection_id: str) -> bool:
        token = await self.get_management_token()
        if not token:
            logger.warning("Cannot revoke: no management token")
            return False
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"https://{self.domain}/api/v2/connections/{connection_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_domain_connection": False, "enabled_clients": []},
            )
            return response.status_code == 200


token_vault_service = TokenVaultService()
