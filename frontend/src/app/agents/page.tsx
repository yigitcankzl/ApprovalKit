"use client";

import { useState } from "react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ShoppingCart, Server, Package, FlaskConical, CreditCard, Mail, Users,
  Play, CheckCircle2, XCircle, Clock, ChevronRight, ArrowRight, Loader2,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface FlowStep {
  type: "agent" | "platform" | "approver" | "gate" | "action";
  label: string;
  sub?: string;
}

interface Scenario {
  title: string;
  description: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
  flow: FlowStep[];
  badge: "success" | "info" | "warning" | "danger" | "default";
  badgeLabel: string;
}

interface Agent {
  id: string;
  title: string;
  icon: React.ElementType;
  description: string;
  scenarios: Scenario[];
}

// ── Agent definitions ─────────────────────────────────────────────────────────

const AGENTS: Agent[] = [
  {
    id: "ecommerce",
    title: "E-Commerce Agent",
    icon: ShoppingCart,
    description: "AI shopping agent that processes Stripe payments and refunds. Amount tiers trigger different approval chains — small orders pass automatically, large ones require step-up approval.",
    scenarios: [
      {
        title: "Small charge ($49)",
        description: "Under threshold — no rule matches, auto-approved instantly.",
        connection: "stripe-prod", action: "charge",
        params: { amount_usd: 49, customer: "alice@example.com", description: "T-shirt" },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "E-Commerce Agent", sub: "charge_customer(49, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "Stripe Charge", sub: "$49 → alice@example.com" },
        ],
      },
      {
        title: "Medium charge ($349)",
        description: "Sales manager receives a Guardian push and taps Approve.",
        connection: "stripe-prod", action: "charge",
        params: { amount_usd: 349, customer: "bob@example.com", description: "Premium plan" },
        badge: "info", badgeLabel: "any_one",
        flow: [
          { type: "agent", label: "E-Commerce Agent", sub: "charge_customer(349, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: medium charge" },
          { type: "approver", label: "Sales Manager", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Charge", sub: "$349 → bob@example.com" },
        ],
      },
      {
        title: "Large charge ($5,000) — STEP-UP",
        description: "Both sales_manager and CFO must approve. all_of_n — neither can skip the other.",
        connection: "stripe-prod", action: "charge",
        params: { amount_usd: 5000, customer: "corp@example.com", description: "Enterprise license" },
        badge: "warning", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "E-Commerce Agent", sub: "charge_customer(5000, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: large charge (step-up)" },
          { type: "approver", label: "Sales Manager", sub: "Guardian push → Approve" },
          { type: "approver", label: "CFO", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Charge", sub: "$5,000 → corp@example.com" },
        ],
      },
      {
        title: "Refund ($340) — partial approval",
        description: "CS Manager may reduce the refund amount before approving.",
        connection: "stripe-prod", action: "refund",
        params: { amount_usd: 340, customer: "alice@example.com", reason: "Wrong size" },
        badge: "default", badgeLabel: "partial",
        flow: [
          { type: "agent", label: "E-Commerce Agent", sub: "refund_customer(340, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: large refund" },
          { type: "approver", label: "CS Manager", sub: "May edit params → Approve" },
          { type: "action", label: "Stripe Refund", sub: "$340 (or modified) → alice" },
        ],
      },
    ],
  },
  {
    id: "hr",
    title: "HR Agent",
    icon: Users,
    description: "AI HR assistant handling hiring, offboarding, and team communication. Termination emails require both HR Manager and CEO. GitHub access removal requires IT + HR sign-off.",
    scenarios: [
      {
        title: "Interview invite",
        description: "Low-risk email — auto-approved, no rule needed.",
        connection: "gmail-prod", action: "send_email",
        params: { type: "invite", recipient: "candidate@example.com", subject: "Interview invitation" },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "HR Agent", sub: "send_email(type=invite, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "Gmail Send", sub: "Invite → candidate" },
        ],
      },
      {
        title: "Offer letter",
        description: "HR Manager must review salary and terms before sending.",
        connection: "gmail-prod", action: "send_email",
        params: { type: "offer_letter", recipient: "hire@example.com", subject: "Offer: $180k Senior Eng" },
        badge: "info", badgeLabel: "specific",
        flow: [
          { type: "agent", label: "HR Agent", sub: "send_email(type=offer_letter, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: offer letter" },
          { type: "approver", label: "HR Manager", sub: "Guardian push → Approve" },
          { type: "action", label: "Gmail Send", sub: "Offer letter → hire@example.com" },
        ],
      },
      {
        title: "Termination letter — all_of_n",
        description: "Highest sensitivity. HR Manager and CEO must both approve before sending.",
        connection: "gmail-prod", action: "send_email",
        params: { type: "termination", recipient: "employee@example.com", subject: "Employment Termination" },
        badge: "danger", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "HR Agent", sub: "send_email(type=termination, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: termination" },
          { type: "approver", label: "HR Manager", sub: "Guardian push → Approve" },
          { type: "approver", label: "CEO", sub: "Guardian push → Approve" },
          { type: "action", label: "Gmail Send", sub: "Termination → employee" },
        ],
      },
      {
        title: "GitHub remove member — IT + HR",
        description: "Offboarding: both IT Manager and HR Manager confirm before revoking access.",
        connection: "github-prod", action: "remove_member",
        params: { username: "employee", org: "acme-corp", reason: "Employment terminated" },
        badge: "danger", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "HR Agent", sub: "remove_github_member(...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: remove member" },
          { type: "approver", label: "IT Manager", sub: "Guardian push → Approve" },
          { type: "approver", label: "HR Manager", sub: "Guardian push → Approve" },
          { type: "action", label: "GitHub API", sub: "Remove employee from acme-corp" },
        ],
      },
    ],
  },
  {
    id: "devops",
    title: "DevOps Agent",
    icon: Server,
    description: "CI/CD agent managing GitHub deployments. Staging is always auto-approved. Production needs a maintainer. Rollbacks require the lead engineer only.",
    scenarios: [
      {
        title: "Deploy to staging",
        description: "Staging deployments are always safe — no approval gate.",
        connection: "github-main", action: "deploy",
        params: { ref: "main", environment: "staging", service: "api" },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "DevOps Agent", sub: "deploy(env=staging)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "GitHub Actions", sub: "Deploy main → staging" },
        ],
      },
      {
        title: "Deploy to production",
        description: "Any maintainer can approve. First response unblocks the deploy.",
        connection: "github-main", action: "deploy",
        params: { ref: "v2.4.1", environment: "production", service: "api" },
        badge: "info", badgeLabel: "any_one",
        flow: [
          { type: "agent", label: "DevOps Agent", sub: "deploy(env=production, ref=v2.4.1)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: production deploy" },
          { type: "approver", label: "Maintainer", sub: "Guardian push → Approve" },
          { type: "action", label: "GitHub Actions", sub: "Deploy v2.4.1 → production" },
        ],
      },
      {
        title: "Production rollback",
        description: "Only the lead engineer can approve a rollback — specific model.",
        connection: "github-main", action: "rollback",
        params: { env: "production", version: "v2.3.8", reason: "p0 latency spike" },
        badge: "warning", badgeLabel: "specific",
        flow: [
          { type: "agent", label: "DevOps Agent", sub: "rollback(env=production, v2.3.8)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: rollback (specific)" },
          { type: "approver", label: "Lead Engineer", sub: "Guardian push → Approve" },
          { type: "action", label: "GitHub Actions", sub: "Rollback production → v2.3.8" },
        ],
      },
    ],
  },
  {
    id: "opensource",
    title: "Open Source Bot",
    icon: Package,
    description: "Governance bot for an open source project. Large PRs require a k-of-n maintainer vote. Treasury disbursements above $100 need the lead plus the treasurer.",
    scenarios: [
      {
        title: "Small PR (42 lines) — auto-merge",
        description: "Tiny diffs auto-merge without bothering maintainers.",
        connection: "github-main", action: "merge_pr",
        params: { pr_number: 1847, title: "fix: typo in README", lines_changed: 42, author: "contributor" },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "OSS Bot", sub: "merge_pr(#1847, 42 lines)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "GitHub", sub: "Merge PR #1847" },
        ],
      },
      {
        title: "Large PR (380 lines) — k-of-n vote",
        description: "At least 2 out of 3 maintainers must approve within the quorum window.",
        connection: "github-main", action: "merge_pr",
        params: { pr_number: 1901, title: "feat: rewrite core parser", lines_changed: 380, author: "core-dev" },
        badge: "warning", badgeLabel: "k_of_n",
        flow: [
          { type: "agent", label: "OSS Bot", sub: "merge_pr(#1901, 380 lines)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: large PR (k=2/3)" },
          { type: "approver", label: "Maintainer A", sub: "Guardian push" },
          { type: "approver", label: "Maintainer B", sub: "Guardian push" },
          { type: "gate", label: "Quorum met (2/3)", sub: "Within window" },
          { type: "action", label: "GitHub", sub: "Merge PR #1901" },
        ],
      },
      {
        title: "Treasury payout $500 — all_of_n",
        description: "Both treasurer and lead maintainer must sign off on large disbursements.",
        connection: "stripe-prod", action: "payout",
        params: { amount_usd: 500, recipient: "infra@example.com", purpose: "Annual hosting" },
        badge: "danger", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "OSS Bot", sub: "treasury_payout(500, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: large treasury spend" },
          { type: "approver", label: "Treasurer", sub: "Guardian push → Approve" },
          { type: "approver", label: "Lead Maintainer", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Payout", sub: "$500 → infra@example.com" },
        ],
      },
    ],
  },
  {
    id: "research",
    title: "Research Lab Agent",
    icon: FlaskConical,
    description: "Lab assistant that provisions compute, submits papers, and manages grant budgets. Paper submissions require every co-author to approve. Large AWS jobs need the PI plus finance.",
    scenarios: [
      {
        title: "Small compute job ($12) — auto",
        description: "Cheap jobs spin up immediately without interrupting researchers.",
        connection: "aws-lab", action: "provision_compute",
        params: { instance_type: "t3.medium", hours: 4, project: "nlp-exp-42", estimated_cost_usd: 12 },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "Lab Agent", sub: "provision_compute($12)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "AWS", sub: "Spin up t3.medium × 4h" },
        ],
      },
      {
        title: "Paper submission — all co-authors",
        description: "All 3 co-authors are notified in parallel and must each approve before submission.",
        connection: "arxiv", action: "submit_paper",
        params: { title: "Efficient Human-in-the-Loop Approval for AI", authors: ["Dr. Smith", "Dr. Jones", "Dr. Lee"], target_journal: "NeurIPS 2026" },
        badge: "warning", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "Lab Agent", sub: "submit_paper(...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: paper submission" },
          { type: "approver", label: "Dr. Smith", sub: "Guardian push → Approve" },
          { type: "approver", label: "Dr. Jones", sub: "Guardian push → Approve" },
          { type: "approver", label: "Dr. Lee", sub: "Guardian push → Approve" },
          { type: "action", label: "arXiv API", sub: "Submit to NeurIPS 2026" },
        ],
      },
      {
        title: "Grant spend $1,200 — PI + Finance",
        description: "Both the Principal Investigator and Finance department must approve grant expenditures.",
        connection: "stripe-prod", action: "charge",
        params: { amount_usd: 1200, project: "NIH-2025-003", purpose: "Conference travel" },
        badge: "danger", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "Lab Agent", sub: "grant_spend(1200, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: grant spend" },
          { type: "approver", label: "PI", sub: "Guardian push → Approve" },
          { type: "approver", label: "Finance Dept", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Charge", sub: "$1,200 from grant account" },
        ],
      },
    ],
  },
  {
    id: "fintech",
    title: "Financial Services",
    icon: CreditCard,
    description: "Payment agent with a strict compliance chain. Wire transfers always go through a three-step sequential approval: Operations → Finance → CFO. New vendors need procurement and legal.",
    scenarios: [
      {
        title: "Standard payout $4,500",
        description: "Manager approves routine supplier payments.",
        connection: "stripe-prod", action: "payout",
        params: { amount_usd: 4500, recipient: "supplier@example.com", reference: "INV-2026-0441" },
        badge: "info", badgeLabel: "any_one",
        flow: [
          { type: "agent", label: "Fintech Agent", sub: "send_payout(4500, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: standard payout" },
          { type: "approver", label: "Manager", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Payout", sub: "$4,500 → supplier" },
        ],
      },
      {
        title: "Wire transfer $250,000 — sequential chain",
        description: "Ops approves first, then Finance, then CFO. Each step only starts after the previous approval.",
        connection: "stripe-prod", action: "wire_transfer",
        params: { amount_usd: 250000, beneficiary: "Acme Holdings", purpose: "Series B tranche" },
        badge: "danger", badgeLabel: "sequential",
        flow: [
          { type: "agent", label: "Fintech Agent", sub: "wire_transfer(250k, ...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: wire transfer" },
          { type: "approver", label: "Operations", sub: "Step 1 → Approve" },
          { type: "approver", label: "Finance", sub: "Step 2 → Approve" },
          { type: "approver", label: "CFO", sub: "Step 3 → Approve" },
          { type: "action", label: "Stripe Wire", sub: "$250,000 → Acme Holdings" },
        ],
      },
      {
        title: "New vendor payment — procurement + legal",
        description: "New vendors must be vetted by procurement and cleared by legal before any payment.",
        connection: "stripe-prod", action: "vendor_payment",
        params: { vendor_name: "NewCloud GmbH", amount_usd: 12000, is_new_vendor: true, invoice_id: "INV-NC-001" },
        badge: "warning", badgeLabel: "all_of_n",
        flow: [
          { type: "agent", label: "Fintech Agent", sub: "pay_vendor(is_new_vendor=True)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: new vendor" },
          { type: "approver", label: "Procurement", sub: "Guardian push → Approve" },
          { type: "approver", label: "Legal", sub: "Guardian push → Approve" },
          { type: "action", label: "Stripe Payment", sub: "$12,000 → NewCloud GmbH" },
        ],
      },
    ],
  },
  {
    id: "comms",
    title: "Communications Agent",
    icon: Mail,
    description: "Marketing and PR agent that sends emails and press releases. Audience size drives the approval level — small batches are automatic, mass sends need legal review, press releases need the CEO.",
    scenarios: [
      {
        title: "Internal email (8 people) — auto",
        description: "Small internal emails need no approval.",
        connection: "gmail-prod", action: "send_email",
        params: { subject: "Team lunch Friday", recipient_count: 8, audience_type: "internal" },
        badge: "success", badgeLabel: "auto",
        flow: [
          { type: "agent", label: "Comms Agent", sub: "send_email(8 recipients)" },
          { type: "platform", label: "ApprovalKit", sub: "No rule matched" },
          { type: "action", label: "Gmail", sub: "Send to 8 people" },
        ],
      },
      {
        title: "Mass email (12,500) — sequential",
        description: "Marketing lead reviews content, then legal checks compliance before sending.",
        connection: "gmail-prod", action: "send_email",
        params: { subject: "ApprovalKit 2.0 GA", recipient_count: 12500, audience_type: "subscribers" },
        badge: "warning", badgeLabel: "sequential",
        flow: [
          { type: "agent", label: "Comms Agent", sub: "send_email(12,500 recipients)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: mass email" },
          { type: "approver", label: "Marketing Lead", sub: "Step 1 → Approve content" },
          { type: "approver", label: "Legal", sub: "Step 2 → Clear compliance" },
          { type: "action", label: "Gmail", sub: "Send to 12,500 subscribers" },
        ],
      },
      {
        title: "Press release — PR → Legal → CEO",
        description: "Three-step sequential chain. CEO is the final gatekeeper before going public.",
        connection: "gmail-prod", action: "press_release",
        params: { headline: "ApprovalKit Raises $8M Seed", embargo_until: "2026-04-01T09:00Z", distribution: "Business Wire, TechCrunch" },
        badge: "danger", badgeLabel: "sequential",
        flow: [
          { type: "agent", label: "Comms Agent", sub: "issue_press_release(...)" },
          { type: "platform", label: "ApprovalKit", sub: "Rule: press release" },
          { type: "approver", label: "PR Manager", sub: "Step 1 → Approve draft" },
          { type: "approver", label: "Legal", sub: "Step 2 → Legal clearance" },
          { type: "approver", label: "CEO", sub: "Step 3 → Final sign-off" },
          { type: "action", label: "Distribution", sub: "Business Wire + TechCrunch" },
        ],
      },
    ],
  },
];

