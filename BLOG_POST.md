# Blog Post: Building Token Vault Token Exchange for AI Agent Approval

## The Discovery

When we started building ApprovalKit, we assumed Token Vault was simple: store OAuth tokens, retrieve them when needed. We were wrong.

Our first implementation used the Auth0 Management API (`GET /api/v2/users/{id}`) to read `identities[].access_token`. This worked for GitHub (which uses long-lived tokens), but it was the wrong approach. Management API requires broad permissions, doesn't auto-refresh tokens, and isn't the recommended pattern.

The proper approach is **Token Exchange (RFC 8693)**: exchange an Auth0 refresh token for a fresh external provider access token. But this required a discovery that cost us significant debugging time.

## The Login Flow vs Connected Accounts Flow

When a user authorizes a social connection via Auth0's standard `/authorize` endpoint, tokens are stored in the `identities[]` array on the user profile. Token Exchange **cannot access these tokens**.

For Token Exchange to work, tokens must be stored via the **Connected Accounts** flow using Auth0's My Account API:

```
POST /me/v1/connected-accounts/connect
→ user authorizes external service
POST /me/v1/connected-accounts/complete
→ tokens stored in connected_accounts[] (Token Vault)
```

This flow requires:
- `oidc_conformant: true` on the application
- Token Vault grant type explicitly enabled
- MFA policy set to "Never" (Token Exchange doesn't support MFA)
- `create:me:connected_accounts` scope via My Account API

None of this was immediately obvious from the documentation. We discovered it through trial and error with the `federated_connection_refresh_token_not_found` error.

## The Architecture

Our final Token Vault integration has two paths:

**Primary (Token Exchange):** For providers that support refresh tokens (Stripe, Google, Salesforce). The user connects via Connected Accounts flow, Auth0 stores the federated refresh token, and Token Exchange retrieves fresh access tokens at execution time.

**Fallback (Management API):** Only when no refresh token exists (legacy connections without Token Vault). If Token Exchange is attempted and fails (expired token), we do **not** fall back — the user must reconnect. This prevents silently downgrading to a less secure path.

**Generic Webhook:** For services without a built-in handler, the webhook config (URL + headers + body template) is rendered with `{{token}}` and `{{params}}` placeholders at execution time. Zero code needed.

## What We Built With Token Vault

ApprovalKit is a human approval middleware for AI agents. When an AI agent wants to charge a credit card, send an email, or deploy code, ApprovalKit:

1. Evaluates the request against configurable rules (step-up authentication, budget limits, blackout windows)
2. Sends a push notification to the right human via Auth0 CIBA + Guardian
3. Waits for approval on the human's phone
4. Executes the action through Token Vault — the agent never sees the credentials

We built 30 service handlers (Stripe, GitHub, Slack, Gmail, Google Calendar, Microsoft, Salesforce, Notion, Jira, Discord, and more) that all execute through Token Vault Token Exchange. The agent calls `kit.gate("stripe-prod", "charge", {"amount": 420})` and ApprovalKit handles the entire OAuth token lifecycle server-side.

In our live demo, an AI agent powered by a local LLM (Qwen 2.5) reasons about customer complaints, decides to issue refunds, send apology emails, and notify teams — all gated through ApprovalKit. The agent calls real Stripe charges and real Gmail sends, but never holds a single API key.

## Patterns We Discovered

**1. Agent authorization is a platform problem, not a per-agent problem.** Building auth into each agent doesn't scale. A middleware layer with centralized rules and per-agent isolation is the right pattern.

**2. LLMs adapt to authorization feedback.** When our agent gets blocked (budget exceeded, scope creep detected), it tries alternative approaches — lower amounts, different actions. Authorization isn't just blocking; it's guiding agent behavior.

**3. Step-up authentication makes security proportional to risk.** A $30 refund auto-approves. A $420 refund needs a manager. A $25,000 bulk refund needs the CFO. Same agent, same code, different approval chains based on risk.

**4. The "rogue agent" scenario is real.** In our demo, we deliberately prompt agents with aggressive instructions ("refund everyone, send emails to all 500 customers"). Without ApprovalKit, $50,000 in charges execute instantly. With it, they're caught and blocked.

## Feedback for Auth0

**Connected Accounts documentation:** The distinction between login flow (`/authorize`) and Connected Accounts flow (`/me/v1/connected-accounts`) is the single most important thing to understand when building with Token Vault. We lost days to `federated_connection_refresh_token_not_found` errors before discovering this. A prominent callout in the Token Vault docs would save every developer this pain.

**Error messages:** The `federated_connection_refresh_token_not_found` error should include a hint: "This token was stored via the login flow. Token Exchange requires tokens stored via Connected Accounts. See [link]."

**Token Exchange + MFA:** Currently Token Exchange doesn't work if MFA is enabled. This is a significant limitation for production use cases where both security features are needed simultaneously.

The biggest insight from building with Token Vault: **the boundary between "login" and "connected account" is the most important architectural decision.** Getting this wrong means your Token Exchange calls silently fail. Getting it right means your AI agents can securely execute actions across 20+ services without ever holding a credential.
