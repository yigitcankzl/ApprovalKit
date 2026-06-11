"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import {
  Shield, ArrowRight, Lock, Smartphone, CheckCircle2,
  XCircle, AlertTriangle, CreditCard, Mail, GitBranch,
  ChevronDown, Zap, Eye, EyeOff, Bot, FileText, Settings,
} from "lucide-react";

// ── Animated terminal ────────────────────────────────────────────────────────

function TypedLine({ text, delay, onDone }: { text: string; delay: number; onDone?: () => void }) {
  const [shown, setShown] = useState(0);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setStarted(true), delay);
    return () => clearTimeout(t1);
  }, [delay]);

  useEffect(() => {
    if (!started || shown >= text.length) {
      if (started && shown >= text.length && onDone) onDone();
      return;
    }
    const t = setTimeout(() => setShown(s => s + 1), 18);
    return () => clearTimeout(t);
  }, [started, shown, text, onDone]);

  if (!started) return null;
  return <span>{text.slice(0, shown)}<span className="animate-pulse">|</span></span>;
}

function LiveDemo() {
  const [step, setStep] = useState(0);

  const steps = [
    { type: "agent", text: 'kit.gate("stripe-prod", "charge", {"amount": 8500, "customer": "alice@example.com"})' },
    { type: "system", text: "Rule matched: [Expense] Large ($5000+) -- step-up to all_of_n" },
    { type: "system", text: "Guardian push sent to Manager..." },
    { type: "approve", text: "Manager approved" },
    { type: "system", text: "Guardian push sent to CFO..." },
    { type: "approve", text: "CFO approved" },
    { type: "system", text: "Token Vault: exchanged refresh token for Stripe access token" },
    { type: "success", text: "Stripe charge $8,500 executed. Agent never saw the token." },
  ];

  const colors: Record<string, string> = {
    agent: "text-blue-400",
    system: "text-zinc-400",
    approve: "text-green-400",
    success: "text-emerald-300 font-semibold",
  };

  const icons: Record<string, React.ReactNode> = {
    agent: <Bot className="h-3 w-3 text-blue-400 shrink-0 mt-1" />,
    system: <Zap className="h-3 w-3 text-zinc-500 shrink-0 mt-1" />,
    approve: <CheckCircle2 className="h-3 w-3 text-green-400 shrink-0 mt-1" />,
    success: <Shield className="h-3 w-3 text-emerald-400 shrink-0 mt-1" />,
  };

  return (
    <div className="rounded-xl overflow-hidden border border-zinc-800 shadow-2xl shadow-black/30">
      <div className="bg-zinc-900 px-4 py-2.5 flex items-center gap-2">
        <div className="h-3 w-3 rounded-full bg-red-500/70" />
        <div className="h-3 w-3 rounded-full bg-yellow-500/70" />
        <div className="h-3 w-3 rounded-full bg-green-500/70" />
        <span className="ml-2 text-xs text-zinc-500">approval_flow.py</span>
      </div>
      <div className="bg-zinc-950 px-5 py-4 font-mono text-xs leading-relaxed min-h-[220px] space-y-1.5">
        {steps.slice(0, step + 1).map((s, i) => (
          <div key={i} className={`flex items-start gap-2 ${colors[s.type]}`}>
            {icons[s.type]}
            {i === step ? (
              <TypedLine
                text={s.text}
                delay={i === 0 ? 800 : 200}
                onDone={() => {
                  if (step < steps.length - 1) {
                    setTimeout(() => setStep(st => st + 1), 600);
                  }
                }}
              />
            ) : (
              <span>{s.text}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Before / After comparison ────────────────────────────────────────────────

function ComparisonCard({ type }: { type: "without" | "with" }) {
  const isWithout = type === "without";
  return (
    <div className={`rounded-xl border p-6 ${
      isWithout
        ? "border-red-200 dark:border-red-900 bg-red-50/50 dark:bg-red-950/10"
        : "border-green-200 dark:border-green-900 bg-green-50/50 dark:bg-green-950/10"
    }`}>
      <div className="flex items-center gap-2 mb-4">
        {isWithout ? (
          <XCircle className="h-5 w-5 text-red-500" />
        ) : (
          <CheckCircle2 className="h-5 w-5 text-green-500" />
        )}
        <h3 className={`text-sm font-bold ${isWithout ? "text-red-800 dark:text-red-300" : "text-green-800 dark:text-green-300"}`}>
          {isWithout ? "Without ApprovalKit" : "With ApprovalKit"}
        </h3>
      </div>
      <ul className="space-y-2.5">
        {(isWithout ? [
          { icon: <Eye className="h-3.5 w-3.5" />, text: "Agent holds your Stripe API key in memory" },
          { icon: <AlertTriangle className="h-3.5 w-3.5" />, text: "Agent can charge any amount, anytime" },
          { icon: <EyeOff className="h-3.5 w-3.5" />, text: "No audit trail, no way to know what happened" },
          { icon: <XCircle className="h-3.5 w-3.5" />, text: "Compromised agent = compromised credentials" },
        ] : [
          { icon: <Lock className="h-3.5 w-3.5" />, text: "Agent never sees credentials (Token Vault)" },
          { icon: <Smartphone className="h-3.5 w-3.5" />, text: "You approve on your phone before anything executes" },
          { icon: <Shield className="h-3.5 w-3.5" />, text: "Step-up: $50 = manager, $5000 = manager + CFO" },
          { icon: <CheckCircle2 className="h-3.5 w-3.5" />, text: "Full audit trail, PII masked, scope creep alerts" },
        ]).map((item, i) => (
          <li key={i} className={`flex items-start gap-2 text-xs ${
            isWithout ? "text-red-700 dark:text-red-400" : "text-green-700 dark:text-green-400"
          }`}>
            <span className="mt-0.5 shrink-0">{item.icon}</span>
            {item.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Supported services ───────────────────────────────────────────────────────

const services = [
  { name: "Stripe", icon: CreditCard, color: "text-purple-500" },
  { name: "Gmail", icon: Mail, color: "text-red-500" },
  { name: "GitHub", icon: GitBranch, color: "text-zinc-700 dark:text-zinc-300" },
  { name: "Slack", icon: Zap, color: "text-yellow-500" },
  { name: "Salesforce", icon: Shield, color: "text-blue-500" },
];

// ── Main page ────────────────────────────────────────────────────────────────

export default function WelcomePage() {
  return (
    <div className="min-h-screen">

      {/* Hero */}
      <section className="pt-12 pb-16 max-w-5xl mx-auto px-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
          {/* Left: text */}
          <div>
            <div className="flex items-center gap-2 mb-5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 bg-gradient-to-r from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 text-purple-700 dark:text-purple-300 text-xs font-semibold px-3 py-1.5 rounded-full border border-purple-200 dark:border-purple-800">
                Open source · Local-first
              </span>
              <span className="inline-flex items-center gap-1.5 bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 text-xs font-medium px-3 py-1.5 rounded-full">
                Pluggable providers — Auth0 optional
              </span>
            </div>

            <h1 className="text-4xl lg:text-5xl font-bold text-zinc-900 dark:text-zinc-100 leading-[1.1] tracking-tight mb-5">
              Your AI agent
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
                asks before it acts
              </span>
            </h1>

            <p className="text-base text-zinc-500 dark:text-zinc-400 mb-8 leading-relaxed max-w-md">
              ApprovalKit is a human approval layer for AI agents.
              One line of code. Push notification to your phone.
              Approve or deny. Token Vault executes — agent never sees the credentials.
            </p>

            <div className="flex items-center gap-3 flex-wrap">
              <Link
                href="/demos/live?chain=orchestrator"
                className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white px-6 py-3 rounded-lg text-sm font-semibold shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-200"
              >
                Try AI Orchestrator
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/demos"
                className="inline-flex items-center gap-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 px-5 py-3 rounded-lg text-sm font-semibold hover:bg-zinc-700 dark:hover:bg-zinc-200 transition-colors"
              >
                All 10 Agents
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 px-5 py-3 rounded-lg text-sm font-medium hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
              >
                Open Dashboard
              </Link>
            </div>
            <div className="flex items-center gap-3 flex-wrap mt-3">
              <Link
                href="/docs"
                className="inline-flex items-center gap-2 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/30 px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
              >
                <FileText className="h-4 w-4" />
                Documentation
              </Link>
              <Link
                href="/settings"
                className="inline-flex items-center gap-2 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/30 px-4 py-2 rounded-lg text-sm font-medium hover:bg-amber-100 dark:hover:bg-amber-900/40 transition-colors"
              >
                <Settings className="h-4 w-4" />
                Setup Guide
              </Link>
            </div>

            {/* Service logos */}
            <div className="flex items-center gap-4 mt-8 pt-6 border-t border-zinc-100 dark:border-zinc-800">
              <span className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold">Works with</span>
              {services.map(s => (
                <div key={s.name} className="flex items-center gap-1.5" title={s.name}>
                  <s.icon className={`h-4 w-4 ${s.color}`} />
                  <span className="text-xs text-zinc-500 dark:text-zinc-400 hidden sm:inline">{s.name}</span>
                </div>
              ))}
              <span className="text-xs text-zinc-400">+ 25 more</span>
            </div>
          </div>

          {/* Right: live terminal animation */}
          <div>
            <LiveDemo />
          </div>
        </div>
      </section>

      {/* Before / After */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <h2 className="text-center text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-6">
          Why this matters
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ComparisonCard type="without" />
          <ComparisonCard type="with" />
        </div>
      </section>

      {/* How it works — visual flow */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <h2 className="text-center text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-8">
          How it works
        </h2>
        <div className="flex flex-col md:flex-row items-stretch gap-3">
          {[
            { n: "1", title: "Agent calls gate()", sub: "One line of code", color: "border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/10", accent: "text-blue-600 dark:text-blue-400" },
            { n: "2", title: "Rule engine evaluates", sub: "Conditions, step-up, budget", color: "border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900", accent: "text-zinc-700 dark:text-zinc-300" },
            { n: "3", title: "Guardian push sent", sub: "Approver sees on phone", color: "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/10", accent: "text-amber-600 dark:text-amber-400" },
            { n: "4", title: "Human approves", sub: "Or denies / modifies params", color: "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/10", accent: "text-green-600 dark:text-green-400" },
            { n: "5", title: "Token Vault executes", sub: "Agent never sees the token", color: "border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/10", accent: "text-emerald-600 dark:text-emerald-400" },
          ].map((s, i) => (
            <div key={i} className="flex items-center gap-3 flex-1">
              <div className={`rounded-xl border p-4 flex-1 ${s.color}`}>
                <div className={`text-2xl font-bold ${s.accent} opacity-30`}>{s.n}</div>
                <p className={`text-sm font-semibold ${s.accent} mt-1`}>{s.title}</p>
                <p className="text-[11px] text-zinc-400 mt-0.5">{s.sub}</p>
              </div>
              {i < 4 && <ArrowRight className="h-4 w-4 text-zinc-300 dark:text-zinc-600 shrink-0 hidden md:block" />}
            </div>
          ))}
        </div>
      </section>

      {/* Code snippet */}
      <section className="max-w-2xl mx-auto px-4 mb-16">
        <h2 className="text-center text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-6">
          Integration
        </h2>
        <div className="rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 shadow-sm">
          <div className="bg-zinc-900 px-4 py-2.5 flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-red-500/70" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/70" />
            <div className="h-3 w-3 rounded-full bg-green-500/70" />
            <span className="ml-2 text-xs text-zinc-500">your_agent.py</span>
          </div>
          <pre className="bg-zinc-950 text-zinc-100 text-sm font-mono px-6 py-5 overflow-x-auto leading-relaxed">{`from approvalkit import ApprovalKit
import os

kit = ApprovalKit(
    base_url=os.environ["APPROVALKIT_URL"],
    api_key=os.environ["APPROVALKIT_API_KEY"],
    hmac_secret=os.environ["APPROVALKIT_HMAC_SECRET"],
)

# That's it. One line per action.
kit.gate("stripe-prod", "charge", {"amount": 349, "customer": "alice@example.com"})
kit.gate("gmail-prod", "send_email", {"to": "bob@test.com", "subject": "Invoice"})
kit.gate("github-main", "deploy", {"ref": "v2.0", "env": "production"})`}</pre>
        </div>
      </section>

      {/* Features — compact */}
      <section className="max-w-4xl mx-auto px-4 mb-16">
        <h2 className="text-center text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-8">
          Built for production
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { title: "5 Approval Models", sub: "any-one, specific, sequential, all-of-n, k-of-n" },
            { title: "Step-up Auth", sub: "Auto-escalate based on amount, type, risk" },
            { title: "Scope Creep Detection", sub: "Alerts on new actions or 3x amount anomaly" },
            { title: "Budget Limits", sub: "Daily, weekly, monthly spend caps per agent" },
            { title: "Blackout Windows", sub: "Block actions during off-hours" },
            { title: "Partial Approval", sub: "Approver can modify params before approving" },
            { title: "Delegation", sub: "Out of office? Route to backup approver" },
            { title: "PII Masking", sub: "Emails and names masked in audit logs" },
          ].map(f => (
            <div key={f.title} className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-4 bg-white dark:bg-zinc-900">
              <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">{f.title}</p>
              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">{f.sub}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-xl mx-auto px-4 pb-16 text-center">
        <div className="bg-gradient-to-br from-zinc-900 to-zinc-800 dark:from-zinc-800 dark:to-zinc-900 rounded-2xl p-10 border border-zinc-700">
          <h2 className="text-2xl font-bold text-white mb-2">See it in action</h2>
          <p className="text-zinc-400 text-sm mb-6">
            Try the demo agents powered by ApprovalKit with real Auth0 Token Vault integration.
          </p>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <Link
              href="/demos/live?chain=orchestrator"
              className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-600 to-blue-500 text-white px-6 py-3 rounded-lg text-sm font-semibold hover:from-purple-700 hover:to-blue-600 transition-colors shadow-lg shadow-purple-500/20"
            >
              AI Orchestrator Demo
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/demos"
              className="inline-flex items-center gap-2 border border-zinc-600 text-zinc-300 px-6 py-3 rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors"
            >
              All 8 Agent Demos
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-4xl mx-auto px-4 pb-8 pt-4 border-t border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <div className="flex items-center gap-4">
            <a href="https://github.com/yigitcankzl/ApprovalKit" target="_blank" rel="noopener noreferrer" className="hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors flex items-center gap-1">
              <GitBranch className="h-3 w-3" /> GitHub
            </a>
            <a href="https://authorizedtoact.devpost.com/" target="_blank" rel="noopener noreferrer" className="hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
              Devpost
            </a>
            <Link href="/docs/demo-architecture" className="hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
              Architecture
            </Link>
          </div>
          <span>Built with Auth0 Token Vault, CIBA &amp; FGA</span>
        </div>
      </footer>

    </div>
  );
}
