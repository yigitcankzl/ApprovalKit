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

const modelBgColors: Record<string, string> = {
  any_one: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800",
  specific: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800",
  all_of_n: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800",
  k_of_n: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
  sequential: "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700",
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

  const userRulesCount = rules.filter(r => !isDemoRule(r)).length;
  const demoRulesCount = rules.filter(r => isDemoRule(r)).length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-12">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
            Rules
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-2 text-sm">
            Define approval workflows for each service action
          </p>
        </div>
        <Link href="/rules/new">
          <Button className="shadow-md hover:shadow-lg transition-shadow duration-200">
            <Plus className="h-4 w-4 mr-2" />
            New Rule
          </Button>
        </Link>
      </div>

      {/* Stat Summary Cards */}
      {consent && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-5 mb-10">
          <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-5 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Connected Services</p>
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{connectedCount} / {consent.services?.length || 0}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center">
              <KeyRound className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
          </div>
          <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20 p-5 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Active Rules</p>
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{consent.total_rules || 0}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
              <Shield className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
          </div>
          <div className="rounded-xl border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20 p-5 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Known Agents</p>
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{consent.total_agents || 0}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center">
              <Activity className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
          </div>
          <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 p-5 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Your Rules</p>
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">{userRulesCount}</p>
              {demoRulesCount > 0 && (
                <p className="text-[10px] text-zinc-400 mt-0.5">+ {demoRulesCount} demo</p>
              )}
            </div>
            <div className="h-10 w-10 rounded-lg bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center">
              <GitBranch className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <p className="text-red-500">{error}</p>
          </CardContent>
        </Card>
      ) : rules.length === 0 ? (
        <Card className="border-dashed border-2 border-zinc-200 dark:border-zinc-700">
          <CardContent className="flex flex-col items-center justify-center py-20">
            <div className="h-14 w-14 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-5">
              <GitBranch className="h-7 w-7 text-zinc-400 dark:text-zinc-500" />
            </div>
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">No rules yet</h3>
            <p className="text-zinc-500 dark:text-zinc-400 mt-1 text-sm">Create your first approval rule to get started</p>
            <Link href="/rules/new" className="mt-5">
              <Button>Create Rule</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <RulesList rules={rules} approverMap={approverMap} onRefresh={() => { api.getRules().then(setRules); }} />
      )}
    </div>
  );
}

function isDemoRule(rule: Rule): boolean {
  return /^\[.+\]/.test(rule.name);
}

function RulesList({ rules, approverMap, onRefresh }: { rules: Rule[]; approverMap: Record<string, Approver>; onRefresh: () => void }) {
  const [showDemo, setShowDemo] = useState(false);
  const userRules = rules.filter(r => !isDemoRule(r));
  const demoRules = rules.filter(r => isDemoRule(r));

  return (
    <div className="space-y-3">
      {userRules.length > 0 && (
        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3">Your Rules</p>
      )}
      <div className="grid grid-cols-1 gap-5">
        {userRules.map((rule) => (
          <RuleCard key={rule.id} rule={rule} approverMap={approverMap} onDelete={onRefresh} />
        ))}
      </div>

      {demoRules.length > 0 && (
        <div className="mt-8">
          <button
            onClick={() => setShowDemo(v => !v)}
            className="flex items-center gap-2 w-full rounded-lg px-4 py-3 bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform duration-200 ${showDemo ? "rotate-90" : ""}`} />
            <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Demo Rules</span>
            <span className="text-[10px] font-medium text-zinc-400 ml-1">({demoRules.length})</span>
            <div className="flex-1" />
            <span className="text-[10px] text-zinc-400">{showDemo ? "Collapse" : "Expand"}</span>
          </button>
          {showDemo && (
            <div className="grid grid-cols-1 gap-5 mt-5 pl-2 border-l-2 border-zinc-200 dark:border-zinc-700">
              {demoRules.map((rule) => (
                <RuleCard key={rule.id} rule={rule} approverMap={approverMap} onDelete={onRefresh} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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

  const modelBg = modelBgColors[rule.model] || modelBgColors["sequential"];

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200 bg-white dark:bg-zinc-900">
      {/* Header */}
      <button className="w-full text-left p-5 hover:bg-zinc-50/80 dark:hover:bg-zinc-800/60 transition-colors" onClick={() => setExpanded(v => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{rule.name}</h3>
                {!rule.is_active && (
                  <span className="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-400">Inactive</span>
                )}
              </div>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded font-mono">{rule.connection}:{rule.action}</code>
                {rule.conditions.length > 0 && <span className="ml-2 text-xs text-zinc-400">({rule.conditions.length} condition{rule.conditions.length > 1 ? "s" : ""})</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${modelBg}`}>
              {modelLabels[rule.model]}
              {rule.model === "k_of_n" && rule.k_value && ` (${rule.k_value}/${rule.approver_ids.length})`}
            </span>
            {rule.step_up_model && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full border border-blue-200 dark:border-blue-800 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">Step-up</span>
            )}
            {rule.on_timeout === "escalate" && (
              <span className="text-xs font-medium px-2.5 py-1 rounded-full border border-amber-200 dark:border-amber-800 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">Escalation</span>
            )}
          </div>
        </div>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 space-y-4">
          {/* Trust Chain */}
          {rule.approver_ids.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">
                {rule.model === "sequential" ? "Approval Chain" : "Approvers"}
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <code className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded font-mono">{rule.connection}:{rule.action}</code>
                {rule.approver_ids.map((id, idx) => {
                  const a = approverMap[id];
                  return (
                    <div key={id} className="flex items-center gap-1">
                      <span className="text-zinc-300 dark:text-zinc-600 text-xs">→</span>
                      <span className="text-xs bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">{a ? a.name : `Approver ${idx + 1}`}</span>
                    </div>
                  );
                })}
                <span className="text-zinc-300 dark:text-zinc-600 text-xs">→</span>
                <span className="text-xs bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">Auth0 Token Vault</span>
              </div>
            </div>
          )}

          {/* Request Params */}
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">Request Params</p>
            <pre className="bg-zinc-900 dark:bg-zinc-950 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">{JSON.stringify({ connection: rule.connection, action: rule.action, params: sampleParams }, null, 2)}</pre>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1">
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
              <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30" onClick={handleDelete}>
                <Trash2 className="h-3.5 w-3.5 mr-1.5" />Delete
              </Button>
            </div>
          </div>

          {/* Check Rule result */}
          {checkResult && (
            <div className={`px-3 py-2.5 rounded-lg text-xs ${
              checkResult.matched ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300" :
              checkResult.error ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300" :
              "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300"
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
            <div className={`px-3 py-2.5 rounded-lg text-xs flex items-center gap-2 ${
              liveStatus === "approved" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
              liveStatus === "rejected" || liveStatus === "timeout" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300" :
              "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300"
            }`}>
              {liveStatus === "submitting" && <><Loader2 className="h-3 w-3 animate-spin" />Submitting...</>}
              {liveStatus === "ciba_sent" && <><Loader2 className="h-3 w-3 animate-spin" />Guardian push sent -- waiting for approval...</>}
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
