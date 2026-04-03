"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";
import {
  CheckCircle2, XCircle, ShieldOff, Clock, KeyRound, Users,
  Activity, AlertTriangle, Radio, ShieldCheck, Gauge, CircleDot,
  TrendingUp, Zap, ArrowRight, BarChart3, Mail, Link2, Copy,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SecurityItem { ok: boolean; detail: string; }
interface SecurityStatus {
  hmac: SecurityItem; fga: SecurityItem; token_vault: SecurityItem;
  credentials_key: SecurityItem; sentry: SecurityItem;
}
interface LiveEvent {
  type: string; job_id: string; connection: string; action: string;
  timestamp: string; exec_note?: string; note?: string;
}

const EVENT_BADGE: Record<string, { variant: "success" | "danger" | "warning" | "info" | "default"; }> = {
  requested:          { variant: "info" },
  approved:           { variant: "success" },
  rejected:           { variant: "danger" },
  blocked:            { variant: "warning" },
  timeout:            { variant: "warning" },
  ciba_sent:          { variant: "info" },
  step_up_triggered:  { variant: "warning" },
  step_up:            { variant: "warning" },
  pre_approved:       { variant: "success" },
  partial_approved:   { variant: "info" },
  escalated:          { variant: "danger" },
};

const EVENT_DOT: Record<string, string> = {
  requested:          "bg-blue-500",
  approved:           "bg-green-500",
  rejected:           "bg-red-500",
  blocked:            "bg-orange-500",
  timeout:            "bg-yellow-500",
  ciba_sent:          "bg-purple-500",
  step_up_triggered:  "bg-yellow-500",
  step_up:            "bg-yellow-500",
  pre_approved:       "bg-emerald-500",
  partial_approved:   "bg-teal-500",
  escalated:          "bg-orange-600",
};

export default function DashboardPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [stats, setStats]       = useState<DashboardStats | null>(null);
  const [security, setSecurity] = useState<SecurityStatus | null>(null);
  const [events, setEvents]     = useState<LiveEvent[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [patterns, setPatterns] = useState<any[]>([]);
  const [pendingJobs, setPendingJobs] = useState<any[]>([]);
  const [riskDist, setRiskDist] = useState<any>(null);
  const [now, setNow]           = useState(Date.now());
  const [copiedLink, setCopiedLink] = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [authLoading, user]);

  const loadStats = () =>
    Promise.all([api.getDashboard(), api.getSecurityStatus().catch(() => null)])
      .then(([s, sec]) => { setStats(s); setSecurity(sec); });

  useEffect(() => {
    if (authLoading || !user) return; // wait for auth before fetching
    const ctrl = { active: true };
    Promise.all([
      loadStats(),
      api.getRecentActivity(20)
        .then((rows: LiveEvent[]) => { if (ctrl.active) setEvents(Array.isArray(rows) ? rows : []); })
        .catch(() => {}),
      api.getApprovalPatterns(30)
        .then((data: any) => { if (ctrl.active) setPatterns(data.patterns || []); })
        .catch(() => {}),
      api.getPendingJobs()
        .then((jobs: any[]) => { if (ctrl.active) setPendingJobs(Array.isArray(jobs) ? jobs : []); })
        .catch(() => {}),
      api.getRiskDistribution(7)
        .then((data: any) => { if (ctrl.active) setRiskDist(data); })
        .catch(() => {}),
    ])
      .catch((err) => { if (ctrl.active) setError(err.message || "Failed to load"); })
      .finally(() => { if (ctrl.active) setLoading(false); });

    // Refresh pending jobs on stat reload
    const refreshPending = () => api.getPendingJobs().then(setPendingJobs).catch(() => {});

    // Auto-refresh stats only — do not replace Live Activity (SSE + initial hydrate)
    const refreshInterval = setInterval(() => { loadStats(); refreshPending(); }, 30000);

    // SSE subscription with exponential backoff reconnection
    let es: EventSource | null = null;
    let reconnectDelay = 1000;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    function connectSSE() {
      if (cancelled) return;
      es = new EventSource(`${API_BASE}/api/v1/events`);
      es.onopen = () => { reconnectDelay = 1000; };
      es.onmessage = (e) => {
        try {
          const data: LiveEvent = JSON.parse(e.data);
          setEvents((prev) => [data, ...prev].slice(0, 20));
          if (["approved", "rejected", "blocked", "requested", "ciba_sent"].includes(data.type)) {
            loadStats();
          }
        } catch {}
      };
      es.onerror = () => {
        es?.close();
        if (!cancelled) {
          reconnectTimer = setTimeout(connectSSE, reconnectDelay);
          reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        }
      };
    }
    connectSSE();

    // Tick every second for countdown timers
    const tickInterval = setInterval(() => setNow(Date.now()), 1000);

    return () => {
      ctrl.active = false;
      cancelled = true;
      es?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearInterval(refreshInterval);
      clearInterval(tickInterval);
    };
  }, [authLoading, user]);

  // Show nothing while auth is resolving (prevents flash of dashboard before login redirect)
  if (authLoading || !user) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" />
    </div>
  );

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" />
    </div>
  );
  if (error) return <div className="flex items-center justify-center h-64"><p className="text-red-500">{error}</p></div>;
  if (!stats) return null;

  const hasNoData = stats.total_actions_week === 0 && (stats.pending_count || 0) === 0;
  const cibaPercent = Math.round((stats.ciba_usage / stats.ciba_limit) * 100);

  const statCards: {
    title: string;
    value: number;
    icon: typeof Activity;
    iconColor: string;
    bg: string;
    border: string;
  }[] = [
    {
      title: "Total Actions (7d)", value: stats.total_actions_week,
      icon: TrendingUp, iconColor: "text-indigo-600 dark:text-indigo-400",
      bg: "bg-indigo-50/60 dark:bg-indigo-950/10",
      border: "border-indigo-200/60 dark:border-indigo-900/40",
    },
    {
      title: "Approved", value: stats.approved,
      icon: CheckCircle2, iconColor: "text-green-600 dark:text-green-400",
      bg: "bg-green-50/60 dark:bg-green-950/10",
      border: "border-green-200/60 dark:border-green-900/40",
    },
    {
      title: "Rejected", value: stats.rejected,
      icon: XCircle, iconColor: "text-red-600 dark:text-red-400",
      bg: "bg-red-50/60 dark:bg-red-950/10",
      border: "border-red-200/60 dark:border-red-900/40",
    },
    {
      title: "Blocked", value: stats.blocked,
      icon: ShieldOff, iconColor: "text-orange-600 dark:text-orange-400",
      bg: "bg-orange-50/60 dark:bg-orange-950/10",
      border: "border-orange-200/60 dark:border-orange-900/40",
    },
    {
      title: "Timed Out", value: stats.timed_out,
      icon: Clock, iconColor: "text-yellow-600 dark:text-yellow-400",
      bg: "bg-yellow-50/60 dark:bg-yellow-950/10",
      border: "border-yellow-200/60 dark:border-yellow-900/40",
    },
    {
      title: "Pre-Approvals", value: stats.active_pre_approvals,
      icon: KeyRound, iconColor: "text-blue-600 dark:text-blue-400",
      bg: "bg-blue-50/60 dark:bg-blue-950/10",
      border: "border-blue-200/60 dark:border-blue-900/40",
    },
    {
      title: "Delegations", value: stats.active_delegations,
      icon: Users, iconColor: "text-purple-600 dark:text-purple-400",
      bg: "bg-purple-50/60 dark:bg-purple-950/10",
      border: "border-purple-200/60 dark:border-purple-900/40",
    },
    {
      title: "Scope Creep", value: stats.scope_creep_alerts,
      icon: AlertTriangle, iconColor: "text-rose-600 dark:text-rose-400",
      bg: "bg-rose-50/60 dark:bg-rose-950/10",
      border: "border-rose-200/60 dark:border-rose-900/40",
    },
  ];

  const securityChecks: { label: string; ok: boolean; detail?: string }[] = [
    { label: "HMAC Request Signing", ok: security?.hmac.ok ?? true, detail: security?.hmac.detail },
    { label: "Pydantic Validation", ok: true, detail: "Always enforced" },
    { label: "FGA Access Control", ok: security?.fga.ok ?? false, detail: security?.fga.detail },
    { label: "Scope Creep Detection", ok: stats.scope_creep_alerts === 0, detail: stats.scope_creep_alerts > 0 ? `${stats.scope_creep_alerts} alerts` : "Clear" },
    { label: "Auth0 Token Vault", ok: security?.token_vault.ok ?? false, detail: security?.token_vault.detail },
    { label: "Credentials Isolation", ok: security?.credentials_key.ok ?? false, detail: security?.credentials_key.detail },
    { label: "Sentry Error Tracking", ok: security?.sentry.ok ?? false, detail: security?.sentry.detail },
  ];

  const cibaColor = cibaPercent >= 80 ? "red" : cibaPercent >= 50 ? "yellow" : "green";
  const cibaBarClass = {
    red: "bg-red-500",
    yellow: "bg-yellow-500",
    green: "bg-green-500",
  }[cibaColor];
  const cibaTrackGlow = {
    red: "shadow-[inset_0_0_6px_rgba(239,68,68,0.15)]",
    yellow: "shadow-[inset_0_0_6px_rgba(234,179,8,0.15)]",
    green: "shadow-[inset_0_0_6px_rgba(34,197,94,0.15)]",
  }[cibaColor];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 dark:from-indigo-400 dark:via-purple-400 dark:to-blue-400">
          Permission Dashboard
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1.5 text-sm">
          Workspace overview — access controlled by FGA role
        </p>
      </div>

      {/* Section: Stats */}
      <section>
        <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-3">
          Activity Summary
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {statCards.map((stat) => (
            <div
              key={stat.title}
              className={`rounded-xl border ${stat.border} ${stat.bg} p-4 transition-colors`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  {stat.title}
                </span>
                <stat.icon className={`h-4 w-4 ${stat.iconColor} opacity-70`} />
              </div>
              <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tabular-nums">
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Empty state CTA */}
      {hasNoData && (
        <div className="rounded-xl border-2 border-dashed border-purple-300 dark:border-purple-700 bg-purple-50/30 dark:bg-purple-950/10 p-6 flex items-center gap-5">
          <div className="p-3 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-500 text-white shrink-0">
            <Zap className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">No activity yet</h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Run the AI Orchestrator demo to see real-time approval decisions, rule matches, and Token Vault execution here.
            </p>
          </div>
          <button
            onClick={() => router.push("/demos/live?chain=orchestrator")}
            className="shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-700 hover:to-blue-600 text-white text-sm font-semibold shadow-lg shadow-purple-500/20 transition-all"
          >
            Run Demo
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Learned Patterns */}
      {patterns.length > 0 && (
        <section className="mb-6">
          <Card className="border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Gauge className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                Learned Patterns
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">{patterns.length}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {patterns.map((p: any, i: number) => (
                <div key={i} className={`flex items-start gap-2.5 text-xs rounded-lg px-3 py-2 ${
                  p.severity === "warning"
                    ? "bg-amber-50 dark:bg-amber-950/15 text-amber-800 dark:text-amber-300 border border-amber-200/60 dark:border-amber-800/40"
                    : "bg-blue-50 dark:bg-blue-950/15 text-blue-800 dark:text-blue-300 border border-blue-200/60 dark:border-blue-800/40"
                }`}>
                  {p.severity === "warning"
                    ? <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    : <TrendingUp className="h-3.5 w-3.5 shrink-0 mt-0.5" />}
                  <span>{p.message}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      )}

      {/* Pending Approvals with Time-Boxed Countdown */}
      {pendingJobs.length > 0 && (
        <section>
          <Card className="border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock className="h-4 w-4 text-amber-500" />
                  Pending Approvals
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400">{pendingJobs.length}</span>
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {pendingJobs.map((job: any) => {
                  const expiresAt = job.expires_at ? new Date(job.expires_at).getTime() : null;
                  const remainingSec = expiresAt ? Math.max(0, Math.floor((expiresAt - now) / 1000)) : null;
                  const isExpired = remainingSec !== null && remainingSec <= 0;
                  const isUrgent = remainingSec !== null && remainingSec > 0 && remainingSec < 120;
                  const riskColor = job.risk_level === "critical" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    : job.risk_level === "high" ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                    : job.risk_level === "medium" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                    : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
                  const formatTime = (s: number) => {
                    const m = Math.floor(s / 60);
                    const sec = s % 60;
                    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
                  };
                  return (
                    <div
                      key={job.job_id}
                      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 border transition-colors ${
                        isExpired ? "border-red-300 dark:border-red-800 bg-red-50/50 dark:bg-red-950/10"
                        : isUrgent ? "border-amber-300 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/10 animate-pulse"
                        : "border-zinc-200/60 dark:border-zinc-800/60 hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                          <code className="bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5 text-[11px]">
                            {job.connection}:{job.action}
                          </code>
                        </p>
                        {job.binding_message && (
                          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5 truncate">{job.binding_message}</p>
                        )}
                      </div>
                      {/* Risk Score Badge */}
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${riskColor}`}>
                        Risk {job.risk_score}
                      </span>
                      {/* Countdown Timer */}
                      {remainingSec !== null && (
                        <span className={`text-[11px] font-mono tabular-nums min-w-[60px] text-right ${
                          isExpired ? "text-red-500 font-bold" : isUrgent ? "text-amber-600 dark:text-amber-400 font-bold" : "text-zinc-500 dark:text-zinc-400"
                        }`}>
                          {isExpired ? "Expired" : formatTime(remainingSec)}
                        </span>
                      )}
                      <Badge variant={job.state === "ciba_sent" ? "info" : "default"} className="text-[10px]">
                        {job.state.replace(/_/g, " ")}
                      </Badge>
                      {/* Quick actions */}
                      <div className="flex items-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            api.generateApprovalLink(job.job_id).then((res: any) => {
                              navigator.clipboard.writeText(res.approve_url);
                              setCopiedLink(job.job_id);
                              setTimeout(() => setCopiedLink(null), 2000);
                            }).catch(() => {});
                          }}
                          title="Copy email approval link"
                          className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                        >
                          {copiedLink === job.job_id ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                          ) : (
                            <Mail className="h-3.5 w-3.5 text-zinc-400" />
                          )}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            api.approveJob(job.job_id).then(() => {
                              setPendingJobs(prev => prev.filter(j => j.job_id !== job.job_id));
                              loadStats();
                            }).catch(() => {});
                          }}
                          title="Quick approve"
                          className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            api.rejectJob(job.job_id).then(() => {
                              setPendingJobs(prev => prev.filter(j => j.job_id !== job.job_id));
                              loadStats();
                            }).catch(() => {});
                          }}
                          title="Quick reject"
                          className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                        >
                          <XCircle className="h-3.5 w-3.5 text-red-400" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      {/* Bottom panels */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

        {/* Live Activity Feed */}
        <section className="lg:col-span-4">
          <Card className="w-full border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2.5 text-base">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
                  </span>
                  Live Activity
                </CardTitle>
                <span className="text-[10px] font-medium uppercase tracking-widest text-zinc-400 dark:text-zinc-500">
                  Stream
                </span>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-1 max-h-[340px] overflow-y-auto pr-1">
                {events.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-zinc-400 dark:text-zinc-500">
                    <Radio className="h-6 w-6 mb-2 opacity-40" />
                    <p className="text-sm">Waiting for events...</p>
                  </div>
                ) : (
                  events.map((ev, i) => {
                    const badge = EVENT_BADGE[ev.type] ?? { variant: "default" as const };
                    const dot = EVENT_DOT[ev.type] ?? "bg-zinc-400";
                    return (
                      <div
                        key={`${ev.job_id}-${i}`}
                        className="group flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                      >
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate">
                            {ev.connection}<span className="text-zinc-400 dark:text-zinc-500 mx-1">:</span>{ev.action}
                          </p>
                          {ev.exec_note && (
                            <p className="text-[10px] text-zinc-400 dark:text-zinc-500 truncate mt-0.5">
                              {ev.exec_note}
                            </p>
                          )}
                        </div>
                        <Badge variant={badge.variant} className="text-[10px] flex-shrink-0">
                          {ev.type.replace(/_/g, " ")}
                        </Badge>
                        <span className="text-[10px] tabular-nums text-zinc-400 dark:text-zinc-500 flex-shrink-0 w-16 text-right">
                          {new Date(ev.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Security Status */}
        <section className="lg:col-span-2">
          <Card className="w-full border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldCheck className="h-4 w-4 text-green-500" />
                  Security Status
                </CardTitle>
                <Badge
                  variant={securityChecks.every((c) => c.ok) ? "success" : "warning"}
                >
                  {securityChecks.filter((c) => c.ok).length}/{securityChecks.length} Active
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-0.5">
                {securityChecks.map((check) => (
                  <div
                    key={check.label}
                    className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  >
                    {check.ok ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-zinc-700 dark:text-zinc-300">{check.label}</p>
                      {check.detail && (
                        <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5 truncate">
                          {check.detail}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>

        {/* Risk Distribution */}
        <section className="lg:col-span-3">
          <Card className="w-full border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-4 w-4 text-rose-500" />
                  Risk Distribution
                </CardTitle>
                {riskDist && (
                  <span className="text-[10px] font-medium text-zinc-400 dark:text-zinc-500">
                    avg {riskDist.avg_score}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              {riskDist && riskDist.total > 0 ? (
                <div className="space-y-3">
                  {(["low", "medium", "high", "critical"] as const).map((level) => {
                    const count = riskDist.distribution[level] || 0;
                    const pct = riskDist.total > 0 ? Math.round((count / riskDist.total) * 100) : 0;
                    const barColor = level === "critical" ? "bg-red-500" : level === "high" ? "bg-orange-500" : level === "medium" ? "bg-yellow-500" : "bg-green-500";
                    const labelColor = level === "critical" ? "text-red-600 dark:text-red-400" : level === "high" ? "text-orange-600 dark:text-orange-400" : level === "medium" ? "text-yellow-600 dark:text-yellow-400" : "text-green-600 dark:text-green-400";
                    return (
                      <div key={level}>
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-[11px] font-semibold capitalize ${labelColor}`}>{level}</span>
                          <span className="text-[10px] text-zinc-400 tabular-nums">{count} ({pct}%)</span>
                        </div>
                        <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-1.5">
                          <div className={`h-1.5 rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                  {/* Top risky connections */}
                  {Object.entries(riskDist.by_connection || {})
                    .sort((a: any, b: any) => b[1].avg_risk - a[1].avg_risk)
                    .slice(0, 3)
                    .map(([conn, data]: any) => (
                      <div key={conn} className="flex items-center justify-between text-[10px] text-zinc-500 dark:text-zinc-400 pt-1">
                        <span className="truncate">{conn}</span>
                        <span className="tabular-nums">avg {data.avg_risk} / max {data.max_risk}</span>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-zinc-400 dark:text-zinc-500">
                  <BarChart3 className="h-6 w-6 mb-2 opacity-40" />
                  <p className="text-xs">No risk data yet</p>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* CIBA Quota */}
        <section className="lg:col-span-3">
          <Card className="w-full border-zinc-200/80 dark:border-zinc-800/80">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Gauge className="h-4 w-4 text-indigo-500" />
                  CIBA Quota
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="flex flex-col items-center">
                {/* Circular-ish visual */}
                <div className="relative w-28 h-28 mb-4">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                    <circle
                      cx="50" cy="50" r="42"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="8"
                      className="text-zinc-100 dark:text-zinc-800"
                    />
                    <circle
                      cx="50" cy="50" r="42"
                      fill="none"
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeDasharray={`${Math.min(cibaPercent, 100) * 2.64} 264`}
                      className={
                        cibaPercent >= 80
                          ? "text-red-500"
                          : cibaPercent >= 50
                            ? "text-yellow-500"
                            : "text-green-500"
                      }
                      stroke="currentColor"
                      style={{ transition: "stroke-dasharray 0.6s ease" }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 tabular-nums">
                      {cibaPercent}%
                    </span>
                  </div>
                </div>

                {/* Linear bar below */}
                <div className="w-full space-y-2">
                  <div className="flex justify-between text-xs text-zinc-500 dark:text-zinc-400">
                    <span>{stats.ciba_usage} used</span>
                    <span>{stats.ciba_limit} limit</span>
                  </div>
                  <div className={`w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 ${cibaTrackGlow}`}>
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${cibaBarClass}`}
                      style={{ width: `${Math.min(cibaPercent, 100)}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-zinc-400 dark:text-zinc-500 text-center mt-2">
                    Auth0 allows {stats.ciba_limit} CIBA requests/hour per tenant. Warning at 80%.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

      </div>
    </div>
  );
}
