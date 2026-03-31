"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import {
  ArrowLeft,
  Shield,
  Zap,
  Brain,
  Lock,
  GitBranch,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Layers,
  RefreshCw,
  Eye,
  FileText,
  Bot,
  ShieldAlert,
  Target,
} from "lucide-react";

function Section({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      {children}
    </section>
  );
}

const NAV = [
  { id: "overview", label: "Overview" },
  { id: "orchestrator", label: "AI Orchestrator" },
  { id: "analysis-tags", label: "  Analysis Tags" },
  { id: "least-privilege", label: "  Least Privilege" },
  { id: "defense-in-depth", label: "Defense-in-Depth" },
  { id: "credential-isolation", label: "  Credential Isolation" },
  { id: "prompt-layering", label: "  Prompt Layering" },
  { id: "input-validation", label: "  Input Validation" },
  { id: "sub-agents", label: "Sub-Agent System" },
  { id: "parallel-execution", label: "  Parallel Execution" },
  { id: "adversarial-validator", label: "  Adversarial Validator" },
  { id: "smart-briefing", label: "  Smart Briefing" },
  { id: "chain-context", label: "Chain Context Passing" },
  { id: "synthesized-spec", label: "  Synthesized Spec" },
  { id: "verified-actions", label: "  Verified Actions" },
  { id: "resilience", label: "Resilience Patterns" },
  { id: "retry-backoff", label: "  Retry with Backoff" },
  { id: "circuit-breaker", label: "  Circuit Breaker" },
  { id: "contextual-tips", label: "Contextual Tips" },
  { id: "structured-audit", label: "Structured Audit" },
];

