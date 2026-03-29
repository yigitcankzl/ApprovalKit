"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { BillingRecord } from "@/lib/types";

export default function BillingPage() {
  const [records, setRecords] = useState<BillingRecord[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [showForm, setShowForm] = useState(false);
  const [patients, setPatients] = useState<any[]>([]);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    patient_id: "",
    description: "",
    amount: 0,
  });

  const loadData = () => {
    apiFetch("/api/billing?limit=50").then(setRecords).catch(console.error);
    apiFetch("/api/billing/stats").then(setStats).catch(console.error);
  };

  useEffect(() => {
    loadData();
    apiFetch("/api/patients").then(setPatients).catch(console.error);
  }, []);

  const getTierPreview = (amount: number) => {
    if (amount >= 25000) return { label: "critical", badge: "bg-purple-100 text-purple-800 badge" };
    if (amount >= 10000) return { label: "high", badge: "badge-danger" };
    if (amount >= 500) return { label: "standard", badge: "badge-warning" };
    return { label: "auto", badge: "badge-success" };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/billing", form);
      setSuccessMsg("Invoice created successfully!");
      setShowForm(false);
      setForm({ patient_id: "", description: "", amount: 0 });
      loadData();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create invoice");
    } finally {
      setSubmitting(false);
    }
  };

  const tierPreview = getTierPreview(form.amount);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Billing</h1>
          <p className="text-sm text-gray-500 mt-1">Invoice processing with amount-based step-up approvals</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className={showForm ? "btn-secondary" : "btn-primary"}>
          {showForm ? "Cancel" : "+ New Invoice"}
        </button>
      </div>

      {successMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-800 rounded-lg text-sm">{successMsg}</div>
      )}
      {errorMsg && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">{errorMsg}</div>
      )}

      {showForm && (
        <div className="card mb-6">
          <h3 className="text-lg font-semibold mb-4">New Invoice</h3>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Patient</label>
                <select required value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select patient...</option>
                  {patients.map((p: any) => (
                    <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.mrn})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <input required type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. MRI Scan - Lumbar Spine" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount ($)</label>
                <input required type="number" min={0} step={0.01} value={form.amount || ""} onChange={(e) => setForm({ ...form, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="0.00" />
              </div>
            </div>
            {form.amount > 0 && (
              <div className="mt-3 text-sm text-gray-600">
                Approval tier: <span className={tierPreview.badge}>{tierPreview.label}</span>
                {tierPreview.label === "auto" && <span className="ml-2 text-gray-400">Auto-approved (under $500)</span>}
                {tierPreview.label === "standard" && <span className="ml-2 text-gray-400">Finance manager approval</span>}
                {tierPreview.label === "high" && <span className="ml-2 text-gray-400">Finance + Director approval</span>}
                {tierPreview.label === "critical" && <span className="ml-2 text-gray-400">Finance + Director + CMO approval</span>}
              </div>
            )}
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? "Creating..." : "Create Invoice"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Step-Up Legend */}
      <div className="card mb-6">
        <h3 className="text-sm font-medium text-gray-500 mb-2">Step-Up Escalation</h3>
        <div className="flex flex-wrap gap-6 text-xs">
          <div><span className="badge-success">&lt;$500</span> Auto-approve</div>
          <div><span className="badge-warning">$500+</span> Finance manager (specific)</div>
          <div><span className="badge-danger">$10k+</span> Finance + Director (step-up &rarr; all_of_n)</div>
          <div><span className="bg-purple-100 text-purple-800 badge">$25k+</span> Finance + Director + CMO</div>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="card text-center">
            <p className="text-sm text-gray-500">Total Billed</p>
            <p className="text-2xl font-bold text-gray-900">${stats.total_billed.toLocaleString()}</p>
          </div>
          <div className="card text-center">
            <p className="text-sm text-gray-500">Pending Approval</p>
            <p className="text-2xl font-bold text-yellow-600">${stats.pending_amount.toLocaleString()}</p>
          </div>
          <div className="card text-center">
            <p className="text-sm text-gray-500">Approved</p>
            <p className="text-2xl font-bold text-green-600">${stats.approved_amount.toLocaleString()}</p>
          </div>
          <div className="card text-center">
            <p className="text-sm text-gray-500">Denied</p>
            <p className="text-2xl font-bold text-red-600">{stats.denied_count}</p>
          </div>
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="table-header">Invoice</th>
              <th className="table-header">Patient</th>
              <th className="table-header">Description</th>
              <th className="table-header">Amount</th>
              <th className="table-header">Insurance</th>
              <th className="table-header">Patient Owes</th>
              <th className="table-header">Tier</th>
              <th className="table-header">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {records.map((b) => {
              const tier = b.amount >= 25000 ? "critical" : b.amount >= 10000 ? "high" : b.amount >= 500 ? "standard" : "auto";
              const tierBadge = {
                auto: "badge-success", standard: "badge-warning", high: "badge-danger",
                critical: "bg-purple-100 text-purple-800 badge",
              }[tier];
              return (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="table-cell font-mono text-xs">{b.invoice_number}</td>
                  <td className="table-cell text-sm">{b.patient_name || "—"}</td>
                  <td className="table-cell text-sm">{b.description}</td>
                  <td className="table-cell font-medium">${b.amount.toLocaleString()}</td>
                  <td className="table-cell text-sm text-green-600">${b.insurance_covered.toLocaleString()}</td>
                  <td className="table-cell text-sm">${b.patient_responsibility.toLocaleString()}</td>
                  <td className="table-cell"><span className={tierBadge}>{tier}</span></td>
                  <td className="table-cell">
                    <span className={
                      b.status === "paid" || b.status === "approved" ? "badge-success" :
                      b.status === "denied" ? "badge-danger" :
                      b.status === "appealed" ? "badge-warning" :
                      "badge-warning"
                    }>{b.status}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
