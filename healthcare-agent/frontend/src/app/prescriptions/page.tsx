"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Prescription } from "@/lib/types";

export default function PrescriptionsPage() {
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [patients, setPatients] = useState<any[]>([]);
  const [doctors, setDoctors] = useState<any[]>([]);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    patient_id: "",
    prescribing_doctor_id: "",
    medication_name: "",
    dosage: "",
    frequency: "once daily",
    quantity: 30,
    is_controlled: false,
    schedule_class: "",
  });

  const loadPrescriptions = () => {
    apiFetch("/api/prescriptions?limit=50").then(setPrescriptions).catch(console.error);
  };

  useEffect(() => {
    loadPrescriptions();
    apiFetch("/api/patients").then(setPatients).catch(console.error);
    apiFetch("/api/staff/doctors").then(setDoctors).catch(console.error);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg("");
    try {
      await apiPost("/api/prescriptions", {
        ...form,
        schedule_class: form.is_controlled && form.schedule_class ? form.schedule_class : null,
      });
      setSuccessMsg("Prescription created successfully!");
      setShowForm(false);
      setForm({ patient_id: "", prescribing_doctor_id: "", medication_name: "", dosage: "", frequency: "once daily", quantity: 30, is_controlled: false, schedule_class: "" });
      loadPrescriptions();
      setTimeout(() => setSuccessMsg(""), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create prescription");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prescriptions</h1>
          <p className="text-sm text-gray-500 mt-1">Medication management with ApprovalKit approval chains</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className={showForm ? "btn-secondary" : "btn-primary"}>
          {showForm ? "Cancel" : "+ New Prescription"}
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
          <h3 className="text-lg font-semibold mb-4">New Prescription</h3>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">Doctor</label>
                <select required value={form.prescribing_doctor_id} onChange={(e) => setForm({ ...form, prescribing_doctor_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select doctor...</option>
                  {doctors.map((d: any) => (
                    <option key={d.id} value={d.id}>Dr. {d.first_name} {d.last_name} - {d.specialty}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Medication Name</label>
                <input required type="text" value={form.medication_name} onChange={(e) => setForm({ ...form, medication_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. Amoxicillin" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Dosage</label>
                <input required type="text" value={form.dosage} onChange={(e) => setForm({ ...form, dosage: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. 500mg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
                <select value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="once daily">Once daily</option>
                  <option value="twice daily">Twice daily</option>
                  <option value="three times daily">Three times daily</option>
                  <option value="as needed">As needed</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                <input required type="number" min={1} value={form.quantity} onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 0 })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="flex items-center gap-3 pt-6">
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.is_controlled} onChange={(e) => setForm({ ...form, is_controlled: e.target.checked, schedule_class: "" })}
                    className="w-4 h-4 rounded border-gray-300" />
                  Controlled Substance
                </label>
              </div>
              {form.is_controlled && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Schedule Class</label>
                  <select required value={form.schedule_class} onChange={(e) => setForm({ ...form, schedule_class: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">Select schedule...</option>
                    <option value="II">Schedule II</option>
                    <option value="III">Schedule III</option>
                    <option value="IV">Schedule IV</option>
                    <option value="V">Schedule V</option>
                  </select>
                </div>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? "Creating..." : "Create Prescription"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Approval Model Legend */}
      <div className="card mb-6">
        <h3 className="text-sm font-medium text-gray-500 mb-2">Approval Models</h3>
        <div className="flex flex-wrap gap-4 text-xs">
          <div><span className="badge-success">Routine</span> specific (doctor only)</div>
          <div><span className="badge-warning">Controlled</span> sequential (doctor &rarr; pharmacist)</div>
          <div><span className="badge-danger">Dose Change</span> all_of_n (doctor + pharmacist + CMO)</div>
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="table-header">Rx #</th>
              <th className="table-header">Patient</th>
              <th className="table-header">Medication</th>
              <th className="table-header">Dosage</th>
              <th className="table-header">Frequency</th>
              <th className="table-header">Type</th>
              <th className="table-header">Approvals</th>
              <th className="table-header">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {prescriptions.map((rx) => (
              <tr key={rx.id} className="hover:bg-gray-50">
                <td className="table-cell font-mono text-xs">{rx.rx_number}</td>
                <td className="table-cell text-sm">{rx.patient_name || "—"}</td>
                <td className="table-cell font-medium text-sm">{rx.medication_name}</td>
                <td className="table-cell text-sm">{rx.dosage}</td>
                <td className="table-cell text-xs text-gray-500">{rx.frequency}</td>
                <td className="table-cell">
                  {rx.is_controlled ? (
                    <span className="badge-danger">{rx.schedule_class || "Controlled"}</span>
                  ) : (
                    <span className="badge-success">Routine</span>
                  )}
                </td>
                <td className="table-cell">
                  <div className="flex gap-1">
                    <span className={`w-2 h-2 rounded-full mt-1 ${rx.approved_by_doctor ? "bg-green-500" : "bg-gray-300"}`} title="Doctor" />
                    <span className={`w-2 h-2 rounded-full mt-1 ${rx.approved_by_pharmacist ? "bg-green-500" : "bg-gray-300"}`} title="Pharmacist" />
                    <span className={`w-2 h-2 rounded-full mt-1 ${rx.approved_by_cmo ? "bg-green-500" : "bg-gray-300"}`} title="CMO" />
                  </div>
                </td>
                <td className="table-cell">
                  <span className={
                    rx.status === "approved" || rx.status === "dispensed" ? "badge-success" :
                    rx.status === "denied" ? "badge-danger" :
                    "badge-warning"
                  }>
                    {rx.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {prescriptions.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">No prescriptions found</div>
        )}
      </div>
    </div>
  );
}
