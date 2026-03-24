"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
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

const mockAuditLog: AuditEntry[] = [
  {
    id: "1",
    job_id: "j1",
    approver_id: "a1",
    approver_name: "CFO",
    event_type: "approved",
    action: "charge",
    connection: "stripe-prod",
    binding_message: "Charge of $340 for john@example.com — 2nd charge this month",
    modified_params: null,
    note: null,
    created_at: "2026-03-24T14:23:11Z",
  },
  {
    id: "2",
    job_id: "j2",
    approver_id: "a1",
    approver_name: "CFO",
    event_type: "escalated",
    action: "payout",
    connection: "stripe-prod",
    binding_message: "Payout of $1200",
    modified_params: null,
    note: "CEO notified after timeout",
    created_at: "2026-03-24T14:31:05Z",
  },
  {
    id: "3",
    job_id: "j3",
    approver_id: "a2",
    approver_name: "Lead Dev",
    event_type: "rejected",
    action: "push",
    connection: "github-main",
    binding_message: "Push to main branch",
    modified_params: null,
    note: "Scope creep flagged",
    created_at: "2026-03-24T14:33:21Z",
  },
  {
    id: "4",
    job_id: "j4",
    approver_id: null,
    approver_name: null,
    event_type: "pre_approved",
    action: "charge",
    connection: "stripe-prod",
    binding_message: null,
    modified_params: null,
    note: "Blanket approval active until 17:00",
    created_at: "2026-03-24T14:45:00Z",
  },
  {
    id: "5",
    job_id: "j5",
    approver_id: "a1",
    approver_name: "CFO",
    event_type: "partial_approved",
    action: "refund",
    connection: "stripe-prod",
    binding_message: "Refund of $340 for order #1234",
    modified_params: { amount: 200 },
    note: "$200 only approved",
    created_at: "2026-03-24T15:02:00Z",
  },
  {
    id: "6",
    job_id: "j6",
    approver_id: null,
    approver_name: null,
    event_type: "scope_creep",
    action: "payout",
    connection: "stripe-prod",
    binding_message: null,
    modified_params: null,
    note: "First time agent requests stripe-prod:payout",
    created_at: "2026-03-24T15:10:00Z",
  },
];

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api
      .getAuditLog({ event_type: filter || undefined })
      .then(setLogs)
      .catch(() => setLogs(mockAuditLog))
      .finally(() => setLoading(false));
  }, [filter]);

  const filteredLogs = filter
    ? logs.filter((l) => l.event_type === filter)
    : logs;

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
                  {filteredLogs.map((log) => (
                    <tr key={log.id} className="border-b border-zinc-100 hover:bg-zinc-50">
                      <td className="p-4 text-zinc-600">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </td>
                      <td className="p-4">
                        <code className="bg-zinc-100 px-2 py-0.5 rounded text-xs">
                          {log.connection}:{log.action}
                        </code>
                      </td>
                      <td className="p-4 text-zinc-600">
                        {log.approver_name || "—"}
                      </td>
                      <td className="p-4">
                        <Badge variant={eventBadge[log.event_type] || "default"}>
                          {log.event_type.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="p-4 text-zinc-500 text-xs max-w-xs truncate">
                        {log.note || log.binding_message || "—"}
                        {log.modified_params && (
                          <span className="ml-2 text-orange-600">
                            Modified: {JSON.stringify(log.modified_params)}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
