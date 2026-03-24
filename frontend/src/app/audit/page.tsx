"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/types";

const PAGE_SIZE = 15;

const eventBadge: Record<string, "success" | "danger" | "warning" | "info" | "default"> = {
  approved: "success",
  pre_approved: "success",
  partial_approved: "success",
  rejected: "danger",
  blocked: "danger",
  scope_creep: "danger",
  revoked: "danger",
  timeout: "warning",
  escalated: "warning",
  requested: "info",
  ciba_sent: "info",
};

function formatDate(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const isToday =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();
  if (isToday) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" }) +
    " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Group sequential events belonging to the same job
function groupByJob(logs: AuditEntry[]): { primary: AuditEntry; events: AuditEntry[] }[] {
  const map = new Map<string, AuditEntry[]>();
  for (const log of logs) {
    const key = log.job_id ?? log.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(log);
  }
  return Array.from(map.values()).map((events) => ({
    primary: events[events.length - 1], // latest event = current state
    events,
  }));
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(0);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setPage(0);
    api
      .getAuditLog({ event_type: filter || undefined, limit: 200 })
      .then(setLogs)
      .catch((err) => setError(err.message || "Failed to load audit log"))
      .finally(() => setLoading(false));
  }, [filter]);

  const grouped = groupByJob(logs);
  const totalPages = Math.ceil(grouped.length / PAGE_SIZE);
  const pageItems = grouped.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

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
        <>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-200 bg-zinc-50">
                      <th className="text-left p-4 font-medium text-zinc-500 w-36">Time</th>
                      <th className="text-left p-4 font-medium text-zinc-500">Action</th>
                      <th className="text-left p-4 font-medium text-zinc-500">Approver</th>
                      <th className="text-left p-4 font-medium text-zinc-500">Decision</th>
                      <th className="text-left p-4 font-medium text-zinc-500">Notes</th>
                      <th className="w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="p-8 text-center text-zinc-400">
                          No audit entries yet
                        </td>
                      </tr>
                    ) : (
                      pageItems.map(({ primary, events }) => {
                        const jobKey = primary.job_id ?? primary.id;
                        const isExpanded = expandedJob === jobKey;
                        const hasMultiple = events.length > 1;

                        return (
                          <>
                            {/* Primary row — latest event for this job */}
                            <tr
                              key={jobKey}
                              className={`border-b border-zinc-100 ${hasMultiple ? "cursor-pointer hover:bg-zinc-50" : "hover:bg-zinc-50"}`}
                              onClick={() => hasMultiple && setExpandedJob(isExpanded ? null : jobKey)}
                            >
                              <td className="p-4 text-zinc-500 text-xs whitespace-nowrap">
                                {formatDate(primary.created_at)}
                              </td>
                              <td className="p-4">
                                <code className="bg-zinc-100 px-2 py-0.5 rounded text-xs text-zinc-700">
                                  {primary.connection}:{primary.action}
                                </code>
                              </td>
                              <td className="p-4 text-zinc-600 text-xs">
                                {primary.approver_name || "—"}
                              </td>
                              <td className="p-4">
                                <Badge variant={eventBadge[primary.event_type] || "default"}>
                                  {primary.event_type.replace(/_/g, " ")}
                                </Badge>
                              </td>
                              <td className="p-4 text-zinc-500 text-xs max-w-xs truncate">
                                {primary.note || primary.binding_message || "—"}
                                {primary.modified_params && (
                                  <span className="ml-2 text-orange-600">
                                    Modified params
                                  </span>
                                )}
                              </td>
                              <td className="pr-4 text-zinc-400">
                                {hasMultiple && (
                                  <span className="flex items-center gap-1 text-xs text-zinc-400">
                                    {events.length}
                                    {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                  </span>
                                )}
                              </td>
                            </tr>

                            {/* Expanded: all intermediate events */}
                            {isExpanded && events.slice(0, -1).map((ev) => (
                              <tr key={ev.id} className="bg-zinc-50 border-b border-zinc-100">
                                <td className="pl-8 py-2 text-zinc-400 text-xs whitespace-nowrap">
                                  {formatDate(ev.created_at)}
                                </td>
                                <td className="py-2 text-zinc-400 text-xs" />
                                <td className="py-2 text-zinc-400 text-xs">
                                  {ev.approver_name || "—"}
                                </td>
                                <td className="py-2">
                                  <Badge variant={eventBadge[ev.event_type] || "default"} className="opacity-60 text-xs">
                                    {ev.event_type.replace(/_/g, " ")}
                                  </Badge>
                                </td>
                                <td className="py-2 text-zinc-400 text-xs max-w-xs truncate">
                                  {ev.note || ev.binding_message || "—"}
                                </td>
                                <td />
                              </tr>
                            ))}
                          </>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-zinc-400">
                {grouped.length} jobs · page {page + 1} of {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page === totalPages - 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
