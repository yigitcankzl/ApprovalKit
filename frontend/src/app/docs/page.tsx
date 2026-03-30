"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Copy, Check, BookOpen, Shield, Key, Smartphone, Lock, Layers, ArrowLeft } from "lucide-react";
import Link from "next/link";

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
  { id: "decorator",   label: "  @requires_approval" },
  { id: "gate",        label: "  kit.gate()" },
  { id: "async",       label: "  Async Support" },
  { id: "errors",      label: "  Error Handling" },
  { id: "token-vault", label: "Token Vault" },
  { id: "approval-models", label: "Approval Models" },
  { id: "step-up",     label: "Step-up Auth" },
  { id: "ciba",        label: "CIBA / Guardian" },
  { id: "endpoints",   label: "API Reference" },
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
                item.label.startsWith("  ") ? "pl-5" : "font-medium"
              } ${
                activeSection === item.id
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              {item.label.trim()}
            </a>
          ))}
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 space-y-12 pb-20">

        {/* Header */}
        <div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 shadow-sm transition-colors mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Dashboard
          </Link>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500 mb-2">
            Documentation
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm">
            Human approval middleware for AI agents — plug in with one line of code.
          </p>
          <div className="mt-4">
            <a
              href="/docs/setup-guide"
              className="inline-flex items-center gap-3 px-5 py-3 rounded-xl text-sm font-semibold bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-200"
            >
              <BookOpen className="h-4 w-4" />
              Full Setup &amp; Integration Guide
            </a>
          </div>
        </div>

        {/* Overview */}
        <Section id="overview">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Overview</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            ApprovalKit sits between your AI agent and any high-risk action. When an agent wants to
            charge a card, deploy to production, or send an email, it asks ApprovalKit first.
            A human gets a push notification via Auth0 Guardian, taps Approve or Deny, and the platform responds.
            The agent never sees actual credentials — Auth0 Token Vault executes the action directly.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
            {[
              { icon: <Lock className="h-5 w-5" />, title: "Token Vault", desc: "Credentials never reach the agent. Auth0 stores and executes via RFC 8693 Token Exchange." },
              { icon: <Smartphone className="h-5 w-5" />, title: "CIBA Push", desc: "Approvers get an Auth0 Guardian push notification on their phone." },
              { icon: <Shield className="h-5 w-5" />, title: "FGA Access Control", desc: "Fine-grained authorization controls who can see and modify what." },
            ].map((item) => (
              <Card key={item.title}>
                <CardContent className="pt-5">
                  <div className="text-zinc-500 dark:text-zinc-400 mb-2">{item.icon}</div>
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

# 2. Open the dashboard and complete the setup wizard
open http://localhost:3000     # generates API key & HMAC secret

# 3. Install the SDK in your agent
pip install ./sdk              # only dependency: requests`} />
        </Section>

        {/* SDK */}
        <Section id="sdk">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Python SDK</h2>
          <CodeBlock code={`from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="ak_...",             # from dashboard
    hmac_secret="your-secret",    # from dashboard
    user_id="my-agent",
    poll_interval=3,
    timeout=300,
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


# AFTER — waits for human approval, Token Vault executes
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    pass  # body never runs — Token Vault handles execution`} />
        </Section>

        {/* Gate */}
        <Section id="gate">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">
            <code className="text-lg bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded">kit.gate()</code>
          </h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">
            Inline alternative — useful inside conditional branches.
          </p>
          <CodeBlock code={`result = kit.gate("stripe-prod", "charge", {
    "amount_usd": total,
    "customer": customer_email,
})
# result: {"status": "approved", "final_params": {...}, "job_id": "..."}`} />
        </Section>

        {/* Async Support */}
        <Section id="async">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">Async Support</h2>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-4">
            Full async/await for asyncio-based agents (LangChain, LlamaIndex, etc.).
          </p>
          <CodeBlock code={`@kit.async_requires_approval(connection="stripe-prod", action="charge")
async def charge_customer(amount: int, customer: str):
    pass  # Token Vault executes

# Or inline
result = await kit.async_gate("github-main", "deploy", {
    "ref": "main",
    "environment": "production",
})`} />
        </Section>

        {/* Error Handling */}
        <Section id="errors">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-1">Error Handling</h2>
          <CodeBlock code={`from approvalkit import ApprovalDenied

try:
    result = kit.gate("stripe-prod", "charge", {"amount": 5000})
    print(f"Approved! Final params: {result['final_params']}")
except ApprovalDenied as e:
    print(f"Status: {e.status}")   # "rejected" | "timeout" | "blocked"
    print(f"Job ID: {e.job_id}")   # for audit trail lookup`} />
        </Section>

        {/* Token Vault */}
        <Section id="token-vault">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Token Vault</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 Token Vault stores OAuth tokens for external services. ApprovalKit retrieves them via Token Exchange (RFC 8693) — the agent never sees raw credentials.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm font-semibold text-red-800 dark:text-red-300 mb-2">Without Token Vault</p>
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
                <li>Fresh token via RFC 8693 exchange per action</li>
                <li>Revoke from dashboard instantly</li>
                <li>Rules control what agent can do</li>
              </ul>
            </div>
          </div>
          <CodeBlock language="text" code={`1. User connects service via Connected Accounts flow
   POST /me/v1/connected-accounts/connect
   Auth0 stores the federated refresh token

2. Agent requests action, human approves via Guardian

3. Platform exchanges refresh token for provider access token:
   POST /oauth/token
   grant_type=urn:auth0:params:oauth:grant-type:token-exchange
            :federated-connection-access-token
   subject_token={auth0_refresh_token}
   connection=stripe

4. Auth0 returns fresh access token, platform executes the action
   Agent never saw the token.`} />
        </Section>

        {/* Approval Models */}
        <Section id="approval-models">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Approval Models</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden">
              <thead className="bg-zinc-50 dark:bg-zinc-800/50">
                <tr>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Model</th>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Behavior</th>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Use Case</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {[
                  { model: "any_one", behavior: "First approver to respond wins", use: "Emergency access, on-call" },
                  { model: "specific", behavior: "Only the designated approver", use: "Manager approval, single owner" },
                  { model: "sequential", behavior: "Ordered chain: A then B then C", use: "Multi-step review, escalation" },
                  { model: "all_of_n", behavior: "Every listed approver must approve", use: "High-value actions, compliance" },
                  { model: "k_of_n", behavior: "k out of n approvers (quorum)", use: "Board votes, committee decisions" },
                ].map((row) => (
                  <tr key={row.model}>
                    <td className="p-3 font-mono text-xs text-zinc-800 dark:text-zinc-200">{row.model}</td>
                    <td className="p-3 text-zinc-600 dark:text-zinc-400">{row.behavior}</td>
                    <td className="p-3 text-zinc-500">{row.use}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">k_of_n with quorum window</p>
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

        {/* Step-up Auth */}
        <Section id="step-up">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Step-up Authentication</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Rules can escalate the approval model based on request parameters. A $50 charge needs one manager, a $5,000 charge requires both manager and CFO.
          </p>
          <CodeBlock language="json" code={`{
  "name": "Stripe charge",
  "connection": "stripe-prod",
  "action": "charge",
  "model": "any_one",
  "step_up_model": "all_of_n",
  "step_up_conditions": [
    { "field": "amount_usd", "operator": "gte", "value": 5000 }
  ]
}

// $349  -> any_one   (manager only)
// $5000 -> all_of_n  (manager + CFO both must approve)`} />
        </Section>

        {/* CIBA / Guardian */}
        <Section id="ciba">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">CIBA / Guardian Push</h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 CIBA sends push notifications to the approver via the Guardian app. The approver sees a binding message and taps Approve or Deny.
          </p>
          <div className="space-y-2 mb-4">
            {[
              { step: "1", text: "Platform sends CIBA request with binding message (max 64 chars)" },
              { step: "2", text: "Auth0 Guardian delivers push notification to approver's phone" },
              { step: "3", text: "Worker polls with exponential backoff (handles 429, slow_down)" },
              { step: "4", text: "Result: approved, rejected (access_denied), or timeout" },
            ].map(s => (
              <div key={s.step} className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                <span className="text-xs font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">{s.step}</span>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">{s.text}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-zinc-400">
            Approvers can also respond via the web dashboard. Both channels work simultaneously — whichever responds first wins.
          </p>
        </Section>

        {/* API Reference */}
        <Section id="endpoints">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">API Reference</h2>

          <div className="mb-6">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3">Authentication</p>
            <CodeBlock language="http" code={`POST /api/v1/request HTTP/1.1
Authorization: Bearer <API_KEY>
X-Signature: hmac-sha256=<timestamp>.<sha256_hex>
Content-Type: application/json`} />
          </div>

          <div className="space-y-1">
            {[
              { cat: "Approval Flow", endpoints: [
                { method: "POST",   path: "/api/v1/request",              desc: "Submit approval request (202 pending, 200 pre-approved, 403 blocked)" },
                { method: "GET",    path: "/api/v1/status/:job_id",       desc: "Poll job status" },
                { method: "POST",   path: "/api/v1/jobs/:id/decision",    desc: "Approve or reject via web" },
                { method: "PATCH",  path: "/api/v1/jobs/:id/params",      desc: "Modify params before approving (partial approval)" },
              ]},
              { cat: "Rules", endpoints: [
                { method: "POST",   path: "/api/v1/rules",                desc: "Create rule" },
                { method: "GET",    path: "/api/v1/rules",                desc: "List all rules" },
                { method: "PUT",    path: "/api/v1/rules/:id",            desc: "Update rule" },
                { method: "POST",   path: "/api/v1/rules/simulate",       desc: "Dry-run rule matching" },
              ]},
              { cat: "Approvers", endpoints: [
                { method: "POST",   path: "/api/v1/approvers",            desc: "Create approver" },
                { method: "DELETE", path: "/api/v1/approvers/:id",         desc: "Delete approver" },
                { method: "PUT",    path: "/api/v1/approvers/:id/delegate",desc: "Set delegation" },
              ]},
              { cat: "Connections", endpoints: [
                { method: "POST",   path: "/api/v1/connections",           desc: "Register service connection" },
                { method: "GET",    path: "/api/v1/connections/:id/connect-url", desc: "Start Connected Accounts OAuth flow" },
              ]},
              { cat: "Agents", endpoints: [
                { method: "POST",   path: "/api/v1/agents",               desc: "Register agent" },
                { method: "POST",   path: "/api/v1/agents/bootstrap",     desc: "Single-call agent provisioning" },
                { method: "POST",   path: "/api/v1/agents/:id/revoke",    desc: "Revoke API key" },
              ]},
              { cat: "Monitoring", endpoints: [
                { method: "GET",    path: "/api/v1/audit",                desc: "Audit log (FGA-filtered)" },
                { method: "GET",    path: "/api/v1/dashboard",            desc: "Aggregated stats" },
                { method: "GET",    path: "/api/v1/events",               desc: "SSE real-time event stream" },
                { method: "GET",    path: "/api/v1/security-status",      desc: "Auth0 / FGA connectivity status" },
              ]},
            ].map(group => (
              <div key={group.cat} className="mb-4">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 mt-4">{group.cat}</p>
                {group.endpoints.map((ep) => (
                  <div key={ep.path} className="flex items-start gap-3 py-2.5 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                    <Badge
                      variant={
                        ep.method === "POST" ? "default" :
                        ep.method === "GET" ? "success" :
                        ep.method === "DELETE" ? "danger" : "warning"
                      }
                      className="font-mono text-[10px] w-14 justify-center shrink-0 mt-0.5"
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
            ))}
          </div>
        </Section>

        {/* Security */}
        <Section id="security">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4">Security</h2>
          <div className="space-y-3">
            {[
              {
                title: "HMAC-SHA256 Request Signing",
                desc: "Every request includes a timestamp + HMAC signature. Requests older than 5 minutes are rejected.",
              },
              {
                title: "Per-Agent API Keys",
                desc: "Each agent gets its own ak_* key with SHA-256 hashing. Revoking one doesn't affect others.",
              },
              {
                title: "Scope Creep Detection",
                desc: "First-time actions and amounts exceeding 3x historical average trigger alerts in the audit log.",
              },
              {
                title: "Credential Isolation",
                desc: "HMAC_SECRET (signing) and CREDENTIALS_KEY (Fernet encryption) are separate keys.",
              },
              {
                title: "Blackout Windows",
                desc: "Rules can block actions during specific hours (e.g. no deploys between 22:00-06:00).",
              },
              {
                title: "Circuit Breaker",
                desc: "Redis-backed circuit breaker prevents cascade failures when Auth0 is unreachable.",
              },
              {
                title: "PII Masking",
                desc: "Emails and names are automatically masked in audit logs.",
              },
            ].map((item) => (
              <div key={item.title} className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-100 dark:border-zinc-800">
                <Shield className="h-4 w-4 text-zinc-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{item.title}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
