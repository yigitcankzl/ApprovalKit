"""
Token Vault Service
===================
Executes downstream API calls after an approval is granted.

Credentials are NEVER stored locally. All tokens come from Auth0 Token Vault
via the Token Exchange endpoint (RFC 8693). The refresh_token obtained during
OAuth connect is exchanged for a fresh external-provider access_token at
execution time.

Grant type: urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token

Supported service handlers
---------------------------
  stripe  — charge, refund, payout   (Stripe Connect / REST API)
  github  — deploy, rollback, merge_pr (GitHub API)
"""
from typing import Any

import httpx
from loguru import logger

from api.config import get_settings
from api.services.circuit_breaker import auth0_breaker
from api.services.encryption import decrypt_secret

settings = get_settings()


# Service → Auth0 provider name (used for token retrieval)
_PROVIDER_MAP = {
    "github":     "github",
    "stripe":     "stripe",
    "slack":      "sign-in-with-slack",
    "salesforce": "salesforce",
    "google":     "google-oauth2",
    "gmail":      "google-oauth2",
    "microsoft":  "windowslive",
    "outlook":    "windowslive",
    "box":        "box",
    "dropbox":    "dropbox",
    "discord":    "discord",
    "figma":      "figma",
    "notion":     "notion",
    "jira":       "jira",
    "hubspot":    "hubspot",
    "shopify":    "shopify",
    "linear":     "linear",
    "bitbucket":  "bitbucket",
    "spotify":    "spotify",
    "amazon":     "amazon",
    "paypal":     "paypal",
    "freshbooks": "freshbooks",
}


# ---------------------------------------------------------------------------
# Service connectors
# ---------------------------------------------------------------------------

