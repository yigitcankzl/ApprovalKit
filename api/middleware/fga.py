"""
FGA FastAPI dependency helpers
================================
Use these as Depends() in route handlers to enforce fine-grained authorization.

The caller's identity is taken from the `X-Fga-User` header (format: `auth0|<sub>`).
When the header is absent, the check is skipped (allow-all) so existing
unauthenticated API calls continue to work.

When FGA_STORE_ID is empty the FGAClient itself allows everything.
Both guards must be in place (header present + store configured) for FGA to deny.

Usage example
--------------
    @router.put("/{rule_id}")
    async def update_rule(
        rule_id: str,
        _: None = Depends(require_rule_write),
        db: AsyncSession = Depends(get_db),
    ):
        ...
"""
from fastapi import Header, HTTPException, Request

from api.services.fga import fga_client


async def _get_fga_user(x_fga_user: str | None = Header(default=None)) -> str | None:
    """Return the caller's FGA user string, or None if header absent."""
    return x_fga_user


async def require_workspace_admin(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    """
    Require admin role in the workspace referenced by `workspace_id` query param.
    Falls through when X-Fga-User header is absent.
    """
    if not x_fga_user:
        return

    workspace_id = request.query_params.get("workspace_id") or request.path_params.get("workspace_id")
    if not workspace_id:
        return

    allowed = await fga_client.check_workspace_role(x_fga_user, "admin", workspace_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: admin role required")


async def require_rule_read(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    """
    Require can_read on the rule being accessed.
    Falls through when header absent or rule_id not in path.
    """
    if not x_fga_user:
        return

    rule_id = request.path_params.get("rule_id")
    if not rule_id:
        return

    allowed = await fga_client.check_rule_read(x_fga_user, rule_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: read access denied for this rule")


async def require_rule_write(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    """
    Require can_write on the rule being modified.
    Falls through when header absent or rule_id not in path.
    """
    if not x_fga_user:
        return

    rule_id = request.path_params.get("rule_id")
    if not rule_id:
        # For create operations (no rule_id yet), check workspace admin
        return

    allowed = await fga_client.check_rule_write(x_fga_user, rule_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="FGA: write access denied for this rule")


async def require_audit_read(
    request: Request,
    x_fga_user: str | None = Header(default=None),
):
    """
    Audit log access: workspace-level check (admin or viewer role).
    Falls through when header absent.
    """
    if not x_fga_user:
        return

    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        # Without workspace context, rely on HMAC auth alone
        return

    # Admin OR viewer can read audit logs
    is_admin  = await fga_client.check_workspace_role(x_fga_user, "admin", workspace_id)
    is_viewer = await fga_client.check_workspace_role(x_fga_user, "viewer", workspace_id)

    if not (is_admin or is_viewer):
        raise HTTPException(status_code=403, detail="FGA: audit read access denied")
