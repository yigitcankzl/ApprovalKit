"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Doctor, StaffMember } from "@/lib/types";

export default function StaffPage() {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [tab, setTab] = useState<"doctors" | "staff">("doctors");
  const [showAccessForm, setShowAccessForm] = useState(false);
  const [showDelegationForm, setShowDelegationForm] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [accessForm, setAccessForm] = useState({
    staff_id: "",
    requested_access_level: "basic",
    reason: "",
  });

  const [delegationForm, setDelegationForm] = useState({
    doctor_id: "",
    delegate_to_id: "",
    days: 14,
    reason: "",
  });

  const loadData = () => {
    apiFetch("/api/staff/doctors").then(setDoctors).catch(console.error);
    apiFetch("/api/staff/members").then(setStaff).catch(console.error);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAccessSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/staff/access-request", accessForm);
      setSuccessMsg("Access change request submitted!");
      setShowAccessForm(false);
      setAccessForm({ staff_id: "", requested_access_level: "basic", reason: "" });
      loadData();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit access change request");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelegationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost(`/api/staff/doctors/${delegationForm.doctor_id}/delegate`, {
        delegate_to_id: delegationForm.delegate_to_id,
        days: delegationForm.days,
        reason: delegationForm.reason,
      });
      setSuccessMsg("Delegation set successfully!");
      setShowDelegationForm(false);
      setDelegationForm({ doctor_id: "", delegate_to_id: "", days: 14, reason: "" });
      loadData();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to set delegation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Staff Management</h1>
        <p className="text-sm text-gray-500 mt-1">Doctors, delegation, and access management</p>
      </div>

      {successMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-800 rounded-lg text-sm">{successMsg}</div>
      )}
      {errorMsg && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg text-sm">{errorMsg}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button onClick={() => setTab("doctors")} className={tab === "doctors" ? "btn-primary" : "btn-secondary"}>
          Doctors ({doctors.length})
        </button>
        <button onClick={() => setTab("staff")} className={tab === "staff" ? "btn-primary" : "btn-secondary"}>
          Staff ({staff.length})
        </button>
      </div>

      {tab === "doctors" && (
        <>
          <div className="mb-4">
            <button onClick={() => { setShowDelegationForm(!showDelegationForm); setShowAccessForm(false); }}
              className={showDelegationForm ? "btn-secondary" : "btn-primary"}>
              {showDelegationForm ? "Cancel" : "+ Set Delegation"}
            </button>
          </div>

          {showDelegationForm && (
            <div className="card mb-6">
              <h3 className="text-lg font-semibold mb-4">Set Delegation</h3>
              <form onSubmit={handleDelegationSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Doctor</label>
                    <select required value={delegationForm.doctor_id} onChange={(e) => setDelegationForm({ ...delegationForm, doctor_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Select doctor...</option>
                      {doctors.map((d) => (
                        <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name} - {d.specialty}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Delegate To</label>
                    <select required value={delegationForm.delegate_to_id} onChange={(e) => setDelegationForm({ ...delegationForm, delegate_to_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Select delegate...</option>
                      {doctors.filter((d) => d.id !== delegationForm.doctor_id).map((d) => (
                        <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name} - {d.specialty}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Duration (days)</label>
                    <input required type="number" min={1} max={365} value={delegationForm.days} onChange={(e) => setDelegationForm({ ...delegationForm, days: parseInt(e.target.value) || 14 })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  </div>
                  <div className="md:col-span-2 lg:col-span-3">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason (optional)</label>
                    <input type="text" value={delegationForm.reason} onChange={(e) => setDelegationForm({ ...delegationForm, reason: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g. Vacation, medical leave..." />
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <button type="submit" disabled={submitting} className="btn-primary">
                    {submitting ? "Setting..." : "Set Delegation"}
                  </button>
                  <button type="button" onClick={() => setShowDelegationForm(false)} className="btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="table-header">NPI</th>
                  <th className="table-header">Name</th>
                  <th className="table-header">Specialty</th>
                  <th className="table-header">Department</th>
                  <th className="table-header">Role</th>
                  <th className="table-header">Delegation</th>
                  <th className="table-header">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {doctors.map((d) => (
                  <tr key={d.id} className="hover:bg-gray-50">
                    <td className="table-cell font-mono text-xs">{d.npi}</td>
                    <td className="table-cell font-medium">Dr. {d.first_name} {d.last_name}</td>
                    <td className="table-cell text-sm">{d.specialty}</td>
                    <td className="table-cell text-sm text-gray-500">{d.department}</td>
                    <td className="table-cell">
                      {d.is_cmo && <span className="badge-danger">CMO</span>}
                    </td>
                    <td className="table-cell text-xs">
                      {d.on_vacation ? (
                        <div>
                          <span className="badge-warning">On Leave</span>
                          {d.delegate_name && <p className="mt-1 text-gray-500">&rarr; {d.delegate_name}</p>}
                          {d.delegate_until && <p className="text-gray-400">until {new Date(d.delegate_until).toLocaleDateString()}</p>}
                        </div>
                      ) : "—"}
                    </td>
                    <td className="table-cell">
                      <span className={d.is_active ? "badge-success" : "badge-gray"}>
                        {d.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "staff" && (
        <>
          <div className="mb-4">
            <button onClick={() => { setShowAccessForm(!showAccessForm); setShowDelegationForm(false); }}
              className={showAccessForm ? "btn-secondary" : "btn-primary"}>
              {showAccessForm ? "Cancel" : "+ Request Access Change"}
            </button>
          </div>

          {showAccessForm && (
            <div className="card mb-6">
              <h3 className="text-lg font-semibold mb-4">Request Access Change</h3>
              <form onSubmit={handleAccessSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Staff Member</label>
                    <select required value={accessForm.staff_id} onChange={(e) => setAccessForm({ ...accessForm, staff_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Select staff member...</option>
                      {staff.map((s) => (
                        <option key={s.id} value={s.id}>{s.first_name} {s.last_name} - {s.role.replace("_", " ")} ({s.access_level})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Requested Access Level</label>
                    <select value={accessForm.requested_access_level} onChange={(e) => setAccessForm({ ...accessForm, requested_access_level: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="basic">Basic</option>
                      <option value="patient_records">Patient Records</option>
                      <option value="medication_system">Medication System</option>
                      <option value="full">Full</option>
                    </select>
                  </div>
                  <div className="md:col-span-2 lg:col-span-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
                    <input required type="text" value={accessForm.reason} onChange={(e) => setAccessForm({ ...accessForm, reason: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Reason for access change..." />
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <button type="submit" disabled={submitting} className="btn-primary">
                    {submitting ? "Submitting..." : "Submit Request"}
                  </button>
                  <button type="button" onClick={() => setShowAccessForm(false)} className="btn-secondary">Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="card p-0 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="table-header">ID</th>
                  <th className="table-header">Name</th>
                  <th className="table-header">Role</th>
                  <th className="table-header">Department</th>
                  <th className="table-header">Access Level</th>
                  <th className="table-header">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {staff.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="table-cell font-mono text-xs">{s.employee_id}</td>
                    <td className="table-cell font-medium">{s.first_name} {s.last_name}</td>
                    <td className="table-cell text-sm">{s.role.replace("_", " ")}</td>
                    <td className="table-cell text-sm text-gray-500">{s.department}</td>
                    <td className="table-cell">
                      <span className={
                        s.access_level === "full" ? "badge-danger" :
                        s.access_level === "medication_system" ? "badge-warning" :
                        s.access_level === "patient_records" ? "badge-info" :
                        "badge-gray"
                      }>{s.access_level}</span>
                    </td>
                    <td className="table-cell">
                      <span className={s.is_active ? "badge-success" : "badge-gray"}>
                        {s.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
