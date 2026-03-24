import httpx
from api.config import get_settings

settings = get_settings()

FGA_MODEL = """
model
  schema 1.1

type user

type workspace
  relations
    define admin: [user]
    define approver: [user]
    define agent_owner: [user]
    define viewer: [user]

type audit_log
  relations
    define workspace: [workspace]
    define owner: [user]
    define agent: [user]
    define can_read: admin from workspace
                 or (approver from workspace and owner)
                 or (agent_owner from workspace and agent)
                 or viewer from workspace

type rule
  relations
    define workspace: [workspace]
    define can_read: admin from workspace or agent_owner from workspace
    define can_write: admin from workspace
"""


class FGAClient:
    def __init__(self):
        self.api_url = settings.FGA_API_URL
        self.store_id = settings.FGA_STORE_ID
        self.model_id = settings.FGA_MODEL_ID

    def _base_url(self) -> str:
        return f"{self.api_url}/stores/{self.store_id}"

    async def check(self, user: str, relation: str, obj: str) -> bool:
        if not self.api_url or not self.store_id:
            return True  # FGA not configured, allow all

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url()}/check",
                json={
                    "tuple_key": {
                        "user": user,
                        "relation": relation,
                        "object": obj,
                    },
                    "authorization_model_id": self.model_id,
                },
            )
            if response.status_code == 200:
                return response.json().get("allowed", False)
            return False

    async def write_tuple(self, user: str, relation: str, obj: str):
        if not self.api_url or not self.store_id:
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base_url()}/write",
                json={
                    "writes": {
                        "tuple_keys": [
                            {
                                "user": user,
                                "relation": relation,
                                "object": obj,
                            }
                        ]
                    },
                    "authorization_model_id": self.model_id,
                },
            )

    async def delete_tuple(self, user: str, relation: str, obj: str):
        if not self.api_url or not self.store_id:
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base_url()}/write",
                json={
                    "deletes": {
                        "tuple_keys": [
                            {
                                "user": user,
                                "relation": relation,
                                "object": obj,
                            }
                        ]
                    },
                    "authorization_model_id": self.model_id,
                },
            )

    async def check_audit_access(self, user_id: str, log_id: str) -> bool:
        return await self.check(f"user:{user_id}", "can_read", f"audit_log:{log_id}")

    async def check_rule_read(self, user_id: str, rule_id: str) -> bool:
        return await self.check(f"user:{user_id}", "can_read", f"rule:{rule_id}")

    async def check_rule_write(self, user_id: str, rule_id: str) -> bool:
        return await self.check(f"user:{user_id}", "can_write", f"rule:{rule_id}")


fga_client = FGAClient()
