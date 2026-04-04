"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Rule } from "@/types";
import {
  Plus, GitBranch, FlaskConical, Send, Loader2, CheckCircle2, XCircle,
  ChevronRight, Eye, Pencil, Trash2, Shield, KeyRound, Activity, Zap,
  Clock, Gauge, BookTemplate, ChevronDown, Lock, Unlock, RefreshCw,
  ChevronUp, CheckCircle, AlertTriangle,
} from "lucide-react";
import { useRouter } from "next/navigation";

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

const modelBgColors: Record<string, string> = {
  any_one: "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800",
  specific: "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800",
  all_of_n: "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800",
  k_of_n: "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
  sequential: "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700",
};

const MODEL_LABELS: Record<string, string> = {
  any_one: "Any One Approver",
  specific: "Specific Approver",
  all_of_n: "All Approvers",
  k_of_n: "K-of-N Quorum",
  sequential: "Sequential Chain",
  fga_dynamic: "FGA Dynamic",
};

const SERVICE_ICONS: Record<string, string> = {
  stripe: "💳", github: "🐙", slack: "💬", google: "📧", microsoft: "📨",
  salesforce: "☁️", notion: "📝", jira: "🎯", discord: "🎮", linear: "📐",
  hubspot: "🔶", shopify: "🛍️", paypal: "💰", dropbox: "📦", amadeus: "✈️",
};

const STATE_COLORS: Record<string, string> = {
  approved: "text-emerald-600 dark:text-emerald-400",
  rejected: "text-red-600 dark:text-red-400",
  blocked: "text-red-600 dark:text-red-400",
  timeout: "text-amber-600 dark:text-amber-400",
  pending: "text-blue-600 dark:text-blue-400",
  ciba_sent: "text-blue-600 dark:text-blue-400",
  waiting_approval: "text-blue-600 dark:text-blue-400",
  pre_approved: "text-emerald-600 dark:text-emerald-400",
};

interface Approver { id: string; name: string; email: string; }

interface ConsentService {
  connection_id: string;
  name: string;
  service: string;
  slug: string;
  connected_user: string | null;
  connected_auth0_user_id: string | null;
  oauth_scopes: string[];
  actions: string[];
  rules: { id: string; name: string; model: string; action: string; approver_count: number; step_up_model: string | null; }[];
  recent_access: { job_id: string; agent_user_id: string; action: string; state: string; created_at: string; }[];
  can_revoke: boolean;
}

interface ConsentData {
  services: ConsentService[];
  total_agents: number;
  total_rules: number;
}

