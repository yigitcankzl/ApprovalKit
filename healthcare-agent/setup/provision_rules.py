#!/usr/bin/env python3
"""
ApprovalKit Rule Provisioner
============================
Reads rules.yaml and creates all necessary connections, approvers, and rules
in the ApprovalKit instance via its admin API.

Usage:
    python -m setup.provision_rules

Environment:
    APPROVALKIT_URL          http://localhost:8000
    APPROVALKIT_API_KEY      (workspace API key)
    APPROVALKIT_HMAC_SECRET  (workspace HMAC secret)
"""
import os
import sys
import json
import hashlib
import hmac
import time
import yaml
import httpx

BASE_URL = os.environ.get("APPROVALKIT_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("APPROVALKIT_API_KEY", "")
HMAC_SECRET = os.environ.get("APPROVALKIT_HMAC_SECRET", "")


def _sign(body_str: str) -> tuple[str, str]:
    ts = str(int(time.time()))
    sign_key = f"{HMAC_SECRET}:{API_KEY}" if API_KEY else HMAC_SECRET
    sig = hmac.new(sign_key.encode(), f"{ts}.{body_str}".encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _headers(ts: str = "", sig: str = "") -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={ts}.{sig}" if ts else "",
        "Content-Type": "application/json",
    }


def api_post_nosign(path: str, data: dict) -> dict:
    """POST without HMAC — uses workspace fallback (no X-User-Sub)."""
    body = json.dumps(data, separators=(",", ":"))
    r = httpx.post(f"{BASE_URL}{path}", content=body, headers={"Content-Type": "application/json"}, timeout=10)
    if r.status_code in (200, 201):
        return r.json()
    print(f"  ERROR {r.status_code}: {r.text[:200]}")
    return {}


def api_get(path: str) -> dict:
    ts, sig = _sign("")
    r = httpx.get(f"{BASE_URL}{path}", headers=_headers(ts, sig), timeout=10)
    return r.json() if r.status_code == 200 else {}


def api_post(path: str, data: dict) -> dict:
    body = json.dumps(data, separators=(",", ":"))
    ts, sig = _sign(body)
    r = httpx.post(f"{BASE_URL}{path}", content=body, headers=_headers(ts, sig), timeout=10)
    if r.status_code in (200, 201):
        return r.json()
    print(f"  ERROR {r.status_code}: {r.text[:200]}")
    return {}


def load_rules_yaml() -> dict:
    yaml_path = os.path.join(os.path.dirname(__file__), "rules.yaml")
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def provision():
    config = load_rules_yaml()

    print("=" * 60)
    print("  Healthcare Agent — ApprovalKit Provisioner")
    print("=" * 60)
    print(f"  ApprovalKit URL: {BASE_URL}")
    print()

    # 0. Register agent with scenarios
    agent_cfg = config.get("agent")
    if agent_cfg:
        print("[0/3] Registering agent in ApprovalKit...")
        agent_data = {
            "name": agent_cfg["name"],
            "description": agent_cfg.get("description", ""),
            "icon": agent_cfg.get("icon", "bot"),
            "scenarios": [
                {
                    "title": s["title"],
                    "connection": s["connection"],
                    "action": s["action"],
                    "params": s.get("params", {}),
                }
                for s in agent_cfg.get("scenarios", [])
            ],
        }
        result = api_post_nosign("/api/v1/agents", agent_data)
        if result.get("api_key"):
            print(f"  ✓ Agent registered: {agent_cfg['name']}")
            print(f"    API Key: {result['api_key']}")
            print(f"    Scenarios: {len(agent_cfg.get('scenarios', []))}")
            print(f"    ⚠ Save this API key — it won't be shown again!")
        elif result.get("id"):
            print(f"  ✓ Agent registered: {agent_cfg['name']} (key in response)")
        else:
            print(f"  ⚠ Agent registration returned no key (may already exist)")
        print()

    # 1. Create connections
    print("[1/3] Creating connections...")
    for conn in config["connections"]:
        print(f"  → {conn['slug']}: {conn['name']}")
        api_post("/api/v1/connections", {
            "name": conn["name"],
            "service": conn["service"],
            "slug": conn["slug"],
            "actions": [a["action"] for a in conn["actions"]],
        })

    # 2. Create approvers
    print("\n[2/3] Creating approvers...")
    approver_map = {}
    for approver in config["approvers"]:
        print(f"  → {approver['name']} ({approver['role']})")
        result = api_post("/api/v1/approvers", {
            "name": approver["name"],
            "email": approver["email"],
            "auth0_user_id": f"auth0|{approver['email'].split('@')[0]}",
        })
        if result.get("id"):
            approver_map[approver["role"]] = result["id"]

    # 3. Create rules
    print("\n[3/3] Creating rules...")
    for rule in config["rules"]:
        approver_ids = [approver_map.get(r) for r in rule.get("approvers", []) if approver_map.get(r)]
        if not approver_ids:
            print(f"  ⚠ Skipping '{rule['name']}': no approvers found")
            continue

        rule_data = {
            "name": rule["name"],
            "connection": rule["connection"],
            "action": rule["action"],
            "conditions": rule.get("conditions", []),
            "model": rule["model"],
            "approver_ids": approver_ids,
            "timeout_seconds": rule.get("timeout_seconds", 300),
            "priority": rule.get("priority", 0),
            "partial_approval": rule.get("partial_approval", False),
        }

        if rule.get("context_template"):
            rule_data["context_template"] = rule["context_template"]
        if rule.get("step_up_conditions"):
            rule_data["step_up_conditions"] = rule["step_up_conditions"]
            rule_data["step_up_model"] = rule.get("step_up_model", "all_of_n")
        if rule.get("blackout_start"):
            rule_data["blackout_start"] = rule["blackout_start"]
            rule_data["blackout_end"] = rule["blackout_end"]
        if rule.get("on_timeout") == "escalate":
            rule_data["on_timeout"] = "escalate"
            if rule.get("escalate_to") and approver_map.get(rule["escalate_to"]):
                rule_data["escalate_to"] = approver_map[rule["escalate_to"]]

        print(f"  → {rule['name']} ({rule['model']}, {len(approver_ids)} approvers)")
        api_post("/api/v1/rules", rule_data)

    print("\n✅ Provisioning complete!")
    if agent_cfg:
        print(f"   Agent:       {agent_cfg['name']} ({len(agent_cfg.get('scenarios', []))} scenarios)")
    print(f"   Connections: {len(config['connections'])}")
    print(f"   Approvers:   {len(config['approvers'])}")
    print(f"   Rules:       {len(config['rules'])}")
    print()


if __name__ == "__main__":
    provision()
