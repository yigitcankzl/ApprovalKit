"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  ClipboardCheck,
  Download,
  Clock,
  CheckCircle,
  XCircle,
  ShieldAlert,
  TrendingUp,
  BarChart3,
  FileText,
  AlertTriangle,
} from "lucide-react";

interface ComplianceStats {
  period_days: number;
  total_jobs: number;
  by_state: Record<string, number>;
  by_connection: Record<string, number>;
  avg_approval_seconds: number | null;
  approval_rate: number;
  daily_trend: Record<string, Record<string, number>>;
}

const STATE_COLORS: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  blocked: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  timeout: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  pre_approved: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  pending: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-400",
  ciba_sent: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  waiting_approval: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
};

const STATE_ICONS: Record<string, React.ReactNode> = {
  approved: <CheckCircle className="h-4 w-4" />,
  rejected: <XCircle className="h-4 w-4" />,
  blocked: <ShieldAlert className="h-4 w-4" />,
  timeout: <Clock className="h-4 w-4" />,
};

export default function CompliancePage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [stats, setStats] = useState<ComplianceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (authLoading || !user) return;
    setLoading(true);
    api.getComplianceStats(days)
      .then((result: ComplianceStats) => setStats(result))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [authLoading, user, days]);

  const handleExport = async (format: string) => {
    setExporting(true);
    try {
      if (format === "csv") {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        window.open(`${apiBase}/api/v1/audit/export?format=csv&days=${days}`, "_blank");
      } else {
        const data = await api.exportCompliance({ format: "json", days });
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `approvalkit-compliance-${days}d.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      // silently fail
    } finally {
      setExporting(false);
    }
  };

  if (authLoading || !user || loading) {
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

  if (!stats) return null;

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "N/A";
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const sortedConnections = Object.entries(stats.by_connection).sort((a, b) => b[1] - a[1]);
  const sortedStates = Object.entries(stats.by_state).sort((a, b) => b[1] - a[1]);

  // Daily trend for simple sparkline
  const trendDays = Object.keys(stats.daily_trend).sort();
  const maxDaily = Math.max(
    ...trendDays.map((d) =>
      Object.values(stats.daily_trend[d]).reduce((a, b) => a + b, 0)
    ),
    1
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-3">
            <ClipboardCheck className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
            Compliance Report
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1.5 text-sm">
            Complete audit trail with timeline visualization. Export for SOC2/HIPAA compliance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period Selector */}
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 text-sm rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
          {/* Export Buttons */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport("json")}
            disabled={exporting}
          >
            <Download className="h-3.5 w-3.5 mr-1.5" />
            JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport("csv")}
            disabled={exporting}
          >
            <FileText className="h-3.5 w-3.5 mr-1.5" />
            CSV
          </Button>
        </div>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                <BarChart3 className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{stats.total_jobs}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Total Actions ({days}d)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30">
                <TrendingUp className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{stats.approval_rate}%</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Approval Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/30">
                <Clock className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  {formatDuration(stats.avg_approval_seconds)}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Avg Approval Time</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30">
                <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                  {(stats.by_state["blocked"] || 0) + (stats.by_state["rejected"] || 0)}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Blocked + Rejected</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Daily Trend (Simple Bar Chart) */}
      {trendDays.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Daily Activity Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-[2px] h-40">
              {trendDays.map((day) => {
                const dayData = stats.daily_trend[day];
                const total = Object.values(dayData).reduce((a, b) => a + b, 0);
                const approved = dayData["approved"] || 0;
                const rejected = (dayData["rejected"] || 0) + (dayData["blocked"] || 0);
                const other = total - approved - rejected;
                const barH = Math.max((total / maxDaily) * 128, 3);

                return (
                  <div key={day} className="flex-1 flex flex-col items-center justify-end h-full" title={`${day}: ${total} actions`}>
                    <div className="w-full flex flex-col-reverse rounded-t overflow-hidden" style={{ height: `${barH}px` }}>
                      {approved > 0 && (
                        <div
                          className="w-full bg-emerald-500 dark:bg-emerald-400"
                          style={{ height: `${(approved / total) * 100}%`, minHeight: "2px" }}
                        />
                      )}
                      {other > 0 && (
                        <div
                          className="w-full bg-blue-500 dark:bg-blue-400"
                          style={{ height: `${(other / total) * 100}%`, minHeight: "2px" }}
                        />
                      )}
                      {rejected > 0 && (
                        <div
                          className="w-full bg-red-500 dark:bg-red-400"
                          style={{ height: `${(rejected / total) * 100}%`, minHeight: "2px" }}
                        />
                      )}
                    </div>
                    <span className="text-[8px] text-zinc-400 mt-1.5 truncate w-full text-center">
                      {day.slice(8)}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-4 text-xs text-zinc-500">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm bg-emerald-400" />
                Approved
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm bg-blue-400" />
                Other
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm bg-red-400" />
                Rejected/Blocked
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* State Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Decision Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {sortedStates.length === 0 ? (
              <p className="text-sm text-zinc-400">No data</p>
            ) : (
              <div className="space-y-3">
                {sortedStates.map(([state, count]) => {
                  const percent = stats.total_jobs > 0 ? (count / stats.total_jobs) * 100 : 0;
                  return (
                    <div key={state}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATE_COLORS[state] || "bg-zinc-100 text-zinc-600"}`}>
                            {STATE_ICONS[state]}
                            {state}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                          {count} ({percent.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            state === "approved"
                              ? "bg-emerald-500"
                              : state === "rejected" || state === "blocked"
                              ? "bg-red-500"
                              : state === "timeout"
                              ? "bg-amber-500"
                              : "bg-blue-500"
                          }`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Connection Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Service Connection</CardTitle>
          </CardHeader>
          <CardContent>
            {sortedConnections.length === 0 ? (
              <p className="text-sm text-zinc-400">No data</p>
            ) : (
              <div className="space-y-3">
                {sortedConnections.map(([conn, count]) => {
                  const percent = stats.total_jobs > 0 ? (count / stats.total_jobs) * 100 : 0;
                  return (
                    <div key={conn}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{conn}</span>
                        <span className="text-sm text-zinc-500">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-indigo-500 transition-all"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Compliance Info */}
      <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800/50 px-5 py-4">
        <div className="flex items-start gap-3">
          <ClipboardCheck className="h-5 w-5 text-zinc-500 mt-0.5 shrink-0" />
          <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Complete chain of custody:</strong>{" "}
              Every action is tracked from agent request through rule evaluation, CIBA notification,
              human decision, Token Vault execution, and final result.
            </p>
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Auth0 Log Streams integration:</strong>{" "}
              When configured, Auth0 authentication events are correlated with ApprovalKit actions
              for a complete compliance picture across both systems.
            </p>
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Export formats:</strong>{" "}
              JSON (full detail with timelines) and CSV (tabular summary) for SOC2, HIPAA, and internal audits.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
