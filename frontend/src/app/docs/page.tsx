"use client";

import { useState } from "react";
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
        <span className="text-xs text-zinc-500">{language}</span>
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
  { id: "demo",        label: "Shopping Bot Demo" },
  { id: "endpoints",   label: "API Reference" },
  { id: "approval-models", label: "Approval Models" },
  { id: "security",    label: "Security" },
];

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState("overview");

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
              onClick={() => setActiveSection(item.id)}
              className={`block px-2 py-1.5 rounded text-sm transition-colors ${
                item.label.startsWith("—") ? "pl-5 text-zinc-500 hover:text-zinc-700" : "font-medium"
              } ${
                activeSection === item.id
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-800"
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
            <BookOpen className="h-6 w-6 text-zinc-700" />
            <h1 className="text-3xl font-bold text-zinc-900">Documentation</h1>
          </div>
          <p className="text-zinc-500 text-lg">
            Human approval middleware for AI agents — plug in with one decorator.
          </p>
        </div>

        {/* Overview */}
        <Section id="overview">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Overview</h2>
          <p className="text-zinc-600 mb-4">
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
                  <p className="font-semibold text-zinc-800 text-sm">{item.title}</p>
                  <p className="text-zinc-500 text-xs mt-1">{item.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* Quick Start */}
        <Section id="quickstart">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Quick Start</h2>
          <p className="text-zinc-600 mb-4">
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
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Python SDK</h2>
          <p className="text-zinc-600 mb-4">
            Install from the repo&apos;s <code className="bg-zinc-100 px-1 rounded text-sm">sdk/</code> folder,
            or copy <code className="bg-zinc-100 px-1 rounded text-sm">sdk/approvalkit/__init__.py</code> into your project.
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
          <h2 className="text-xl font-bold text-zinc-900 mb-1">
            <code className="text-lg bg-zinc-100 px-2 py-0.5 rounded">@requires_approval</code>
          </h2>
          <p className="text-zinc-500 text-sm mb-4">Add one decorator. Everything else stays the same.</p>
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

          <div className="mt-4 mb-2 text-sm font-medium text-zinc-700">
            Custom params mapping
          </div>
          <p className="text-zinc-500 text-sm mb-3">
            By default the decorator sends all function arguments as approval params.
            Use <code className="bg-zinc-100 px-1 rounded text-xs">params_fn</code> to control exactly what the approver sees.
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

          <div className="mt-4 mb-2 text-sm font-medium text-zinc-700">
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
          <h2 className="text-xl font-bold text-zinc-900 mb-1">
            <code className="text-lg bg-zinc-100 px-2 py-0.5 rounded">kit.gate()</code>
          </h2>
          <p className="text-zinc-500 text-sm mb-4">
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

        {/* Demo */}
        <Section id="demo">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Shopping Bot Demo</h2>
          <p className="text-zinc-600 mb-4">
            <code className="bg-zinc-100 px-1 rounded text-sm">examples/shopping_bot.py</code> is a
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

          <div className="mt-4 rounded-lg bg-zinc-50 border border-zinc-200 p-4 font-mono text-xs text-zinc-700 space-y-1">
            <p className="text-zinc-400"># terminal output</p>
            <p>============================================================</p>
            <p>  Shopping Bot  |  customer: alice@example.com</p>
            <p>============================================================</p>
            <p className="text-zinc-500"></p>
            <p>Searching for &apos;Headphones&apos;...</p>
            <p>Found: Sony WH-1000XM5 Headphones — $349</p>
            <p className="text-zinc-500"></p>
            <p>Adding 1x to cart...</p>
            <p>   Cart created: CART_4821</p>
            <p className="text-zinc-500"></p>
            <p>Initiating payment: $349</p>
            <p className="text-blue-600">[ApprovalKit] Requesting approval: stripe-prod/charge</p>
            <p className="text-blue-600">[ApprovalKit] Waiting for approval... (job=a1b2c3d4...)</p>
            <p className="text-blue-600">[ApprovalKit] Push notification sent to approver&apos;s phone.</p>
            <p className="text-zinc-400">... approver taps Approve in Auth0 Guardian ...</p>
            <p className="text-green-600">[ApprovalKit] Approved — executing function.</p>
            <p>   Stripe charged: $349 → alice@example.com  (id=ch_52841)</p>
            <p className="text-zinc-500"></p>
            <p>Order complete. Charge ID: ch_52841</p>
          </div>
        </Section>

        {/* Endpoints */}
        <Section id="endpoints">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">API Reference</h2>
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
              <div key={ep.path} className="flex items-start gap-3 py-3 border-b border-zinc-100 last:border-0">
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
                  <code className="text-sm text-zinc-800">{ep.path}</code>
                  <p className="text-xs text-zinc-500 mt-0.5">{ep.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <p className="text-sm font-medium text-zinc-700 mb-3">Authentication</p>
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

        {/* Approval Models */}
        <Section id="approval-models">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Approval Models</h2>
          <div className="space-y-3">
            {[
              { model: "any_one",    label: "Any One",    desc: "First approval from any listed approver unblocks the action." },
              { model: "specific",   label: "Specific",   desc: "Only the single designated approver can approve." },
              { model: "all_of_n",   label: "All of N",   desc: "Every approver in the list must approve sequentially." },
              { model: "k_of_n",     label: "K of N",     desc: "k out of n approvers must approve within the quorum window." },
              { model: "sequential", label: "Sequential", desc: "Approvers are asked in order (A → B → C). Any rejection stops the chain." },
            ].map((m) => (
              <div key={m.model} className="flex items-start gap-4 p-4 rounded-lg bg-zinc-50 border border-zinc-100">
                <code className="text-sm font-mono bg-white border border-zinc-200 px-2 py-1 rounded shrink-0">
                  {m.model}
                </code>
                <div>
                  <p className="text-sm font-medium text-zinc-800">{m.label}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{m.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6">
            <p className="text-sm font-medium text-zinc-700 mb-3">Rule with k_of_n + quorum window</p>
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
        <Section id="security">
          <h2 className="text-xl font-bold text-zinc-900 mb-4">Security</h2>
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
                  <p className="text-sm text-zinc-500">{item.desc}</p>
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
