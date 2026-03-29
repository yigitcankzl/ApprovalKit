"use client";

import { useEffect, useState } from "react";
import { apiFetch, apiPost } from "@/lib/api";
import type { Scenario } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  patient: "border-l-blue-500 bg-blue-50/30",
  prescription: "border-l-green-500 bg-green-50/30",
  billing: "border-l-yellow-500 bg-yellow-50/30",
  hipaa: "border-l-purple-500 bg-purple-50/30",
  emergency: "border-l-red-500 bg-red-50/30",
  staff: "border-l-cyan-500 bg-cyan-50/30",
};

const CATEGORY_BADGE: Record<string, string> = {
  patient: "badge-info",
  prescription: "badge-success",
  billing: "badge-warning",
  hipaa: "bg-purple-100 text-purple-800 badge",
  emergency: "badge-danger",
  staff: "bg-cyan-100 text-cyan-800 badge",
};

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [running, setRunning] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<Record<string, any>>({});

  useEffect(() => {
    apiFetch("/api/scenarios").then(setScenarios).catch(console.error);
  }, []);

  const runScenario = async (id: string) => {
    setRunning((prev) => new Set(prev).add(id));
    try {
      const result = await apiPost(`/api/scenarios/${id}/run`, {});
      setResults((prev) => ({ ...prev, [id]: result }));
    } catch (e: any) {
      setResults((prev) => ({ ...prev, [id]: { status: "error", message: e.message } }));
    }
    setTimeout(() => {
      setRunning((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 2000);
  };

  const grouped = scenarios.reduce<Record<string, Scenario[]>>((acc, s) => {
    (acc[s.category] = acc[s.category] || []).push(s);
    return acc;
  }, {});

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Scenarios</h1>
        <p className="text-sm text-gray-500 mt-1">
          Pre-built demo scenarios showcasing every ApprovalKit feature in healthcare context
        </p>
      </div>

      {/* Feature Matrix */}
      <div className="card mb-8">
        <h3 className="text-sm font-medium text-gray-500 mb-3">ApprovalKit Features Used</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2 text-xs">
          {[
            { name: "Token Vault", desc: "Gmail, Calendar, Drive, Slack" },
            { name: "CIBA Guardian", desc: "Push notification approvals" },
            { name: "any_one", desc: "First approver wins" },
            { name: "specific", desc: "Designated approver" },
            { name: "all_of_n", desc: "Every approver must approve" },
            { name: "sequential", desc: "Ordered approval chain" },
            { name: "step-up", desc: "Escalate on conditions" },
            { name: "partial_approval", desc: "Modify params before approve" },
            { name: "delegation", desc: "Vacation approver handoff" },
            { name: "blackout", desc: "Time-based restrictions" },
            { name: "scope_creep", desc: "First-time action detection" },
            { name: "amount_anomaly", desc: "Large volume flagging" },
          ].map((f) => (
            <div key={f.name} className="p-2 bg-gray-50 rounded-lg">
              <p className="font-medium text-gray-700">{f.name}</p>
              <p className="text-gray-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Scenarios by Category */}
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="mb-8">
          <h2 className="text-lg font-semibold mb-3 capitalize flex items-center gap-2">
            <span className={CATEGORY_BADGE[category] || "badge-gray"}>{category}</span>
            <span className="text-gray-400 text-sm font-normal">({items.length} scenarios)</span>
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {items.map((scenario) => (
              <div key={scenario.id} className={`card border-l-4 ${CATEGORY_COLORS[category] || ""}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-900">{scenario.title}</h3>
                    <p className="text-xs text-gray-500 mt-1">{scenario.description}</p>
                  </div>
                  <button
                    onClick={() => runScenario(scenario.id)}
                    disabled={running.has(scenario.id)}
                    className={running.has(scenario.id) ? "btn-secondary opacity-50" : "btn-primary text-sm"}
                  >
                    {running.has(scenario.id) ? "Running..." : "Run"}
                  </button>
                </div>

                {/* Approval Types */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {scenario.approval_types.map((t) => (
                    <span key={t} className="badge-info text-[10px]">{t}</span>
                  ))}
                </div>

                {/* Steps */}
                <div className="space-y-1.5">
                  {scenario.steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-gray-600">
                      <span className="text-gray-400 font-mono mt-0.5">{i + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>

                {/* Result */}
                {results[scenario.id] && (
                  <div className={`mt-3 p-2 rounded-lg text-xs ${
                    results[scenario.id].status === "running" ? "bg-blue-50 text-blue-700" :
                    results[scenario.id].status === "error" ? "bg-red-50 text-red-700" :
                    "bg-green-50 text-green-700"
                  }`}>
                    {results[scenario.id].message || results[scenario.id].status}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
