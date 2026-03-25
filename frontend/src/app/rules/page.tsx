"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Rule } from "@/types";
import { Plus, GitBranch, ArrowRight, FlaskConical, Send, Loader2, CheckCircle2, XCircle, ChevronRight, Eye, Pencil, Trash2, Shield, KeyRound, Activity } from "lucide-react";
import { useRouter } from "next/navigation";

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

const modelColors: Record<string, "default" | "success" | "warning" | "danger" | "info"> = {
  any_one: "info",
  specific: "warning",
  all_of_n: "danger",
  k_of_n: "success",
  sequential: "default",
};

interface Approver { id: string; name: string; email: string; }

export default function RulesPage() {
  const [rules, setRules]       = useState<Rule[]>([]);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [consent, setConsent]   = useState<any>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getRules(),
      api.getApprovers().catch(() => []),
      api.getConsent().catch(() => null),
    ])
      .then(([r, a, c]) => { setRules(r); setApprovers(a); setConsent(c); })
      .catch((err) => setError(err.message || "Failed to load rules"))
      .finally(() => setLoading(false));
  }, []);

  const approverMap = Object.fromEntries(approvers.map((a) => [a.id, a]));
  const connectedCount = consent?.services?.filter((s: any) => s.connected_auth0_user_id)?.length || 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Rules</h1>
          <p className="text-zinc-500 mt-1">
            Define approval workflows for each service action
          </p>
        </div>
        <Link href="/rules/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Rule
          </Button>
        </Link>
      </div>

      {/* Permissions Summary */}
      {consent && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-zinc-200 p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-zinc-500">Connected Services</p>
              <p className="text-2xl font-bold text-zinc-900">{connectedCount} / {consent.services?.length || 0}</p>
            </div>
            <KeyRound className="h-6 w-6 text-blue-500" />
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-zinc-500">Active Rules</p>
              <p className="text-2xl font-bold text-zinc-900">{consent.total_rules || 0}</p>
            </div>
            <Shield className="h-6 w-6 text-green-500" />
          </div>
          <div className="bg-white rounded-xl border border-zinc-200 p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-zinc-500">Known Agents</p>
              <p className="text-2xl font-bold text-zinc-900">{consent.total_agents || 0}</p>
            </div>
            <Activity className="h-6 w-6 text-purple-500" />
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <p className="text-red-500">{error}</p>
          </CardContent>
        </Card>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <GitBranch className="h-12 w-12 text-zinc-300 mb-4" />
            <h3 className="text-lg font-medium text-zinc-900">No rules yet</h3>
            <p className="text-zinc-500 mt-1">Create your first approval rule to get started</p>
            <Link href="/rules/new" className="mt-4">
              <Button>Create Rule</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => (
            <RuleCard key={rule.id} rule={rule} approverMap={approverMap} onDelete={() => { api.getRules().then(setRules); }} />
          ))}
        </div>
      )}
    </div>
  );
}

interface Approver { id: string; name: string; email: string; }

