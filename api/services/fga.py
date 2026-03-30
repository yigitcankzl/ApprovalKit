"""
FGA (Fine-Grained Authorization) Client
=========================================
Wraps Auth0 FGA (OpenFGA) API calls.

When FGA_STORE_ID or FGA_API_URL is not configured, every check returns True
so the system degrades gracefully and existing API calls continue to work.

Authorization model (summary)
------------------------------
  workspace
    admin       — full access
    approver    — can read audit logs they own
    agent_owner — can read rules + read their own job logs
    viewer      — read-only audit access

  rule
    can_read    — admin or agent_owner (via workspace)
    can_write   — admin only (via workspace)

  audit_log
    can_read    — admin, viewer, or (approver AND owner)

FGA API authentication
-----------------------
When FGA_CLIENT_ID and FGA_CLIENT_SECRET are set, the client obtains a
short-lived Bearer token from Auth0 and passes it on every FGA call.
The token is cached until it expires (minus 60s buffer).
"""
import asyncio
import time

import httpx
from loguru import logger

from api.config import get_settings

settings = get_settings()



class FGAClient:
    def __init__(self):
        self.api_url  = settings.FGA_API_URL
        self.store_id = settings.FGA_STORE_ID
        self.model_id = settings.FGA_MODEL_ID
        self._token:    str | None = None
        self._token_exp: float = 0.0
        self._lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # Token acquisition (cached, auto-refresh)
    # -----------------------------------------------------------------------

    async def _get_token(self) -> str:
        """Return a valid FGA Bearer token, refreshing if necessary."""
        if not settings.FGA_CLIENT_ID or not settings.FGA_CLIENT_SECRET:
            return ""

        async with self._lock:
            if self._token and time.monotonic() < self._token_exp:
                return self._token

            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.post(
                        "https://fga.us.auth0.com/oauth/token",
                        json={
                            "client_id":     settings.FGA_CLIENT_ID,
                            "client_secret": settings.FGA_CLIENT_SECRET,
                            "audience":      f"{self.api_url}/",
                            "grant_type":    "client_credentials",
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
                    self._token     = data["access_token"]
                    expires_in      = data.get("expires_in", 3600)
                    self._token_exp = time.monotonic() + expires_in - 60
                    return self._token
            except Exception as e:
                logger.warning(f"FGA token acquisition failed: {e}")
                return ""

    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _base_url(self) -> str:
        return f"{self.api_url}/stores/{self.store_id}"

    def _configured(self) -> bool:
        return bool(self.api_url and self.store_id)

    def _warn_if_misconfigured(self) -> None:
        """Log a startup warning when partial FGA config is detected."""
        has_url   = bool(self.api_url)
        has_store = bool(self.store_id)
        if has_url != has_store:
            logger.warning(
                "FGA is partially configured (FGA_API_URL=%s, FGA_STORE_ID=%s). "
                "All checks will DENY until both are set.",
                "set" if has_url else "missing",
                "set" if has_store else "missing",
            )

    # -----------------------------------------------------------------------
    # Core check
    # -----------------------------------------------------------------------

    async def check(self, user: str, relation: str, obj: str) -> bool:
        """
        Returns True when the user has the given relation on the object.

        Behaviour by configuration state
        ---------------------------------
        NOT configured (no URL + no store)  → True  (allow-all, FGA disabled)
        PARTIALLY configured                → False (deny — config is broken)
        FULLY configured, API error         → False (fail-closed, safe default)
        FULLY configured, allowed           → True
        """
        if not self._configured():
            # Both missing → FGA intentionally disabled
            if self.api_url or self.store_id:
                # One is set, the other is not → misconfiguration → deny
                logger.warning(
                    f"FGA deny: partial config (api_url={'set' if self.api_url else 'missing'}, "
                    f"store_id={'set' if self.store_id else 'missing'})"
                )
                return False
            return True

        token = await self._get_token()
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"{self._base_url()}/check",
                    headers=self._auth_header(token),
                    json={
                        "tuple_key": {
                            "user":     user,
                            "relation": relation,
                            "object":   obj,
                        },
                        "authorization_model_id": self.model_id or None,
                    },
                )
                if r.status_code == 200:
                    return r.json().get("allowed", False)
                # 401 — token may have expired, clear cache and retry once
                if r.status_code == 401:
                    self._token = None
                    token = await self._get_token()
                    r2 = await c.post(
                        f"{self._base_url()}/check",
                        headers=self._auth_header(token),
                        json={
                            "tuple_key": {
                                "user": user, "relation": relation, "object": obj,
                            },
                        },
                    )
                    if r2.status_code == 200:
                        return r2.json().get("allowed", False)
                    logger.warning(f"FGA retry after 401 also failed ({r2.status_code}) — denying access (fail-closed)")
                    return False
                logger.warning(f"FGA check returned {r.status_code}: {r.text[:200]}")
                return False
        except Exception as e:
            logger.warning(f"FGA check error ({user} {relation} {obj}): {e}")
            return False

    # -----------------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------------

    async def check_rule_read(self, user_id: str, rule_id: str) -> bool:
        return await self.check(f"user:{user_id}", "can_read", f"rule:{rule_id}")

    async def check_rule_write(self, user_id: str, rule_id: str) -> bool:
        return await self.check(f"user:{user_id}", "can_write", f"rule:{rule_id}")

    async def check_workspace_role(self, user_id: str, role: str, workspace_id: str) -> bool:
        return await self.check(f"user:{user_id}", role, f"workspace:{workspace_id}")

    # -----------------------------------------------------------------------
    # Write tuples (for Auth0 Actions integration)
    # -----------------------------------------------------------------------

    async def write_tuple(self, user: str, relation: str, obj: str) -> bool:
        """
        Write an FGA tuple (user, relation, object).

        Used by Auth0 post-login Action to sync user roles automatically.
        Returns True on success, False on failure or when FGA is not configured.
        """
        if not self._configured():
            logger.info(f"FGA write skipped (not configured): {user} {relation} {obj}")
            return False

        token = await self._get_token()
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"{self._base_url()}/write",
                    headers=self._auth_header(token),
                    json={
                        "writes": {
                            "tuple_keys": [
                                {"user": user, "relation": relation, "object": obj}
                            ]
                        },
                        "authorization_model_id": self.model_id or None,
                    },
                )
                if r.status_code == 200:
                    logger.info(f"FGA tuple written: {user} {relation} {obj}")
                    return True
                # 422 = tuple already exists — treat as success
                if r.status_code == 422:
                    logger.debug(f"FGA tuple already exists: {user} {relation} {obj}")
                    return True
                logger.warning(f"FGA write failed ({r.status_code}): {r.text[:200]}")
                return False
        except Exception as e:
            logger.warning(f"FGA write error ({user} {relation} {obj}): {e}")
            return False

    # -----------------------------------------------------------------------
    # List users (for FGA dynamic approval routing)
    # -----------------------------------------------------------------------

    async def list_users(self, relation: str, obj: str) -> list[str]:
        """
        List all users that have the given relation on the object.

        Used by the fga_dynamic approval model to resolve approvers at runtime
        based on FGA relationships instead of static approver lists.

        Returns a list of user identifiers (e.g. ["user:auth0|abc", "user:auth0|def"]).
        Returns empty list when FGA is not configured or on error.
        """
        if not self._configured():
            return []

        token = await self._get_token()
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"{self._base_url()}/list-users",
                    headers=self._auth_header(token),
                    json={
                        "relation": relation,
                        "object": obj,
                        "user_filter": [{"type": "user"}],
                        "authorization_model_id": self.model_id or None,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    users = []
                    for u in data.get("users", []):
                        obj_data = u.get("object", {})
                        user_id = obj_data.get("id", "")
                        user_type = obj_data.get("type", "user")
                        if user_id:
                            users.append(f"{user_type}:{user_id}")
                    return users
                logger.warning(f"FGA list-users failed ({r.status_code}): {r.text[:200]}")
                return []
        except Exception as e:
            logger.warning(f"FGA list-users error ({relation} {obj}): {e}")
            return []


fga_client = FGAClient()
