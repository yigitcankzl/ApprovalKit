"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Patient } from "@/lib/types";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "badge-success",
    discharged: "badge-gray",
    admitted: "badge-info",
    restricted: "badge-danger",
  };
  return <span className={map[status] || "badge-gray"}>{status}</span>;
}

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ limit: "50" });
    if (statusFilter) params.set("status", statusFilter);
    apiFetch(`/api/patients?${params}`).then(setPatients).catch(console.error);
  }, [statusFilter]);

  const filtered = patients.filter((p) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      p.first_name.toLowerCase().includes(q) ||
      p.last_name.toLowerCase().includes(q) ||
      p.mrn.toLowerCase().includes(q) ||
      p.email.toLowerCase().includes(q)
    );
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Patients</h1>
          <p className="text-sm text-gray-500 mt-1">{patients.length} patients in system</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="text"
          placeholder="Search by name, MRN, or email..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-healthcare-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-healthcare-500"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="admitted">Admitted</option>
          <option value="discharged">Discharged</option>
        </select>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="table-header">MRN</th>
              <th className="table-header">Name</th>
              <th className="table-header">Age</th>
              <th className="table-header">Conditions</th>
              <th className="table-header">Doctor</th>
              <th className="table-header">Insurance</th>
              <th className="table-header">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map((patient) => {
              const age = Math.floor(
                (Date.now() - new Date(patient.date_of_birth).getTime()) / (365.25 * 24 * 60 * 60 * 1000)
              );
              return (
                <tr key={patient.id} className="hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => window.location.href = `/patients/${patient.id}`}>
                  <td className="table-cell font-mono text-xs">{patient.mrn}</td>
                  <td className="table-cell font-medium">
                    {patient.first_name} {patient.last_name}
                    <span className="text-xs text-gray-400 ml-2">{patient.blood_type}</span>
                  </td>
                  <td className="table-cell">{age}</td>
                  <td className="table-cell">
                    <div className="flex flex-wrap gap-1">
                      {patient.conditions.slice(0, 2).map((c) => (
                        <span key={c} className="badge-info text-[10px]">{c.split(" ").slice(0, 2).join(" ")}</span>
                      ))}
                      {patient.conditions.length > 2 && (
                        <span className="badge-gray text-[10px]">+{patient.conditions.length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td className="table-cell text-xs">{patient.primary_doctor || "—"}</td>
                  <td className="table-cell text-xs">{patient.insurance || "—"}</td>
                  <td className="table-cell"><StatusBadge status={patient.status} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">No patients found</div>
        )}
      </div>
    </div>
  );
}
