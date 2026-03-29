"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { DashboardStats, ActivityEvent } from "@/lib/types";

function StatCard({ title, value, subtitle, color }: { title: string; value: string | number; subtitle?: string; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    green: "bg-green-50 text-green-700 border-green-200",
    red: "bg-red-50 text-red-700 border-red-200",
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    purple: "bg-purple-50 text-purple-700 border-purple-200",
    cyan: "bg-cyan-50 text-cyan-700 border-cyan-200",
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[color] || colors.blue}`}>
      <p className="text-sm font-medium opacity-75">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {subtitle && <p className="text-xs mt-1 opacity-60">{subtitle}</p>}
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    info: "badge-info",
    warning: "badge-warning",
    error: "badge-danger",
    critical: "badge-danger",
  };
  return <span className={map[severity] || "badge-gray"}>{severity}</span>;
}

function CategoryBadge({ category }: { category: string }) {
  const map: Record<string, string> = {
    patient: "badge-info",
    prescription: "badge-success",
    billing: "badge-warning",
    hipaa: "badge-gray",
    emergency: "badge-danger",
    staff: "badge-info",
    system: "badge-gray",
  };
  return <span className={map[category] || "badge-gray"}>{category}</span>;
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [seeding, setSeeding] = useState(false);

  const loadData = async () => {
    try {
      const [s, a] = await Promise.all([
        apiFetch("/api/dashboard/stats"),
        apiFetch("/api/dashboard/activity?limit=20"),
      ]);
      setStats(s);
      setActivity(a);
    } catch (e) {
      console.error("Failed to load dashboard:", e);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await apiPost("/api/seed", {});
      await loadData();
    } catch (e) {
      console.error("Seed failed:", e);
    }
    setSeeding(false);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">MedCore General Hospital — Real-time overview</p>
        </div>
        {stats && stats.patients.total === 0 && (
          <button onClick={handleSeed} disabled={seeding} className="btn-primary">
            {seeding ? "Seeding..." : "Seed Demo Data"}
          </button>
        )}
      </div>

      {/* Emergency Banner */}
      {stats && stats.emergencies.active > 0 && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
          <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
          <span className="text-red-800 font-medium">
            {stats.emergencies.active} Active Emergency{stats.emergencies.active > 1 ? "ies" : ""}
          </span>
          <a href="/emergency" className="ml-auto text-red-600 text-sm hover:underline">View Details</a>
        </div>
      )}

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard title="Total Patients" value={stats.patients.total} subtitle={`${stats.patients.active} active`} color="blue" />
          <StatCard title="Pending Approvals" value={stats.prescriptions.pending_approval} color="yellow" />
          <StatCard title="Active Emergencies" value={stats.emergencies.active} color="red" />
          <StatCard title="Today's Appointments" value={stats.appointments.today} color="green" />
          <StatCard title="Total Billed" value={`$${stats.billing.total_billed.toLocaleString()}`} color="purple" />
          <StatCard title="Activity (24h)" value={stats.activity.last_24h} color="cyan" />
        </div>
      )}

      {/* Approval Summary */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Prescriptions</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Pending</span>
                <span className="font-medium text-yellow-600">{stats.prescriptions.pending_approval}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Approved</span>
                <span className="font-medium text-green-600">{stats.prescriptions.approved}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Denied</span>
                <span className="font-medium text-red-600">{stats.prescriptions.denied}</span>
              </div>
            </div>
          </div>
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Billing</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Total</span>
                <span className="font-medium">${stats.billing.total_billed.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Pending</span>
                <span className="font-medium text-yellow-600">${stats.billing.pending.toLocaleString()}</span>
              </div>
            </div>
          </div>
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-3">ApprovalKit Features</h3>
            <div className="flex flex-wrap gap-1.5">
              {["Token Vault", "CIBA", "any_one", "specific", "all_of_n", "sequential", "step-up", "partial", "delegation", "scope creep"].map((f) => (
                <span key={f} className="badge-info">{f}</span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Activity Feed */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Recent Activity</h2>
        {activity.length === 0 ? (
          <p className="text-sm text-gray-400">No activity yet. Seed the database to get started.</p>
        ) : (
          <div className="space-y-3 max-h-[500px] overflow-y-auto">
            {activity.map((event) => (
              <div key={event.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors">
                <div className="flex-shrink-0 mt-0.5">
                  <SeverityBadge severity={event.severity} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{event.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{event.description}</p>
                </div>
                <div className="flex-shrink-0 flex items-center gap-2">
                  <CategoryBadge category={event.category} />
                  <span className="text-xs text-gray-400">
                    {new Date(event.created_at).toLocaleTimeString()}
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
