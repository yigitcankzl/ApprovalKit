"use client";

import { useEffect, useRef, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ShoppingCart, Server, Package, FlaskConical, CreditCard, Mail, Users,
  Play, CheckCircle2, XCircle, Clock, ChevronRight, ArrowRight, Loader2, Send,
  Bot, Trash2, Plus, Plug, RefreshCw,
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

interface SetupItem {
  type: "connection" | "approver" | "rule";
  name: string;
  detail: string;
}

interface Agent {
  id: string;
  title: string;
  icon: React.ElementType;
  iconName?: string;
  description: string;
  scenarios: Scenario[];
  setupInfo: SetupItem[];
}

// ── Agent definitions (extracted for independent maintenance) ──────────────────

const AGENTS: Agent[] = [
  {
    id: "ecommerce",
    title: "E-Commerce Agent",
    icon: ShoppingCart,
    description: "AI shopping agent that processes Stripe payments and refunds. Amount tiers trigger different approval chains — small orders pass automatically, large ones require step-up approval.",
    setupInfo: [
      { type: "connection", name: "stripe-prod", detail: "Stripe payments (charge, refund)" },
      { type: "connection", name: "slack-prod", detail: "Team notifications (#general, #finance, #hr)" },
      { type: "approver", name: "Sales Manager", detail: "Approves medium charges ($100-$999)" },
      { type: "approver", name: "CFO", detail: "Co-approves large charges ($1000+)" },
      { type: "approver", name: "CS Agent", detail: "Approves small refunds (<$50)" },
      { type: "approver", name: "CS Manager", detail: "Approves large refunds ($50+), can edit amount" },
      { type: "approver", name: "Team Lead", detail: "Approves Slack posts to #general" },
      { type: "rule", name: "Stripe charge — medium ($100-999)", detail: "any_one → Sales Manager" },
      { type: "rule", name: "Stripe charge — large ($1000+)", detail: "all_of_n → Sales Manager + CFO" },
      { type: "rule", name: "Stripe refund — small (<$50)", detail: "any_one → CS Agent" },
      { type: "rule", name: "Stripe refund — large ($50+)", detail: "specific → CS Manager (partial approval)" },
      { type: "rule", name: "Slack #general", detail: "any_one → Team Lead" },
      { type: "rule", name: "Slack #finance", detail: "specific → CFO" },
    ],
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
    setupInfo: [
      { type: "connection", name: "gmail-prod", detail: "Email (offer letters, terminations)" },
      { type: "connection", name: "github-prod", detail: "GitHub org member management" },
      { type: "approver", name: "HR Manager", detail: "Approves offer letters, co-approves terminations" },
      { type: "approver", name: "CEO", detail: "Co-approves termination emails" },
      { type: "approver", name: "IT Manager", detail: "Co-approves GitHub access removal" },
      { type: "rule", name: "Gmail offer letter", detail: "specific → HR Manager" },
      { type: "rule", name: "Gmail termination", detail: "all_of_n → HR Manager + CEO" },
      { type: "rule", name: "GitHub remove member", detail: "all_of_n → IT Manager + HR Manager" },
      { type: "rule", name: "GitHub add member (admin)", detail: "specific → CTO" },
    ],
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
    setupInfo: [
      { type: "connection", name: "github-main", detail: "GitHub deployments and rollbacks" },
      { type: "approver", name: "Maintainer", detail: "Approves production deployments" },
      { type: "approver", name: "Lead Engineer", detail: "Approves rollbacks (specific)" },
      { type: "approver", name: "CTO", detail: "Backup escalation" },
      { type: "rule", name: "GitHub deploy — production", detail: "any_one → Maintainer" },
      { type: "rule", name: "GitHub rollback — production", detail: "specific → Lead Engineer" },
    ],
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
    setupInfo: [
      { type: "connection", name: "github-main", detail: "PR merges" },
      { type: "connection", name: "stripe-prod", detail: "Treasury payouts" },
      { type: "approver", name: "Maintainer", detail: "PR review vote" },
      { type: "approver", name: "Lead Maintainer", detail: "PR review + treasury co-sign" },
      { type: "approver", name: "CTO", detail: "PR review vote" },
      { type: "approver", name: "Treasurer", detail: "Treasury co-sign" },
      { type: "rule", name: "PR merge — large (200+ lines)", detail: "k_of_n (2/3) → Maintainer, Lead, CTO" },
      { type: "rule", name: "Treasury payout — large ($100+)", detail: "all_of_n → Treasurer + Lead Maintainer" },
    ],
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
    setupInfo: [
      { type: "connection", name: "aws-lab", detail: "AWS compute provisioning" },
      { type: "connection", name: "arxiv", detail: "Paper submissions" },
      { type: "approver", name: "PI", detail: "Approves compute and papers" },
      { type: "approver", name: "Finance Dept", detail: "Co-approves large compute ($500+)" },
      { type: "rule", name: "AWS compute — medium ($50-499)", detail: "any_one → PI" },
      { type: "rule", name: "AWS compute — large ($500+)", detail: "all_of_n → PI + Finance" },
      { type: "rule", name: "Paper submission", detail: "all_of_n → PI + HR + CTO" },
    ],
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
    setupInfo: [
      { type: "connection", name: "stripe-prod", detail: "Payouts, wire transfers, vendor payments" },
      { type: "approver", name: "Manager", detail: "Approves standard payouts ($1k-$50k)" },
      { type: "approver", name: "Operations", detail: "Wire transfer step 1" },
      { type: "approver", name: "Finance Dept", detail: "Wire transfer step 2 + vendor co-sign" },
      { type: "approver", name: "CFO", detail: "Wire transfer step 3" },
      { type: "approver", name: "Procurement", detail: "New vendor vetting" },
      { type: "approver", name: "Legal", detail: "New vendor legal clearance" },
      { type: "rule", name: "Payout — standard ($1k-$50k)", detail: "any_one → Manager" },
      { type: "rule", name: "Wire transfer ($50k+)", detail: "all_of_n → Ops + Finance + CFO" },
      { type: "rule", name: "New vendor payment", detail: "all_of_n → Procurement + Legal" },
    ],
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
    setupInfo: [
      { type: "connection", name: "gmail-prod", detail: "Email sending and press releases" },
      { type: "approver", name: "Marketing Lead", detail: "Reviews mass email content" },
      { type: "approver", name: "Legal", detail: "Compliance review for mass sends" },
      { type: "approver", name: "CEO", detail: "Approves press releases" },
      { type: "rule", name: "Gmail mass email (500+)", detail: "sequential → Marketing Lead → Legal" },
      { type: "rule", name: "Gmail mass email legal (10k+)", detail: "all_of_n → Marketing + Legal + CEO" },
      { type: "rule", name: "Gmail press release", detail: "specific → CEO" },
    ],
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
          {i < steps.length - 1 && <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600 shrink-0" />}
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
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-4 py-3">
        <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-green-800 dark:text-green-300">
            Demo data seeded — {state.created} created, {state.skipped} skipped
          </p>
          <p className="text-xs text-green-700 dark:text-green-400 mt-0.5">
            Connections, approvers and rules are now in your database. Hit Check Rule on any scenario below.
          </p>
          {state.items && state.items.length > 0 && (
            <button className="text-xs text-green-600 underline mt-1" onClick={() => setShowLog((v) => !v)}>
              {showLog ? "Hide" : "Show"} created items ({state.items.length})
            </button>
          )}
          {showLog && state.items && (
            <ul className="mt-2 space-y-0.5 max-h-40 overflow-y-auto">
              {state.items.map((item, i) => (
                <li key={i} className="text-xs text-green-700 dark:text-green-400 font-mono">+ {item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/30 px-4 py-3">
        <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-red-800">Seed failed</p>
          <p className="text-xs text-red-700 dark:text-red-400 mt-0.5">{state.error}</p>
          <button className="mt-2 text-xs text-red-600 underline" onClick={() => setState({ status: "idle" })}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 flex items-center gap-4 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">No rules configured yet?</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          Seed all demo connections, approvers, and rules into your database in one click.
          Check Rule will then show real rule matches instead of &quot;no rule found&quot;.
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
  const [sending, setSending] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<string[]>([]);

  const handleCheckRule = async () => {
    setResult({ status: "running" });
    setLiveStatus(null);
    try {
      const res = await api.simulateRule({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.matched) {
        setResult({ status: "matched", rule: res.rule_name, model: res.model, approvers: res.approvers, detail: res.timeout_seconds ? `Timeout: ${res.timeout_seconds}s` : undefined });
      } else {
        if (scenario.badge === "success") {
          setResult({ status: "no_match", detail: "No rule configured — auto-approved as expected." });
        } else {
          setResult({ status: "no_rule", detail: `No matching rule found for "${scenario.connection} / ${scenario.action}". Click Setup Demo above.` });
        }
      }
    } catch (e: any) {
      setResult({ status: "error", detail: e.message });
    }
  };

  const handleSendReal = async () => {
    setSending(true);
    setLiveStatus("submitting");
    setLiveSteps(["submitting"]);
    try {
      const res = await api.sendTestRequest({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.status === "auto_approved" && scenario.badge !== "success") {
        // No rule found but this scenario SHOULD have a rule — setup not done
        setLiveStatus("no_setup");
        setLiveSteps(["submitting", "no_setup"]);
        return;
      }
      if (res.status === "auto_approved") {
        setLiveStatus("auto_approved");
        setLiveSteps(["submitting", "rule_matched", "auto_approved"]);
      } else if (res.job_id) {
        setLiveStatus("rule_matched");
        setLiveSteps(["submitting", "rule_matched"]);
        // Small delay to show rule matched step
        await new Promise(r => setTimeout(r, 800));
        setLiveStatus("ciba_sent");
        setLiveSteps(["submitting", "rule_matched", "ciba_sent"]);
        // Poll for result
        let attempts = 0;
        const poll = async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            if (["approved", "rejected", "timeout", "blocked"].includes(s.status)) {
              setLiveStatus(s.status);
              setLiveSteps(prev => [...prev, s.status]);
              return;
            }
          } catch {}
          if (++attempts < 60) setTimeout(poll, 2000);
        };
        poll();
      }
    } catch (e: any) {
      setLiveStatus("error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <button className="w-full text-left p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800 dark:bg-zinc-800/50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge variant={scenario.badge} className="text-xs font-mono w-20 justify-center shrink-0">
              {scenario.badgeLabel}
            </Badge>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 ml-[92px]">{scenario.description}</p>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50/50 space-y-4">
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

          {/* Actions */}
          <div className="flex items-start gap-3 flex-wrap">
            <Button size="sm" variant="outline" onClick={handleCheckRule} disabled={result?.status === "running"} className="shrink-0">
              {result?.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Running…</>
                : <><FlaskConical className="h-3.5 w-3.5 mr-1.5" />Check Rule</>}
            </Button>
            <Button size="sm" onClick={handleSendReal} disabled={sending || liveStatus === "ciba_sent"} className="shrink-0">
              {sending
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending…</>
                : <><Send className="h-3.5 w-3.5 mr-1.5" />Run Live</>}
            </Button>
            {liveSteps.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <LiveStep done={liveSteps.includes("submitting")} active={liveStatus === "submitting"} label="Submitted" />
                <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                {liveStatus === "no_setup" ? (
                  <LiveStep done={true} error={true} label="No rules configured — click Setup Demo first" />
                ) : (
                <LiveStep done={liveSteps.includes("rule_matched") || liveSteps.includes("auto_approved")} active={liveStatus === "rule_matched"} label={liveStatus === "auto_approved" ? "Auto-approved" : "Rule matched"} />
                )}
                {liveStatus !== "auto_approved" && liveStatus !== "no_setup" && <>
                  <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                  <LiveStep done={liveSteps.includes("ciba_sent")} active={liveStatus === "ciba_sent"} label="Guardian push sent" />
                  <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                  <LiveStep
                    done={liveSteps.includes("approved") || liveSteps.includes("rejected") || liveSteps.includes("timeout")}
                    active={liveStatus === "ciba_sent"}
                    error={liveStatus === "rejected" || liveStatus === "timeout"}
                    label={
                      liveStatus === "approved" ? "Approved" :
                      liveStatus === "rejected" ? "Rejected" :
                      liveStatus === "timeout" ? "Timed out" :
                      "Waiting..."
                    }
                  />
                </>}
              </div>
            )}

            {result && result.status !== "running" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                result.status === "matched"  ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800" :
                result.status === "no_match" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
                result.status === "no_rule"  ? "bg-amber-50 border border-amber-200 text-amber-800" :
                "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800"
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

// ── Icon resolver for registered agents ──────────────────────────────────────

const ICON_MAP: Record<string, React.ElementType> = {
  "bot":           Bot,
  "shopping-cart": ShoppingCart,
  "users":         Users,
  "server":        Server,
  "package":       Package,
  "flask":         FlaskConical,
  "credit-card":   CreditCard,
  "mail":          Mail,
};
function AgentIcon({ icon }: { icon: string }) {
  const Icon = ICON_MAP[icon] ?? Bot;
  return <Icon className="h-5 w-5 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600" />;
}

// ── My Agent scenario card (live test inline) ─────────────────────────────────

interface MyAgentScenario {
  id: string;
  title: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
}

interface LiveState {
  status: "idle" | "running" | "pending" | "approved" | "rejected" | "auto_approved" | "timeout" | "error";
  jobId?: string;
  message?: string;
  error?: string;
}

function MyScenarioCard({ scenario }: { scenario: MyAgentScenario }) {
  const [expanded, setExpanded] = useState(false);
  const [live, setLive] = useState<LiveState>({ status: "idle" });
  const [deciding, setDeciding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPoll = (id: string) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getJobStatus(id);
        const terminal = ["approved", "rejected", "timeout", "blocked"];
        setLive((prev) => ({ ...prev, status: terminal.includes(s.status) ? s.status : "pending", jobId: id }));
        if (terminal.includes(s.status)) stopPoll();
      } catch {}
    }, 2000);
  };

  const handleTest = async () => {
    setLive({ status: "running" });
    try {
      const res = await api.sendTestRequest({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.job_id) {
        setLive({ status: "pending", jobId: res.job_id, message: res.message });
        startPoll(res.job_id);
      } else {
        setLive({ status: res.status, message: res.message });
      }
    } catch (e: any) {
      setLive({ status: "error", error: e.message });
    }
  };

  const handleDecide = async (decision: "approve" | "reject") => {
    if (!live.jobId) return;
    setDeciding(true);
    try {
      await api.submitDecision(live.jobId, { decision });
      const s = await api.getJobStatus(live.jobId);
      setLive((prev) => ({ ...prev, status: s.status }));
      stopPoll();
    } catch {}
    setDeciding(false);
  };

  const isPending = live.status === "pending";
  const isDone = ["approved", "rejected", "auto_approved", "timeout", "error"].includes(live.status);

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <button className="w-full text-left p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800 dark:bg-zinc-800/50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 px-2 py-0.5 rounded font-mono">
              {scenario.connection} / {scenario.action}
            </code>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50/50 space-y-3">
          <pre className="mt-3 bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(scenario.params, null, 2)}
          </pre>

          <div className="flex items-start gap-3">
            <Button size="sm" onClick={handleTest} disabled={live.status === "running" || isPending} className="shrink-0">
              {live.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending…</>
                : <><Play className="h-3.5 w-3.5 mr-1.5" />Live Test</>}
            </Button>

            {live.status !== "idle" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                live.status === "approved" || live.status === "auto_approved" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
                live.status === "rejected" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800" :
                isPending ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800" :
                live.status === "error" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800" :
                "bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
              }`}>
                {isPending && (
                  <div className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Waiting for approval… {live.message && <span className="opacity-70">— {live.message}</span>}</span>
                  </div>
                )}
                {(live.status === "approved" || live.status === "auto_approved") && (
                  <div className="flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" /> {live.status === "auto_approved" ? "Auto-approved (no rule)" : "Approved"}</div>
                )}
                {live.status === "rejected" && <div className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5" /> Rejected</div>}
                {live.status === "error" && <div className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5" /> {live.error}</div>}
              </div>
            )}
          </div>

          {isPending && live.jobId && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handleDecide("approve")} disabled={deciding} className="flex-1 bg-green-600 hover:bg-green-700 text-white">
                {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5 mr-1" />} Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleDecide("reject")} disabled={deciding} className="flex-1 border-red-200 text-red-600 hover:bg-red-50 dark:bg-red-950/30">
                {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <XCircle className="h-3.5 w-3.5 mr-1" />} Reject
              </Button>
            </div>
          )}

          {isDone && (
            <button className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-600 dark:text-zinc-400" onClick={() => setLive({ status: "idle" })}>
              <RefreshCw className="h-3 w-3" /> Test again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── My Agents tab ─────────────────────────────────────────────────────────────

interface MyAgent {
  id: string;
  name: string;
  description?: string;
  icon: string;
  created_at: string;
  scenarios: MyAgentScenario[];
}

function MyAgentsTab() {
  const [agents, setAgents] = useState<MyAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getMyAgents();
      setAgents(data);
      if (data.length > 0 && !activeId) setActiveId(data[0].id);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await api.deleteMyAgent(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      if (activeId === id) setActiveId(agents.find((a) => a.id !== id)?.id ?? null);
    } catch {}
    setDeleting(null);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 justify-center text-zinc-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading your agents…
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-2xl mb-4">
          <Bot className="h-10 w-10 text-zinc-400" />
        </div>
        <h3 className="text-base font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-1">No agents yet</h3>
        <p className="text-sm text-zinc-400 mb-4 max-w-xs">
          Go to Connect Agent, configure your connection and action, then save it as an agent.
        </p>
        <a
          href="/connect"
          className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors"
        >
          <Plug className="h-4 w-4" /> Connect Your Agent
        </a>
      </div>
    );
  }

  const active = agents.find((a) => a.id === activeId) ?? agents[0];

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <aside className="w-52 shrink-0">
        <div className="space-y-1 sticky top-6">
          {agents.map((a) => (
            <button
              key={a.id}
              onClick={() => setActiveId(a.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                activeId === a.id ? "bg-zinc-900 text-white" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800"
              }`}
            >
              <AgentIcon icon={a.icon} />
              <span className="truncate">{a.name}</span>
            </button>
          ))}
          <a
            href="/connect"
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800 hover:text-zinc-600 dark:text-zinc-400 transition-colors"
          >
            <Plus className="h-4 w-4 shrink-0" /> Add agent
          </a>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                  <AgentIcon icon={active.icon} />
                </div>
                <div>
                  <CardTitle>{active.name}</CardTitle>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{active.description || "No description"}</p>
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDelete(active.id)}
                disabled={deleting === active.id}
                className="border-red-200 text-red-600 hover:bg-red-50 dark:bg-red-950/30"
              >
                {deleting === active.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              </Button>
            </div>
          </CardHeader>
        </Card>

        {active.scenarios.length === 0 ? (
          <div className="border border-dashed border-zinc-200 dark:border-zinc-700 rounded-xl p-8 text-center text-zinc-400">
            <p className="text-sm">No scenarios yet.</p>
            <a href="/connect" className="text-xs text-zinc-500 dark:text-zinc-400 underline mt-1 inline-block">
              Add a scenario from the Connect Agent page
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {active.scenarios.map((scenario) => (
              <MyScenarioCard key={scenario.id} scenario={scenario} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { user } = useUser();
  const [tab, setTab] = useState<"demo" | "my">("my");
  const [activeId, setActiveId] = useState(AGENTS[0].id);
  const [settingUp, setSettingUp] = useState<string | null>(null);
  const [setupDone, setSetupDone] = useState<Record<string, boolean>>({});
  const agent = AGENTS.find((a) => a.id === activeId)!;

  // Check which agents are already configured on mount
  useEffect(() => {
    api.getRules().then((rules: any[]) => {
      const ruleNames = rules.map((r: any) => r.name);
      const done: Record<string, boolean> = {};
      for (const [agentId, prefixes] of Object.entries({
        ecommerce: ["[Demo] Stripe charge"],
        hr: ["[Demo] Gmail offer"],
        devops: ["[Demo] GitHub deploy"],
        opensource: ["[Demo] PR merge"],
        research: ["[Demo] AWS compute"],
        fintech: ["[Demo] Payout"],
        comms: ["[Demo] Gmail mass email"],
      })) {
        done[agentId] = (prefixes as string[]).some((p) => ruleNames.some((n: string) => n.startsWith(p)));
      }
      setSetupDone(done);
    }).catch(() => {});
  }, []);

  const handleSetupAgent = async (agentId: string) => {
    setSettingUp(agentId);
    try {
      await api.seedDemoData(agentId, user?.sub || undefined);
      setSetupDone((prev) => ({ ...prev, [agentId]: true }));
    } catch {}
    setSettingUp(null);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Agents</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Seven real-world agents with interactive approval flow diagrams.
          Expand any scenario to see the chain, then hit Check Rule to test against your rules.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-6 border-b border-zinc-200 dark:border-zinc-700">
        <button
          onClick={() => setTab("demo")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === "demo" ? "border-zinc-900 text-zinc-900 dark:text-zinc-100" : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
          }`}
        >
          Demo Agents
        </button>
        <button
          onClick={() => setTab("my")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === "my" ? "border-zinc-900 text-zinc-900 dark:text-zinc-100" : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
          }`}
        >
          My Agents
        </button>
      </div>

      {tab === "my" && <MyAgentsTab />}

      {tab === "demo" && <div className="flex gap-6">
        {/* Sidebar */}
        <aside className="w-52 shrink-0">
          <div className="space-y-1 sticky top-6">
            {AGENTS.map((a) => (
              <button
                key={a.id}
                onClick={() => setActiveId(a.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                  activeId === a.id ? "bg-zinc-900 text-white" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800"
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
                  <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                    <agent.icon className="h-5 w-5 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600" />
                  </div>
                  <div>
                    <CardTitle>{agent.title}</CardTitle>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{agent.description}</p>
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
            {/* Setup Details */}
            {agent.setupInfo && (
              <CardContent className="border-t border-zinc-100 dark:border-zinc-800 pt-4">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-3">Setup Demo will create:</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <p className="text-xs font-medium text-blue-600 mb-1.5">Connections</p>
                    {agent.setupInfo.filter(s => s.type === "connection").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">{s.name}</code>
                        <span className="text-zinc-400 ml-1">{s.detail}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-amber-600 mb-1.5">Approvers</p>
                    {agent.setupInfo.filter(s => s.type === "approver").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <span className="font-medium">{s.name}</span>
                        <span className="text-zinc-400 ml-1">— {s.detail}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-green-600 mb-1.5">Rules</p>
                    {agent.setupInfo.filter(s => s.type === "rule").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <span className="font-medium">{s.name}</span>
                        <span className="text-zinc-400 ml-1">— {s.detail}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            )}
          </Card>

          <div className="space-y-3">
            {agent.scenarios.map((scenario) => (
              <ScenarioCard key={scenario.title} scenario={scenario} />
            ))}
          </div>
        </div>
      </div>}
    </div>
  );
}

function LiveStep({ done, active, label, error }: { done: boolean; active?: boolean; label: string; error?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
      error ? "bg-red-100 text-red-700 dark:text-red-400" :
      done ? "bg-green-100 text-green-700 dark:text-green-400" :
      active ? "bg-blue-100 text-blue-700 dark:text-blue-400" :
      "bg-zinc-100 dark:bg-zinc-800 text-zinc-400"
    }`}>
      {active && <Loader2 className="h-3 w-3 animate-spin" />}
      {error && <XCircle className="h-3 w-3" />}
      {done && !error && <CheckCircle2 className="h-3 w-3" />}
      {label}
    </span>
  );
}
