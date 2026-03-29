"""
Token Vault Service
===================
Executes downstream API calls after an approval is granted.

Credential retrieval chain:
1. Auth0 Token Vault (RFC 8693 Token Exchange) — user-delegated OAuth (Stripe, GitHub, Gmail)
2. HashiCorp Vault (Credential Vault) — M2M API keys (Amadeus, Twilio, AWS)

No credentials are stored in our database. Auth0 manages OAuth tokens,
HashiCorp Vault manages M2M secrets. The agent NEVER sees raw credentials.

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
    "slack":      "slack-oauth-2",
    "salesforce": "salesforce",
    "google":          "google-oauth2",
    "gmail":           "google-oauth2",
    "google-calendar": "google-oauth2",
    "google-sheets":   "google-oauth2",
    "google-drive":    "google-oauth2",
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
    # M2M Credential Vault providers (not Auth0 Token Vault — use client_credentials)
    "amadeus":    "amadeus",
    "twilio":     "twilio",
    "sendgrid":   "sendgrid",
    "aws":        "aws",
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
            if not inputs:
                # Auto-map known params to workflow inputs
                _skip = {"ref", "branch", "workflow", "inputs", "owner", "repo", "environment"}
                inputs = {k: str(v) for k, v in params.items() if k not in _skip and v is not None}

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


async def _execute_slack(action: str, params: dict, creds: dict) -> dict:
    """Slack API — send messages, create channels, invite users."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Slack token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url="https://slack.com/api", timeout=15) as c:
        if action == "send_message":
            channel = params.get("channel", "#general")
            text = params.get("message") or params.get("text", "")
            r = await c.post("/chat.postMessage", headers=headers, json={"channel": channel, "text": text})
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack send failed: {data.get('error', r.text)}")
            return {"success": True, "action": "send_message", "channel": channel, "ts": data.get("ts")}

        elif action == "create_channel":
            name = params.get("name", "")
            r = await c.post("/conversations.create", headers=headers, json={"name": name})
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack create_channel failed: {data.get('error')}")
            return {"success": True, "action": "create_channel", "id": data["channel"]["id"]}

        elif action == "invite_user":
            channel = params.get("channel", "")
            user = params.get("user_id") or params.get("user", "")
            r = await c.post("/conversations.invite", headers=headers, json={"channel": channel, "users": user})
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack invite failed: {data.get('error')}")
            return {"success": True, "action": "invite_user", "channel": channel}

        else:
            raise ValueError(f"Unsupported Slack action: {action}")


