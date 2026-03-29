"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Referral } from "@/lib/types";

export default function ReferralsPage() {
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [showForm, setShowForm] = useState<"" | "external" | "insurance">("");
  const [patients, setPatients] = useState<any[]>([]);
  const [doctors, setDoctors] = useState<any[]>([]);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [extForm, setExtForm] = useState({
    patient_id: "",
    referring_doctor_id: "",
    clinic_name: "",
    clinic_email: "",
    reason: "",
    data_scope: "summary",
  });

  const [insForm, setInsForm] = useState({
    patient_id: "",
    insurance_provider_id: "",
    requested_data_scope: "summary",
    reason: "",
  });

  const loadReferrals = () => {
    const params = new URLSearchParams({ limit: "50" });
    if (typeFilter) params.set("referral_type", typeFilter);
    apiFetch(`/api/referrals?${params}`).then(setReferrals).catch(console.error);
  };

  useEffect(() => {
    loadReferrals();
  }, [typeFilter]);

  useEffect(() => {
    apiFetch("/api/patients").then(setPatients).catch(console.error);
    apiFetch("/api/staff/doctors").then(setDoctors).catch(console.error);
  }, []);

  const handleExtSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/referrals/external", extForm);
      setSuccessMsg("External referral created successfully!");
      setShowForm("");
      setExtForm({ patient_id: "", referring_doctor_id: "", clinic_name: "", clinic_email: "", reason: "", data_scope: "summary" });
      loadReferrals();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create external referral");
    } finally {
      setSubmitting(false);
    }
  };

  const handleInsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/referrals/insurance-request", insForm);
      setSuccessMsg("Insurance data request created successfully!");
      setShowForm("");
      setInsForm({ patient_id: "", insurance_provider_id: "", requested_data_scope: "summary", reason: "" });
      loadReferrals();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create insurance data request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">HIPAA / Referrals</h1>
          <p className="text-sm text-gray-500 mt-1">HIPAA-compliant data sharing with full audit trail</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm(showForm === "external" ? "" : "external")}
            className={showForm === "external" ? "btn-secondary" : "btn-primary"}
          >
            {showForm === "external" ? "Cancel" : "+ External Referral"}
          </button>
          <button
            onClick={() => setShowForm(showForm === "insurance" ? "" : "insurance")}
            className={showForm === "insurance" ? "btn-secondary" : "btn-primary"}
          >
            {showForm === "insurance" ? "Cancel" : "+ Insurance Data"}
          </button>
        </div>
      </div>

      {successMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-800 rounded-lg text-sm">{successMsg}</div>
      )}
      {errorMsg && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">{errorMsg}</div>
      )}

      {showForm === "external" && (
        <div className="card mb-6">
          <h3 className="text-lg font-semibold mb-4">New External Referral</h3>
          <form onSubmit={handleExtSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Patient</label>
                <select required value={extForm.patient_id} onChange={(e) => setExtForm({ ...extForm, patient_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select patient...</option>
                  {patients.map((p: any) => (
                    <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.mrn})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Referring Doctor</label>
                <select required value={extForm.referring_doctor_id} onChange={(e) => setExtForm({ ...extForm, referring_doctor_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select doctor...</option>
                  {doctors.map((d: any) => (
                    <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name} - {d.specialty}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Clinic Name</label>
                <input required type="text" value={extForm.clinic_name} onChange={(e) => setExtForm({ ...extForm, clinic_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. City Radiology Center" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Clinic Email</label>
                <input required type="email" value={extForm.clinic_email} onChange={(e) => setExtForm({ ...extForm, clinic_email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="referrals@clinic.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data Scope</label>
                <select value={extForm.data_scope} onChange={(e) => setExtForm({ ...extForm, data_scope: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="summary">Summary</option>
                  <option value="full">Full</option>
                  <option value="specific_records">Specific Records</option>
                </select>
              </div>
              <div className="md:col-span-2 lg:col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <textarea required value={extForm.reason} onChange={(e) => setExtForm({ ...extForm, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2} placeholder="Reason for referral..." />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? "Creating..." : "Create Referral"}
              </button>
              <button type="button" onClick={() => setShowForm("")} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {showForm === "insurance" && (
        <div className="card mb-6">
          <h3 className="text-lg font-semibold mb-4">Insurance Data Request</h3>
          <form onSubmit={handleInsSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Patient</label>
                <select required value={insForm.patient_id} onChange={(e) => setInsForm({ ...insForm, patient_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select patient...</option>
                  {patients.map((p: any) => (
                    <option key={p.id} value={p.id}>{p.first_name} {p.last_name} ({p.mrn})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Insurance Provider</label>
                <input required type="text" value={insForm.insurance_provider_id} onChange={(e) => setInsForm({ ...insForm, insurance_provider_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. BlueCross BlueShield" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Requested Data Scope</label>
                <select value={insForm.requested_data_scope} onChange={(e) => setInsForm({ ...insForm, requested_data_scope: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="summary">Summary</option>
                  <option value="full">Full</option>
                  <option value="claims_only">Claims Only</option>
                </select>
              </div>
              <div className="md:col-span-2 lg:col-span-3">
                <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                <textarea required value={insForm.reason} onChange={(e) => setInsForm({ ...insForm, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={2} placeholder="Reason for insurance data request..." />
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? "Submitting..." : "Submit Request"}
              </button>
              <button type="button" onClick={() => setShowForm("")} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Approval Model Legend */}
      <div className="card mb-6">
        <h3 className="text-sm font-medium text-gray-500 mb-2">Data Sharing Approval Models</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-blue-50 rounded-lg">
            <p className="font-medium text-blue-800 mb-1">External Referral</p>
            <p className="text-blue-600">specific (referring doctor) &rarr; Drive share + Gmail notify</p>
          </div>
          <div className="p-3 bg-yellow-50 rounded-lg">
            <p className="font-medium text-yellow-800 mb-1">Insurance Data</p>
            <p className="text-yellow-600">all_of_n + partial_approval (patient rep + doctor, scope narrowing)</p>
          </div>
          <div className="p-3 bg-purple-50 rounded-lg">
            <p className="font-medium text-purple-800 mb-1">Research Export</p>
            <p className="text-purple-600">sequential (ethics &rarr; CMO &rarr; director) + amount anomaly</p>
          </div>
        </div>
      </div>

      <div className="flex gap-3 mb-6">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-healthcare-500">
          <option value="">All Types</option>
          <option value="external_clinic">External Referral</option>
          <option value="research_export">Research Export</option>
        </select>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="table-header">Type</th>
              <th className="table-header">Patient</th>
              <th className="table-header">Entity</th>
              <th className="table-header">Reason</th>
              <th className="table-header">Scope</th>
              <th className="table-header">Final Scope</th>
              <th className="table-header">Count</th>
              <th className="table-header">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {referrals.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="table-cell">
                  <span className={
                    r.referral_type === "external_clinic" ? "badge-info" :
                    r.referral_type === "research_export" ? "bg-purple-100 text-purple-800 badge" :
                    "badge-warning"
                  }>{r.referral_type.replace("_", " ")}</span>
                </td>
                <td className="table-cell text-sm">{r.patient_name || "—"}</td>
                <td className="table-cell text-sm font-medium">{r.external_entity_name}</td>
                <td className="table-cell text-xs text-gray-500 max-w-xs truncate">{r.reason}</td>
                <td className="table-cell text-xs">{r.data_scope}</td>
                <td className="table-cell text-xs">
                  {r.final_data_scope && r.final_data_scope !== r.data_scope ? (
                    <span className="badge-warning">{r.final_data_scope} (narrowed)</span>
                  ) : (
                    r.final_data_scope || "—"
                  )}
                </td>
                <td className="table-cell">
                  {r.patient_count > 1 && (
                    <span className={r.patient_count >= 100 ? "badge-danger" : "badge-gray"}>
                      {r.patient_count} {r.patient_count >= 100 ? "ANOMALY" : ""}
                    </span>
                  )}
                </td>
                <td className="table-cell">
                  <span className={r.status === "approved" ? "badge-success" : r.status === "denied" ? "badge-danger" : "badge-warning"}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {referrals.length === 0 && <div className="p-8 text-center text-gray-400 text-sm">No referrals found</div>}
      </div>
    </div>
  );
}