function RuleCard({ rule, approverMap, onDelete }: { rule: Rule; approverMap: Record<string, Approver>; onDelete: () => void }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [checkResult, setCheckResult] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const sampleParams: Record<string, any> = {};
  for (const c of rule.conditions) {
    if (c.operator === "gte") sampleParams[c.field] = c.value;
    else if (c.operator === "eq") sampleParams[c.field] = c.value;
    else if (c.operator === "gt") sampleParams[c.field] = (c.value as number) + 1;
    else if (!sampleParams[c.field]) sampleParams[c.field] = c.value;
  }
  // Add common fields based on action type
  if (rule.action.includes("charge") || rule.action.includes("refund") || rule.action.includes("payout")) {
    if (!sampleParams.customer) sampleParams.customer = "demo@example.com";
    if (!sampleParams.description) sampleParams.description = "Test transaction";
  }
  if (rule.action.includes("deploy") || rule.action.includes("rollback")) {
    if (!sampleParams.ref) sampleParams.ref = "main";
    if (!sampleParams.environment) sampleParams.environment = "production";
  }
  if (rule.action.includes("email") || rule.action.includes("message")) {
    if (!sampleParams.recipient) sampleParams.recipient = "team@example.com";
  }
  if (Object.keys(sampleParams).length === 0) sampleParams["test"] = true;

  const handleCheck = async () => {
    setChecking(true); setCheckResult(null);
    try {
      const res = await api.simulateRule({ connection: rule.connection, action: rule.action, params: sampleParams });
      setCheckResult(res);
    } catch (e: any) { setCheckResult({ error: e.message }); }
    setChecking(false);
  };

  const handleRunLive = async () => {
    setSending(true); setLiveStatus("submitting");
    try {
      const res = await api.sendTestRequest({ connection: rule.connection, action: rule.action, params: sampleParams });
      if (res.status === "auto_approved") { setLiveStatus("auto_approved"); }
      else if (res.job_id) {
        setLiveStatus("ciba_sent");
        let attempts = 0;
        const poll = async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            if (["approved", "rejected", "timeout", "blocked"].includes(s.status)) { setLiveStatus(s.status); return; }
          } catch {}
          if (++attempts < 60) setTimeout(poll, 2000);
        };
        poll();
      }
    } catch { setLiveStatus("error"); }
    setSending(false);
  };

  const handleDelete = async () => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    try { await api.deleteRule(rule.id); onDelete(); } catch {}
  };

  return (
    <div className="border border-zinc-200 rounded-xl overflow-hidden mb-3">
      {/* Header — clickable to expand */}
      <button className="w-full text-left p-4 hover:bg-zinc-50 transition-colors" onClick={() => setExpanded(v => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-zinc-900">{rule.name}</h3>
                {!rule.is_active && <Badge variant="default">Inactive</Badge>}
              </div>
              <p className="text-sm text-zinc-500 mt-0.5">
                <code className="text-xs bg-zinc-100 px-1.5 py-0.5 rounded">{rule.connection}:{rule.action}</code>
                {rule.conditions.length > 0 && <span className="ml-2 text-xs">({rule.conditions.length} condition{rule.conditions.length > 1 ? "s" : ""})</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={modelColors[rule.model]}>
              {modelLabels[rule.model]}
              {rule.model === "k_of_n" && rule.k_value && ` (${rule.k_value}/${rule.approver_ids.length})`}
            </Badge>
            {rule.step_up_model && <Badge variant="info">Step-up</Badge>}
            {rule.on_timeout === "escalate" && <Badge variant="warning">Escalation</Badge>}
          </div>
        </div>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 bg-zinc-50/50 space-y-4">
          {/* Trust Chain */}
          {rule.approver_ids.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-zinc-400 mb-2 uppercase tracking-wide">
                {rule.model === "sequential" ? "Approval chain" : "Approvers"}
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <code className="text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded font-mono">{rule.connection}:{rule.action}</code>
                {rule.approver_ids.map((id, idx) => {
                  const a = approverMap[id];
                  return (
                    <div key={id} className="flex items-center gap-1">
                      <span className="text-zinc-300 text-xs">→</span>
                      <span className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded">{a ? a.name : `Approver ${idx + 1}`}</span>
                    </div>
                  );
                })}
                <span className="text-zinc-300 text-xs">→</span>
                <span className="text-xs bg-green-50 border border-green-200 text-green-700 px-2 py-0.5 rounded">Auth0 Token Vault</span>
              </div>
            </div>
          )}

          {/* Request Params */}
          <div>
            <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Request Params</p>
            <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">{JSON.stringify({ connection: rule.connection, action: rule.action, params: sampleParams }, null, 2)}</pre>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={handleCheck} disabled={checking}>
              {checking ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Checking...</> : <><FlaskConical className="h-3.5 w-3.5 mr-1.5" />Check Rule</>}
            </Button>
            <Button size="sm" onClick={handleRunLive} disabled={sending || liveStatus === "ciba_sent"}>
              {sending ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending...</> : <><Send className="h-3.5 w-3.5 mr-1.5" />Run Live</>}
            </Button>
            <div className="ml-auto flex items-center gap-1">
              <Button size="sm" variant="ghost" onClick={() => router.push(`/rules/${rule.id}`)}>
                <Eye className="h-3.5 w-3.5 mr-1.5" />View
              </Button>
              <Button size="sm" variant="ghost" onClick={() => router.push(`/rules/${rule.id}/edit`)}>
                <Pencil className="h-3.5 w-3.5 mr-1.5" />Edit
              </Button>
              <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-700 hover:bg-red-50" onClick={handleDelete}>
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />Delete
              </Button>
            </div>
          </div>

          {/* Check Rule result */}
          {checkResult && (
            <div className={`px-3 py-2 rounded-lg text-xs ${
              checkResult.matched ? "bg-blue-50 border border-blue-200 text-blue-800" :
              checkResult.error ? "bg-red-50 border border-red-200 text-red-800" :
              "bg-green-50 border border-green-200 text-green-800"
            }`}>
              {checkResult.matched ? (
                <span><CheckCircle2 className="h-3 w-3 inline mr-1" />Matched: {checkResult.rule_name} ({checkResult.model}){checkResult.step_up_triggered ? ` → Step-up: ${checkResult.effective_model}` : ""}</span>
              ) : checkResult.error ? (
                <span><XCircle className="h-3 w-3 inline mr-1" />{checkResult.error}</span>
              ) : (
                <span>Auto-approve (no rule match with sample params)</span>
              )}
            </div>
          )}

          {/* Run Live status */}
          {liveStatus && (
            <div className={`px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${
              liveStatus === "approved" ? "bg-green-50 border border-green-200 text-green-800" :
              liveStatus === "rejected" || liveStatus === "timeout" ? "bg-red-50 border border-red-200 text-red-800" :
              "bg-blue-50 border border-blue-200 text-blue-800"
            }`}>
              {liveStatus === "submitting" && <><Loader2 className="h-3 w-3 animate-spin" />Submitting...</>}
              {liveStatus === "ciba_sent" && <><Loader2 className="h-3 w-3 animate-spin" />Guardian push sent — waiting for approval...</>}
              {liveStatus === "approved" && <><CheckCircle2 className="h-3 w-3" />Approved via Guardian</>}
              {liveStatus === "rejected" && <><XCircle className="h-3 w-3" />Rejected</>}
              {liveStatus === "timeout" && <><XCircle className="h-3 w-3" />Timed out</>}
              {liveStatus === "auto_approved" && <><CheckCircle2 className="h-3 w-3" />Auto-approved</>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
