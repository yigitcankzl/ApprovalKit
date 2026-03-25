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

const EVENT_COLORS: Record<string, string> = {
  requested: "bg-blue-500",
  approved:  "bg-green-500",
  rejected:  "bg-red-500",
  blocked:   "bg-orange-500",
  timeout:   "bg-yellow-500",
  ciba_sent: "bg-purple-500",
  step_up_triggered: "bg-yellow-500",
  step_up: "bg-yellow-500",
  pre_approved: "bg-emerald-500",
  partial_approved: "bg-teal-500",
  escalated: "bg-orange-600",
};

export default function DashboardPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [stats, setStats]       = useState<DashboardStats | null>(null);
  const [security, setSecurity] = useState<SecurityStatus | null>(null);
  const [events, setEvents]     = useState<LiveEvent[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/auth/login?returnTo=/dashboard");
    }
  }, [authLoading, user]);

  const loadStats = () =>
    Promise.all([api.getDashboard(), api.getSecurityStatus().catch(() => null)])
      .then(([s, sec]) => { setStats(s); setSecurity(sec); });

  useEffect(() => {
    Promise.all([
      loadStats(),
      api.getRecentActivity(20)
        .then((rows: LiveEvent[]) => setEvents(Array.isArray(rows) ? rows : []))
        .catch(() => {}),
    ])
      .catch((err) => setError(err.message || "Failed to load"))
      .finally(() => setLoading(false));

    // Auto-refresh stats only — do not replace Live Activity (SSE + initial hydrate)
    const refreshInterval = setInterval(() => { loadStats(); }, 30000);

    // SSE subscription
    const es = new EventSource(`${API_BASE}/api/v1/events`);
    es.onmessage = (e) => {
      try {
        const data: LiveEvent = JSON.parse(e.data);
        setEvents((prev) => [data, ...prev].slice(0, 20));
        if (["approved", "rejected", "blocked", "requested", "ciba_sent"].includes(data.type)) {
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
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Permission Dashboard</h1>
        <p className="text-zinc-500 mt-1">Workspace overview — access controlled by FGA role</p>
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

      {/* CIBA + Security + Live Feed — items-start so short cards are not stretched to tallest column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <Card className="w-full">
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

        <Card className="w-full">
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
              <SecurityRow label="Auth0 Token Vault" ok={security?.token_vault.ok ?? false} detail={security?.token_vault.detail} />
              <SecurityRow
                label="Credentials Key Isolation"
                ok={security?.credentials_key.ok ?? false}
                detail={security?.credentials_key.detail}
              />
              <SecurityRow
                label="Sentry Error Tracking"
                ok={security?.sentry.ok ?? false}
                detail={security?.sentry.detail}
                isLast
              />
            </div>
          </CardContent>
        </Card>

        <Card className="w-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Radio className="h-4 w-4 text-green-500 animate-pulse" /> Live Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-64 overflow-y-auto">
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
