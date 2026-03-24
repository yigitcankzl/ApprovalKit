"use client";

import Link from "next/link";
import { Shield, ArrowRight, Zap, Lock, Users, GitBranch, FlaskConical, FileText } from "lucide-react";

const features = [
  {
    icon: Lock,
    title: "Token Vault",
    desc: "Credentials never reach your agent. Auth0 executes the action after approval.",
  },
  {
    icon: Zap,
    title: "CIBA Push",
    desc: "Approvers get a Guardian push notification on their phone. One tap to approve or deny.",
  },
  {
    icon: Shield,
    title: "FGA Access Control",
    desc: "Fine-grained authorization — admins, approvers, agents each see only what they own.",
  },
  {
    icon: Users,
    title: "Flexible Approval Models",
    desc: "Any-one, specific, all-of-n, k-of-n quorum, or sequential chain — pick per rule.",
  },
  {
    icon: GitBranch,
    title: "Rule Engine",
    desc: "Blackout windows, cooldown limits, scope creep detection, escalation chains.",
  },
  {
    icon: FlaskConical,
    title: "Simulation Mode",
    desc: "Test your rules without sending real notifications. Instant feedback loop.",
  },
];

const steps = [
  { n: "01", title: "Install the SDK", code: "pip install ./sdk" },
  { n: "02", title: "Add one decorator", code: "@kit.requires_approval(...)" },
  { n: "03", title: "Human approves on phone", code: "Auth0 Guardian push →  ✓ Approve" },
];

function Arrow() {
  return <span className="text-zinc-300 text-lg font-light select-none">→</span>;
}
function ArrowLeft() {
  return <span className="text-zinc-300 text-lg font-light select-none">←</span>;
}

