# Contributing to ApprovalKit

Thanks for your interest in improving ApprovalKit! This is an open-source
human approval gateway for AI agents — contributions of all kinds are welcome.

## Getting started (local-first)

You do **not** need an Auth0 account to develop or run ApprovalKit. The
default local stack uses the `local` provider:

```bash
# API + worker + Postgres + Redis, no Auth0 / Ollama
docker compose -f docker-compose.local.yml up
```

The API is then at http://localhost:8000. Pending approvals are listed at
`GET /local-approvals` and can be approved/rejected over HTTP.

## Running the tests

```bash
# Backend (Python)
pip install -r api/requirements.txt
pytest -q

# Python SDK is exercised by tests/test_sdk_execution_mode.py

# TypeScript SDK
cd sdk-ts && npm install && npm run build
```

Many backend tests are pure unit tests (schemas, providers, rule engine) and
need no services. The `tests/test_e2e_api.py` suite auto-skips unless an API
is running on `APPROVALKIT_TEST_URL` (default http://localhost:8000).

## Project layout

| Path | What it is |
|------|------------|
| `api/` | FastAPI backend, Celery worker, rule engine, providers |
| `api/providers/` | Pluggable `ApprovalChannel` / `CredentialStore` / `ActionExecutor` / `IdentityProvider` (`local` + `auth0`) |
| `sdk/` | Python SDK + MCP server |
| `sdk-ts/` | TypeScript SDK |
| `frontend/` | Next.js dashboard |
| `docs/` | MkDocs documentation site |

## Execution modes

ApprovalKit supports two execution modes (see [docs](docs/sdk-python.md)):

- `client` (default) — ApprovalKit does policy/approval/audit; the caller runs
  the action after approval.
- `server` — ApprovalKit runs the action server-side via an `ActionExecutor`
  provider (e.g. Auth0 Token Vault).

When adding behavior that runs an approved action, route it through the
`ActionExecutor` provider rather than calling a service directly, and respect
`execution_mode` so client-mode requests never trigger server-side execution.

## Pull requests

1. Fork and create a feature branch off `main`.
2. Keep changes focused; add or update tests for behavior changes.
3. Run `pytest -q` (and `npm run build` in `sdk-ts/` if you touched the TS SDK).
4. Make sure CI is green. Describe the change and the reasoning in the PR.

## Reporting security issues

Please do **not** open public issues for security vulnerabilities. See
[SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
