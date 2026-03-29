"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useParams } from "next/navigation";

export default function PatientDetailPage() {
  const params = useParams();
  const [patient, setPatient] = useState<any>(null);
  const [prescriptions, setRx] = useState<any[]>([]);
  const [billing, setBilling] = useState<any[]>([]);

  useEffect(() => {
    const id = params.id as string;
    apiFetch(`/api/patients/${id}`).then(setPatient).catch(console.error);
    apiFetch(`/api/prescriptions?patient_id=${id}&limit=10`).then(setRx).catch(console.error);
    apiFetch(`/api/billing?patient_id=${id}&limit=10`).then(setBilling).catch(console.error);
  }, [params.id]);

  if (!patient) return <div className="p-8 text-gray-400">Loading...</div>;

  const age = Math.floor((Date.now() - new Date(patient.date_of_birth).getTime()) / (365.25 * 24 * 60 * 60 * 1000));

  return (
    <div>
      <div className="mb-6">
        <a href="/patients" className="text-sm text-healthcare-600 hover:underline">&larr; Back to Patients</a>
      </div>

      <div className="flex items-center gap-4 mb-8">
        <div className="w-16 h-16 bg-healthcare-100 rounded-full flex items-center justify-center text-healthcare-700 text-xl font-bold">
          {patient.first_name[0]}{patient.last_name[0]}
        </div>
        <div>
          <h1 className="text-2xl font-bold">{patient.first_name} {patient.last_name}</h1>
          <p className="text-sm text-gray-500">{patient.mrn} &middot; {age} years &middot; {patient.gender} &middot; {patient.blood_type}</p>
        </div>
        <span className={`ml-4 ${patient.status === "active" ? "badge-success" : patient.status === "restricted" ? "badge-danger" : "badge-gray"}`}>
          {patient.status}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Demographics */}
        <div className="card">
          <h3 className="font-semibold mb-3">Demographics</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Email</dt><dd>{patient.email}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Phone</dt><dd>{patient.phone}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">SSN</dt><dd>{patient.ssn_masked}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Doctor</dt><dd>{patient.primary_doctor || "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Insurance</dt><dd>{patient.insurance || "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Policy #</dt><dd>{patient.insurance_policy_number || "—"}</dd></div>
          </dl>
        </div>

        {/* Medical */}
        <div className="card">
          <h3 className="font-semibold mb-3">Medical Information</h3>
          <div className="mb-3">
            <p className="text-xs text-gray-500 mb-1.5">Conditions</p>
            <div className="flex flex-wrap gap-1.5">
              {patient.conditions.length > 0 ? patient.conditions.map((c: string) => (
                <span key={c} className="badge-info">{c}</span>
              )) : <span className="text-sm text-gray-400">None</span>}
            </div>
          </div>
          <div className="mb-3">
            <p className="text-xs text-gray-500 mb-1.5">Allergies</p>
            <div className="flex flex-wrap gap-1.5">
              {patient.allergies.length > 0 ? patient.allergies.map((a: string) => (
                <span key={a} className="badge-danger">{a}</span>
              )) : <span className="text-sm text-gray-400">None</span>}
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1.5">Current Medications</p>
            <div className="flex flex-wrap gap-1.5">
              {patient.medications_current.length > 0 ? patient.medications_current.map((m: string) => (
                <span key={m} className="badge-success">{m}</span>
              )) : <span className="text-sm text-gray-400">None</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Prescriptions */}
      <div className="card mb-6">
        <h3 className="font-semibold mb-3">Prescriptions</h3>
        {prescriptions.length === 0 ? (
          <p className="text-sm text-gray-400">No prescriptions</p>
        ) : (
          <div className="space-y-2">
            {prescriptions.map((rx) => (
              <div key={rx.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium">{rx.medication_name} {rx.dosage}</p>
                  <p className="text-xs text-gray-500">{rx.rx_number} &middot; {rx.frequency}</p>
                </div>
                <div className="flex items-center gap-2">
                  {rx.is_controlled && <span className="badge-danger">Controlled</span>}
                  <span className={rx.status === "approved" ? "badge-success" : rx.status === "denied" ? "badge-danger" : "badge-warning"}>
                    {rx.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Billing */}
      <div className="card">
        <h3 className="font-semibold mb-3">Billing History</h3>
        {billing.length === 0 ? (
          <p className="text-sm text-gray-400">No billing records</p>
        ) : (
          <div className="space-y-2">
            {billing.map((b) => (
              <div key={b.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium">{b.description}</p>
                  <p className="text-xs text-gray-500">{b.invoice_number}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">${b.amount.toLocaleString()}</span>
                  <span className={b.status === "paid" ? "badge-success" : b.status === "denied" ? "badge-danger" : "badge-warning"}>
                    {b.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
