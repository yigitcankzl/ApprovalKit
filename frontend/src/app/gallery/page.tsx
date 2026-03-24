"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Approver } from "@/types";
import {
  ShoppingCart, Package, FlaskConical, CreditCard, Server, Mail,
  Check, Loader2,
} from "lucide-react";

interface UseCaseRule {
  name: string;
  connection: string;
  action: string;
  conditions: { field: string; operator: string; value: string | number }[];
  model: string;
  timeout_seconds: number;
  on_timeout: string;
  context_template: string;
  priority: number;
  label: string;
  badge: "success" | "info" | "warning" | "danger" | "default";
}

interface UseCase {
  title: string;
  icon: React.ElementType;
  description: string;
  preview: { label: string; action: string; badge: "success" | "info" | "warning" | "danger" | "default" }[];
  rules: UseCaseRule[];
}

const useCases: UseCase[] = [
  {
    title: "E-commerce Agent",
    icon: ShoppingCart,
    description: "Stripe payment processing with tiered approvals",
    preview: [
      { label: "Under $50", action: "auto-approve", badge: "success" },
      { label: "$50–$200", action: "CS approval", badge: "info" },
      { label: "$200+", action: "CS + CFO sequential", badge: "warning" },
      { label: "Refunds", action: "partial approval enabled", badge: "default" },
    ],
    rules: [
      { name: "Small Stripe charge (auto)", connection: "stripe-prod", action: "charge", conditions: [{ field: "amount", operator: "lt", value: 50 }], model: "any_one", timeout_seconds: 300, on_timeout: "block", context_template: "Charge ${{amount}} for {{customer}}", priority: 20, label: "Under $50", badge: "success" },
      { name: "Mid Stripe charge (CS)", connection: "stripe-prod", action: "charge", conditions: [{ field: "amount", operator: "gte", value: 50 }], model: "any_one", timeout_seconds: 300, on_timeout: "block", context_template: "Charge ${{amount}} for {{customer}}", priority: 10, label: "$50–$200", badge: "info" },
      { name: "Large Stripe charge (CFO)", connection: "stripe-prod", action: "charge", conditions: [{ field: "amount", operator: "gte", value: 200 }], model: "sequential", timeout_seconds: 600, on_timeout: "escalate", context_template: "Large charge ${{amount}} — needs CFO sign-off", priority: 30, label: "$200+", badge: "warning" },
    ],
  },
  {
    title: "DevOps Agent",
    icon: Server,
    description: "GitHub deployments with environment-based rules",
    preview: [
      { label: "Staging", action: "auto-approve", badge: "success" },
      { label: "Production", action: "any-one maintainer", badge: "info" },
      { label: "Rollback", action: "specific lead only", badge: "warning" },
      { label: "After 23:00", action: "blackout window", badge: "danger" },
    ],
    rules: [
      { name: "Production deploy approval", connection: "github-main", action: "deploy", conditions: [{ field: "environment", operator: "eq", value: "production" }], model: "any_one", timeout_seconds: 120, on_timeout: "block", context_template: "Deploy to {{environment}} — ref {{ref}}", priority: 20, label: "Production", badge: "info" },
      { name: "Production rollback", connection: "github-main", action: "rollback", conditions: [{ field: "env", operator: "eq", value: "production" }], model: "specific", timeout_seconds: 120, on_timeout: "block", context_template: "Rollback {{env}} to {{version}}", priority: 30, label: "Rollback", badge: "warning" },
    ],
  },
  {
    title: "Open Source Project",
    icon: Package,
    description: "Multi-maintainer governance with k-of-n voting",
    preview: [
      { label: "PR < 100 lines", action: "auto-merge", badge: "success" },
      { label: "npm patch", action: "lead maintainer", badge: "info" },
      { label: "npm major", action: "2/3 maintainers (k-of-n)", badge: "warning" },
      { label: "Treasury > $100", action: "treasurer + lead", badge: "danger" },
    ],
    rules: [
      { name: "PR merge approval", connection: "github-main", action: "merge_pr", conditions: [], model: "any_one", timeout_seconds: 300, on_timeout: "block", context_template: "Merge PR #{{pr_number}}", priority: 10, label: "PR merge", badge: "info" },
      { name: "Large PR — k-of-n", connection: "github-main", action: "merge_pr", conditions: [{ field: "lines_changed", operator: "gte", value: 100 }], model: "k_of_n", timeout_seconds: 600, on_timeout: "block", context_template: "Large PR #{{pr_number}} — {{lines_changed}} lines changed", priority: 20, label: "npm major", badge: "warning" },
    ],
  },
  {
    title: "Research Lab",
    icon: FlaskConical,
    description: "AWS spending and publication controls",
    preview: [
      { label: "Compute < $20", action: "researcher auto", badge: "success" },
      { label: "Compute > $100", action: "PI approval", badge: "info" },
      { label: "Paper submit", action: "all co-authors (all-of-n)", badge: "warning" },
      { label: "Grant spending", action: "PI + finance dept", badge: "danger" },
    ],
    rules: [
      { name: "Large compute spend", connection: "stripe-prod", action: "charge", conditions: [{ field: "amount", operator: "gt", value: 100 }], model: "any_one", timeout_seconds: 600, on_timeout: "block", context_template: "Compute spend ${{amount}} for {{project}}", priority: 10, label: "Compute > $100", badge: "info" },
    ],
  },
  {
    title: "Financial Services",
    icon: CreditCard,
    description: "Payment processing with compliance chain",
    preview: [
      { label: "Transfer < $1k", action: "manager approval", badge: "success" },
      { label: "Transfer > $10k", action: "manager + compliance", badge: "warning" },
      { label: "New vendor", action: "procurement + legal", badge: "danger" },
      { label: "Wire transfer", action: "sequential: ops → finance → CFO", badge: "danger" },
    ],
    rules: [
      { name: "High-value transfer", connection: "stripe-prod", action: "payout", conditions: [{ field: "amount", operator: "gt", value: 10000 }], model: "sequential", timeout_seconds: 900, on_timeout: "block", context_template: "Payout ${{amount}} to {{recipient}}", priority: 30, label: "Transfer > $10k", badge: "warning" },
      { name: "Standard transfer", connection: "stripe-prod", action: "payout", conditions: [{ field: "amount", operator: "lte", value: 10000 }], model: "any_one", timeout_seconds: 300, on_timeout: "block", context_template: "Payout ${{amount}} to {{recipient}}", priority: 10, label: "Transfer < $1k", badge: "info" },
    ],
  },
  {
    title: "Communications Agent",
    icon: Mail,
    description: "Email and messaging with audience-based controls",
    preview: [
      { label: "Internal email", action: "auto-approve", badge: "success" },
      { label: "Client email", action: "manager review", badge: "info" },
      { label: "Mass email (>100)", action: "marketing lead + legal", badge: "warning" },
      { label: "Press release", action: "sequential: PR → legal → CEO", badge: "danger" },
    ],
    rules: [
      { name: "Mass email approval", connection: "gmail", action: "send_email", conditions: [{ field: "recipient_count", operator: "gt", value: 100 }], model: "sequential", timeout_seconds: 600, on_timeout: "block", context_template: "Mass email to {{recipient_count}} recipients: {{subject}}", priority: 20, label: "Mass email", badge: "warning" },
    ],
  },
];

