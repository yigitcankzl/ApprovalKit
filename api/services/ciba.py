import asyncio
import re
import httpx
from loguru import logger

from api.config import get_settings

settings = get_settings()

_CIBA_MSG_ALLOWED = re.compile(r"[^A-Za-z0-9 +\-_.,:#]")


def _sanitize_binding_message(msg: str, max_len: int = 256) -> str:
    """Strip characters not allowed by Auth0 CIBA binding_message."""
    sanitized = _CIBA_MSG_ALLOWED.sub("", msg)
    return sanitized[:max_len]


class CIBAService:
    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_CLIENT_SECRET

    async def initiate_ciba_request(
        self, user_id: str, binding_message: str, scope: str = "openid"
    ) -> dict:
        if not self.domain:
            logger.warning("Auth0 domain not configured, returning mock CIBA response")
            return {"auth_req_id": "mock_auth_req_id", "expires_in": 300, "interval": 5}

        url = f"https://{self.domain}/bc-authorize"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "login_hint": f'{{"format":"iss_sub","iss":"https://{self.domain}/","sub":"{user_id}"}}',
                    "binding_message": _sanitize_binding_message(binding_message),
                    "scope": scope,
                },
            )
            if response.status_code != 200:
                logger.error(f"CIBA bc-authorize failed {response.status_code}: {response.text}")
            response.raise_for_status()
            return response.json()

    async def poll_ciba_token(self, auth_req_id: str, timeout: int = 300) -> dict:
        if not self.domain:
            logger.warning("Auth0 domain not configured, returning mock approval")
            return {"status": "approved", "access_token": "mock_token"}

        url = f"https://{self.domain}/oauth/token"
        interval = settings.CIBA_POLL_INTERVAL
        elapsed = 0

        while elapsed < timeout:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    data={
                        "grant_type": "urn:openid:params:grant-type:ciba",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_req_id": auth_req_id,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return {"status": "approved", "access_token": data.get("access_token")}

                error_data = response.json()
                error = error_data.get("error")

                if error == "authorization_pending":
                    await asyncio.sleep(interval)
                    elapsed += interval
                    interval = min(interval * 2, settings.CIBA_MAX_POLL_INTERVAL)
                    continue
                elif error == "slow_down":
                    interval = min(interval * 2, settings.CIBA_MAX_POLL_INTERVAL)
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
