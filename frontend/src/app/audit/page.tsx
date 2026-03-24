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
  requested: "info",
  ciba_sent: "info",
  partial_approved: "success",
  revoked: "danger",
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
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Consent History & Audit Log</h1>
          <p className="text-zinc-500 mt-1">
            FGA-controlled — approvers see own history only, admins see everything
          </p>
        </div>
        <Select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-48">
          <option value="">All events</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="blocked">Blocked</option>
          <option value="escalated">Escalated</option>
          <option value="timeout">Timed Out</option>
          <option value="scope_creep">Scope Creep</option>
          <option value="pre_approved">Pre-approved</option>
          <option value="partial_approved">Partial</option>
        </Select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64">
          <p className="text-red-500">{error}</p>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-50">
                    <th className="text-left p-4 font-medium text-zinc-500">Time</th>
                    <th className="text-left p-4 font-medium text-zinc-500">Action</th>
                    <th className="text-left p-4 font-medium text-zinc-500">Approver</th>
                    <th className="text-left p-4 font-medium text-zinc-500">Decision</th>
                    <th className="text-left p-4 font-medium text-zinc-500">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-zinc-400">
                        No audit entries yet
                      </td>
                    </tr>
                  ) : (
                    filteredLogs.map((log) => (
                      <tr key={log.id} className="border-b border-zinc-100 hover:bg-zinc-50">
                        <td className="p-4 text-zinc-600 text-xs whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString([], {
                            month: "short", day: "numeric",
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </td>
                        <td className="p-4">
                          <code className="bg-zinc-800 text-zinc-100 px-2 py-0.5 rounded text-xs font-mono">
                            {log.connection}:{log.action}
                          </code>
                        </td>
                        <td className="p-4 text-zinc-600">
                          {log.approver_name || "—"}
                        </td>
                        <td className="p-4">
                          <Badge variant={eventBadge[log.event_type] || "default"}>
                            {log.event_type.replace(/_/g, " ")}
                          </Badge>
                        </td>
                        <td className="p-4 text-zinc-500 text-xs max-w-xs truncate">
                          {log.note || log.binding_message || "—"}
                          {log.modified_params && (
                            <span className="ml-2 text-orange-600">Modified params</span>
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