export default function DemoArchitecturePage() {
  const [activeSection, setActiveSection] = useState("overview");

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    NAV.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveSection(id); },
        { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
      );
      obs.observe(el);
      observers.push(obs);
    });
    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <div className="flex gap-8 max-w-6xl mx-auto">
      {/* Sidebar */}
      <aside className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-6 space-y-0.5 max-h-[calc(100vh-3rem)] overflow-y-auto pb-12">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 px-2">
            Architecture
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
      <div className="flex-1 space-y-14 pb-24">

        {/* Header */}
        <Section id="overview">
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 shadow-sm transition-colors mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Docs
          </Link>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500 mb-2">
            Demo Architecture
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-6">
            Deep dive into the patterns and architectural decisions powering the ApprovalKit live demo.
            Many patterns are inspired by production agent systems like Claude Code&apos;s coordinator architecture.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { icon: <Brain className="h-5 w-5" />, title: "AI Orchestrator", desc: "LLM plans multi-agent workflows" },
              { icon: <Shield className="h-5 w-5" />, title: "Defense-in-Depth", desc: "3-layer security at every level" },
              { icon: <Zap className="h-5 w-5" />, title: "7 Sub-Agents", desc: "Risk, cost, compliance, rollback, validator, audit, summary" },
            ].map((c) => (
              <Card key={c.title}>
                <CardContent className="pt-5 pb-4">
                  <div className="text-zinc-500 dark:text-zinc-400 mb-2">{c.icon}</div>
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{c.title}</h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{c.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* AI Orchestrator */}
        <Section id="orchestrator">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            AI Orchestrator
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
            The orchestrator is the entry point for the live demo. Given a natural language request,
            it plans a multi-agent workflow: selecting agents, assigning tools, and ordering steps.
          </p>
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-5 bg-zinc-50/50 dark:bg-zinc-800/30 space-y-4">
            <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Workflow Pipeline</h4>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {["User Prompt", "Orchestrator (LLM)", "Sub-Agent Analysis", "Agent Chain", "Validator", "Audit + Summary"].map((step, i) => (
                <div key={step} className="flex items-center gap-2">
                  <span className="px-3 py-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium">{step}</span>
                  {i < 5 && <span className="text-zinc-300 dark:text-zinc-600">→</span>}
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* Analysis Tags */}
        <Section id="analysis-tags">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Eye className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            Analysis Tags Pattern
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Before producing a plan, the orchestrator wraps its reasoning in <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">&lt;analysis&gt;</code> tags.
            This pattern, inspired by Claude Code&apos;s context compaction system, forces the LLM to think through
            domain identification, operation ordering, security implications, and least privilege assignment before outputting JSON.
          </p>
          <div className="rounded-lg bg-zinc-950 text-zinc-100 text-xs font-mono p-4 overflow-x-auto">
            <pre>{`<analysis>
- Domains: FINANCE (refund) + COMMUNICATION (email, Slack)
- Order: refund first → apology email → team notification
- Security: All via Token Vault, agent never sees Stripe key
- Least privilege: expense gets process_refund only, comms gets send_email + send_slack
</analysis>

{"plan": [{"agent_id": "expense", ...}, {"agent_id": "comms", ...}]}`}</pre>
          </div>
          <p className="text-xs text-zinc-400 mt-2">
            The <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">&lt;analysis&gt;</code> block is automatically stripped from the JSON output by the parser.
            This improves plan quality without affecting downstream processing.
          </p>
        </Section>

        {/* Least Privilege */}
        <Section id="least-privilege">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Lock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            Per-Step Least Privilege
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Each agent in a chain receives only the tools needed for its specific step (1-2 tools, not the full 15+).
            This is <strong>framework-level enforcement</strong>, not prompt-level — even prompt injection cannot access filtered tools.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { agent: "E-Commerce Agent", tools: ["process_refund"], color: "emerald" },
              { agent: "Communications Agent", tools: ["send_email", "send_slack"], color: "blue" },
              { agent: "Security Agent", tools: ["lock_repo"], color: "red" },
            ].map(a => (
              <div key={a.agent} className={`rounded-lg border border-${a.color}-200 dark:border-${a.color}-800 bg-${a.color}-50/50 dark:bg-${a.color}-950/20 p-3`}>
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">{a.agent}</p>
                <div className="flex gap-1 mt-1.5 flex-wrap">
                  {a.tools.map(t => (
                    <code key={t} className="text-[10px] bg-white dark:bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-600 dark:text-zinc-400">{t}</code>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Defense-in-Depth */}
        <Section id="defense-in-depth">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <ShieldAlert className="h-5 w-5 text-red-600 dark:text-red-400" />
            Defense-in-Depth Security
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
            Security rules are enforced at multiple layers simultaneously. Even if one layer is compromised,
            the others prevent unauthorized actions. This pattern mirrors Claude Code&apos;s layered permission system.
          </p>
        </Section>

        {/* Credential Isolation */}
        <Section id="credential-isolation">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Lock className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            Credential Isolation via Auth0 Token Vault
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Agents <strong>never see, hold, or handle</strong> user credentials. All API execution goes through
            Auth0 Token Vault using Token Exchange (RFC 8693). The agent sends an action request;
            ApprovalKit exchanges the refresh token for a short-lived access token server-side and executes the action.
          </p>
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-5 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {[
                { label: "Agent", sub: "Sends action request" },
                { label: "ApprovalKit", sub: "Rule evaluation + CIBA" },
                { label: "Token Vault", sub: "RFC 8693 exchange" },
                { label: "Stripe/Gmail/GitHub", sub: "Executes with fresh token" },
              ].map((s, i) => (
                <div key={s.label} className="flex items-center gap-2">
                  <div className="text-center">
                    <span className="px-3 py-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 font-medium block">{s.label}</span>
                    <span className="text-[9px] text-zinc-400 mt-0.5 block">{s.sub}</span>
                  </div>
                  {i < 3 && <span className="text-zinc-300 dark:text-zinc-600">→</span>}
                </div>
              ))}
            </div>
          </div>
        </Section>

        {/* Prompt Layering */}
        <Section id="prompt-layering">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Layers className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            Prompt Layering
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Security rules are repeated across 3 layers in the prompt hierarchy. LLMs tend to forget instructions
            in long contexts — repeating critical rules at multiple points ensures consistent behavior.
          </p>
          <div className="space-y-2">
            {[
              { layer: "Layer 1: Core Behavior", desc: "Every agent's system prompt includes 4 NEVER rules: never see credentials, never bypass approval, never expose tokens, never access APIs directly.", color: "red" },
              { layer: "Layer 2: Orchestrator", desc: "The orchestrator prompt repeats credential isolation and least privilege rules before planning.", color: "amber" },
              { layer: "Layer 3: Chain Context", desc: "Each step's context includes 'SECURITY: You never hold credentials — all execution goes through Auth0 Token Vault.'", color: "blue" },
            ].map(l => (
              <div key={l.layer} className={`rounded-lg border border-${l.color}-200 dark:border-${l.color}-800 bg-${l.color}-50/30 dark:bg-${l.color}-950/10 p-3`}>
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">{l.layer}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{l.desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Input Validation */}
        <Section id="input-validation">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
            Input Parameter Validation
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s 23-point bash security system, every tool parameter is validated before processing.
            Dangerous patterns are blocked at the framework level:
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[
              { pattern: "SQL Injection", example: "DROP TABLE; --", icon: "🛡️" },
              { pattern: "Shell Injection", example: "; rm -rf /", icon: "🛡️" },
              { pattern: "Path Traversal", example: "../../etc/passwd", icon: "🛡️" },
              { pattern: "Script Injection", example: "<script>alert(1)</script>", icon: "🛡️" },
            ].map(p => (
              <div key={p.pattern} className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-2.5">
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">{p.icon} {p.pattern}</p>
                <code className="text-[10px] text-red-500 dark:text-red-400 font-mono">{p.example}</code>
              </div>
            ))}
          </div>
        </Section>

        {/* Sub-Agent System */}
        <Section id="sub-agents">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <Bot className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            Sub-Agent System
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
            Every orchestrator workflow is analyzed by 7 specialized sub-agents. 4 run before execution (pre-flight checks),
            1 runs after each step (validation), and 2 run after completion (audit + summary).
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { name: "Risk Assessor", when: "Pre-execution", desc: "Financial, security, compliance, and blast radius analysis", icon: "🛡️", color: "red" },
              { name: "Cost Estimator", when: "Pre-execution", desc: "Estimates spend, identifies approval thresholds", icon: "💰", color: "emerald" },
              { name: "Compliance Checker", when: "Pre-execution", desc: "GDPR, PCI-DSS, HIPAA, PII exposure checks", icon: "📜", color: "blue" },
              { name: "Rollback Planner", when: "Pre-execution", desc: "Defines undo actions for each step if failure occurs", icon: "🔄", color: "amber" },
              { name: "Validator", when: "Per-step", desc: "Independent adversarial review of each action's results", icon: "✅", color: "green" },
              { name: "Audit Reporter", when: "Post-chain", desc: "SOC2-ready audit trail with timestamps and rule matches", icon: "📝", color: "purple" },
              { name: "Summary Agent", when: "Post-chain", desc: "Structured executive brief: request, actions, impact, next steps", icon: "📊", color: "indigo" },
            ].map(a => (
              <div key={a.name} className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">{a.icon} {a.name}</span>
                  <span className={`text-[9px] font-medium px-2 py-0.5 rounded-full bg-${a.color}-100 dark:bg-${a.color}-900/30 text-${a.color}-700 dark:text-${a.color}-400`}>{a.when}</span>
                </div>
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{a.desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Parallel Execution */}
        <Section id="parallel-execution">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Zap className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
            Parallel Execution
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s coordinator pattern and <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">/simplify</code> skill
            (which launches 3 review agents in parallel), pre-execution sub-agents run concurrently via
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">Promise.allSettled()</code>.
          </p>
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-5 bg-zinc-50/50 dark:bg-zinc-800/30">
            <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mb-2">Before (sequential): ~12 seconds</p>
            <div className="flex items-center gap-1 mb-3 text-[10px]">
              {["Risk", "Cost", "Compliance", "Rollback"].map((s, i) => (
                <div key={s} className="flex items-center gap-1">
                  <span className="px-2 py-1 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300">{s} (~3s)</span>
                  {i < 3 && <span className="text-zinc-300">→</span>}
                </div>
              ))}
            </div>
            <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mb-2">After (parallel): ~3 seconds</p>
            <div className="flex items-center gap-1 text-[10px]">
              {["Risk", "Cost", "Compliance", "Rollback"].map(s => (
                <span key={s} className="px-2 py-1 rounded bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">{s} (~3s)</span>
              ))}
              <span className="text-zinc-400 ml-1">(all at once)</span>
            </div>
          </div>
        </Section>

        {/* Adversarial Validator */}
        <Section id="adversarial-validator">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Target className="h-4 w-4 text-red-600 dark:text-red-400" />
            Adversarial Validator
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s verification agent (&quot;Your job is not to confirm it works — it&apos;s to try to break it&quot;),
            the validator runs after each chain step as an independent reviewer with adversarial probes:
          </p>
          <div className="space-y-1.5">
            {[
              "Amount Anomaly — Is the total spend unusually high for this type of request?",
              "Scope Creep — Did the agent do MORE than what was asked?",
              "Target Mismatch — Are emails/payments going to the correct recipients?",
              "Sequence Violation — Were actions executed in the wrong order?",
            ].map(probe => (
              <div key={probe} className="flex items-start gap-2 text-xs text-zinc-600 dark:text-zinc-400">
                <CheckCircle2 className="h-3.5 w-3.5 text-red-500 mt-0.5 shrink-0" />
                <span>{probe}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Smart Briefing */}
        <Section id="smart-briefing">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <FileText className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
            Smart Colleague Briefing
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            From Claude Code&apos;s coordinator prompt: &quot;Brief the agent like a smart colleague who just walked into the room.&quot;
            Each sub-agent receives context that explains its role in the workflow lifecycle:
          </p>
          <div className="rounded-lg bg-zinc-950 text-zinc-100 text-xs font-mono p-4 overflow-x-auto">
            <pre>{`// Risk Assessor (pre-execution):
"You are being briefed on a workflow that is ABOUT TO execute —
 your assessment determines whether additional guardrails are needed."

// Validator (per-step):
"A workflow step just completed — you are an independent reviewer.
 Your verdict determines if the chain continues or halts."

// Audit Reporter (post-chain):
"The workflow is complete — you are generating the official
 compliance-ready audit trail for SOC2/regulatory review."`}</pre>
          </div>
        </Section>

        {/* Chain Context */}
        <Section id="chain-context">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <GitBranch className="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
            Chain Context Passing
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
            Multi-agent chains pass verified action results (not LLM-generated text) between steps.
            This prevents cascading hallucinations where Agent A&apos;s fabricated output becomes Agent B&apos;s &quot;facts&quot;.
          </p>
        </Section>

        {/* Synthesized Spec */}
        <Section id="synthesized-spec">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <Brain className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            Synthesized Spec Pattern
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            From Claude Code&apos;s coordinator: &quot;Never write &apos;based on your findings&apos; — these phrases delegate understanding
            to the worker instead of doing it yourself.&quot; Each chain step receives synthesized context with:
          </p>
          <div className="space-y-1.5">
            {[
              "Scenario description and step position (Step 2 of 4)",
              "Verified action results from ALL previous agents",
              "Specific role assignment (not generic delegation)",
              "Security reminder (credential isolation)",
            ].map(item => (
              <div key={item} className="flex items-start gap-2 text-xs text-zinc-600 dark:text-zinc-400">
                <CheckCircle2 className="h-3.5 w-3.5 text-blue-500 mt-0.5 shrink-0" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Verified Actions */}
        <Section id="verified-actions">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            Verified Action Results
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Only verified tool execution results pass between agents — never raw LLM text.
            Each result includes connection, action, amount, status, and matched rule name:
          </p>
          <div className="rounded-lg bg-zinc-950 text-zinc-100 text-xs font-mono p-4 overflow-x-auto">
            <pre>{`VERIFIED ACTIONS (from previous agents — real system results, not claims):

Step 1 — E-Commerce Agent:
  - stripe-prod/process_refund ($420) → PENDING (rule: Large Refund - Manager Approval)
  - gmail-prod/send_email → AUTO_APPROVED

Step 2 — Communications Agent:
  Build on the results above. PENDING means awaiting human approval.`}</pre>
          </div>
        </Section>

        {/* Resilience */}
        <Section id="resilience">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <RefreshCw className="h-5 w-5 text-green-600 dark:text-green-400" />
            Resilience Patterns
          </h2>
        </Section>

        {/* Retry with Backoff */}
        <Section id="retry-backoff">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <RefreshCw className="h-4 w-4 text-green-600 dark:text-green-400" />
            Retry with Exponential Backoff
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">withRetry.ts</code> pattern,
            Token Exchange calls retry with exponential backoff on server errors (5xx):
          </p>
          <div className="rounded-lg bg-zinc-950 text-zinc-100 text-xs font-mono p-4 overflow-x-auto">
            <pre>{`Attempt 1: Token Exchange → 502 Bad Gateway
  → Wait 500ms (base_delay)
Attempt 2: Token Exchange → 503 Service Unavailable
  → Wait 1000ms (base_delay × 2)
Attempt 3: Token Exchange → 200 OK ✓
  → Success! Token cached for 4.5 minutes`}</pre>
          </div>
          <p className="text-xs text-zinc-400 mt-2">
            Client errors (401 Unauthorized, 403 Forbidden) fail immediately — no retry, since the issue is credential-related.
          </p>
        </Section>

        {/* Circuit Breaker */}
        <Section id="circuit-breaker">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            Circuit Breaker
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Redis-backed circuit breaker protects against Auth0 downtime cascade. After 5 consecutive failures
            within 60 seconds, the circuit opens and all Token Exchange requests are skipped for 30 seconds.
          </p>
          <div className="flex items-center gap-3 text-xs">
            {[
              { state: "CLOSED", desc: "Normal — all requests pass through", color: "emerald" },
              { state: "OPEN", desc: "5 failures — requests skipped for 30s", color: "red" },
              { state: "HALF-OPEN", desc: "Testing — 1 request allowed to check recovery", color: "amber" },
            ].map(s => (
              <div key={s.state} className={`flex-1 rounded-lg border border-${s.color}-200 dark:border-${s.color}-800 bg-${s.color}-50/30 dark:bg-${s.color}-950/10 p-2.5 text-center`}>
                <p className={`text-[10px] font-bold text-${s.color}-700 dark:text-${s.color}-400`}>{s.state}</p>
                <p className="text-[9px] text-zinc-400 mt-0.5">{s.desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Contextual Tips */}
        <Section id="contextual-tips">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <Activity className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            Contextual Tips
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s tip system, the shield panel shows inline explanations for each event:
          </p>
          <div className="space-y-2">
            {[
              { event: "Auto-approved", tip: "Below threshold — auto-approved by rule engine", color: "emerald" },
              { event: "Step-up triggered", tip: "High-value action — approval model escalated automatically", color: "amber" },
              { event: "Blocked", tip: "Rule engine blocked this action — agent never had access to credentials", color: "orange" },
              { event: "Scope creep", tip: "First-time action or 3x amount anomaly detected", color: "red" },
              { event: "Shield OFF", tip: "Without ApprovalKit, this action executes with zero oversight", color: "red" },
            ].map(t => (
              <div key={t.event} className={`rounded-lg border border-${t.color}-200 dark:border-${t.color}-800 bg-${t.color}-50/30 dark:bg-${t.color}-950/10 p-3 flex items-start gap-2`}>
                <span className={`text-[10px] font-bold text-${t.color}-700 dark:text-${t.color}-400 shrink-0 w-28`}>{t.event}</span>
                <span className="text-[11px] text-zinc-500 dark:text-zinc-400 italic">{t.tip}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Structured Audit */}
        <Section id="structured-audit">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2 mb-4">
            <FileText className="h-5 w-5 text-slate-600 dark:text-slate-400" />
            Structured Audit Output
          </h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
            Inspired by Claude Code&apos;s Session Memory template, the summary agent produces a structured executive brief:
          </p>
          <div className="rounded-lg bg-zinc-950 text-zinc-100 text-xs font-mono p-4 overflow-x-auto">
            <pre>{`REQUEST: VIP customer $420 refund with apology
ACTIONS TAKEN:
- process_refund ($420) → PENDING via stripe-prod (rule: Large Refund)
- send_email → AUTO_APPROVED via gmail-prod
- send_slack → AUTO_APPROVED via slack-prod
FINANCIAL IMPACT: $420 total ($0 auto, $420 pending, $0 blocked)
SECURITY: All actions via Token Vault — zero credential exposure
PENDING: $420 refund awaiting manager approval
NEXT STEPS: Approve refund in dashboard; monitor Stripe for confirmation`}</pre>
          </div>
        </Section>

        {/* Footer */}
        <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800/50 px-5 py-4">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-zinc-500 mt-0.5 shrink-0" />
            <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
              <p>
                <strong className="text-zinc-700 dark:text-zinc-300">Architecture references:</strong>{" "}
                Patterns documented here are inspired by production agent systems. Claude Code&apos;s
                coordinator mode, verification agent, and layered security system informed several
                architectural decisions in ApprovalKit.
              </p>
              <p>
                <strong className="text-zinc-700 dark:text-zinc-300">Open source:</strong>{" "}
                All source code is available in the repository. See{" "}
                <code className="bg-zinc-200 dark:bg-zinc-700 px-1 rounded">api/services/agent_chat.py</code>,{" "}
                <code className="bg-zinc-200 dark:bg-zinc-700 px-1 rounded">api/routes/agent_chat.py</code>, and{" "}
                <code className="bg-zinc-200 dark:bg-zinc-700 px-1 rounded">frontend/src/app/demos/live/page.tsx</code>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
