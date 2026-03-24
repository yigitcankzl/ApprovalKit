import httpx
from loguru import logger

from api.config import get_settings

settings = get_settings()


class TokenVaultService:
    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_CLIENT_ID
        self.client_secret = settings.AUTH0_CLIENT_SECRET

    async def get_management_token(self) -> str | None:
        if not self.domain:
            return None

        url = f"https://{self.domain}/oauth/token"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "audience": settings.AUTH0_MGMT_API_AUDIENCE,
                    "grant_type": "client_credentials",
                },
            )
            response.raise_for_status()
            return response.json().get("access_token")

    async def list_connections(self) -> list[dict]:
        token = await self.get_management_token()
        if not token:
            return []

        url = f"https://{self.domain}/api/v2/connections"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"strategy": "oauth2"},
            )
            response.raise_for_status()
            return response.json()

    async def execute_action(
        self, connection_id: str, user_id: str, access_token: str, action: str, params: dict
    ) -> dict:
        """
        Execute an action using the token obtained from Token Vault.
        The token never reaches the agent - the platform executes directly.
        """
        logger.info(
            f"Executing action {action} on connection {connection_id} "
            f"for user {user_id} with params {params}"
        )

        # In production, this would use the access_token to call the target service.
        # Token Vault provides just-in-time, scoped, short-lived tokens.
        return {
            "success": True,
            "connection_id": connection_id,
            "action": action,
            "params": params,
        }

    async def revoke_connection(self, connection_id: str) -> bool:
        token = await self.get_management_token()
        if not token:
            logger.warning("Cannot revoke: no management token")
            return False

        url = f"https://{self.domain}/api/v2/connections/{connection_id}"
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"is_domain_connection": False, "enabled_clients": []},
            )
            return response.status_code == 200


token_vault_service = TokenVaultService()