export default function RulesPage() {
  const [tab, setTab] = useState<"rules" | "consent" | "permissions">("rules");
  const [rules, setRules] = useState<Rule[]>([]);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [consent, setConsent] = useState<ConsentData | null>(null);
  const [permissionMap, setPermissionMap] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<any[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  useEffect(() => {
    Promise.all([
      api.getRules(),
      api.getApprovers().catch(() => []),
      api.getConsent().catch(() => null),
      fetch("/api/v1/rules/templates").then(r => r.ok ? r.json() : { templates: [] }).catch(() => ({ templates: [] })),
      api.getPermissionMap().catch(() => null),
    ])
      .then(([r, a, c, t, pm]) => { setRules(r); setApprovers(a); setConsent(c); setTemplates(t.templates || []); setPermissionMap(pm); })
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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
            Rules & Consent
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-2 text-sm">
            Approval workflows, service permissions, and access visibility
          </p>
        </div>
        {tab === "rules" && (
          <Link href="/rules/new">
            <Button className="shadow-md hover:shadow-lg transition-shadow duration-200">
              <Plus className="h-4 w-4 mr-2" />
              New Rule
            </Button>
          </Link>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-8 border-b border-zinc-200 dark:border-zinc-800">
        <button
          onClick={() => setTab("rules")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            tab === "rules"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
          }`}
        >
          <GitBranch className="h-4 w-4 inline mr-1.5" />
          Approval Rules
          {rules.length > 0 && <span className="ml-1.5 text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded-full">{rules.length}</span>}
        </button>
        <button
          onClick={() => setTab("consent")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            tab === "consent"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
          }`}
        >
          <Shield className="h-4 w-4 inline mr-1.5" />
          Consent & Permissions
          {consent && <span className="ml-1.5 text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded-full">{consent.services.length}</span>}
        </button>
        <button
          onClick={() => setTab("permissions")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            tab === "permissions"
              ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
              : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300"
          }`}
        >
          <Eye className="h-4 w-4 inline mr-1.5" />
          Permission Map
          {permissionMap && <span className="ml-1.5 text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded-full">{permissionMap.total_agents}</span>}
        </button>
      </div>

      {tab === "rules" ? (
        <RulesTab
          rules={rules}
          approverMap={approverMap}
          consent={consent}
          connectedCount={connectedCount}
          userRulesCount={userRulesCount}
          demoRulesCount={demoRulesCount}
          templates={templates}
          showTemplates={showTemplates}
          setShowTemplates={setShowTemplates}
          loading={loading}
          error={error}
          onRefresh={() => { api.getRules().then(setRules); }}
        />
      ) : tab === "consent" ? (
        <ConsentTab
          consent={consent}
          loading={loading}
          error={error}
          onRefresh={() => { api.getConsent().then((c: ConsentData) => setConsent(c)).catch(() => {}); }}
        />
      ) : (
        <PermissionMapTab data={permissionMap} loading={loading} />
      )}
    </div>
  );
}

/* ─── Rules Tab ─── */
function RulesTab({
  rules, approverMap, consent, connectedCount, userRulesCount, demoRulesCount,
  templates, showTemplates, setShowTemplates, loading, error, onRefresh,
}: any) {
  return (
    <>
      {/* Rule Templates */}
      {templates.length > 0 && (
        <div className="mb-8">
          <button
            onClick={() => setShowTemplates((v: boolean) => !v)}
            className="flex items-center gap-2 w-full rounded-xl px-5 py-4 bg-gradient-to-r from-violet-50 to-blue-50 dark:from-violet-950/20 dark:to-blue-950/20 border border-violet-200 dark:border-violet-800 hover:from-violet-100 hover:to-blue-100 dark:hover:from-violet-950/30 dark:hover:to-blue-950/30 transition-all"
          >
            <BookTemplate className="h-5 w-5 text-violet-600 dark:text-violet-400" />
            <span className="text-sm font-semibold text-violet-700 dark:text-violet-300">Rule Templates</span>
            <span className="text-xs text-violet-500 dark:text-violet-400 ml-1">— {templates.length} pre-built configurations</span>
            <div className="flex-1" />
            <ChevronDown className={`h-4 w-4 text-violet-400 transition-transform duration-200 ${showTemplates ? "rotate-180" : ""}`} />
          </button>
          {showTemplates && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
              {templates.map((tpl: any) => (
                <Link
                  key={tpl.id}
                  href={`/rules/new?template=${tpl.id}`}
                  className="group rounded-xl border border-zinc-200 dark:border-zinc-700 p-4 hover:border-violet-300 dark:hover:border-violet-700 hover:shadow-md transition-all bg-white dark:bg-zinc-900"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tpl.category === 'finance' ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' :
                        tpl.category === 'devops' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' :
                          tpl.category === 'communication' ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' :
                            'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300'
                      }`}>{tpl.category}</span>
                  </div>
                  <h4 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm group-hover:text-violet-700 dark:group-hover:text-violet-400 transition-colors">{tpl.name}</h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2">{tpl.description}</p>
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <code className="text-[10px] bg-zinc-100 dark:bg-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded font-mono">{tpl.connection}:{tpl.action}</code>
                    {tpl.max_requests_per_hour && <span className="text-[10px] text-zinc-400"><Gauge className="h-3 w-3 inline" /> {tpl.max_requests_per_hour}/hr</span>}
                    {tpl.approval_expiry_seconds && <span className="text-[10px] text-zinc-400"><Clock className="h-3 w-3 inline" /> {Math.round(tpl.approval_expiry_seconds / 60)}m expiry</span>}
                    {tpl.trigger_rules?.length > 0 && <span className="text-[10px] text-zinc-400"><Zap className="h-3 w-3 inline" /> chain</span>}
                  </div>
                  <div className="mt-3 text-[10px] font-medium text-violet-600 dark:text-violet-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    Use this template →
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

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
        <RulesList rules={rules} approverMap={approverMap} onRefresh={onRefresh} />
      )}
    </>
  );
}