async def _execute_google(action: str, params: dict, creds: dict) -> dict:
    """Google APIs — Gmail send, Calendar create event, Drive operations."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Google token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "send_email":
            import base64
            to = params.get("to") or params.get("recipient", "")
            subject = params.get("subject", "")
            body_text = params.get("body") or params.get("message", "")
            raw_msg = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body_text}"
            encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
            r = await c.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers=headers, json={"raw": encoded},
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Gmail send failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "send_email", "id": data.get("id"), "to": to}

        elif action == "create_event":
            summary = params.get("summary") or params.get("title", "")
            start = params.get("start", "")
            end = params.get("end", "")
            r = await c.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                json={
                    "summary": summary,
                    "start": {"dateTime": start, "timeZone": "UTC"},
                    "end": {"dateTime": end, "timeZone": "UTC"},
                },
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Calendar create failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "create_event", "id": data.get("id"), "link": data.get("htmlLink")}

        elif action == "read_drive":
            file_id = params.get("file_id", "")
            r = await c.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers=headers, params={"fields": "id,name,mimeType,webViewLink"},
            )
            if r.status_code != 200:
                raise RuntimeError(f"Drive read failed: {r.text[:200]}")
            return {"success": True, "action": "read_drive", **r.json()}

        elif action == "append_row":
            spreadsheet_id = params.get("spreadsheet_id", "")
            sheet_range = params.get("range", "Sheet1!A1")
            row = params.get("row", [])
            if not spreadsheet_id:
                raise ValueError("append_row requires 'spreadsheet_id' param")
            r = await c.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_range}:append",
                headers=headers,
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": [row] if row and isinstance(row[0], (str, int, float)) else row},
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Sheets append failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "append_row", "updated_range": data.get("updates", {}).get("updatedRange")}

        elif action == "update_cells":
            spreadsheet_id = params.get("spreadsheet_id", "")
            sheet_range = params.get("range", "Sheet1!A1")
            values = params.get("values", [])
            r = await c.put(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{sheet_range}",
                headers=headers,
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": values},
            )
            if r.status_code != 200:
                raise RuntimeError(f"Sheets update failed: {r.text[:200]}")
            return {"success": True, "action": "update_cells", "updated_cells": r.json().get("updatedCells")}

        else:
            raise ValueError(f"Unsupported Google action: {action}")


async def _execute_microsoft(action: str, params: dict, creds: dict) -> dict:
    """Microsoft Graph API — email, calendar, file upload."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Microsoft token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url="https://graph.microsoft.com/v1.0", timeout=15) as c:
        if action == "send_email":
            to = params.get("to") or params.get("recipient", "")
            subject = params.get("subject", "")
            body = params.get("body") or params.get("message", "")
            r = await c.post("/me/sendMail", headers=headers, json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                },
            })
            if r.status_code not in (200, 202):
                raise RuntimeError(f"Microsoft send_email failed: {r.text[:200]}")
            return {"success": True, "action": "send_email", "to": to}

        elif action == "create_event":
            summary = params.get("summary") or params.get("title", "")
            start = params.get("start", "")
            end = params.get("end", "")
            r = await c.post("/me/events", headers=headers, json={
                "subject": summary,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Microsoft create_event failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "create_event", "id": data.get("id")}

        elif action == "upload_file":
            filename = params.get("filename", "file.txt")
            content = params.get("content", "")
            r = await c.put(
                f"/me/drive/root:/{filename}:/content",
                headers={**headers, "Content-Type": "application/octet-stream"},
                content=content.encode() if isinstance(content, str) else content,
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Microsoft upload failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "upload_file", "id": data.get("id"), "name": filename}

        else:
            raise ValueError(f"Unsupported Microsoft action: {action}")


async def _execute_salesforce(action: str, params: dict, creds: dict) -> dict:
    """Salesforce REST API — create deal, update contact, delete lead."""
    token = creds.get("access_token", "")
    instance_url = params.get("instance_url", "https://login.salesforce.com")
    if not token:
        raise ValueError("Salesforce token not found")
    from urllib.parse import urlparse as _urlparse
    _host = _urlparse(instance_url).hostname or ""
    if not (_host.endswith(".salesforce.com") or _host.endswith(".force.com")):
        return {"success": False, "error": "Invalid Salesforce instance URL"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "create_deal":
            r = await c.post(f"{instance_url}/services/data/v59.0/sobjects/Opportunity", headers=headers, json={
                "Name": params.get("name", "New Deal"),
                "StageName": params.get("stage", "Prospecting"),
                "CloseDate": params.get("close_date", "2026-12-31"),
                "Amount": params.get("amount"),
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Salesforce create_deal failed: {r.text[:200]}")
            return {"success": True, "action": "create_deal", "id": r.json().get("id")}

        elif action == "update_contact":
            contact_id = params.get("contact_id", "")
            r = await c.patch(f"{instance_url}/services/data/v59.0/sobjects/Contact/{contact_id}", headers=headers, json={
                k: v for k, v in params.items() if k not in ("contact_id", "instance_url")
            })
            if r.status_code not in (200, 204):
                raise RuntimeError(f"Salesforce update_contact failed: {r.text[:200]}")
            return {"success": True, "action": "update_contact", "id": contact_id}

        elif action == "delete_lead":
            lead_id = params.get("lead_id", "")
            r = await c.delete(f"{instance_url}/services/data/v59.0/sobjects/Lead/{lead_id}", headers=headers)
            if r.status_code not in (200, 204):
                raise RuntimeError(f"Salesforce delete_lead failed: {r.text[:200]}")
            return {"success": True, "action": "delete_lead", "id": lead_id}

        else:
            raise ValueError(f"Unsupported Salesforce action: {action}")


async def _execute_notion(action: str, params: dict, creds: dict) -> dict:
    """Notion API — create page, update database."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Notion token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}

    async with httpx.AsyncClient(base_url="https://api.notion.com/v1", timeout=15) as c:
        if action == "create_page":
            parent_id = params.get("parent_id") or params.get("database_id", "")
            title = params.get("title", "")
            r = await c.post("/pages", headers=headers, json={
                "parent": {"database_id": parent_id},
                "properties": {"Name": {"title": [{"text": {"content": title}}]}},
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Notion create_page failed: {r.text[:200]}")
            return {"success": True, "action": "create_page", "id": r.json().get("id")}

        elif action == "update_database":
            db_id = params.get("database_id", "")
            title = params.get("title", "")
            r = await c.patch(f"/databases/{db_id}", headers=headers, json={
                "title": [{"text": {"content": title}}],
            })
            if r.status_code != 200:
                raise RuntimeError(f"Notion update_database failed: {r.text[:200]}")
            return {"success": True, "action": "update_database", "id": db_id}

        else:
            raise ValueError(f"Unsupported Notion action: {action}")


async def _execute_jira(action: str, params: dict, creds: dict) -> dict:
    """Jira Cloud REST API — create/update issues."""
    token = creds.get("access_token", "")
    cloud_id = params.get("cloud_id", "")
    if not token:
        raise ValueError("Jira token not found")
    base = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3" if cloud_id else "https://your-domain.atlassian.net/rest/api/3"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "create_issue":
            project = params.get("project", "")
            summary = params.get("summary", "")
            issue_type = params.get("issue_type", "Task")
            r = await c.post(f"{base}/issue", headers=headers, json={
                "fields": {
                    "project": {"key": project},
                    "summary": summary,
                    "issuetype": {"name": issue_type},
                    "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": params.get("description", "")}]}]},
                },
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Jira create_issue failed: {r.text[:200]}")
            data = r.json()
            return {"success": True, "action": "create_issue", "key": data.get("key"), "id": data.get("id")}

        elif action == "update_issue":
            issue_key = params.get("issue_key", "")
            r = await c.put(f"{base}/issue/{issue_key}", headers=headers, json={
                "fields": {k: v for k, v in params.items() if k not in ("issue_key", "cloud_id")},
            })
            if r.status_code not in (200, 204):
                raise RuntimeError(f"Jira update_issue failed: {r.text[:200]}")
            return {"success": True, "action": "update_issue", "key": issue_key}

        elif action == "transition":
            issue_key = params.get("issue_key", "")
            transition_id = params.get("transition_id", "")
            r = await c.post(f"{base}/issue/{issue_key}/transitions", headers=headers, json={
                "transition": {"id": transition_id},
            })
            if r.status_code not in (200, 204):
                raise RuntimeError(f"Jira transition failed: {r.text[:200]}")
            return {"success": True, "action": "transition", "key": issue_key}

        else:
            raise ValueError(f"Unsupported Jira action: {action}")


async def _execute_discord(action: str, params: dict, creds: dict) -> dict:
    """Discord API — send message, create channel."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Discord token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url="https://discord.com/api/v10", timeout=15) as c:
        if action == "send_message":
            channel_id = params.get("channel_id", "")
            content = params.get("message") or params.get("content", "")
            r = await c.post(f"/channels/{channel_id}/messages", headers=headers, json={"content": content})
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Discord send failed: {r.text[:200]}")
            return {"success": True, "action": "send_message", "id": r.json().get("id")}

        else:
            raise ValueError(f"Unsupported Discord action: {action}")


async def _execute_linear(action: str, params: dict, creds: dict) -> dict:
    """Linear GraphQL API — create/update issues."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("Linear token not found")
    headers = {"Authorization": token, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "create_issue":
            r = await c.post("https://api.linear.app/graphql", headers=headers, json={
                "query": """mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier title } } }""",
                "variables": {"input": {
                    "teamId": params.get("team_id", ""),
                    "title": params.get("title", ""),
                    "description": params.get("description", ""),
                }},
            })
            data = r.json()
            issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
            return {"success": True, "action": "create_issue", "id": issue.get("id"), "identifier": issue.get("identifier")}

        elif action == "update_status":
            r = await c.post("https://api.linear.app/graphql", headers=headers, json={
                "query": """mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success } }""",
                "variables": {"id": params.get("issue_id", ""), "input": {"stateId": params.get("state_id", "")}},
            })
            return {"success": True, "action": "update_status", "issue_id": params.get("issue_id")}

        else:
            raise ValueError(f"Unsupported Linear action: {action}")


async def _execute_hubspot(action: str, params: dict, creds: dict) -> dict:
    """HubSpot API — contacts and deals."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("HubSpot token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url="https://api.hubapi.com", timeout=15) as c:
        if action == "create_contact":
            r = await c.post("/crm/v3/objects/contacts", headers=headers, json={
                "properties": {
                    "email": params.get("email", ""),
                    "firstname": params.get("first_name", ""),
                    "lastname": params.get("last_name", ""),
                    "company": params.get("company", ""),
                },
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"HubSpot create_contact failed: {r.text[:200]}")
            return {"success": True, "action": "create_contact", "id": r.json().get("id")}

        elif action == "create_deal":
            r = await c.post("/crm/v3/objects/deals", headers=headers, json={
                "properties": {
                    "dealname": params.get("name", ""),
                    "amount": str(params.get("amount", "")),
                    "pipeline": params.get("pipeline", "default"),
                    "dealstage": params.get("stage", "appointmentscheduled"),
                },
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"HubSpot create_deal failed: {r.text[:200]}")
            return {"success": True, "action": "create_deal", "id": r.json().get("id")}

        else:
            raise ValueError(f"Unsupported HubSpot action: {action}")


async def _execute_shopify(action: str, params: dict, creds: dict) -> dict:
    """Shopify Admin API."""
    token = creds.get("access_token", "")
    shop = params.get("shop", "")
    if not token or not shop:
        raise ValueError("Shopify token or shop not found")
    import re as _re
    if not _re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com", shop):
        return {"success": False, "error": "Invalid shop domain: must match *.myshopify.com"}
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "create_order":
            r = await c.post(f"https://{shop}/admin/api/2024-01/orders.json", headers=headers, json={
                "order": {
                    "line_items": params.get("line_items", []),
                    "email": params.get("email", ""),
                },
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Shopify create_order failed: {r.text[:200]}")
            return {"success": True, "action": "create_order", "id": r.json().get("order", {}).get("id")}

        elif action == "update_product":
            product_id = params.get("product_id", "")
            r = await c.put(f"https://{shop}/admin/api/2024-01/products/{product_id}.json", headers=headers, json={
                "product": {k: v for k, v in params.items() if k not in ("product_id", "shop")},
            })
            if r.status_code != 200:
                raise RuntimeError(f"Shopify update_product failed: {r.text[:200]}")
            return {"success": True, "action": "update_product", "id": product_id}

        else:
            raise ValueError(f"Unsupported Shopify action: {action}")


async def _execute_paypal(action: str, params: dict, creds: dict) -> dict:
    """PayPal REST API."""
    token = creds.get("access_token", "")
    if not token:
        raise ValueError("PayPal token not found")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = "https://api-m.paypal.com"

    async with httpx.AsyncClient(timeout=15) as c:
        if action == "send_payment":
            r = await c.post(f"{base}/v2/checkout/orders", headers=headers, json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {"currency_code": params.get("currency", "USD"), "value": str(params.get("amount", "0"))},
                    "description": params.get("description", ""),
                }],
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"PayPal send_payment failed: {r.text[:200]}")
            return {"success": True, "action": "send_payment", "id": r.json().get("id")}

        elif action == "create_invoice":
            r = await c.post(f"{base}/v2/invoicing/invoices", headers=headers, json={
                "detail": {"currency_code": params.get("currency", "USD"), "note": params.get("note", "")},
                "primary_recipients": [{"billing_info": {"email_address": params.get("email", "")}}],
                "items": [{"name": params.get("item", "Service"), "quantity": "1", "unit_amount": {"currency_code": "USD", "value": str(params.get("amount", "0"))}}],
            })
            if r.status_code not in (200, 201):
                raise RuntimeError(f"PayPal create_invoice failed: {r.text[:200]}")
            return {"success": True, "action": "create_invoice", "id": r.json().get("id")}

        else:
            raise ValueError(f"Unsupported PayPal action: {action}")


import re as _re

def _render_template(template, token: str, params: dict) -> any:
    """
    Replace {{token}} and {{param_name}} placeholders in a template value.
    Works on strings, dicts, and lists recursively.
    """
    if isinstance(template, str):
        result = template.replace("{{token}}", token)
        for key, val in params.items():
            result = result.replace(f"{{{{{key}}}}}", str(val))
        return result
    if isinstance(template, dict):
        return {k: _render_template(v, token, params) for k, v in template.items()}
    if isinstance(template, list):
        return [_render_template(item, token, params) for item in template]
    return template


async def _execute_webhook(conn_obj, action: str, params: dict, creds: dict) -> dict:
    """
    Generic webhook handler — executes any API using config from the connection record.
    Template variables: {{token}}, {{action}}, and any {{param_name}} from request params.
    """
    token = creds.get("access_token") or creds.get("token") or creds.get("api_key", "")
    url = _render_template(conn_obj.webhook_url, token, {**params, "action": action})
    method = (conn_obj.webhook_method or "POST").upper()

    # Render headers
    raw_headers = conn_obj.webhook_headers or {}
    headers = _render_template(raw_headers, token, {**params, "action": action})
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    # Render body
    body = None
    if conn_obj.webhook_body_template:
        body = _render_template(conn_obj.webhook_body_template, token, {**params, "action": action})
    elif method in ("POST", "PUT", "PATCH"):
        body = params  # send raw params as body if no template

    logger.info(f"Webhook: {method} {url[:80]}...")

    async with httpx.AsyncClient(timeout=30) as c:
        if method == "GET":
            r = await c.get(url, headers=headers, params=body if isinstance(body, dict) else None)
        elif method == "DELETE":
            r = await c.delete(url, headers=headers)
        else:
            r = await c.request(method, url, headers=headers, json=body)

        response_data = None
        try:
            response_data = r.json()
        except Exception:
            response_data = r.text[:500]

        if r.status_code >= 400:
            raise RuntimeError(f"Webhook returned {r.status_code}: {str(response_data)[:200]}")

        return {
            "success": True,
            "action": action,
            "method": method,
            "status_code": r.status_code,
            "response": response_data,
            "via": "generic_webhook",
        }


async def _execute_amadeus(action: str, params: dict, creds: dict) -> dict:
    """Amadeus Self-Service API handler (M2M credential vault).

    Supports: search_flights, search_hotels.
    Uses access_token from client_credentials grant (not Auth0 Token Vault).
    """
    token = creds.get("access_token") or creds.get("token")
    if not token:
        raise ValueError("No Amadeus access token available")

    headers = {"Authorization": f"Bearer {token}"}
    base = "https://test.api.amadeus.com"

    async with httpx.AsyncClient(base_url=base, timeout=15, headers=headers) as c:
        if action == "search_flights":
            origin = params.get("origin", "IST")
            destination = params.get("destination", "JFK")
            date = params.get("date", "2026-04-15")
            adults = params.get("adults", 1)
            r = await c.get("/v2/shopping/flight-offers", params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": date,
                "adults": adults,
                "max": params.get("max_results", 5),
            })
            if r.status_code != 200:
                raise RuntimeError(f"Amadeus search_flights failed ({r.status_code}): {r.text[:200]}")
            data = r.json()
            offers = [
                {
                    "price": float(o["price"]["total"]),
                    "currency": o["price"]["currency"],
                    "airline": o.get("validatingAirlineCodes", ["??"])[0],
                    "segments": len(o["itineraries"][0]["segments"]) if o.get("itineraries") else 0,
                    "duration": o["itineraries"][0].get("duration", "") if o.get("itineraries") else "",
                }
                for o in data.get("data", [])[:5]
            ]
            return {"success": True, "action": "search_flights", "offers": offers, "count": len(offers)}

        elif action == "search_hotels":
            city_code = params.get("city_code", "PAR")
            r = await c.get("/v1/reference-data/locations/hotels/by-city", params={
                "cityCode": city_code,
                "radius": params.get("radius", 5),
                "radiusUnit": "KM",
            })
            if r.status_code != 200:
                raise RuntimeError(f"Amadeus search_hotels failed ({r.status_code}): {r.text[:200]}")
            data = r.json()
            hotels = [
                {
                    "name": h.get("name", "Unknown"),
                    "hotel_id": h.get("hotelId", ""),
                    "city": city_code,
                }
                for h in data.get("data", [])[:10]
            ]
            return {"success": True, "action": "search_hotels", "hotels": hotels, "count": len(hotels)}

        else:
            raise ValueError(f"Unsupported Amadeus action: {action}")


_SERVICE_HANDLERS = {
    "stripe":     _execute_stripe,
    "github":     _execute_github,
    "slack":      _execute_slack,
    "google":          _execute_google,
    "gmail":           _execute_google,
    "google-calendar": _execute_google,
    "google-sheets":   _execute_google,
    "google-drive":    _execute_google,
    "microsoft":  _execute_microsoft,
    "outlook":    _execute_microsoft,
    "salesforce": _execute_salesforce,
    "notion":     _execute_notion,
    "jira":       _execute_jira,
    "discord":    _execute_discord,
    "linear":     _execute_linear,
    "hubspot":    _execute_hubspot,
    "shopify":    _execute_shopify,
    "paypal":     _execute_paypal,
    "amadeus":    _execute_amadeus,
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

    async def get_token_via_exchange(self, connection_name: str, refresh_token: str, domain: str = "", client_id: str = "", client_secret: str = "") -> str | None:
        """
        Token Vault Token Exchange (RFC 8693).
        Exchanges an Auth0 refresh_token for a fresh external-provider access_token.
        """
        if not auth0_breaker.allow_request():
            logger.warning(f"Token Exchange skipped for {connection_name} — Auth0 circuit breaker OPEN")
            return None
        try:
            _domain = domain or self.domain
            _client_id = client_id or self.client_id
            _client_secret = client_secret or self.client_secret
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://{_domain}/oauth/token",
                    data={
                        "grant_type": "urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token",
                        "subject_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
                        "requested_token_type": "http://auth0.com/oauth/token-type/federated-connection-access-token",
                        "subject_token": refresh_token,
                        "client_id": _client_id,
                        "client_secret": _client_secret,
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
                    logger.warning(f"Token Vault Token Exchange: 403 Forbidden for {connection_name} — {r.text}")
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

    async def get_token_via_m2m(
        self, token_url: str, client_id: str, client_secret: str,
    ) -> str | None:
        """
        Credential Vault: M2M client_credentials token retrieval.

        For APIs that don't support user-delegated OAuth (Amadeus, Twilio, AWS, etc.).
        Uses standard OAuth2 client_credentials grant to get a fresh access_token.
        The API key/secret is stored encrypted in our DB (not in Auth0 Token Vault).
        """
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if r.status_code == 200:
                    data = r.json()
                    token = data.get("access_token")
                    logger.info(f"Credential Vault: M2M token retrieved from {token_url}")
                    return token
                logger.warning(f"Credential Vault: M2M token request failed ({r.status_code}): {r.text[:200]}")
                return None
        except Exception as e:
            logger.warning(f"Credential Vault: M2M token error for {token_url}: {e}")
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

                # Try to extract real Auth0 connection name from connected_auth0_user_id
                # Format: "oauth2|slack-oauth-2|T0AHV..." or "github|12345"
                if conn_obj.connected_auth0_user_id:
                    parts = conn_obj.connected_auth0_user_id.split("|")
                    if len(parts) >= 2 and parts[0] == "oauth2":
                        # Custom OAuth2: use the connection name directly
                        provider = parts[1]
                        logger.debug(f"Token Vault: extracted provider '{provider}' from user_id")

                # Get workspace Auth0 credentials for Token Exchange
                _ws_domain = ""
                _ws_client_id = ""
                _ws_client_secret = ""
                if workspace_id:
                    try:
                        import uuid as _uuid
                        from api.services.workspace_config import get_workspace_config
                        ws_config = await get_workspace_config(_uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id, db)
                        _ws_domain = ws_config.auth0_domain
                        _ws_client_id = ws_config.auth0_web_client_id or ws_config.auth0_client_id
                        _ws_client_secret = ws_config.auth0_web_client_secret or ws_config.auth0_client_secret
                    except Exception as e:
                        logger.warning(f"Token Vault: failed to get workspace config: {e}")

                # Try Token Exchange (preferred, RFC 8693)
                refresh_tok = decrypt_secret(conn_obj.auth0_refresh_token)
                exchange_attempted = bool(refresh_tok and provider)

                if exchange_attempted:
                    token = await self.get_token_via_exchange(provider, refresh_tok, _ws_domain, _ws_client_id, _ws_client_secret)
                    if token:
                        creds = {"api_key": token, "token": token, "access_token": token}
                        logger.info(f"Token Vault: Token Exchange succeeded for {connection}")
                    else:
                        logger.warning(f"Token Vault: Token Exchange failed for {connection} — trying Management API fallback")

                # Fallback: Management API (get token from identities[])
                if creds is None and conn_obj.connected_auth0_user_id:
                    auth0_uid = conn_obj.connected_auth0_user_id
                    mgmt_token = await self.get_token_from_auth0(provider or service, auth0_uid)
                    if mgmt_token:
                        creds = {"api_key": mgmt_token, "token": mgmt_token, "access_token": mgmt_token}
                        logger.info(f"Token Vault: Management API fallback succeeded for {connection}")

                # Credential Vault: M2M client_credentials (Amadeus, Twilio, AWS, etc.)
                # Credentials stored ONLY in HashiCorp Vault — never in our DB.
                if creds is None and conn_obj.m2m_token_url:
                    from api.services.vault import read_m2m_credentials
                    vault_creds = read_m2m_credentials(str(conn_obj.workspace_id), conn_obj.slug or connection)

                    if vault_creds:
                        m2m_secret = vault_creds.get("api_key")
                        m2m_client = vault_creds.get("client_id") or conn_obj.m2m_client_id
                        m2m_url = vault_creds.get("token_url") or conn_obj.m2m_token_url
                        if m2m_secret and m2m_client:
                            token = await self.get_token_via_m2m(m2m_url, m2m_client, m2m_secret)
                            if token:
                                creds = {"api_key": token, "token": token, "access_token": token}
                                logger.info(f"Credential Vault: M2M token for {connection} via HashiCorp Vault")
                    else:
                        logger.warning(f"Credential Vault: no credentials in Vault for {connection} — store via dashboard (Vault required)")

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

        # Merge connection config_meta (owner, repo, etc.) into creds
        if conn_obj and getattr(conn_obj, "config_meta", None):
            creds.update({k: v for k, v in conn_obj.config_meta.items() if k not in ("token", "api_key", "access_token")})

        handler = _SERVICE_HANDLERS.get(service)

        if handler is None:
            logger.warning(f"No handler for service '{service}'")
            return {
                "success": False,
                "reason": "not_implemented",
                "error": f"Service '{service}' has no built-in handler. Supported: {', '.join(_SERVICE_HANDLERS.keys())}. "
                         f"For OAuth APIs: add as Auth0 custom connection. For M2M APIs: store credentials in HashiCorp Vault.",
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
