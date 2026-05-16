# ApprovalKit Documentation

ApprovalKit is a human-approval middleware for AI agents. This
documentation covers installation, the SDK and REST APIs, the
approval pipeline, the pluggable provider system, and the security
model.

## Table of contents

* [Quickstart](quickstart.md) — install, run, gate your first
  function.
* [Architecture](architecture.md) — how requests flow from agent →
  rule engine → approval channel → credential store → downstream API.
* [Approval models](approval-models.md) — `any_one`, `specific`,
  `all_of_n`, `k_of_n`, `sequential`, `fga_dynamic`.
* [Providers](providers.md) — the Auth0 default vs. the local (Auth0-
  less) backends. How to plug in your own.
* [SDK reference (Python)](sdk-python.md) — decorator, inline gate,
  async usage.
* [SDK reference (TypeScript)](sdk-typescript.md) — work in progress.
* [REST API reference](rest-api.md) — endpoints, payloads, status
  codes.
* [Security model](security.md) — credential handling, HMAC, audit
  trail, threat model.
* [Self-hosting](self-hosting.md) — deploy without Auth0; production
  checklist.
* [Contributing](https://github.com/yigitcankzl/ApprovalKit/blob/main/CONTRIBUTING.md) — coming soon.

## Where to file issues

GitHub: https://github.com/yigitcankzl/ApprovalKit/issues
