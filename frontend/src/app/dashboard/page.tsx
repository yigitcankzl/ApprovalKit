"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";
import {
  CheckCircle2, XCircle, ShieldOff, Clock, KeyRound, Users,
  Activity, AlertTriangle, Radio,
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
interface PendingJob {
  job_id: string; connection: string; action: string; params: any;
  state: string; created_at: string; binding_message?: string;
}

const EVENT_COLORS: Record<string, string> = {
  requested: "bg-blue-500",
  approved:  "bg-green-500",
  rejected:  "bg-red-500",
  blocked:   "bg-orange-500",
  timeout:   "bg-yellow-500",
  ciba_sent: "bg-purple-500",
};

export default function DashboardPage() {
  const [stats, setStats]       = useState<DashboardStats & { pending_count?: number } | null>(null);
  const [security, setSecurity] = useState<SecurityStatus | null>(null);
  const [events, setEvents]     = useState<LiveEvent[]>([]);
  const [pending, setPending]   = useState<PendingJob[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const eventsRef = useRef<HTMLDivElement>(null);

  const loadStats = () =>
    Promise.all([api.getDashboard(), api.getSecurityStatus().catch(() => null)])
      .then(([s, sec]) => { setStats(s); setSecurity(sec); });

  const loadPending = () =>
    api.getPendingJobs().then(setPending).catch(() => {});

  useEffect(() => {
    Promise.all([loadStats(), loadPending()])
      .catch((err) => setError(err.message || "Failed to load"))
      .finally(() => setLoading(false));

    // Auto-refresh every 30s
    const refreshInterval = setInterval(() => { loadStats(); loadPending(); }, 30000);

    // SSE subscription
    const es = new EventSource(`${API_BASE}/api/v1/events`);
    es.onmessage = (e) => {
      try {
        const data: LiveEvent = JSON.parse(e.data);
        setEvents((prev) => [data, ...prev].slice(0, 20));
        if (["approved", "rejected", "blocked"].includes(data.type)) {
          loadPending();
          loadStats();
        }
      } catch {}
    };

    return () => { es.close(); clearInterval(refreshInterval); };
  }, []);


  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
    </div>
  );
  if (error) return <div className="flex items-center justify-center h-64"><p className="text-red-500">{error}</p></div>;
  if (!stats) return null;

  const cibaPercent = Math.round((stats.ciba_usage / stats.ciba_limit) * 100);
  const pendingCount = stats.pending_count ?? pending.length;

  const statCards = [
    { title: "Total Actions (7d)", value: stats.total_actions_week, icon: Activity,       color: "text-zinc-600" },
    { title: "Approved",           value: stats.approved,           icon: CheckCircle2,   color: "text-green-600" },
    { title: "Rejected",           value: stats.rejected,           icon: XCircle,        color: "text-red-600" },
    { title: "Blocked",            value: stats.blocked,            icon: ShieldOff,      color: "text-orange-600" },
    { title: "Timed Out",          value: stats.timed_out,          icon: Clock,          color: "text-yellow-600" },
    { title: "Pre-Approvals",      value: stats.active_pre_approvals, icon: KeyRound,     color: "text-blue-600" },
    { title: "Delegations",        value: stats.active_delegations, icon: Users,          color: "text-purple-600" },
    { title: "Scope Creep",        value: stats.scope_creep_alerts, icon: AlertTriangle,  color: "text-red-600" },
  ];

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Permission Dashboard</h1>
          <p className="text-zinc-500 mt-1">Workspace overview — access controlled by FGA role</p>
        </div>
        {pendingCount > 0 && (
          <span className="inline-flex items-center gap-1.5 bg-red-500 text-white text-sm font-semibold px-3 py-1.5 rounded-full animate-pulse">
            <Clock className="h-4 w-4" /> {pendingCount} pending
          </span>
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-500">{stat.title}</p>
                  <p className="text-3xl font-bold text-zinc-900 mt-1">{stat.value}</p>
                </div>
                <stat.icon className={`h-8 w-8 ${stat.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pending Approvals */}
      {pending.length > 0 && (
        <Card className="mb-6 border-orange-200 bg-orange-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-orange-800">
              <Clock className="h-5 w-5" /> Pending Approvals ({pending.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {pending.map((job) => (
              <div key={job.job_id} className="bg-white rounded-lg border border-orange-200 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="text-sm font-semibold text-zinc-900">{job.connection}:{job.action}</code>
                      <Badge variant="warning">{job.state}</Badge>
                    </div>
                    {job.binding_message && (
                      <p className="text-xs text-purple-700 font-mono bg-purple-50 px-2 py-1 rounded inline-block mb-2">
                        Binding: {job.binding_message}
                      </p>
                    )}
                    <pre className="text-xs text-zinc-500 bg-zinc-50 px-2 py-1.5 rounded overflow-x-auto">
                      {JSON.stringify(job.params, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* CIBA + Security + Live Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader><CardTitle>CIBA Quota Usage</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">{stats.ciba_usage} / {stats.ciba_limit} requests/hour</span>
                <Badge variant={cibaPercent >= 80 ? "danger" : cibaPercent >= 50 ? "warning" : "success"}>{cibaPercent}%</Badge>
              </div>
              <div className="w-full bg-zinc-100 rounded-full h-3">
                <div className={`h-3 rounded-full transition-all ${cibaPercent >= 80 ? "bg-red-500" : cibaPercent >= 50 ? "bg-yellow-500" : "bg-green-500"}`}
                  style={{ width: `${Math.min(cibaPercent, 100)}%` }} />
              </div>
              <p className="text-xs text-zinc-400">Auth0 allows 500 CIBA requests/hour per tenant. Warning at 80%.</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Security Status</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              <SecurityRow label="HMAC Request Signing" ok={security?.hmac.ok ?? true} detail={security?.hmac.detail} />
              <SecurityRow label="Pydantic Validation" ok={true} detail="Always enforced" />
              <SecurityRow label="FGA Access Control" ok={security?.fga.ok ?? false} detail={security?.fga.detail} />
              <div className="flex items-start justify-between py-2 border-b border-zinc-100">
                <span className="text-sm text-zinc-600">Scope Creep Detection</span>
                <Badge variant={stats.scope_creep_alerts > 0 ? "warning" : "success"}>
                  {stats.scope_creep_alerts > 0 ? `${stats.scope_creep_alerts} alerts` : "Clear"}
                </Badge>
              </div>
              <SecurityRow label="Auth0 Token Vault" ok={security?.token_vault.ok ?? false} detail={security?.token_vault.detail} isLast />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-green-500 animate-pulse" /> Live Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div ref={eventsRef} className="space-y-2 max-h-64 overflow-y-auto">
              {events.length === 0 ? (
                <p className="text-sm text-zinc-400 text-center py-8">Waiting for events…</p>
              ) : (
                events.map((ev, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${EVENT_COLORS[ev.type] ?? "bg-zinc-400"}`} />
                    <span className="text-zinc-500 font-mono">{ev.connection}:{ev.action}</span>
                    <Badge variant={ev.type === "approved" ? "success" : ev.type === "rejected" ? "danger" : "default"} className="text-xs">
                      {ev.type}
                    </Badge>
                    <span className="text-zinc-300 ml-auto">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}

function SecurityRow({ label, ok, detail, isLast = false }: { label: string; ok: boolean; detail?: string; isLast?: boolean }) {
  return (
    <div className={`flex items-start justify-between py-2 ${isLast ? "" : "border-b border-zinc-100"}`}>
      <div>
        <span className="text-sm text-zinc-600">{label}</span>
        {detail && <p className="text-xs text-zinc-400 mt-0.5">{detail}</p>}
      </div>
      <Badge variant={ok ? "success" : "danger"} className="ml-4 flex-shrink-0">{ok ? "Active" : "Inactive"}</Badge>
    </div>
  );
}
