"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Copy, Check, Terminal, Code2, Plug, BookOpen } from "lucide-react";

function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative rounded-lg bg-zinc-950 text-zinc-100 text-sm font-mono overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800">
        <span className="text-xs text-zinc-500 dark:text-zinc-400">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto leading-relaxed whitespace-pre">{code}</pre>
    </div>
  );
}

function Section({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      {children}
    </section>
  );
}

const NAV = [
  { id: "overview",    label: "Overview" },
  { id: "quickstart",  label: "Quick Start" },
  { id: "sdk",         label: "Python SDK" },
  { id: "decorator",   label: "— @requires_approval" },
  { id: "gate",        label: "— kit.gate()" },
  { id: "async",       label: "— Async Support" },
  { id: "errors",      label: "— Error Handling" },
  { id: "token-vault", label: "Token Vault" },
  { id: "step-up",     label: "Step-up Auth" },
  { id: "ciba",        label: "CIBA / Guardian" },
  { id: "sse",         label: "Real-time Events" },
  { id: "demo",        label: "Shopping Bot Demo" },
  { id: "travelops",   label: "TravelOps Agent" },
  { id: "endpoints",   label: "API Reference" },
  { id: "approval-models", label: "Approval Models" },
  { id: "multi-tenant", label: "Multi-tenant" },
  { id: "security",    label: "Security" },
];

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("overview");

  useEffect(() => {
    const observers: IntersectionObserver[] = [];

    NAV.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveSection(id);
        },
        { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
      );
      obs.observe(el);
      observers.push(obs);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <div className="flex gap-8 max-w-6xl mx-auto">
      {/* Left nav */}
      <aside className="hidden lg:block w-52 shrink-0">
        <div className="sticky top-6 space-y-1">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 px-2">
            Contents
          </p>
          {NAV.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={`block px-2 py-1.5 rounded text-sm transition-all duration-150 ${
                item.label.startsWith("—") ? "pl-5" : "font-medium"
              } ${
                activeSection === item.id
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:bg-zinc-800"
              }`}
            >
              {item.label}
            </a>
          ))}
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 space-y-12 pb-20">

        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <BookOpen className="h-6 w-6 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600" />
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">Documentation</h1>
          </div>
          <p className="text-zinc-500 dark:text-zinc-400 text-lg">
            Human approval middleware for AI agents — plug in with one decorator.
          </p>
        </div>

        {/* Overview */}
        <Section id="overview">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Overview</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            ApprovalKit sits between your AI agent and any high-risk action. When an agent wants to
            charge a card, deploy to production, or send an email blast, it asks ApprovalKit first.
            A human gets a push notification, taps Approve or Deny, and the platform responds.
            The agent never sees the actual credentials — Auth0 Token Vault executes the action directly.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
            {[
              { icon: "🔐", title: "Token Vault", desc: "Credentials never reach the agent. Auth0 executes the action after approval." },
              { icon: "📱", title: "CIBA Push", desc: "Approvers get an Auth0 Guardian push notification on their phone." },
              { icon: "🛡️", title: "FGA Access", desc: "Fine-grained authorization controls who can see and modify what." },
            ].map((item) => (
              <Card key={item.title}>
                <CardContent className="pt-5">
                  <div className="text-2xl mb-2">{item.icon}</div>
                  <p className="font-semibold text-zinc-800 dark:text-zinc-200 text-sm">{item.title}</p>
                  <p className="text-zinc-500 dark:text-zinc-400 text-xs mt-1">{item.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* Quick Start */}
        <Section id="quickstart">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Quick Start</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Spin up the platform locally with Docker, then point your agent at it.
          </p>
          <CodeBlock language="bash" code={`# 1. Clone & configure
git clone <repo> && cd ApprovalKit
cp .env.example .env          # fill in Auth0 credentials
docker compose up -d
docker compose exec api alembic upgrade head

# 2. Run the setup wizard — generates API key & HMAC secret
docker compose exec api python scripts/setup.py

# 3. Install the SDK in your agent's environment
pip install requests           # only stdlib + requests needed

# 4. Install the SDK
pip install ./sdk       # local install from repo
# or once published: pip install approvalkit`} />
        </Section>

        {/* SDK */}
        <Section id="sdk">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Python SDK</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Install from the repo&apos;s <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded text-sm">sdk/</code> folder,
            or copy <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded text-sm">sdk/approvalkit/__init__.py</code> into your project.
          </p>
          <CodeBlock code={`from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="your-api-key",          # from setup wizard
    hmac_secret="your-hmac-secret",  # from setup wizard
    user_id="auth0|your_agent_id",
    poll_interval=3,   # seconds between status polls
    timeout=300,       # give up after 5 minutes
)`} />
        </Section>

        {/* Decorator */}
        <Section id="decorator">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">
            <code className="text-lg bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">@requires_approval</code>
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">Add one decorator. Everything else stays the same.</p>
          <CodeBlock code={`# BEFORE — runs immediately, no approval
def charge_customer(amount: int, customer: str):
    stripe.charge(amount=amount, customer=customer)


# AFTER — waits for human approval first
@kit.requires_approval(
    connection="stripe-prod",   # must match a Connection in the dashboard
    action="charge",            # must match the rule's action field
)
def charge_customer(amount: int, customer: str):
    stripe.charge(amount=amount, customer=customer)
    # this line only runs after approval`} />

          <div className="mt-4 mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">
            Custom params mapping
          </div>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-3">
            By default the decorator sends all function arguments as approval params.
            Use <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded text-xs">params_fn</code> to control exactly what the approver sees.
          </p>
          <CodeBlock code={`@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, customer: {
        "amount_usd": amount,
        "customer_email": customer,
        "note": "auto-generated by shopping bot",
    },
)
def charge_customer(amount: int, customer: str):
    ...`} />

          <div className="mt-4 mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">
            Handling approval outcomes
          </div>
          <CodeBlock code={`from approvalkit import ApprovalDenied

try:
    charge_customer(99, "alice@example.com")
    print("Payment processed.")
except ApprovalDenied as e:
    # e.status: "rejected" | "timeout" | "blocked"
    # e.job_id: approval job UUID for audit lookup
    print(f"Payment not processed — approval {e.status}")`} />
        </Section>

        {/* Gate */}
        <Section id="gate">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">
            <code className="text-lg bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">kit.gate()</code>
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">
            Inline alternative to the decorator — useful inside conditional branches.
          </p>
          <CodeBlock code={`# Approval gate inline — no decorator needed
try:
    kit.gate("stripe-prod", "charge", {
        "amount_usd": total,
        "customer": customer_email,
    })
    # reaching here = approved
    stripe.charge(amount=total, customer=customer_email)

except ApprovalDenied as e:
    print(f"Blocked: {e.status}")`} />
        </Section>

        {/* Async Support */}
        <Section id="async">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">
            <code className="text-lg bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">Async Support</code>
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">
            Full async/await support for asyncio-based agents (LangChain, LlamaIndex, etc.).
          </p>
          <CodeBlock code={`from approvalkit import ApprovalKit

kit = ApprovalKit(base_url="...", api_key="...", hmac_secret="...")

# Async decorator
@kit.async_requires_approval(connection="stripe-prod", action="charge")
async def charge_customer(amount: int, customer: str):
    pass  # Token Vault executes

# Async inline gate
result = await kit.async_gate("github-main", "deploy", {
    "ref": "main",
    "environment": "production",
})

# Works with any async framework
async def langchain_tool():
    await kit.async_gate("stripe-prod", "charge", {"amount": 500})
    return "Payment approved and executed"`} />
        </Section>

        {/* Error Handling */}
        <Section id="errors">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">Error Handling</h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">
            <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded text-sm">ApprovalDenied</code> is raised when the request is rejected, times out, or is blocked by a rule.
          </p>
          <CodeBlock code={`from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(...)

try:
    result = kit.gate("stripe-prod", "charge", {"amount": 5000})
    # result contains: status, final_params, job_id
    print(f"Approved! Final params: {result['final_params']}")

except ApprovalDenied as e:
    print(f"Status: {e.status}")   # "rejected" | "timeout" | "blocked"
    print(f"Job ID: {e.job_id}")   # For audit trail lookup

    if e.status == "rejected":
        print("Approver denied this action")
    elif e.status == "timeout":
        print("No response within timeout window")
    elif e.status == "blocked":
        print("Blocked by rule (blackout/cooldown)")`} />
        </Section>

        {/* Token Vault */}
        <Section id="token-vault">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Token Vault</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 Token Vault stores OAuth tokens for external services. ApprovalKit retrieves them via <strong>Token Exchange (RFC 8693)</strong> — the agent never sees raw credentials.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 rounded-lg">
              <p className="text-sm font-semibold text-red-800 mb-2">Without Token Vault</p>
              <ul className="text-xs text-red-700 dark:text-red-400 space-y-1">
                <li>Agent holds Stripe API key in memory</li>
                <li>Key exposed if agent is compromised</li>
                <li>No way to revoke without rotating key</li>
                <li>Agent can charge any amount</li>
              </ul>
            </div>
            <div className="p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg">
              <p className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">With Token Vault</p>
              <ul className="text-xs text-green-700 dark:text-green-400 space-y-1">
                <li>Tokens stored in Auth0, never in agent</li>
                <li>Fresh token via RFC 8693 exchange</li>
                <li>Revoke from dashboard instantly</li>
                <li>Rules control what agent can do</li>
              </ul>
            </div>
          </div>
          <p className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-2">How it works:</p>
          <CodeBlock language="text" code={`1. User connects service via Connected Accounts flow
   POST /me/v1/connected-accounts/connect → Auth0 stores federated refresh token

2. Agent requests action → human approves via Guardian

3. Platform exchanges refresh token for provider access token:
   POST /oauth/token
   grant_type=urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token
   subject_token={auth0_refresh_token}
   connection=stripe

4. Auth0 returns fresh Stripe access token → platform executes charge
   Agent never saw the token.`} />
          <p className="text-xs text-zinc-400 mt-3">
            Fallback: For providers without refresh tokens (e.g., GitHub), the Management API reads long-lived tokens from user identities.
          </p>
        </Section>

        {/* Step-up Auth */}
        <Section id="step-up">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Step-up Authentication</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Rules can define step-up conditions — when matched, the approval model automatically escalates to a stricter level.
          </p>
          <CodeBlock language="json" code={`{
  "name": "Stripe charge",
  "connection": "stripe-prod",
  "action": "charge",
  "model": "any_one",
  "step_up_model": "all_of_n",
  "step_up_conditions": [
    { "field": "amount_usd", "operator": "gte", "value": 1000 }
  ],
  "approver_ids": ["manager-uuid", "cfo-uuid"]
}

// $349 charge → any_one (manager only)
// $5000 charge → step-up → all_of_n (manager + CFO both approve)`} />
          <p className="text-xs text-zinc-400 mt-3">
            Step-up evaluation happens in the Celery worker before dispatching to the approval model processor. A <code>step_up</code> audit event is logged.
          </p>
        </Section>

        {/* CIBA / Guardian */}
        <Section id="ciba">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">CIBA / Guardian Push</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 CIBA (Client-Initiated Backchannel Authentication) sends push notifications to the approver via the Auth0 Guardian app. The approver sees a binding message and taps Approve or Deny.
          </p>
          <div className="space-y-3 mb-4">
            <div className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
              <span className="text-xs font-mono bg-blue-100 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">1</span>
              <div className="text-sm text-zinc-600 dark:text-zinc-400"><strong>bc-authorize</strong> — Platform sends CIBA request with binding message (max 64 chars)</div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
              <span className="text-xs font-mono bg-blue-100 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">2</span>
              <div className="text-sm text-zinc-600 dark:text-zinc-400"><strong>Guardian push</strong> — Approver sees the binding message on their phone</div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
              <span className="text-xs font-mono bg-blue-100 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">3</span>
              <div className="text-sm text-zinc-600 dark:text-zinc-400"><strong>Poll</strong> — Worker polls with exponential backoff (handles 429, slow_down)</div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
              <span className="text-xs font-mono bg-blue-100 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">4</span>
              <div className="text-sm text-zinc-600 dark:text-zinc-400"><strong>Result</strong> — approved, rejected (access_denied), or timeout (300s default)</div>
            </div>
          </div>
          <p className="text-xs text-zinc-400">Guardian enrollment: Auth0 Dashboard → Users → select user → Guardian tab → scan QR code with Guardian app.</p>
        </Section>

        {/* Real-time Events */}
        <Section id="sse">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Real-time Events (SSE)</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Subscribe to live approval events via Server-Sent Events. Every state change is published to a Redis channel and streamed to connected clients.
          </p>
          <CodeBlock language="javascript" code={`// Browser
const events = new EventSource("http://localhost:8000/api/v1/events");

events.onmessage = (e) => {
  const event = JSON.parse(e.data);
  console.log(event.type);       // "requested" | "approved" | "rejected" | "step_up_triggered"
  console.log(event.connection);  // "stripe-prod"
  console.log(event.action);     // "charge"
  console.log(event.job_id);     // UUID
  console.log(event.timestamp);  // ISO 8601
};

// Events: requested, ciba_sent, approved, rejected, timeout, blocked, step_up_triggered`} />
        </Section>

        {/* Demo */}
        <Section id="demo">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Shopping Bot Demo</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded text-sm">examples/shopping_bot.py</code> is a
            complete demo showing a bot before and after integration. The diff between the two
            versions is exactly 6 lines — only the two decorators.
          </p>
          <CodeBlock language="bash" code={`# Set credentials
export APPROVALKIT_API_KEY=<your-key>
export APPROVALKIT_HMAC_SECRET=<your-secret>

# Run — bot searches, adds to cart, then pauses for approval
python examples/shopping_bot.py alice@example.com "Headphones" 1

# With refund demo
DEMO_REFUND=1 python examples/shopping_bot.py alice@example.com "Headphones" 1`} />

          <div className="mt-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 p-4 font-mono text-xs text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 space-y-1">
            <p className="text-zinc-400"># terminal output</p>
            <p>============================================================</p>
            <p>  Shopping Bot  |  customer: alice@example.com</p>
            <p>============================================================</p>
            <p className="text-zinc-500 dark:text-zinc-400"></p>
            <p>Searching for &apos;Headphones&apos;...</p>
            <p>Found: Sony WH-1000XM5 Headphones — $349</p>
            <p className="text-zinc-500 dark:text-zinc-400"></p>
            <p>Adding 1x to cart...</p>
            <p>   Cart created: CART_4821</p>
            <p className="text-zinc-500 dark:text-zinc-400"></p>
            <p>Initiating payment: $349</p>
            <p className="text-blue-600">[ApprovalKit] Requesting approval: stripe-prod/charge</p>
            <p className="text-blue-600">[ApprovalKit] Waiting for approval... (job=a1b2c3d4...)</p>
            <p className="text-blue-600">[ApprovalKit] Push notification sent to approver&apos;s phone.</p>
            <p className="text-zinc-400">... approver taps Approve in Auth0 Guardian ...</p>
            <p className="text-green-600">[ApprovalKit] Approved — executing function.</p>
            <p>   Stripe charged: $349 → alice@example.com  (id=ch_52841)</p>
            <p className="text-zinc-500 dark:text-zinc-400"></p>
            <p>Order complete. Charge ID: ch_52841</p>
          </div>
        </Section>

        {/* Endpoints */}
        <Section id="endpoints">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">API Reference</h2>
          <div className="space-y-2">
            {[
              { method: "POST",   path: "/api/v1/request",            desc: "Submit an approval request. Returns 202 pending, 200 pre-approved, or 403 blocked." },
              { method: "GET",    path: "/api/v1/status/:job_id",     desc: "Poll job status. Returns state, approvals_count, final_params." },
              { method: "PATCH",  path: "/api/v1/jobs/:job_id/params",desc: "Approver modifies action params before approving (partial approval)." },
              { method: "POST",   path: "/api/v1/rules",              desc: "Create an approval rule." },
              { method: "GET",    path: "/api/v1/rules",              desc: "List all rules." },
              { method: "PUT",    path: "/api/v1/rules/:id",          desc: "Update a rule." },
              { method: "POST",   path: "/api/v1/rules/simulate",     desc: "Test rule matching without sending CIBA notifications." },
              { method: "POST",   path: "/api/v1/approvers",          desc: "Create an approver." },
              { method: "DELETE", path: "/api/v1/approvers/:id",      desc: "Delete an approver." },
              { method: "PUT",    path: "/api/v1/approvers/:id/delegate", desc: "Set a temporary delegation to another approver." },
              { method: "GET",    path: "/api/v1/audit",              desc: "Audit log, FGA-filtered by caller role." },
              { method: "GET",    path: "/api/v1/dashboard",          desc: "Aggregated stats: approved, rejected, timeout, scope creep alerts." },
              { method: "GET",    path: "/api/v1/security-status",    desc: "Live status of HMAC, FGA, Token Vault, key isolation, Sentry." },
              { method: "GET",    path: "/api/v1/ciba-quota",         desc: "Auth0 CIBA usage (500/hour limit)." },
            ].map((ep) => (
              <div key={ep.path} className="flex items-start gap-3 py-3 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                <Badge
                  variant={
                    ep.method === "POST" ? "default" :
                    ep.method === "GET" ? "success" :
                    ep.method === "DELETE" ? "danger" : "warning"
                  }
                  className="font-mono text-xs w-16 justify-center shrink-0 mt-0.5"
                >
                  {ep.method}
                </Badge>
                <div>
                  <code className="text-sm text-zinc-800 dark:text-zinc-200">{ep.path}</code>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{ep.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-3">Authentication</p>
            <CodeBlock language="http" code={`POST /api/v1/request HTTP/1.1
Authorization: Bearer <API_KEY>
X-Signature: hmac-sha256=<timestamp>.<sha256_hex>
Content-Type: application/json

{
  "connection": "stripe-prod",
  "action": "charge",
  "params": { "amount": 99, "customer": "alice@example.com" },
  "user_id": "auth0|agent_id",
  "idempotency_key": "uuid-v4"
}`} />
          </div>
        </Section>

        {/* TravelOps Agent */}
        <Section id="travelops">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">TravelOps Agent</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            A complete corporate travel booking agent demonstrating ApprovalKit in a real-world scenario. Available as a <strong>separate project</strong> with its own dashboard.
          </p>
          <div className="space-y-2 mb-4">
            {[
              { step: "1", label: "Book flight", detail: "Stripe charge — step-up for > $2000" },
              { step: "2", label: "Reserve hotel", detail: "Stripe charge — approval for > $150/night" },
              { step: "3", label: "Travel insurance", detail: "Stripe charge — auto-approve (< $120)" },
              { step: "4", label: "Add to calendar", detail: "Google Calendar — auto" },
              { step: "5", label: "Notify team", detail: "Slack message — auto" },
              { step: "6", label: "Log expense", detail: "Internal — auto" },
              { step: "7", label: "Visa reminder", detail: "Gmail — auto if visa required" },
            ].map(s => (
              <div key={s.step} className="flex items-center gap-3 text-sm">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 dark:text-blue-400 flex items-center justify-center text-xs font-bold">{s.step}</span>
                <span className="font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 w-36">{s.label}</span>
                <span className="text-zinc-500 dark:text-zinc-400">{s.detail}</span>
              </div>
            ))}
          </div>
          <CodeBlock code={`# Run the safe version (with ApprovalKit)
cd travelops/with-approvalkit
python agent.py --dest "new york" --flight-price 3200 --class business

# Run the unsafe version (without ApprovalKit) for comparison
cd travelops/without-approvalkit
python agent.py --dest "new york" --flight-price 3200 --class business

# Open the TravelOps dashboard (separate app on port 3001)
cd travelops && docker compose up -d
open http://localhost:3001`} />
        </Section>

        {/* Approval Models */}
        <Section id="approval-models">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Approval Models</h2>
          <div className="space-y-3">
            {[
              { model: "any_one",    label: "Any One",    desc: "First approval from any listed approver unblocks the action." },
              { model: "specific",   label: "Specific",   desc: "Only the single designated approver can approve." },
              { model: "all_of_n",   label: "All of N",   desc: "Every approver in the list must approve sequentially." },
              { model: "k_of_n",     label: "K of N",     desc: "k out of n approvers must approve within the quorum window." },
              { model: "sequential", label: "Sequential", desc: "Approvers are asked in order (A → B → C). Any rejection stops the chain." },
            ].map((m) => (
              <div key={m.model} className="flex items-start gap-4 p-4 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-800">
                <code className="text-sm font-mono bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 px-2 py-1 rounded shrink-0">
                  {m.model}
                </code>
                <div>
                  <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{m.label}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{m.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-3">Rule with k_of_n + quorum window</p>
            <CodeBlock language="json" code={`{
  "name": "Large transfer approval",
  "connection": "stripe-prod",
  "action": "transfer",
  "model": "k_of_n",
  "k_value": 2,
  "quorum_window": 120,
  "timeout_seconds": 300,
  "on_timeout": "escalate",
  "escalate_to": "<approver-uuid>"
}`} />
          </div>
        </Section>

        {/* Security */}
        {/* Multi-tenant */}
        <Section id="multi-tenant">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Multi-tenant</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Each organization stores its own Auth0 and FGA credentials in the database. No <code>.env</code> editing needed — everything configured via the Settings page.
          </p>
          <div className="space-y-3 mb-4">
            <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg text-sm">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Workspace credentials stored in DB:</span>
              <span className="text-zinc-500 dark:text-zinc-400 ml-2">Auth0 domain, M2M client, Web client, FGA store, FGA client</span>
            </div>
            <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg text-sm">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Encryption at rest:</span>
              <span className="text-zinc-500 dark:text-zinc-400 ml-2">Client secrets encrypted with Fernet (AES-128-CBC + HMAC-SHA256)</span>
            </div>
            <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg text-sm">
              <span className="font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Fallback chain:</span>
              <span className="text-zinc-500 dark:text-zinc-400 ml-2">DB workspace value → .env global value → empty</span>
            </div>
          </div>
          <CodeBlock language="text" code={`# Organization A configures via dashboard:
Settings → Auth0 Domain: org-a.us.auth0.com
Settings → M2M Client ID: xxx
Settings → Web Client ID: yyy

# Organization B has completely separate credentials:
Settings → Auth0 Domain: org-b.eu.auth0.com
Settings → M2M Client ID: aaa
Settings → Web Client ID: bbb

# Both orgs share the same ApprovalKit deployment
# but never see each other's data`} />
        </Section>

        <Section id="security">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Security</h2>
          <div className="space-y-4">
            {[
              {
                title: "HMAC-SHA256 Request Signing",
                desc: "Every request must include a timestamp + HMAC signature. Requests older than 5 minutes are rejected, preventing replay attacks.",
                code: `timestamp = str(int(time.time()))
sig = hmac.new(SECRET.encode(),
               f"{timestamp}.{body}".encode(),
               hashlib.sha256).hexdigest()
headers["X-Signature"] = f"hmac-sha256={timestamp}.{sig}"`,
              },
              {
                title: "Scope Creep Detection",
                desc: "If an agent uses an action it has never used before, the platform flags it as a scope creep alert in the audit log and dashboard.",
                code: null,
              },
              {
                title: "Credential Key Isolation",
                desc: "HMAC_SECRET (request signing) and CREDENTIALS_KEY (Fernet encryption of stored tokens) are separate keys. Compromise of one does not expose the other.",
                code: null,
              },
              {
                title: "FGA Least Privilege",
                desc: "workspace_admin can do everything. approver sees only their own history. agent_owner sees only their agent's jobs. viewer sees aggregated stats only.",
                code: null,
              },
              {
                title: "Blackout Windows & Cooldowns",
                desc: "Rules can hard-block actions during specific hours (e.g. no deploys on weekends) and enforce cooldown limits (e.g. max 3 charges per hour).",
                code: null,
              },
            ].map((item) => (
              <Card key={item.title}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{item.title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{item.desc}</p>
                  {item.code && <CodeBlock code={item.code} />}
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