export default function WelcomePage() {
  return (
    <div className="min-h-screen">

      {/* Hero */}
      <section className="pt-16 pb-20 text-center max-w-3xl mx-auto px-4">
        <div className="inline-flex items-center gap-2 bg-zinc-100 text-zinc-600 text-xs font-medium px-3 py-1.5 rounded-full mb-6">
          <Shield className="h-3.5 w-3.5" />
          Auth0 Token Vault · CIBA · FGA
        </div>

        <h1 className="text-5xl font-bold text-zinc-900 leading-tight tracking-tight mb-6">
          Human approval middleware
          <br />
          <span className="text-zinc-400">for AI agents</span>
        </h1>

        <p className="text-lg text-zinc-500 mb-10 leading-relaxed">
          One decorator. Any agent. Any action.
          <br />
          Your agent asks — a human approves — the platform executes.
          <br />
          The token <em>never</em> reaches the agent.
        </p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-zinc-900 text-white px-6 py-3 rounded-lg text-sm font-medium hover:bg-zinc-700 transition-colors"
          >
            Open Dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 border border-zinc-200 text-zinc-700 px-6 py-3 rounded-lg text-sm font-medium hover:bg-zinc-50 transition-colors"
          >
            <FileText className="h-4 w-4" />
            Read the Docs
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-3xl mx-auto px-4 mb-20">
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest text-center mb-8">
          How it works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
          {steps.map((s) => (
            <div key={s.n} className="bg-white border border-zinc-200 rounded-xl p-5">
              <span className="text-3xl font-bold text-zinc-100">{s.n}</span>
              <p className="text-sm font-semibold text-zinc-800 mt-2 mb-3">{s.title}</p>
              <code className="text-xs bg-zinc-950 text-green-400 px-3 py-1.5 rounded block font-mono">
                {s.code}
              </code>
            </div>
          ))}
        </div>

        {/* Architecture diagram */}
        <div className="bg-white border border-zinc-200 rounded-2xl p-8">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-widest text-center mb-8">Architecture</p>
          <div className="flex flex-col gap-4">
            {/* Row 1 */}
            <div className="flex items-center justify-center gap-2 flex-wrap">
              <div className="flex items-center gap-1.5 border border-zinc-200 rounded-lg px-4 py-2.5 bg-zinc-50">
                <span className="text-sm font-medium text-zinc-700">AI Agent</span>
                <span className="text-xs text-zinc-400">(Claude, GPT-4)</span>
              </div>
              <Arrow />
              <div className="flex items-center gap-1.5 border border-zinc-200 rounded-lg px-4 py-2.5 bg-zinc-50">
                <span className="text-sm font-medium text-zinc-700">ApprovalKit SDK</span>
              </div>
              <Arrow />
              <div className="flex items-center gap-1.5 border border-zinc-900 rounded-lg px-4 py-2.5 bg-zinc-900">
                <span className="text-sm font-medium text-white">CIBA Push</span>
                <span className="text-xs text-zinc-400">(Guardian)</span>
              </div>
              <Arrow />
              <div className="flex items-center gap-1.5 border border-zinc-200 rounded-lg px-4 py-2.5 bg-zinc-50">
                <span className="text-sm font-medium text-zinc-700">Human approves</span>
              </div>
            </div>
            {/* Connector */}
            <div className="flex justify-end pr-[6.5rem]">
              <div className="flex flex-col items-center">
                <div className="w-px h-4 bg-zinc-300" />
                <span className="text-xs text-zinc-400">approved</span>
                <div className="w-px h-4 bg-zinc-300" />
              </div>
            </div>
            {/* Row 2 */}
            <div className="flex items-center justify-end gap-2 flex-wrap">
              <div className="flex items-center gap-1.5 border border-zinc-200 rounded-lg px-4 py-2.5 bg-zinc-50">
                <span className="text-sm font-medium text-zinc-700">GitHub / Stripe API</span>
              </div>
              <ArrowLeft />
              <div className="flex items-center gap-1.5 border-2 border-blue-400 rounded-lg px-4 py-2.5 bg-blue-50">
                <span className="text-sm font-medium text-blue-700">Auth0 Token Vault</span>
                <span className="text-xs text-blue-400">retrieves token</span>
              </div>
            </div>
          </div>
          <p className="text-xs text-zinc-400 text-center mt-6">
            The token <strong>never reaches the agent</strong> — Auth0 Token Vault executes the action server-side after approval.
          </p>
        </div>
      </section>

      {/* Code snippet */}
      <section className="max-w-2xl mx-auto px-4 mb-20">
        <div className="rounded-xl overflow-hidden border border-zinc-200 shadow-sm">
          <div className="bg-zinc-900 px-4 py-2 flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-red-500/70" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/70" />
            <div className="h-3 w-3 rounded-full bg-green-500/70" />
            <span className="ml-2 text-xs text-zinc-500">shopping_bot.py</span>
          </div>
          <pre className="bg-zinc-950 text-zinc-100 text-sm font-mono px-6 py-5 overflow-x-auto leading-relaxed">{`from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url="http://localhost:8000",
    api_key="...",
    hmac_secret="...",
)

# Add one decorator — everything else stays the same
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str):
    stripe.charge(amount=amount, customer=customer)

# Bot calls it normally — ApprovalKit handles the rest
charge_customer(349, "alice@example.com")
# → push sent to approver's phone
# → human taps Approve
# → function executes`}</pre>
        </div>
      </section>

      {/* Features grid */}
      <section className="max-w-4xl mx-auto px-4 mb-20">
        <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest text-center mb-8">
          Everything you need
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f) => (
            <div key={f.title} className="bg-white border border-zinc-200 rounded-xl p-5 hover:border-zinc-300 transition-colors">
              <f.icon className="h-5 w-5 text-zinc-700 mb-3" />
              <p className="text-sm font-semibold text-zinc-800 mb-1">{f.title}</p>
              <p className="text-xs text-zinc-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-xl mx-auto px-4 pb-20 text-center">
        <div className="bg-zinc-900 rounded-2xl p-10">
          <h2 className="text-2xl font-bold text-white mb-3">Ready to integrate?</h2>
          <p className="text-zinc-400 text-sm mb-6">
            Set up in minutes. Works with any Python agent or framework.
          </p>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <Link
              href="/onboarding"
              className="inline-flex items-center gap-2 bg-white text-zinc-900 px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-zinc-100 transition-colors"
            >
              Get Started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 border border-zinc-700 text-zinc-300 px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors"
            >
              <FileText className="h-4 w-4" />
              Documentation
            </Link>
          </div>
        </div>
      </section>

    </div>
  );
}
