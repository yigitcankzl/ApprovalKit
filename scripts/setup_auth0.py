#!/usr/bin/env python3
"""
Auth0 Automated Setup via Management API

This script configures everything ApprovalKit needs:
1. Creates a Regular Web Application (frontend)
2. Creates a Machine-to-Machine Application (backend API)
3. Creates an API (Resource Server)
4. Enables Guardian Push (MFA)
5. Creates a test user
6. Outputs all credentials for .env files

Prerequisites:
  - Auth0 tenant with Management API access
  - pip install requests

Usage:
  python scripts/setup_auth0.py \
    --domain YOUR_TENANT.us.auth0.com \
    --token YOUR_MANAGEMENT_API_TOKEN

  OR if you have M2M client credentials:

  python scripts/setup_auth0.py \
    --domain YOUR_TENANT.us.auth0.com \
    --client-id YOUR_M2M_CLIENT_ID \
    --client-secret YOUR_M2M_CLIENT_SECRET
"""

import argparse
import json
import secrets
import sys

import requests


class Auth0Setup:
    def __init__(self, domain: str, token: str):
        self.domain = domain
        self.base_url = f"https://{domain}/api/v2"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.results = {}

    def _request(self, method: str, path: str, data: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, headers=self.headers, json=data)
        if response.status_code >= 400:
            print(f"  ERROR {response.status_code}: {response.text}")
            return {}
        return response.json() if response.text else {}

    def create_api(self):
        """Create the ApprovalKit API (Resource Server)"""
        print("\n[1/6] Creating API (Resource Server)...")
        result = self._request("POST", "/resource-servers", {
            "name": "ApprovalKit API",
            "identifier": "https://api.approvalkit.io",
            "signing_alg": "RS256",
            "scopes": [
                {"value": "read:rules", "description": "Read approval rules"},
                {"value": "write:rules", "description": "Create/update rules"},
                {"value": "read:audit", "description": "Read audit log"},
                {"value": "write:request", "description": "Submit approval requests"},
                {"value": "read:dashboard", "description": "View dashboard"},
            ],
            "token_lifetime": 86400,
            "allow_offline_access": True,
        })
        if result:
            self.results["api_identifier"] = result.get("identifier", "https://api.approvalkit.io")
            print(f"  API created: {self.results['api_identifier']}")
        else:
            self.results["api_identifier"] = "https://api.approvalkit.io"
            print("  API may already exist, continuing...")

    def create_web_app(self):
        """Create Regular Web Application for Next.js frontend"""
        print("\n[2/6] Creating Web Application (frontend)...")
        result = self._request("POST", "/clients", {
            "name": "ApprovalKit Frontend",
            "app_type": "regular_web",
            "callbacks": [
                "http://localhost:3000/api/auth/callback",
                "https://approvalkit.vercel.app/api/auth/callback",
            ],
            "allowed_logout_urls": [
                "http://localhost:3000",
                "https://approvalkit.vercel.app",
            ],
            "web_origins": [
                "http://localhost:3000",
                "https://approvalkit.vercel.app",
            ],
            "grant_types": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_method": "client_secret_post",
        })
        if result:
            self.results["web_client_id"] = result["client_id"]
            self.results["web_client_secret"] = result["client_secret"]
            print(f"  Web App created: {result['client_id']}")

    def create_m2m_app(self):
        """Create Machine-to-Machine Application for backend API"""
        print("\n[3/6] Creating M2M Application (backend)...")
        result = self._request("POST", "/clients", {
            "name": "ApprovalKit Backend",
            "app_type": "non_interactive",
            "grant_types": [
                "client_credentials",
                "urn:openid:params:grant-type:ciba",
            ],
            "token_endpoint_auth_method": "client_secret_post",
        })
        if result:
            self.results["m2m_client_id"] = result["client_id"]
            self.results["m2m_client_secret"] = result["client_secret"]
            print(f"  M2M App created: {result['client_id']}")

            # Grant Management API access to M2M app
            mgmt_api = self._get_management_api_id()
            if mgmt_api:
                self._request("POST", f"/client-grants", {
                    "client_id": result["client_id"],
                    "audience": f"https://{self.domain}/api/v2/",
                    "scope": [
                        "read:users",
                        "read:connections",
                        "update:connections",
                        "read:client_grants",
                    ],
                })
                print("  Management API access granted")

            # Grant ApprovalKit API access
            self._request("POST", "/client-grants", {
                "client_id": result["client_id"],
                "audience": "https://api.approvalkit.io",
                "scope": ["read:rules", "write:rules", "read:audit", "write:request", "read:dashboard"],
            })
            print("  ApprovalKit API access granted")

    def _get_management_api_id(self) -> str | None:
        result = self._request("GET", "/resource-servers")
        if isinstance(result, list):
            for rs in result:
                if "api/v2" in rs.get("identifier", ""):
                    return rs["id"]
        return None

    def enable_guardian(self):
        """Enable Guardian Push MFA"""
        print("\n[4/6] Enabling Guardian Push MFA...")

        # Enable push notification factor
        self._request("PUT", "/guardian/factors/push-notification", {
            "enabled": True,
        })
        print("  Guardian Push enabled")

        # Set MFA policy
        self._request("PUT", "/guardian/policies", ["all-applications"])
        print("  MFA policy set (note: set to 'never' if you want optional MFA)")

        # Enable SNS for push (AWS SNS or Auth0 default)
        self._request("PUT", "/guardian/factors/push-notification/providers/sns", {
            "aws_access_key_id": "",
            "aws_secret_access_key": "",
            "aws_region": "",
            "sns_apns_platform_application_arn": "",
            "sns_gcm_platform_application_arn": "",
        })

    def enable_ciba(self):
        """Enable CIBA (Client-Initiated Backchannel Authentication)"""
        print("\n[5/6] Enabling CIBA...")

        # Enable CIBA on the tenant
        result = self._request("PATCH", f"/clients/{self.results.get('m2m_client_id', '')}", {
            "grant_types": [
                "client_credentials",
                "urn:openid:params:grant-type:ciba",
            ],
        })
        if result:
            print("  CIBA grant type enabled on M2M app")

        # CIBA requires backchannel_token_delivery_mode
        # This is configured at tenant level
        tenant_result = self._request("PATCH", "/tenants/settings", {
            "flags": {
                "enable_ciba": True,
            },
        })
        if tenant_result:
            print("  CIBA enabled on tenant")
        else:
            print("  CIBA tenant flag may need manual activation")
            print("  Go to: Dashboard > Settings > Advanced > CIBA")

    def create_test_user(self):
        """Create a test user for CIBA approval demos"""
        print("\n[6/6] Creating test user...")
        password = secrets.token_urlsafe(16)
        result = self._request("POST", "/users", {
            "email": "approver@approvalkit-demo.com",
            "password": password,
            "connection": "Username-Password-Authentication",
            "name": "Demo Approver",
            "email_verified": True,
        })
        if result:
            self.results["test_user_id"] = result["user_id"]
            self.results["test_user_email"] = result["email"]
            self.results["test_user_password"] = password
            print(f"  User created: {result['email']} (ID: {result['user_id']})")
        else:
            print("  User may already exist")

    def print_env_config(self):
        """Print the .env configuration"""
        hmac_secret = secrets.token_hex(32)
        auth0_secret = secrets.token_hex(32)

        print("\n" + "=" * 60)
        print("  SETUP COMPLETE — Copy these to your .env files")
        print("=" * 60)

        print("\n--- .env (backend) ---\n")
        print(f"DEBUG=true")
        print(f"DATABASE_URL=postgresql+asyncpg://approvalkit:approvalkit@postgres:5432/approvalkit")
        print(f"REDIS_URL=redis://redis:6379/0")
        print(f"AUTH0_DOMAIN={self.domain}")
        print(f"AUTH0_CLIENT_ID={self.results.get('m2m_client_id', 'FILL_IN')}")
        print(f"AUTH0_CLIENT_SECRET={self.results.get('m2m_client_secret', 'FILL_IN')}")
        print(f"AUTH0_AUDIENCE=https://api.approvalkit.io")
        print(f"AUTH0_MGMT_API_AUDIENCE=https://{self.domain}/api/v2/")
        print(f"FGA_API_URL=https://api.us1.fga.dev")
        print(f"FGA_STORE_ID=FILL_IN_AFTER_FGA_SETUP")
        print(f"FGA_MODEL_ID=FILL_IN_AFTER_FGA_SETUP")
        print(f"HMAC_SECRET={hmac_secret}")
        print(f"CELERY_BROKER_URL=redis://redis:6379/1")
        print(f"CELERY_RESULT_BACKEND=redis://redis:6379/2")

        print("\n--- frontend/.env.local ---\n")
        print(f"NEXT_PUBLIC_API_URL=http://localhost:8000")
        print(f"AUTH0_SECRET={auth0_secret}")
        print(f"AUTH0_BASE_URL=http://localhost:3000")
        print(f"AUTH0_ISSUER_BASE_URL=https://{self.domain}")
        print(f"AUTH0_CLIENT_ID={self.results.get('web_client_id', 'FILL_IN')}")
        print(f"AUTH0_CLIENT_SECRET={self.results.get('web_client_secret', 'FILL_IN')}")

        if self.results.get("test_user_id"):
            print("\n--- Test User ---\n")
            print(f"Email:    {self.results['test_user_email']}")
            print(f"Password: {self.results['test_user_password']}")
            print(f"User ID:  {self.results['test_user_id']}")
            print(f"\nThis user needs to enroll in Guardian Push:")
            print(f"  1. Login at https://{self.domain}/authorize?...")
            print(f"  2. Scan QR code with Auth0 Guardian app (iOS/Android)")

        print("\n--- FGA Setup (manual — dashboard.fga.dev) ---\n")
        print("  1. Go to https://dashboard.fga.dev")
        print("  2. Create Store: 'ApprovalKit'")
        print("  3. Paste model from fga/model.fga")
        print("  4. Copy Store ID and Model ID to .env")
        print()


def get_management_token(domain: str, client_id: str, client_secret: str) -> str:
    """Get Management API token from M2M credentials"""
    response = requests.post(
        f"https://{domain}/oauth/token",
        json={
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": f"https://{domain}/api/v2/",
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    parser = argparse.ArgumentParser(description="Auth0 Setup for ApprovalKit")
    parser.add_argument("--domain", required=True, help="Auth0 tenant domain")
    parser.add_argument("--token", help="Management API Bearer token")
    parser.add_argument("--client-id", help="M2M Client ID (alternative to --token)")
    parser.add_argument("--client-secret", help="M2M Client Secret (alternative to --token)")
    args = parser.parse_args()

    if args.token:
        token = args.token
    elif args.client_id and args.client_secret:
        print("Getting Management API token...")
        token = get_management_token(args.domain, args.client_id, args.client_secret)
        print("  Token acquired")
    else:
        print("ERROR: Provide either --token or both --client-id and --client-secret")
        sys.exit(1)

    setup = Auth0Setup(args.domain, token)
    setup.create_api()
    setup.create_web_app()
    setup.create_m2m_app()
    setup.enable_guardian()
    setup.enable_ciba()
    setup.create_test_user()
    setup.print_env_config()


if __name__ == "__main__":
    main()
