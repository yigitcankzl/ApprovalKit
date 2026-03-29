"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { EmergencyEvent } from "@/lib/types";

export default function EmergencyPage() {
  const [events, setEvents] = useState<EmergencyEvent[]>([]);
  const [activeCount, setActiveCount] = useState(0);
  const [showForm, setShowForm] = useState<"" | "access" | "breach">("");
  const [patients, setPatients] = useState<any[]>([]);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [accessForm, setAccessForm] = useState({
    patient_id: "",
    triggered_by: "",
    reason: "",
  });

  const [breachForm, setBreachForm] = useState({
    triggered_by: "",
    reason: "",
    severity: "critical",
  });

  const load = async () => {
    const [all, active] = await Promise.all([
      apiFetch("/api/emergency/events?limit=50"),
      apiFetch("/api/emergency/active"),
    ]);
    setEvents(all);
    setActiveCount(active.length);
  };

  useEffect(() => {
    load().catch(console.error);
    apiFetch("/api/patients").then(setPatients).catch(console.error);
    const interval = setInterval(() => load().catch(console.error), 5000);
    return () => clearInterval(interval);
  }, []);

  const handleAccessSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/emergency/data-access", accessForm);
      setSuccessMsg("Emergency data access request submitted!");
      setShowForm("");
      setAccessForm({ patient_id: "", triggered_by: "", reason: "" });
      load().catch(console.error);
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit emergency access request");
    } finally {
      setSubmitting(false);
    }
  };

  const handleBreachSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/emergency/security-breach", breachForm);
      setSuccessMsg("Security breach reported successfully!");
      setShowForm("");
      setBreachForm({ triggered_by: "", reason: "", severity: "critical" });
      load().catch(console.error);
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to report security breach");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Emergency</h1>
          <p className="text-sm text-gray-500 mt-1">Critical situation management with fast-track approvals</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm(showForm === "access" ? "" : "access")}
            className={showForm === "access" ? "btn-secondary" : "btn-primary"}
          >
            {showForm === "access" ? "Cancel" : "Emergency Data Access"}
          </button>
          <button
            onClick={() => setShowForm(showForm === "breach" ? "" : "breach")}
            className={`${showForm === "breach" ? "btn-secondary" : "px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"}`}
          >
            {showForm === "breach" ? "Cancel" : "Report Security Breach"}
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-800 rounded-lg text-sm">{successMsg}</div>
      )}
      {errorMsg && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">{errorMsg}</div>
      )}

      {showForm === "access" && (
        <div className="card mb-6 border-l-4 border-l-orange-500">
          <h3 className="text-lg font-semibold mb-4">Emergency Data Access</h3>
          <form onSubmit={handleAccessSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Patient</label>
                <select required value={accessForm.patient_id} onChange={(e) => setAccessForm({ ...accessForm, patient_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select patient...</option>
                  {patients.map((p: any) => (
                    <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.mrn})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Triggered By</label>
                <input required type="text" value={accessForm.triggered_by} onChange={(e) => setAccessForm({ ...accessForm, triggered_by: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Dr. Smith" />
              </div>
              <div className="md:col-span-2 lg:col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <textarea required value={accessForm.reason} onChange={(e) => setAccessForm({ ...accessForm, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2} placeholder="Describe the emergency..." />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? "Submitting..." : "Request Emergency Access"}
              </button>
              <button type="button" onClick={() => setShowForm("")} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {showForm === "breach" && (
        <div className="card mb-6 border-l-4 border-l-red-500">
          <h3 className="text-lg font-semibold text-red-800 mb-4">Report Security Breach</h3>
          <form onSubmit={handleBreachSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Triggered By</label>
                <input required type="text" value={breachForm.triggered_by} onChange={(e) => setBreachForm({ ...breachForm, triggered_by: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Security System" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select value={breachForm.severity} onChange={(e) => setBreachForm({ ...breachForm, severity: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="md:col-span-2 lg:col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason / Description</label>
                <textarea required value={breachForm.reason} onChange={(e) => setBreachForm({ ...breachForm, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2} placeholder="Describe the security breach..." />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors">
                {submitting ? "Reporting..." : "Report Breach"}
              </button>
              <button type="button" onClick={() => setShowForm("")} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Status Banner */}
      <div className={`mb-6 p-6 rounded-xl border-2 ${
        activeCount > 0 ? "bg-red-50 border-red-300" : "bg-green-50 border-green-300"
      }`}>
        <div className="flex items-center gap-4">
          <div className={`w-6 h-6 rounded-full ${activeCount > 0 ? "bg-red-500 animate-pulse" : "bg-green-500"}`} />
          <div>
            <p className={`text-xl font-bold ${activeCount > 0 ? "text-red-800" : "text-green-800"}`}>
              {activeCount > 0 ? `${activeCount} ACTIVE EMERGENC${activeCount > 1 ? "IES" : "Y"}` : "ALL CLEAR"}
            </p>
            <p className={`text-sm ${activeCount > 0 ? "text-red-600" : "text-green-600"}`}>
              {activeCount > 0 ? "Immediate attention required" : "No active emergency situations"}
            </p>
          </div>
        </div>
      </div>

      {/* Approval Models */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="card border-l-4 border-l-red-500">
          <h3 className="font-semibold text-red-800 mb-2">Emergency Data Access</h3>
          <ul className="text-xs text-gray-600 space-y-1">
            <li>Model: <span className="font-medium">any_one</span> (first available doctor)</li>
            <li>Timeout: <span className="font-medium">2 minutes</span></li>
            <li>Blackout: <span className="font-medium">None</span> (override)</li>
            <li>On timeout: <span className="font-medium">Escalate to CMO</span></li>
            <li>Audit: <span className="font-medium">Special emergency logging</span></li>
          </ul>
        </div>
        <div className="card border-l-4 border-l-purple-500">
          <h3 className="font-semibold text-purple-800 mb-2">Security Breach</h3>
          <ul className="text-xs text-gray-600 space-y-1">
            <li>Step 1: <span className="font-medium">Auto-freeze account</span> (immediate)</li>
            <li>Step 2: <span className="font-medium">Slack #security alert</span> (immediate)</li>
            <li>Step 3: <span className="font-medium">all_of_n</span> (security + CMO)</li>
            <li>Step 4: <span className="font-medium">Gmail → patient notification</span></li>
          </ul>
        </div>
      </div>

      {/* Events Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="table-header">Type</th>
              <th className="table-header">Severity</th>
              <th className="table-header">Patient</th>
              <th className="table-header">Triggered By</th>
              <th className="table-header">Reason</th>
              <th className="table-header">Status</th>
              <th className="table-header">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {events.map((e) => (
              <tr key={e.id} className={`hover:bg-gray-50 ${e.status === "active" ? "bg-red-50" : ""}`}>
                <td className="table-cell">
                  <span className={e.event_type === "security_breach" ? "badge-danger" : "badge-warning"}>
                    {e.event_type.replace("_", " ")}
                  </span>
                </td>
                <td className="table-cell">
                  <span className={e.severity === "critical" ? "badge-danger" : "badge-warning"}>{e.severity}</span>
                </td>
                <td className="table-cell text-sm">{e.patient_name || "System"}</td>
                <td className="table-cell text-xs text-gray-500">{e.triggered_by}</td>
                <td className="table-cell text-xs text-gray-500 max-w-xs truncate">{e.reason}</td>
                <td className="table-cell">
                  <span className={
                    e.status === "resolved" ? "badge-success" :
                    e.status === "active" ? "badge-danger" :
                    "badge-warning"
                  }>{e.status}</span>
                </td>
                <td className="table-cell text-xs text-gray-400">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && <div className="p-8 text-center text-gray-400 text-sm">No emergency events</div>}
      </div>
    </div>
  );
}
