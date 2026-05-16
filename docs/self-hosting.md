# Self-hosting

This page covers deploying ApprovalKit to your own infrastructure. For
the smoothest path use **Auth0** for approvals and credentials — it's
the production-tested backend. If Auth0 isn't an option, the **local**
providers let you run the full stack with no third-party accounts.

## Prerequisites

* Docker + Docker Compose (or a Kubernetes cluster — manifests are
  not yet shipped, contributions welcome).
* PostgreSQL 16 reachable from the API/worker.
* Redis 7 reachable from the API/worker.
* A reverse proxy that terminates TLS (nginx, Caddy, Traefik).
* For Auth0 mode: a tenant with two applications and Token Vault
  enabled (see [`SETUP.md`](https://github.com/yigitcankzl/ApprovalKit/blob/main/SETUP.md)).

## Production checklist

* `ENVIRONMENT=production` set in `.env` (refuses the `X-User-Sub`
  header bypass).
* `HMAC_SECRET` and `CREDENTIALS_KEY` generated with strong entropy
  and stored outside the repo. Rotate `CREDENTIALS_KEY` via
  `CREDENTIALS_KEY_PREVIOUS` rather than overwriting in place.
* `CALLBACK_BASE_URL` and `FRONTEND_URL` point at the public HTTPS
  hostnames, not localhost. Auth0 OAuth callbacks will fail otherwise.
* TLS terminated at the reverse proxy; the API itself should listen
  on plain HTTP behind it.
* CORS origins limited to your frontend domain(s) — see
  `FRONTEND_URL` (comma-separated).
* Rate limiting tuned for your traffic (`API_RATE_LIMIT`,
  `TRUSTED_PROXY_COUNT`).
* Sentry DSN set (`SENTRY_DSN`) for error tracking.
* Database backups configured. The audit log is the source of truth
  for compliance and should be retained per your policy.
* The Celery worker is supervised by a process manager (systemd,
  Docker `restart: unless-stopped`, k8s Deployment).
* Auth0 tenant configured with the **Connected Accounts** flow, not
  the login flow — see [`HACKATHON.md`](https://github.com/yigitcankzl/ApprovalKit/blob/main/HACKATHON.md) for the
  background on why this matters.

## Running without Auth0

Layer `docker-compose.demo.yml` on top of `docker-compose.yml`:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up
```

This sets `APPROVAL_PROVIDER=local` and stubs out Auth0 env vars. The
core approval pipeline works; agent-chat features that need a local
LLM via Ollama are disabled.

You will need to provide your own integration for storing third-party
credentials. The local credential store accepts a `loader(user_id,
connection) -> ciphertext` callable — wire it to your DB or secret
manager. See [`providers.md`](providers.md).

## Scaling notes

* **API**: stateless. Scale horizontally behind a load balancer.
* **Worker**: scale by adding Celery worker replicas. Tasks are
  idempotent w.r.t. `job_id`.
* **Postgres**: read-heavy for the audit log. Consider partitioning
  the audit table by month for very high volumes.
* **Redis**: needs to outlive both API and worker — use a managed
  Redis with persistence enabled.

## Observability

* Logs are structured (loguru) and route to stderr.
* Every request carries `X-Trace-Id` (generated if absent).
* Sentry integrations are wired for FastAPI and SQLAlchemy.
* OpenTelemetry / Prometheus exporters are not yet shipped —
  contributions welcome.