/* ─── Consent Tab ─── */
function ConsentTab({ consent, loading, error, onRefresh }: { consent: ConsentData | null; loading: boolean; error: string | null; onRefresh: () => void }) {
  const [expandedServices, setExpandedServices] = useState<Set<string>>(new Set());
  const [revoking, setRevoking] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedServices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRevoke = async (connectionId: string) => {
    if (!confirm("Are you sure you want to revoke this connection? The agent will no longer be able to perform actions through this service.")) return;
    setRevoking(connectionId);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/connections/${connectionId}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      onRefresh();
    } catch {
      // silently fail
    } finally {
      setRevoking(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-3" />
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (!consent) return null;

  const connectedCount = consent.services.filter((s) => s.connected_auth0_user_id).length;
  const totalScopes = consent.services.reduce((acc, s) => acc + (Array.isArray(s.oauth_scopes) ? s.oauth_scopes.length : 0), 0);

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                <Lock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{consent.services.length}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Connected Services</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30">
                <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{connectedCount}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Token Vault Linked</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/30">
                <Eye className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{totalScopes}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">OAuth Scopes Granted</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30">
                <Shield className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{consent.total_rules}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Active Approval Rules</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Count Banner */}
      {consent.total_agents > 0 && (
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 px-4 py-3 flex items-center gap-3">
          <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
          <p className="text-sm text-blue-800 dark:text-blue-300">
            <strong>{consent.total_agents} distinct agent{consent.total_agents > 1 ? "s" : ""}</strong> have interacted with your workspace.
            All actions are gated by approval rules — agents never hold your credentials.
          </p>
        </div>
      )}

      {/* Service Cards */}
      {consent.services.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Unlock className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
            <p className="text-zinc-500 dark:text-zinc-400 text-lg font-medium">No connected services</p>
            <p className="text-zinc-400 dark:text-zinc-500 text-sm mt-1">
              Connect services in the Connections page to see consent details here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {consent.services.map((service) => {
            const isExpanded = expandedServices.has(service.connection_id);
            const icon = SERVICE_ICONS[service.service.toLowerCase()] || "🔗";
            const isVaultLinked = !!service.connected_auth0_user_id;

            return (
              <Card key={service.connection_id} className="overflow-hidden">
                <div
                  className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  onClick={() => toggleExpand(service.connection_id)}
                >
                  <div className="flex items-center gap-4">
                    <span className="text-2xl">{icon}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{service.name}</h3>
                        <Badge variant={isVaultLinked ? "success" : "warning"}>
                          {isVaultLinked ? "Token Vault" : "Not Linked"}
                        </Badge>
                      </div>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                        {service.service} &middot; {service.actions.length} action{service.actions.length !== 1 ? "s" : ""} &middot;{" "}
                        {service.rules.length} rule{service.rules.length !== 1 ? "s" : ""}
                        {service.connected_user && ` · Connected as ${service.connected_user}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {service.can_revoke && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={(e) => { e.stopPropagation(); handleRevoke(service.connection_id); }}
                        disabled={revoking === service.connection_id}
                      >
                        {revoking === service.connection_id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <XCircle className="h-3 w-3" />}
                        <span className="ml-1.5">Revoke</span>
                      </Button>
                    )}
                    {isExpanded ? <ChevronUp className="h-5 w-5 text-zinc-400" /> : <ChevronDown className="h-5 w-5 text-zinc-400" />}
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-zinc-100 dark:border-zinc-800">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-zinc-100 dark:divide-zinc-800">
                      {/* OAuth Scopes */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Lock className="h-3.5 w-3.5" />
                          OAuth Scopes
                        </h4>
                        <div className="space-y-1.5">
                          {(Array.isArray(service.oauth_scopes) ? service.oauth_scopes : []).map((scope) => (
                            <div key={scope} className="text-xs font-mono px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                              {scope}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Approval Rules */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Shield className="h-3.5 w-3.5" />
                          Approval Rules
                        </h4>
                        {service.rules.length === 0 ? (
                          <p className="text-xs text-zinc-400 italic">No rules configured</p>
                        ) : (
                          <div className="space-y-2">
                            {service.rules.map((rule) => (
                              <div key={rule.id} className="text-xs p-2 rounded border border-zinc-100 dark:border-zinc-800">
                                <div className="flex items-center justify-between">
                                  <span className="font-medium text-zinc-900 dark:text-zinc-100">{rule.name}</span>
                                  <Badge variant="default">{MODEL_LABELS[rule.model] || rule.model}</Badge>
                                </div>
                                <div className="mt-1 text-zinc-500 dark:text-zinc-400">
                                  Action: <span className="font-mono">{rule.action}</span>
                                  {" · "}{rule.approver_count} approver{rule.approver_count !== 1 ? "s" : ""}
                                  {rule.step_up_model && (
                                    <span className="text-amber-600 dark:text-amber-400">
                                      {" · "}Step-up → {MODEL_LABELS[rule.step_up_model] || rule.step_up_model}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Recent Access */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          Recent Access
                        </h4>
                        {service.recent_access.length === 0 ? (
                          <p className="text-xs text-zinc-400 italic">No recent activity</p>
                        ) : (
                          <div className="space-y-1.5">
                            {service.recent_access.slice(0, 5).map((access) => (
                              <div key={access.job_id} className="text-xs flex items-center justify-between">
                                <span className="font-mono text-zinc-700 dark:text-zinc-300">{access.action}</span>
                                <div className="flex items-center gap-2">
                                  <span className={STATE_COLORS[access.state] || "text-zinc-500"}>{access.state}</span>
                                  <span className="text-zinc-400">{new Date(access.created_at).toLocaleDateString()}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Security Footer */}
      <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800/50 px-5 py-4">
        <div className="flex items-start gap-3">
          <Shield className="h-5 w-5 text-zinc-500 mt-0.5 shrink-0" />
          <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Zero credential exposure:</strong>{" "}
              All agent actions are executed through Auth0 Token Vault. Agents never see or hold your API keys, OAuth tokens, or credentials.
            </p>
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Human-in-the-loop:</strong>{" "}
              Every action matching an approval rule requires explicit human consent via CIBA push notification before execution.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Helpers ─── */
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
          } catch { }
          if (++attempts < 60) setTimeout(poll, 2000);
        };
        poll();
      }
    } catch { setLiveStatus("error"); }
    setSending(false);
  };

  const handleDelete = async () => {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    try { await api.deleteRule(rule.id); onDelete(); } catch { }
  };

  const modelBg = modelBgColors[rule.model] || modelBgColors["sequential"];

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200 bg-white dark:bg-zinc-900">
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
            {rule.max_requests_per_hour && (
              <span className="text-xs font-medium px-2 py-1 rounded-full border border-violet-200 dark:border-violet-800 bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300" title={`Max ${rule.max_requests_per_hour} requests/hour`}>
                <Gauge className="h-3 w-3 inline mr-0.5" />{rule.max_requests_per_hour}/hr
              </span>
            )}
            {rule.approval_expiry_seconds && (
              <span className="text-xs font-medium px-2 py-1 rounded-full border border-cyan-200 dark:border-cyan-800 bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300" title={`Approval expires after ${Math.round(rule.approval_expiry_seconds / 60)} minutes`}>
                <Clock className="h-3 w-3 inline mr-0.5" />{Math.round(rule.approval_expiry_seconds / 60)}m
              </span>
            )}
            {(rule.trigger_rules?.length || 0) > 0 && (
              <span className="text-xs font-medium px-2 py-1 rounded-full border border-orange-200 dark:border-orange-800 bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300" title="Rule chaining enabled">
                <Zap className="h-3 w-3 inline mr-0.5" />Chain
              </span>
            )}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30 space-y-4">
          {rule.approver_ids.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">
                {rule.model === "sequential" ? "Approval Chain" : "Approvers"}
              </p>
              <div className="flex items-center gap-2 flex-wrap">
                <code className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded font-mono">{rule.connection}:{rule.action}</code>
                {rule.approver_ids.map((id: string, idx: number) => {
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

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">Request Params</p>
            <pre className="bg-zinc-900 dark:bg-zinc-950 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">{JSON.stringify({ connection: rule.connection, action: rule.action, params: sampleParams }, null, 2)}</pre>
          </div>

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

          {checkResult && (
            <div className={`px-3 py-2.5 rounded-lg text-xs ${checkResult.matched ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300" :
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

          {liveStatus && (
            <div className={`px-3 py-2.5 rounded-lg text-xs flex items-center gap-2 ${liveStatus === "approved" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
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


/* ─── Permission Map Tab ─── */
function PermissionMapTab({ data, loading }: { data: any; loading: boolean }) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  if (loading) return (
    <div className="flex items-center justify-center h-40">
      <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
    </div>
  );

  if (!data || !data.agents || data.agents.length === 0) return (
    <Card>
      <CardContent className="py-12 text-center">
        <Eye className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
        <p className="text-zinc-500 dark:text-zinc-400 text-lg font-medium">No agents registered</p>
        <p className="text-zinc-400 dark:text-zinc-500 text-sm mt-1">
          Register agents in the Connect Agent page to see their permission map here.
        </p>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{data.total_agents}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Active Agents</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-50 dark:bg-green-950/30">
                <KeyRound className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{data.total_connections}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Connected Services</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/30">
                <Shield className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{data.total_rules}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Active Rules</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Permission Cards */}
      {data.agents.map((agent: any) => {
        const isExpanded = expandedAgent === agent.agent_id;
        const trustColor = agent.trust_level === "high" ? "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30"
          : agent.trust_level === "medium" ? "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950/30"
          : "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30";

        return (
          <Card key={agent.agent_id} className="overflow-hidden">
            <div
              className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
              onClick={() => setExpandedAgent(isExpanded ? null : agent.agent_id)}
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
                  {agent.agent_name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{agent.agent_name}</p>
                  {agent.description && (
                    <p className="text-[11px] text-zinc-400 dark:text-zinc-500 truncate max-w-md">{agent.description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${trustColor}`}>
                  Trust {agent.trust_score}
                </span>
                <span className="text-xs text-zinc-400">{agent.total_connections} services</span>
                {isExpanded ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
              </div>
            </div>

            {isExpanded && (
              <div className="border-t border-zinc-200 dark:border-zinc-800 px-6 py-4 space-y-3">
                {agent.permissions.length === 0 ? (
                  <p className="text-sm text-zinc-400 py-4 text-center">No service permissions</p>
                ) : (
                  <div className="grid gap-3">
                    {agent.permissions.map((perm: any) => (
                      <div key={perm.connection} className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${perm.connected ? "bg-green-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
                            <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">{perm.name}</span>
                            <code className="text-[10px] bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5 text-zinc-500">{perm.connection}</code>
                          </div>
                          <div className="flex items-center gap-2">
                            {perm.connected && (
                              <Badge variant="success" className="text-[9px]">Token Vault</Badge>
                            )}
                            {perm.rules_count > 0 && (
                              <span className="text-[10px] text-zinc-400">{perm.rules_count} rule{perm.rules_count > 1 ? "s" : ""}</span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex flex-wrap gap-1 mb-2">
                          {(perm.actions || []).map((a: string) => (
                            <span key={a} className="text-[10px] bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 rounded px-1.5 py-0.5">{a}</span>
                          ))}
                        </div>

                        {/* Scopes */}
                        {perm.scopes && perm.scopes.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {perm.scopes.map((s: string) => (
                              <span key={s} className="text-[9px] bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400 rounded px-1.5 py-0.5 border border-blue-200/50 dark:border-blue-800/50">{s}</span>
                            ))}
                          </div>
                        )}

                        {/* Approval Models */}
                        {perm.models && perm.models.length > 0 && (
                          <div className="flex gap-1 mb-2">
                            {perm.models.map((m: string) => (
                              <span key={m} className="text-[9px] bg-purple-50 dark:bg-purple-950/20 text-purple-600 dark:text-purple-400 rounded px-1.5 py-0.5">{m.replace(/_/g, " ")}</span>
                            ))}
                          </div>
                        )}

                        {/* Usage Stats */}
                        {perm.usage_7d && perm.usage_7d.total > 0 && (
                          <div className="flex items-center gap-4 mt-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                            <span className="text-[10px] text-zinc-400">{perm.usage_7d.total} requests (7d)</span>
                            <span className="text-[10px] text-green-500">{perm.usage_7d.approved} approved</span>
                            {perm.usage_7d.rejected > 0 && (
                              <span className="text-[10px] text-red-500">{perm.usage_7d.rejected} rejected</span>
                            )}
                            {perm.usage_7d.last_used && (
                              <span className="text-[10px] text-zinc-400 ml-auto">
                                Last: {new Date(perm.usage_7d.last_used).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
