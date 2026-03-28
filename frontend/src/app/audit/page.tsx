"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/types";

const eventBadge: Record<string, "success" | "danger" | "warning" | "info" | "default"> = {
  approved: "success",
  pre_approved: "success",
  rejected: "danger",
  blocked: "danger",
  timeout: "warning",
  escalated: "warning",
  scope_creep: "danger",
  step_up: "warning",
  requested: "info",
  ciba_sent: "info",
  partial_approved: "success",
  revoked: "danger",
};

const eventColors: Record<string, string> = {
  approved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
  pre_approved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
  partial_approved: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
  rejected: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
  blocked: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
  scope_creep: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
  revoked: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
  timeout: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
  escalated: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
  step_up: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20",
  requested: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20",
  ciba_sent: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20",
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getAuditLog({ event_type: filter || undefined })
      .then(setLogs)
      .catch((err) => setError(err.message || "Failed to load audit log"))
      .finally(() => setLoading(false));
  }, [filter]);

  const filteredLogs = filter ? logs.filter((l) => l.event_type === filter) : logs;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-12">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
            Consent History & Audit Log
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-2">
            FGA-controlled -- approvers see own history only, admins see everything
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">
            Filter by event
          </span>
          <Select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-52 rounded-lg border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 shadow-sm text-sm font-medium"
          >
            <option value="">All events</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="blocked">Blocked</option>
            <option value="escalated">Escalated</option>
            <option value="timeout">Timed Out</option>
            <option value="scope_creep">Scope Creep</option>
            <option value="pre_approved">Pre-approved</option>
            <option value="partial_approved">Partial</option>
            <option value="step_up">Step-up</option>
          </Select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64">
          <p className="text-red-500">{error}</p>
        </div>
      ) : (
        <Card className="overflow-hidden border-zinc-200 dark:border-zinc-700/60 shadow-sm">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50/80 dark:bg-zinc-800/60">
                    <th className="text-left px-5 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Time</span>
                    </th>
                    <th className="text-left px-5 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Action</span>
                    </th>
                    <th className="text-left px-5 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Approver</span>
                    </th>
                    <th className="text-left px-5 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Decision</span>
                    </th>
                    <th className="text-left px-5 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Notes</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {filteredLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-16 text-center text-zinc-400 text-sm">
                        No audit entries yet
                      </td>
                    </tr>
                  ) : (
                    filteredLogs.map((log) => (
                      <tr
                        key={log.id}
                        className="transition-colors duration-150 hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40"
                      >
                        <td className="px-5 py-4 text-zinc-500 dark:text-zinc-400 text-xs whitespace-nowrap tabular-nums">
                          {new Date(log.created_at).toLocaleString([], {
                            month: "short", day: "numeric",
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </td>
                        <td className="px-5 py-4">
                          <code className="bg-zinc-800 dark:bg-zinc-900 text-zinc-100 px-2.5 py-1 rounded-md text-xs font-mono">
                            {log.connection}:{log.action}
                          </code>
                        </td>
                        <td className="px-5 py-4 text-zinc-600 dark:text-zinc-300 text-sm">
                          {log.approver_name || "\u2014"}
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${eventColors[log.event_type] || "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20"}`}
                          >
                            {log.event_type.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-xs max-w-sm">
                          {log.event_type === "ciba_sent" && log.binding_message && (
                            <span className="inline-flex items-center gap-1 bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-800 px-2.5 py-1 rounded-md font-mono text-xs">
                              Binding: {log.binding_message}
                            </span>
                          )}
                          {log.event_type === "approved" && log.note?.startsWith("executed:") && (
                            <span className="inline-flex items-center gap-1 bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800 px-2.5 py-1 rounded-md text-xs font-medium">
                              Auth0 Token Vault
                            </span>
                          )}
                          {log.note && !log.note.startsWith("executed:") && (
                            <span className="text-zinc-500 dark:text-zinc-400">{log.note}</span>
                          )}
                          {!log.event_type.includes("ciba") && !log.note && "\u2014"}
                          {log.modified_params && (
                            <span className="ml-2 text-orange-600 dark:text-orange-400 font-medium">Modified params</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