// ── Flow diagram ──────────────────────────────────────────────────────────────

function FlowDiagram({ steps }: { steps: FlowStep[] }) {
  const colors: Record<string, string> = {
    agent:    "bg-zinc-800 text-white",
    platform: "bg-blue-600 text-white",
    approver: "bg-amber-500 text-white",
    gate:     "bg-purple-600 text-white",
    action:   "bg-green-600 text-white",
  };
  return (
    <div className="flex flex-wrap items-center gap-1 mt-3">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-1">
          <div className={`rounded-lg px-3 py-2 text-xs ${colors[step.type]}`}>
            <div className="font-semibold whitespace-nowrap">{step.label}</div>
            {step.sub && <div className="opacity-75 mt-0.5 whitespace-nowrap">{step.sub}</div>}
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-3 w-3 text-zinc-300 shrink-0" />}
        </div>
      ))}
    </div>
  );
}

// ── Seed banner ───────────────────────────────────────────────────────────────

interface SeedState {
  status: "idle" | "loading" | "done" | "error";
  created?: number;
  skipped?: number;
  items?: string[];
  error?: string;
}

function SeedBanner() {
  const [state, setState] = useState<SeedState>({ status: "idle" });
  const [showLog, setShowLog] = useState(false);

  const handleSeed = async () => {
    setState({ status: "loading" });
    try {
      const res = await api.seedDemoData();
      setState({ status: "done", created: res.created_count, skipped: res.skipped_count, items: res.created });
    } catch (e: any) {
      setState({ status: "error", error: e.message });
    }
  };

  if (state.status === "done") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
        <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-green-800">
            Demo data seeded — {state.created} created, {state.skipped} skipped
          </p>
          <p className="text-xs text-green-700 mt-0.5">
            Connections, approvers and rules are now in your database. Hit Simulate on any scenario below.
          </p>
          {state.items && state.items.length > 0 && (
            <button className="text-xs text-green-600 underline mt-1" onClick={() => setShowLog((v) => !v)}>
              {showLog ? "Hide" : "Show"} created items ({state.items.length})
            </button>
          )}
          {showLog && state.items && (
            <ul className="mt-2 space-y-0.5 max-h-40 overflow-y-auto">
              {state.items.map((item, i) => (
                <li key={i} className="text-xs text-green-700 font-mono">+ {item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
        <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-red-800">Seed failed</p>
          <p className="text-xs text-red-700 mt-0.5">{state.error}</p>
          <button className="mt-2 text-xs text-red-600 underline" onClick={() => setState({ status: "idle" })}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 flex items-center gap-4 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-zinc-800">No rules configured yet?</p>
        <p className="text-xs text-zinc-500 mt-0.5">
          Seed all demo connections, approvers, and rules into your database in one click.
          Simulate will then show real rule matches instead of &quot;no rule found&quot;.
        </p>
      </div>
      <Button onClick={handleSeed} disabled={state.status === "loading"} size="sm" className="shrink-0">
        {state.status === "loading"
          ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Seeding…</>
          : <><Play className="h-3.5 w-3.5 mr-1.5" />Seed Demo Data</>}
      </Button>
    </div>
  );
}

// ── Scenario card ─────────────────────────────────────────────────────────────

interface RunResult {
  status: "running" | "matched" | "no_rule" | "no_match" | "error";
  rule?: string;
  model?: string;
  approvers?: { name: string }[];
  detail?: string;
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const [result, setResult] = useState<RunResult | null>(null);
  const [expanded, setExpanded] = useState(false);

  const handleSimulate = async () => {
    setResult({ status: "running" });
    try {
      const res = await api.simulateRule({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.matched) {
        setResult({ status: "matched", rule: res.rule_name, model: res.model, approvers: res.approvers, detail: res.timeout_seconds ? `Timeout: ${res.timeout_seconds}s` : undefined });
      } else {
        if (scenario.badge === "success") {
          setResult({ status: "no_match", detail: "No rule configured — auto-approved as expected." });
        } else {
          setResult({ status: "no_rule", detail: `No matching rule found for "${scenario.connection} / ${scenario.action}". Click "Seed Demo Data" above.` });
        }
      }
    } catch (e: any) {
      setResult({ status: "error", detail: e.message });
    }
  };

  return (
    <div className="border border-zinc-200 rounded-xl overflow-hidden">
      <button className="w-full text-left p-4 hover:bg-zinc-50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge variant={scenario.badge} className="text-xs font-mono w-20 justify-center shrink-0">
              {scenario.badgeLabel}
            </Badge>
            <span className="text-sm font-medium text-zinc-800">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
        <p className="text-xs text-zinc-500 mt-1 ml-[92px]">{scenario.description}</p>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 bg-zinc-50/50 space-y-4">
          {/* Flow diagram */}
          <div>
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mt-3 mb-1">Approval Flow</p>
            <div className="overflow-x-auto pb-1">
              <FlowDiagram steps={scenario.flow} />
            </div>
            <div className="flex gap-3 mt-2 flex-wrap">
              {[
                { color: "bg-zinc-800", label: "Agent" },
                { color: "bg-blue-600", label: "ApprovalKit" },
                { color: "bg-amber-500", label: "Approver" },
                { color: "bg-purple-600", label: "Gate" },
                { color: "bg-green-600", label: "Action" },
              ].map((l) => (
                <div key={l.label} className="flex items-center gap-1">
                  <div className={`h-2 w-2 rounded-sm ${l.color}`} />
                  <span className="text-xs text-zinc-400">{l.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Params */}
          <div>
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Request Params</p>
            <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">
              {JSON.stringify({ connection: scenario.connection, action: scenario.action, params: scenario.params }, null, 2)}
            </pre>
          </div>

          {/* Simulate */}
          <div className="flex items-start gap-3">
            <Button size="sm" onClick={handleSimulate} disabled={result?.status === "running"} className="shrink-0">
              {result?.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Running…</>
                : <><Play className="h-3.5 w-3.5 mr-1.5" />Simulate</>}
            </Button>

            {result && result.status !== "running" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                result.status === "matched"  ? "bg-blue-50 border border-blue-200 text-blue-800" :
                result.status === "no_match" ? "bg-green-50 border border-green-200 text-green-800" :
                result.status === "no_rule"  ? "bg-amber-50 border border-amber-200 text-amber-800" :
                "bg-red-50 border border-red-200 text-red-800"
              }`}>
                {result.status === "matched" && (
                  <>
                    <div className="flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Rule matched
                    </div>
                    {result.rule && <div className="mt-0.5">Rule: <strong>{result.rule}</strong></div>}
                    <div>
                      Model: <strong>{result.model}</strong>
                      {result.approvers && result.approvers.length > 0 && <> · Approvers: {result.approvers.map((a) => a.name).join(", ")}</>}
                      {result.detail && <> · {result.detail}</>}
                    </div>
                  </>
                )}
                {result.status === "no_match" && (
                  <div className="flex items-center gap-1 font-semibold">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {result.detail}
                  </div>
                )}
                {result.status === "no_rule" && (
                  <div className="flex items-start gap-1.5">
                    <Clock className="h-3.5 w-3.5 mt-0.5 shrink-0" /> <span>{result.detail}</span>
                  </div>
                )}
                {result.status === "error" && (
                  <div className="flex items-center gap-1">
                    <XCircle className="h-3.5 w-3.5" /> {result.detail}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const [activeId, setActiveId] = useState(AGENTS[0].id);
  const [settingUp, setSettingUp] = useState<string | null>(null);
  const [setupDone, setSetupDone] = useState<Record<string, boolean>>({});
  const agent = AGENTS.find((a) => a.id === activeId)!;

  const handleSetupAgent = async (agentId: string) => {
    setSettingUp(agentId);
    try {
      await api.seedDemoData(agentId);
      setSetupDone((prev) => ({ ...prev, [agentId]: true }));
    } catch {}
    setSettingUp(null);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-900">Agent Demos</h1>
        <p className="text-zinc-500 mt-1">
          Seven real-world agents with interactive approval flow diagrams.
          Expand any scenario to see the chain, then hit Simulate to test against your rules.
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <aside className="w-52 shrink-0">
          <div className="space-y-1 sticky top-6">
            {AGENTS.map((a) => (
              <button
                key={a.id}
                onClick={() => setActiveId(a.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                  activeId === a.id ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100"
                }`}
              >
                <a.icon className="h-4 w-4 shrink-0" />
                {a.title}
              </button>
            ))}
          </div>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-zinc-100 rounded-lg">
                    <agent.icon className="h-5 w-5 text-zinc-700" />
                  </div>
                  <div>
                    <CardTitle>{agent.title}</CardTitle>
                    <p className="text-sm text-zinc-500 mt-0.5">{agent.description}</p>
                  </div>
                </div>
                {setupDone[agent.id] ? (
                  <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> Ready</Badge>
                ) : (
                <Button
                  size="sm"
                  disabled={settingUp === agent.id}
                  onClick={() => handleSetupAgent(agent.id)}
                >
                  {settingUp === agent.id ? (
                    <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Creating rules &amp; approvers...</>
                  ) : (
                    <>Setup Demo</>
                  )}
                </Button>
                )}
              </div>
            </CardHeader>
          </Card>

          <div className="space-y-3">
            {agent.scenarios.map((scenario) => (
              <ScenarioCard key={scenario.title} scenario={scenario} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
