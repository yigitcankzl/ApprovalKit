"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ActivityEvent } from "@/lib/types";

export default function AuditPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (categoryFilter) params.set("category", categoryFilter);
    apiFetch(`/api/dashboard/activity?${params}`).then(setEvents).catch(console.error);
  }, [categoryFilter]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Audit Trail</h1>
        <p className="text-sm text-gray-500 mt-1">Immutable event log with PII masking — HIPAA compliance</p>
      </div>

      <div className="flex gap-3 mb-6">
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-healthcare-500">
          <option value="">All Categories</option>
          <option value="patient">Patient</option>
          <option value="prescription">Prescription</option>
          <option value="billing">Billing</option>
          <option value="hipaa">HIPAA</option>
          <option value="emergency">Emergency</option>
          <option value="staff">Staff</option>
          <option value="system">System</option>
        </select>
        <span className="text-sm text-gray-400 self-center">{events.length} events</span>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="max-h-[700px] overflow-y-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
              <tr>
                <th className="table-header">Time</th>
                <th className="table-header">Category</th>
                <th className="table-header">Severity</th>
                <th className="table-header">Event</th>
                <th className="table-header">Title</th>
                <th className="table-header">Description</th>
                <th className="table-header">Job ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {events.map((e) => (
                <tr key={e.id} className={`hover:bg-gray-50 ${e.severity === "critical" ? "bg-red-50" : ""}`}>
                  <td className="table-cell text-xs text-gray-400 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="table-cell">
                    <span className={
                      e.category === "emergency" ? "badge-danger" :
                      e.category === "hipaa" ? "badge-warning" :
                      e.category === "billing" ? "badge-info" :
                      "badge-gray"
                    }>{e.category}</span>
                  </td>
                  <td className="table-cell">
                    <span className={
                      e.severity === "critical" ? "badge-danger" :
                      e.severity === "warning" ? "badge-warning" :
                      e.severity === "error" ? "badge-danger" :
                      "badge-info"
                    }>{e.severity}</span>
                  </td>
                  <td className="table-cell text-xs font-mono text-gray-500">{e.event_type}</td>
                  <td className="table-cell text-sm font-medium max-w-xs truncate">{e.title}</td>
                  <td className="table-cell text-xs text-gray-500 max-w-md truncate">{e.description}</td>
                  <td className="table-cell text-xs font-mono text-gray-400">
                    {e.approval_job_id ? e.approval_job_id.slice(0, 8) + "..." : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && <div className="p-8 text-center text-gray-400 text-sm">No audit events</div>}
        </div>
      </div>
    </div>
  );
}
