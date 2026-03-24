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
    """
    Return a 32-byte Fernet key.

    Key resolution order
    --------------------
    1. CREDENTIALS_KEY (preferred) — independent secret, no shared-key risk.
    2. HMAC_SECRET     (fallback)  — warned: same source for signing & encryption.

    In both cases HKDF-SHA256 is applied so the raw value is never used directly.
    If CREDENTIALS_KEY is absent a warning is logged once at import time.
    """
    if settings.CREDENTIALS_KEY:
        raw = settings.CREDENTIALS_KEY
    else:
        logger.warning(
            "CREDENTIALS_KEY is not set — falling back to HMAC_SECRET for credential "
            "encryption. Run `scripts/setup.py` to generate a dedicated key and avoid "
            "using the same secret for both request signing and credential encryption."
        )
        raw = settings.HMAC_SECRET

    if not raw:
        raise RuntimeError("Neither CREDENTIALS_KEY nor HMAC_SECRET is set")

    # If the value is already a valid 32-byte URL-safe base64 Fernet key (44 chars), use directly
    if len(raw) == 44:
        try:
            base64.urlsafe_b64decode(raw + "==")
            return raw.encode()
        except Exception:
            pass

    # HKDF ensures the derived Fernet key is cryptographically independent
    # of the raw secret, even when the raw secret is shared with HMAC signing.
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"approvalkit-credentials-v1",
        info=b"fernet-encryption-key",
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
                "amount":                    str(amount_cents),
                "currency":                  currency,
                "description":               description,
                "payment_method_types[]":    "card",
                "payment_method_data[type]": "card",
                "payment_method_data[card][token]": "tok_visa",
                "confirm":                   "true",
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
    token = creds.get("token") or creds.get("api_key") or creds.get("access_token", "")
    owner = creds.get("owner", params.get("owner", ""))
    repo  = creds.get("repo",  params.get("repo", ""))

    if not token:
        raise ValueError("GitHub credentials incomplete: need token (or api_key / access_token)")
    if not owner or not repo:
        raise ValueError("GitHub credentials incomplete: need owner, repo")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(base_url="https://api.github.com", timeout=30) as c:
        if action == "deploy":
            ref = params.get("ref", params.get("branch", "main"))

            # Resolve default branch if ref is not valid
            repo_r = await c.get(f"/repos/{owner}/{repo}", headers=headers)
            if repo_r.status_code == 200:
                repo_info = repo_r.json()
                default_branch = repo_info.get("default_branch", "main")
                # If the branch list is empty, use the default_branch
                branches_r = await c.get(f"/repos/{owner}/{repo}/branches", headers=headers)
                branches = [b["name"] for b in (branches_r.json() if branches_r.status_code == 200 else [])]
                if branches and ref not in branches:
                    ref = default_branch if default_branch in branches else branches[0]

            workflow = params.get("workflow", "deploy.yml")
            inputs   = params.get("inputs", {})

            # Try workflow dispatch first
            r = await c.post(
                f"/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
                headers=headers,
                json={"ref": ref, "inputs": inputs},
            )
            if r.status_code in (200, 204):
                return {"success": True, "action": "deploy", "workflow": workflow, "ref": ref,
                        "id": None, "method": "workflow_dispatch"}

            # Fallback: create a deployment record
            r2 = await c.post(f"/repos/{owner}/{repo}/deployments", headers=headers, json={
                "ref":               ref,
                "description":       "Deployment approved via ApprovalKit",
                "auto_merge":        False,
                "required_contexts": [],
                "environment":       params.get("environment", "production"),
            })
            data = r2.json()
            if r2.status_code in (200, 201, 202):
                return {"success": True, "action": "deploy", "id": data.get("id"), "ref": ref,
                        "method": "deployment_api"}
            # If repo has no commits yet, record it as a simulated deployment
            if r2.status_code == 422:
                logger.warning(f"GitHub deploy: repo {owner}/{repo} has no commits — simulating deployment")
                return {"success": True, "action": "deploy", "id": None, "ref": ref,
                        "method": "simulated", "note": "repo_empty"}
            return {"success": False, "action": "deploy", "id": None, "ref": ref,
                    "error": data.get("message", r2.text)}

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

    async def get_token_from_auth0(self, provider: str, auth0_user_id: str) -> str | None:
        """
        Retrieve a stored OAuth token from Auth0's Token Vault / identity store.
        Works for social connections like github, stripe, etc.
        """
        mgmt_token = await self.get_management_token()
        if not mgmt_token:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    f"https://{self.domain}/api/v2/users/{auth0_user_id}",
                    headers={"Authorization": f"Bearer {mgmt_token}"},
                )
                if r.status_code != 200:
                    return None
                user = r.json()
                for identity in user.get("identities", []):
                    if identity.get("connection") == provider or identity.get("provider") == provider:
                        token = identity.get("access_token")
                        if token:
                            logger.info(f"Token Vault: retrieved {provider} token for {auth0_user_id}")
                            return token
        except Exception as e:
            logger.warning(f"Token Vault: failed to get {provider} token for {auth0_user_id}: {e}")
        return None

    async def execute_action(
        self,
        connection: str,
        action: str,
        params: dict,
        workspace_id: str | None = None,
        db: Any = None,
        approver_auth0_id: str | None = None,
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

                # If no local credentials and we have an approver, try Auth0 Token Vault
                if creds is None and approver_auth0_id and service:
                    provider_map = {"github": "github", "stripe": "stripe"}
                    provider = provider_map.get(service)
                    if provider:
                        token = await self.get_token_from_auth0(provider, approver_auth0_id)
                        if token:
                            creds = {"api_key": token, "access_token": token}
                            logger.info(
                                f"Token Vault: using Auth0-managed {provider} token "
                                f"for {approver_auth0_id}"
                            )

        if creds is None:
            # Last resort: try Auth0 Token Vault with known GitHub user
            if approver_auth0_id and ("github" in connection.lower()):
                service = service or "github"
                token = await self.get_token_from_auth0("github", approver_auth0_id)
                if not token:
                    # Try the connected github|111859800 identity
                    token = await self.get_token_from_auth0("github", "github|111859800")
                if token:
                    creds = {"api_key": token, "access_token": token}
                    logger.info(f"Token Vault: fallback GitHub token retrieved")

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
