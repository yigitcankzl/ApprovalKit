import asyncio
import re
import httpx
from loguru import logger

from api.config import get_settings
from api.services.circuit_breaker import auth0_breaker

settings = get_settings()

_CIBA_MSG_ALLOWED = re.compile(r"[^A-Za-z0-9 +\-_.,]")


def _backoff(interval: int) -> int:
    """Double the interval up to CIBA_MAX_POLL_INTERVAL."""
    return min(interval * 2, settings.CIBA_MAX_POLL_INTERVAL)


def _sanitize_binding_message(msg: str, max_len: int = 64) -> str:
    """Strip characters not allowed by Auth0 CIBA binding_message (max 64 chars per spec)."""
    sanitized = _CIBA_MSG_ALLOWED.sub("", msg)
    return sanitized[:max_len]


class CIBAService:
    async def initiate_ciba_request(
        self, user_id: str, binding_message: str, scope: str = "openid",
        *, domain: str = "", client_id: str = "", client_secret: str = "",
    ) -> dict:
        domain = domain or settings.AUTH0_DOMAIN
        client_id = client_id or settings.AUTH0_CLIENT_ID
        client_secret = client_secret or settings.AUTH0_CLIENT_SECRET

        if not domain:
            raise RuntimeError("AUTH0_DOMAIN is not configured — cannot send CIBA push notification")

        if not auth0_breaker.allow_request():
            raise RuntimeError(f"CIBA skipped — Auth0 circuit breaker OPEN (will retry in {auth0_breaker.reset_timeout}s)")

        if "openid" not in scope.split():
            scope = f"openid {scope}"

        url = f"https://{domain}/bc-authorize"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "login_hint": f'{{"format":"iss_sub","iss":"https://{domain}/","sub":"{user_id}"}}',
                    "binding_message": _sanitize_binding_message(binding_message),
                    "scope": scope,
                },
            )
            if response.status_code != 200:
                if response.status_code >= 500:
                    auth0_breaker.record_failure()
                logger.error(f"CIBA bc-authorize failed {response.status_code}: {response.text}")
                response.raise_for_status()
            auth0_breaker.record_success()
            return response.json()

    async def poll_ciba_token(
        self, auth_req_id: str, timeout: int = 300,
        *, domain: str = "", client_id: str = "", client_secret: str = "",
    ) -> dict:
        domain = domain or settings.AUTH0_DOMAIN
        client_id = client_id or settings.AUTH0_CLIENT_ID
        client_secret = client_secret or settings.AUTH0_CLIENT_SECRET

        url = f"https://{domain}/oauth/token"
        interval = settings.CIBA_POLL_INTERVAL
        elapsed = 0

        while elapsed < timeout:
            if not auth0_breaker.allow_request():
                logger.warning("CIBA poll skipped — Auth0 circuit breaker OPEN")
                await asyncio.sleep(interval)
                elapsed += interval
                continue
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data={
                        "grant_type": "urn:openid:params:grant-type:ciba",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_req_id": auth_req_id,
                    },
                )

                if response.status_code == 200:
                    auth0_breaker.record_success()
                    data = response.json()
                    return {"status": "approved", "access_token": data.get("access_token")}

                if response.status_code >= 500:
                    auth0_breaker.record_failure()

                if response.status_code == 429:
                    interval = _backoff(interval)
                    await asyncio.sleep(interval)
                    elapsed += interval
                    continue

                error_data = response.json()
                error = error_data.get("error")

                if error == "authorization_pending":
                    await asyncio.sleep(interval)
                    elapsed += interval
                    interval = _backoff(interval)
                    continue
                elif error == "slow_down":
                    interval = _backoff(interval)
                    await asyncio.sleep(interval)
                    elapsed += interval
                    continue
                elif error == "access_denied":
                    return {"status": "rejected"}
                elif error == "expired_token":
                    return {"status": "timeout"}
                else:
                    logger.error(f"CIBA polling error: {error_data}")
                    return {"status": "error", "error": error}

        return {"status": "timeout"}


ciba_service = CIBAService()
