# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in ApprovalKit, please report it
privately. **Do not open a public GitHub issue.**

- Email the maintainers (see the repository owner's profile), or
- Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
  ("Report a vulnerability" under the **Security** tab).

Please include:

- A description of the issue and its impact.
- Steps to reproduce (a minimal proof of concept if possible).
- Affected component (API, worker, SDK, MCP server, frontend) and version/commit.

We aim to acknowledge reports within a few business days and will keep you
updated on remediation. Please give us reasonable time to ship a fix before
any public disclosure.

## Scope notes

- The **local provider** (`APPROVAL_PROVIDER=local`) is intended for
  development and self-hosted starter deployments. It does not make
  production-grade security guarantees (e.g. the local approval channel is a
  Redis-backed mock, not a real push/authentication flow). For production,
  use the Auth0 provider (CIBA + Token Vault + FGA).
- In **client execution mode**, approved actions run in *your* process with
  *your* credentials. ApprovalKit's job is policy, approval, and audit — it is
  not a credential vault in this mode. Use **server execution mode** with the
  Auth0 Token Vault provider if you need credentials kept out of the agent.

## Supported versions

ApprovalKit is pre-1.0; security fixes target the `main` branch. Pin to a
commit for reproducible deployments.
