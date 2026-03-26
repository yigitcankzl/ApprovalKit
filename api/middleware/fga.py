"""
FGA FastAPI dependency helpers
================================
Enforce fine-grained authorization via Auth0 FGA.

The caller's identity is taken from the `X-Fga-User` header (format: `auth0|<sub>`).

When FGA_STORE_ID is not configured, all checks are skipped (dev mode).
When FGA IS configured and header is missing, the request is DENIED (fail-closed).
"""
from fastapi import Header, HTTPException, Request

from api.config import get_settings
from api.services.fga import fga_client

settings = get_settings()
_fga_configured = bool(settings.FGA_STORE_ID and settings.FGA_API_URL)


def _require_fga_user(x_fga_user: str | None) -> str | None:
    """If FGA is configured, require the header. Skip check if FGA is off."""
    if not _fga_configured:
        return None  # FGA not set up — allow all (dev mode)
    if not x_fga_user:
        raise HTTPException(status_code=403, detail="FGA: X-Fga-User header required")
    return x_fga_user


async def require_workspace_admin(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    user = _require_fga_user(x_fga_user)
    if not user:
        return

    workspace_id = request.query_params.get("workspace_id") or request.path_params.get("workspace_id")
    if not workspace_id:
        return

    allowed = await fga_client.check_workspace_role(user, "admin", workspace_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: admin role required")


async def require_rule_read(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    user = _require_fga_user(x_fga_user)
    if not user:
        return

    rule_id = request.path_params.get("rule_id")
    if not rule_id:
        return

    allowed = await fga_client.check_rule_read(user, rule_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: read access denied for this rule")


async def require_rule_write(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    user = _require_fga_user(x_fga_user)
    if not user:
        return

    rule_id = request.path_params.get("rule_id")
    if not rule_id:
        return

    allowed = await fga_client.check_rule_write(user, rule_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: write access denied for this rule")


async def require_audit_read(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    user = _require_fga_user(x_fga_user)
    if not user:
        return

    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        return

    is_admin = await fga_client.check_workspace_role(user, "admin", workspace_id)
    is_viewer = await fga_client.check_workspace_role(user, "viewer", workspace_id)

    if not (is_admin or is_viewer):
        raise HTTPException(status_code=403, detail="FGA: audit read access denied")