export default function GalleryPage() {
  const router = useRouter();
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [importing, setImporting] = useState<string | null>(null);
  const [imported, setImported] = useState<Set<string>>(new Set());
  const [importError, setImportError] = useState<string | null>(null);

  useEffect(() => {
    api.getApprovers().then(setApprovers).catch(() => {});
  }, []);

  const handleImport = async (uc: UseCase) => {
    if (approvers.length === 0) {
      setImportError("Add at least one approver first before importing rules.");
      return;
    }
    setImporting(uc.title);
    setImportError(null);
    try {
      const firstApprover = approvers[0].id;
      for (const rule of uc.rules) {
        await api.createRule({
          name: rule.name,
          connection: rule.connection,
          action: rule.action,
          conditions: rule.conditions,
          model: rule.model,
          approver_ids: [firstApprover],
          k_value: rule.model === "k_of_n" ? 2 : null,
          timeout_seconds: rule.timeout_seconds,
          on_timeout: rule.on_timeout,
          partial_approval: false,
          context_template: rule.context_template,
          blackout_start: null,
          blackout_end: null,
          cooldown_max: null,
          quorum_window: null,
          priority: rule.priority,
        });
      }
      setImported((prev) => { const next = new Set(Array.from(prev)); next.add(uc.title); return next; });
    } catch (e: any) {
      setImportError(`Failed to import "${uc.title}": ${e.message}`);
    } finally {
      setImporting(null);
    }
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Use Case Gallery</h1>
          <p className="text-zinc-500 mt-1">
            Pre-built rule sets. Import creates real approval rules in your workspace.
          </p>
        </div>
        <Button variant="outline" onClick={() => router.push("/rules")}>
          View My Rules
        </Button>
      </div>

      {importError && (
        <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between">
          {importError}
          <button onClick={() => setImportError(null)} className="text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {approvers.length === 0 && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
          <strong>No approvers configured.</strong> Import will assign rules to the first available approver.{" "}
          <button onClick={() => router.push("/approvers")} className="underline font-medium">
            Add approvers first →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {useCases.map((uc) => {
          const isImporting = importing === uc.title;
          const isImported = imported.has(uc.title);
          return (
            <Card key={uc.title} className="hover:border-zinc-300 transition-colors flex flex-col">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-zinc-100 rounded-lg">
                    <uc.icon className="h-5 w-5 text-zinc-700" />
                  </div>
                  <div>
                    <CardTitle className="text-base">{uc.title}</CardTitle>
                    <CardDescription>{uc.description}</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col">
                <div className="space-y-2 flex-1">
                  {uc.preview.map((p, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-zinc-600">{p.label}</span>
                      <Badge variant={p.badge}>{p.action}</Badge>
                    </div>
                  ))}
                </div>
                <div className="mt-4 space-y-2">
                  <p className="text-xs text-zinc-400">{uc.rules.length} rule{uc.rules.length > 1 ? "s" : ""} will be created</p>
                  <Button
                    variant={isImported ? "outline" : "outline"}
                    size="sm"
                    className={`w-full ${isImported ? "border-green-500 text-green-600" : ""}`}
                    onClick={() => isImported ? router.push("/rules") : handleImport(uc)}
                    disabled={isImporting}
                  >
                    {isImporting ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Importing…</>
                    ) : isImported ? (
                      <><Check className="h-4 w-4 mr-2" /> Imported — View Rules</>
                    ) : (
                      "Import Rules"
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
