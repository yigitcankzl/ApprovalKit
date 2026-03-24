"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  CheckCircle2, XCircle, Loader2, ArrowRight,
  Shield, Link2, GitBranch, Users, LayoutDashboard,
} from "lucide-react";

interface StatusItem {
  label: string;
  key: string;
  status: "ok" | "warn" | "error" | "loading";
  detail: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [checks, setChecks] = useState<StatusItem[]>([
    { key: "api",       label: "API reachable",        status: "loading", detail: "Checking…" },
    { key: "rules",     label: "Rules configured",     status: "loading", detail: "Checking…" },
    { key: "approvers", label: "Approvers configured", status: "loading", detail: "Checking…" },
    { key: "ciba",      label: "CIBA quota",           status: "loading", detail: "Checking…" },
    { key: "auth0",     label: "Auth0 connection",     status: "loading", detail: "Checking…" },
  ]);
  const [ready, setReady] = useState(false);

  const update = (key: string, patch: Partial<StatusItem>) =>
    setChecks((prev) => prev.map((c) => (c.key === key ? { ...c, ...patch } : c)));

  useEffect(() => {
    const run = async () => {
      // 1. API health
      try {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/health`);
        update("api", { status: "ok", detail: "Connected" });
      } catch {
        update("api", { status: "error", detail: "Cannot reach API — is Docker running?" });
        return;
      }

      // 2. Rules
      try {
        const rules = await api.getRules();
        if (rules.length === 0) {
          update("rules", { status: "warn", detail: "No rules yet — create your first rule" });
        } else {
          update("rules", { status: "ok", detail: `${rules.length} rule${rules.length > 1 ? "s" : ""} configured` });
        }
      } catch {
        update("rules", { status: "error", detail: "Could not load rules" });
      }

      // 3. Approvers
      try {
        const approvers = await api.getApprovers();
        if (approvers.length === 0) {
          update("approvers", { status: "warn", detail: "No approvers — add at least one" });
        } else {
          update("approvers", { status: "ok", detail: `${approvers.length} approver${approvers.length > 1 ? "s" : ""} registered` });
        }
      } catch {
        update("approvers", { status: "error", detail: "Could not load approvers" });
      }

      // 4. CIBA quota
      try {
        const quota = await api.getCibaQuota();
        const pct = Math.round((quota.used / quota.limit) * 100);
        if (pct >= 80) {
          update("ciba", { status: "warn", detail: `${quota.used}/${quota.limit} requests/hour (${pct}% — approaching limit)` });
        } else {
          update("ciba", { status: "ok", detail: `${quota.used}/${quota.limit} requests/hour (${pct}% used)` });
        }
      } catch {
        update("ciba", { status: "warn", detail: "CIBA quota unavailable" });
      }

      // 5. Auth0 (check dashboard endpoint which uses Auth0 config)
      try {
        await api.getDashboard();
        update("auth0", { status: "ok", detail: "Auth0 + FGA integration active" });
      } catch {
        update("auth0", { status: "warn", detail: "Auth0 may not be fully configured — run setup.py" });
      }

      setReady(true);
    };
    run();
  }, []);

  const allOk = checks.every((c) => c.status === "ok");
  const hasError = checks.some((c) => c.status === "error");
  const loading = checks.some((c) => c.status === "loading");

  const steps = [
    {
      icon: Shield,
      title: "Auth0 Setup",
      description: "Run docker compose exec api python scripts/setup.py to auto-configure Auth0, FGA, and HMAC secret.",
      action: null,
    },
    {
      icon: Users,
      title: "Add Approvers",
      description: "Register the people who will approve agent actions via Auth0 Guardian push.",
      action: () => router.push("/approvers"),
      actionLabel: "Manage Approvers",
    },
    {
      icon: GitBranch,
      title: "Create Rules",
      description: "Define approval workflows: which agent actions require human sign-off and from whom.",
      action: () => router.push("/rules/new"),
      actionLabel: "Create First Rule",
    },
    {
      icon: Link2,
      title: "Store Credentials",
      description: "Add API keys for Stripe, GitHub etc. so Token Vault can execute actions after approval.",
      action: null,
    },
    {
      icon: LayoutDashboard,
      title: "Go Live",
      description: "Your agents can now call POST /api/v1/request. Track activity in the dashboard.",
      action: () => router.push("/dashboard"),
      actionLabel: "Open Dashboard",
    },
  ];

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-zinc-900">ApprovalKit Setup</h1>
        <p className="text-zinc-500 mt-2">
          Human approval middleware for AI agents — Auth0 Token Vault + CIBA + FGA
        </p>
      </div>

      {/* System Status */}
      <Card className="mb-8">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>System Status</CardTitle>
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            ) : allOk ? (
              <Badge variant="success">All Systems Go</Badge>
            ) : hasError ? (
              <Badge variant="danger">Action Required</Badge>
            ) : (
              <Badge variant="warning">Needs Attention</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {checks.map((c) => (
              <div key={c.key} className="flex items-center gap-3">
                {c.status === "loading" ? (
                  <Loader2 className="h-5 w-5 animate-spin text-zinc-300 flex-shrink-0" />
                ) : c.status === "ok" ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                ) : c.status === "warn" ? (
                  <CheckCircle2 className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-zinc-800">{c.label}</span>
                  <span className="text-sm text-zinc-400 ml-2">{c.detail}</span>
                </div>
              </div>
            ))}
          </div>
          {ready && !allOk && (
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              Re-check
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Setup Steps */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-zinc-800">Setup Checklist</h2>
        {steps.map((step, i) => (
          <Card key={i} className="hover:border-zinc-300 transition-colors">
            <CardContent className="py-4">
              <div className="flex items-start gap-4">
                <div className="w-9 h-9 rounded-full bg-zinc-100 flex items-center justify-center flex-shrink-0">
                  <step.icon className="h-4 w-4 text-zinc-700" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-zinc-400">Step {i + 1}</span>
                  </div>
                  <p className="font-medium text-zinc-900">{step.title}</p>
                  <p className="text-sm text-zinc-500 mt-0.5">{step.description}</p>
                </div>
                {step.action && (
                  <Button size="sm" variant="outline" onClick={step.action}>
                    {step.actionLabel} <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 text-center">
        <Button size="lg" onClick={() => router.push("/dashboard")}>
          Go to Dashboard <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