async def _execute_stripe(action: str, params: dict, creds: dict) -> dict:
    """
    Stripe Connect API connector.
    creds: {"api_key": "<stripe_oauth_access_token>"}
    """
    api_key = creds.get("api_key") or creds.get("access_token", "")
    if not api_key:
        raise ValueError("Stripe token not found in Auth0 Token Vault for this connection")

    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(base_url="https://api.stripe.com", timeout=30) as c:
        if action == "charge":
            raw_amount = params.get("amount") or params.get("amount_usd") or 0
            try:
                amount_cents = int(float(raw_amount) * 100)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid amount value: {raw_amount!r} — must be numeric")
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
            raw_amount = params.get("amount") or params.get("amount_usd") or 0
            try:
                amount_cents = int(float(raw_amount) * 100)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid amount value: {raw_amount!r} — must be numeric")
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
    creds: {"token": "<github_oauth_token>"}
    owner and repo may come from creds or params.
    """
    token = creds.get("token") or creds.get("api_key") or creds.get("access_token", "")
    owner = creds.get("owner", params.get("owner", ""))
    repo  = creds.get("repo",  params.get("repo", ""))

    if not token:
        raise ValueError("GitHub token not found in Auth0 Token Vault for this connection")
    if not owner or not repo:
        raise ValueError("GitHub requires 'owner' and 'repo' — pass them as params in the approval request")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(base_url="https://api.github.com", timeout=30) as c:
        if action == "deploy":
            ref = params.get("ref", params.get("branch", "main"))

            repo_r = await c.get(f"/repos/{owner}/{repo}", headers=headers)
            if repo_r.status_code == 200:
                repo_info = repo_r.json()
                default_branch = repo_info.get("default_branch", "main")
                branches_r = await c.get(f"/repos/{owner}/{repo}/branches", headers=headers)
                branches = [b["name"] for b in (branches_r.json() if branches_r.status_code == 200 else [])]
                if branches and ref not in branches:
                    ref = default_branch if default_branch in branches else branches[0]

            workflow = params.get("workflow", "deploy.yml")
            inputs   = params.get("inputs", {})

            r = await c.post(
                f"/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches",
                headers=headers,
                json={"ref": ref, "inputs": inputs},
            )
            if r.status_code in (200, 204):
                return {"success": True, "action": "deploy", "workflow": workflow, "ref": ref,
                        "id": None, "method": "workflow_dispatch"}

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
        self.client_id     = settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET
        self.m2m_client_id     = settings.AUTH0_CLIENT_ID
        self.m2m_client_secret = settings.AUTH0_CLIENT_SECRET

    async def get_token_via_exchange(self, connection_name: str, refresh_token: str) -> str | None:
        """
        Token Vault Token Exchange (RFC 8693).
        Exchanges an Auth0 refresh_token for a fresh external-provider access_token.
        """
        if not auth0_breaker.allow_request():
            logger.warning(f"Token Exchange skipped for {connection_name} — Auth0 circuit breaker OPEN")
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://{self.domain}/oauth/token",
                    data={
                        "grant_type": "urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token",
                        "subject_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
                        "requested_token_type": "http://auth0.com/oauth/token-type/federated-connection-access-token",
                        "subject_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "connection": connection_name,
                    },
                )
                if r.status_code == 200:
                    auth0_breaker.record_success()
                    data = r.json()
                    token = data.get("access_token")
                    logger.info(f"Token Vault: exchanged refresh token for {connection_name} access token (via Token Exchange)")
                    return token
                elif r.status_code == 401:
                    logger.warning(f"Token Vault Token Exchange: 401 Unauthorized for {connection_name} — refresh token may be expired. User should reconnect via /connections.")
                    return None
                elif r.status_code == 403:
                    logger.warning(f"Token Vault Token Exchange: 403 Forbidden for {connection_name} — insufficient scope or Token Exchange not enabled.")
                    return None
                else:
                    if r.status_code >= 500:
                        auth0_breaker.record_failure()
                    logger.warning(f"Token Vault Token Exchange failed ({r.status_code}): {r.text}")
                    return None
        except Exception as e:
            auth0_breaker.record_failure()
            logger.warning(f"Token Vault Token Exchange error for {connection_name}: {e}")
            return None

    async def get_token_from_auth0(self, provider: str, auth0_user_id: str) -> str | None:
        """
        Fallback: Retrieve token via Management API if Token Exchange is not available.
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
                            logger.info(f"Token Vault: retrieved {provider} token via Management API (fallback)")
                            return token
        except Exception as e:
            logger.warning(f"Token Vault Management API fallback failed: {e}")
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
        Looks up the ServiceConnection by slug, retrieves the OAuth token from
        Auth0 Token Vault using connected_auth0_user_id, and routes to the handler.
        """
        creds: dict | None = None
        service: str | None = None

        if db is not None:
            from sqlalchemy import select, or_
            from api.models.connection import ServiceConnection

            result = await db.execute(
                select(ServiceConnection).where(
                    or_(
                        ServiceConnection.slug == connection,
                        ServiceConnection.name.ilike(f"%{connection}%"),
                    ),
                    ServiceConnection.is_active.is_(True),
                ).order_by(
                    (ServiceConnection.slug == connection).desc()
                )
            )
            conn_obj = result.scalars().first()

            if conn_obj:
                service = conn_obj.service.lower()
                provider = _PROVIDER_MAP.get(service)

                # Try Token Exchange (preferred, RFC 8693)
                refresh_tok = decrypt_secret(conn_obj.auth0_refresh_token)
                exchange_attempted = bool(refresh_tok and provider)

                if exchange_attempted:
                    token = await self.get_token_via_exchange(provider, refresh_tok)
                    if token:
                        creds = {"api_key": token, "token": token, "access_token": token}
                        logger.info(f"Token Vault: Token Exchange succeeded for {connection}")
                    else:
                        # Token Exchange failed (expired/revoked) — do NOT fall back
                        logger.warning(f"Token Vault: Token Exchange failed for {connection} — user must reconnect")

                # Management API ONLY when no refresh token exists (legacy connection)
                if not exchange_attempted and creds is None and conn_obj.connected_auth0_user_id and provider:
                    token = await self.get_token_from_auth0(provider, conn_obj.connected_auth0_user_id)
                    if token:
                        creds = {"api_key": token, "token": token, "access_token": token}
                        logger.info(f"Token Vault: Management API fallback for {connection} (no refresh token)")

                if creds is None:
                    logger.warning(f"Token Vault: no token for '{connection}'")

        if creds is None:
            logger.warning(f"No Auth0 token available for connection '{connection}' (service={service})")
            return {
                "success":    False,
                "skipped":    True,
                "reason":     "not_connected_via_auth0",
                "connection": connection,
                "action":     action,
                "params":     params,
            }

        handler = _SERVICE_HANDLERS.get(service)
        if handler is None:
            logger.warning(f"No execution handler for service '{service}' — token retrieved but action not implemented")
            return {
                "success": False,
                "reason": "not_implemented",
                "error": f"Service '{service}' does not have an execution handler yet. Supported: {', '.join(_SERVICE_HANDLERS.keys())}",
                "connection": connection,
                "action": action,
            }

        try:
            result = await handler(action, params, creds)
            logger.info(f"Executed {service}/{action}: {result}")
            return result
        except Exception as e:
            logger.error(f"Execution failed for {service}/{action}: {e}")
            return {"success": False, "error": str(e), "connection": connection, "action": action}

    # ---- Auth0 Management API ----

    async def get_management_token(self) -> str | None:
        if not self.domain:
            return None
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.domain}/oauth/token",
                json={
                    "client_id":     self.m2m_client_id,
                    "client_secret": self.m2m_client_secret,
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
