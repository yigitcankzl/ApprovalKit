"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight, CheckCircle2, ChevronDown, Clock, Loader2,
  Play, XCircle, RotateCcw, ThumbsUp, ThumbsDown, Smartphone,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types (re-exported from agent-chat for compatibility) ────────────────────

export interface FlowStep {
  type: "agent" | "platform" | "approver" | "gate" | "action";
  label: string;
  sub?: string;
}

export interface AgentScenario {
  title: string;
  description: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
  flow: FlowStep[];
  badge: "success" | "info" | "warning" | "danger" | "default";
  badgeLabel: string;
}

export interface AgentSetupItem {
  type: "connection" | "approver" | "rule";
  name: string;
  detail: string;
}

export interface DemoAgent {
  id: string;
  title: string;
  icon: string;
  category: string;
  categoryLabel: string;
  description: string;
  scenarios: AgentScenario[];
  setupInfo: AgentSetupItem[];
}

// ── Flow Diagram ─────────────────────────────────────────────────────────────

function FlowDiagram({ steps }: { steps: FlowStep[] }) {
  const colors: Record<string, string> = {
    agent: "bg-zinc-800 text-white",
    platform: "bg-blue-600 text-white",
    approver: "bg-amber-500 text-white",
    gate: "bg-purple-600 text-white",
    action: "bg-green-600 text-white",
  };
  return (
    <div className="flex flex-wrap items-center gap-1">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-1">
          <div className={`rounded-lg px-2.5 py-1.5 text-xs ${colors[step.type]}`}>
            <div className="font-semibold whitespace-nowrap">{step.label}</div>
            {step.sub && <div className="opacity-75 mt-0.5 whitespace-nowrap text-[10px]">{step.sub}</div>}
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600 shrink-0" />}
        </div>
      ))}
    </div>
  );
}

// ── Result Log Entry ─────────────────────────────────────────────────────────

interface ResultEntry {
  id: string;
  timestamp: Date;
  scenarioTitle: string;
  status: "submitting" | "auto_approved" | "pending" | "approved" | "rejected" | "timeout" | "blocked" | "error";
  jobId?: string;
  ruleName?: string;
  model?: string;
  approvers?: string[];
  error?: string;
  params?: Record<string, unknown>;
}

function ResultLogItem({ entry, onApprove, onReject, deciding }: {
  entry: ResultEntry;
  onApprove: (jobId: string) => void;
  onReject: (jobId: string) => void;
  deciding: string | null;
}) {
  const time = entry.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const statusConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
    submitting: { icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />, color: "text-zinc-400", label: "Submitting..." },
    auto_approved: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, color: "text-green-500", label: "Auto-approved" },
    pending: { icon: <Clock className="h-3.5 w-3.5 animate-pulse" />, color: "text-amber-500", label: "Pending Approval" },
    approved: { icon: <CheckCircle2 className="h-3.5 w-3.5" />, color: "text-green-500", label: "Approved" },
    rejected: { icon: <XCircle className="h-3.5 w-3.5" />, color: "text-red-500", label: "Rejected" },
    timeout: { icon: <Clock className="h-3.5 w-3.5" />, color: "text-zinc-400", label: "Timed Out" },
    blocked: { icon: <XCircle className="h-3.5 w-3.5" />, color: "text-red-500", label: "Blocked" },
    error: { icon: <XCircle className="h-3.5 w-3.5" />, color: "text-red-500", label: "Error" },
  };

  const cfg = statusConfig[entry.status] || statusConfig.error;

  return (
    <div className={`flex items-start gap-3 p-3 rounded-xl border transition-colors ${
      entry.status === "pending"
        ? "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20"
        : entry.status === "auto_approved" || entry.status === "approved"
        ? "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20"
        : entry.status === "rejected" || entry.status === "blocked"
        ? "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20"
        : "border-zinc-200 dark:border-zinc-700"
    }`}>
      {/* Status icon */}
      <div className={`mt-0.5 ${cfg.color}`}>{cfg.icon}</div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold ${cfg.color}`}>{cfg.label}</span>
          <span className="text-[10px] text-zinc-400">{time}</span>
        </div>
        <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200 mt-0.5">
          {entry.scenarioTitle}
        </div>

        {/* Rule info for pending/approved/rejected */}
        {entry.ruleName && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
            <span>Rule: <span className="font-medium text-zinc-700 dark:text-zinc-300">{entry.ruleName}</span></span>
            {entry.model && <span>Model: <span className="font-medium text-zinc-700 dark:text-zinc-300">{entry.model}</span></span>}
            {entry.approvers && entry.approvers.length > 0 && (
              <span>Approvers: <span className="font-medium text-zinc-700 dark:text-zinc-300">{entry.approvers.join(", ")}</span></span>
            )}
          </div>
        )}

        {entry.error && (
          <div className="text-xs text-red-600 dark:text-red-400 mt-1">{entry.error}</div>
        )}

        {/* Guardian notice + Approve / Reject buttons for pending jobs */}
        {entry.status === "pending" && entry.jobId && (
          <div className="mt-3 space-y-2.5">
            <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
              <Smartphone className="h-3.5 w-3.5 shrink-0" />
              <span>Also waiting on <span className="font-semibold">Auth0 Guardian</span> — approvers can respond via push notification on their phone</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => onApprove(entry.jobId!)}
                disabled={deciding === entry.jobId}
                className="h-7 px-3 text-xs bg-green-600 hover:bg-green-700 text-white"
              >
                {deciding === entry.jobId ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <><ThumbsUp className="h-3 w-3 mr-1.5" /> Approve via Web</>
                )}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onReject(entry.jobId!)}
                disabled={deciding === entry.jobId}
                className="h-7 px-3 text-xs border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
              >
                <ThumbsDown className="h-3 w-3 mr-1.5" /> Reject
              </Button>
              <span className="text-[10px] text-zinc-400 ml-1">or approve from phone</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Scenario Card ────────────────────────────────────────────────────────────

function ScenarioCard({ scenario, onRun, running }: {
  scenario: AgentScenario;
  onRun: (params: Record<string, unknown>) => void;
  running: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editedParams, setEditedParams] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(scenario.params).map(([k, v]) => [k, String(v)]))
  );

  const resetParams = () => {
    setEditedParams(
      Object.fromEntries(Object.entries(scenario.params).map(([k, v]) => [k, String(v)]))
    );
  };

  const buildParams = (): Record<string, unknown> => {
    const result: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(editedParams)) {
      const original = scenario.params[key];
      if (typeof original === "number") {
        const num = Number(val);
        result[key] = isNaN(num) ? val : num;
      } else if (typeof original === "boolean") {
        result[key] = val === "true";
      } else {
        result[key] = val;
      }
    }
    return result;
  };

  const isModified = Object.entries(editedParams).some(
    ([k, v]) => String(scenario.params[k]) !== v
  );

  return (
    <div className={`border rounded-xl transition-colors ${
      expanded
        ? "border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800/80"
        : "border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50 hover:border-zinc-300 dark:hover:border-zinc-600"
    }`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between p-3 text-left"
      >
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          <Badge variant={scenario.badge} className="text-[10px] font-mono shrink-0 w-16 justify-center">
            {scenario.badgeLabel}
          </Badge>
          <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
            {scenario.title}
          </span>
          {isModified && (
            <Badge variant="default" className="text-[9px] shrink-0 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">
              MODIFIED
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <ChevronDown className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-zinc-100 dark:border-zinc-700/50 pt-3 space-y-3">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{scenario.description}</p>

          {/* Flow diagram */}
          <div>
            <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Approval Flow</div>
            <div className="overflow-x-auto pb-1">
              <FlowDiagram steps={scenario.flow} />
            </div>
          </div>

          {/* Editable params */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Parameters</div>
              {isModified && (
                <button
                  onClick={resetParams}
                  className="flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-600 transition-colors"
                >
                  <RotateCcw className="h-2.5 w-2.5" /> Reset
                </button>
              )}
            </div>
            <div className="space-y-1.5">
              {Object.entries(editedParams).map(([key, val]) => {
                const original = scenario.params[key];
                const isNum = typeof original === "number";
                const isBool = typeof original === "boolean";
                const changed = String(original) !== val;

                return (
                  <div key={key} className="flex items-center gap-2">
                    <label className="text-xs text-zinc-500 dark:text-zinc-400 w-28 shrink-0 font-mono truncate" title={key}>
                      {key}
                    </label>
                    {isBool ? (
                      <select
                        value={val}
                        onChange={(e) => setEditedParams(prev => ({ ...prev, [key]: e.target.value }))}
                        className={`flex-1 rounded-lg border px-2.5 py-1.5 text-xs font-mono transition-colors ${
                          changed
                            ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/20 text-blue-800 dark:text-blue-300"
                            : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200"
                        } focus:outline-none focus:ring-2 focus:ring-blue-500`}
                      >
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    ) : (
                      <input
                        type={isNum ? "number" : "text"}
                        value={val}
                        onChange={(e) => setEditedParams(prev => ({ ...prev, [key]: e.target.value }))}
                        className={`flex-1 rounded-lg border px-2.5 py-1.5 text-xs font-mono transition-colors ${
                          changed
                            ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/20 text-blue-800 dark:text-blue-300"
                            : "border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200"
                        } focus:outline-none focus:ring-2 focus:ring-blue-500`}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Run button */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              onClick={() => onRun(buildParams())}
              disabled={running}
              className="h-8 px-4 text-xs"
            >
              {running ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Running...</>
              ) : (
                <><Play className="h-3.5 w-3.5 mr-1.5" /> Run Scenario</>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main ScenarioRunner Component ────────────────────────────────────────────

let _resultId = 0;
function resultId() { return `r-${++_resultId}-${Date.now()}`; }

export function ScenarioRunner({ agent }: { agent: DemoAgent }) {
  const [results, setResults] = useState<ResultEntry[]>([]);
  const [runningIndex, setRunningIndex] = useState<number | null>(null);
  const [deciding, setDeciding] = useState<string | null>(null);
  const pollRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const resultsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll results
  useEffect(() => {
    resultsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [results]);

  // Cleanup polls on unmount
  useEffect(() => {
    return () => {
      pollRefs.current.forEach(interval => clearInterval(interval));
    };
  }, []);

  const stopPoll = (jobId: string) => {
    const interval = pollRefs.current.get(jobId);
    if (interval) {
      clearInterval(interval);
      pollRefs.current.delete(jobId);
    }
  };

  const updateResult = (id: string, updates: Partial<ResultEntry>) => {
    setResults(prev => prev.map(r => r.id === id ? { ...r, ...updates } : r));
  };

  const handleRunScenario = async (index: number, params: Record<string, unknown>) => {
    const scenario = agent.scenarios[index];
    if (!scenario) return;

    setRunningIndex(index);

    const entryId = resultId();
    const entry: ResultEntry = {
      id: entryId,
      timestamp: new Date(),
      scenarioTitle: scenario.title,
      status: "submitting",
      params,
    };
    setResults(prev => [...prev, entry]);

    try {
      const res = await api.sendTestRequest({
        connection: scenario.connection,
        action: scenario.action,
        params,
      });

      if (res.status === "auto_approved" || res.status === "pre_approved") {
        updateResult(entryId, { status: "auto_approved" });
      } else if (res.job_id) {
        updateResult(entryId, {
          status: "pending",
          jobId: res.job_id,
          ruleName: res.rule_name || res.rule,
          model: res.model,
          approvers: res.approvers?.map((a: any) => a.name) || [],
        });

        // Start polling
        let attempts = 0;
        const interval = setInterval(async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            const terminal = ["approved", "rejected", "timeout", "blocked"];
            if (terminal.includes(s.status)) {
              stopPoll(res.job_id);
              updateResult(entryId, { status: s.status as ResultEntry["status"] });
            }
          } catch {}
          if (++attempts > 150) {
            stopPoll(res.job_id);
            updateResult(entryId, { status: "timeout" });
          }
        }, 2000);
        pollRefs.current.set(res.job_id, interval);
      } else {
        updateResult(entryId, { status: "error", error: "Unexpected response" });
      }
    } catch (e: any) {
      updateResult(entryId, { status: "error", error: e.message || "Request failed" });
    }

    setRunningIndex(null);
  };

  const handleDecision = async (jobId: string, decision: "approve" | "reject") => {
    setDeciding(jobId);
    try {
      await api.submitDecision(jobId, { decision });
      // Update the result immediately
      const newStatus = decision === "approve" ? "approved" : "rejected";
      setResults(prev => prev.map(r =>
        r.jobId === jobId ? { ...r, status: newStatus as ResultEntry["status"] } : r
      ));
      stopPoll(jobId);
    } catch (e: any) {
      // Still try to update - the poll will catch the real status
    }
    setDeciding(null);
  };

  const pendingCount = results.filter(r => r.status === "pending").length;

  return (
    <div className="flex flex-col h-full">
      {/* Scenarios panel */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {/* Agent description */}
          <div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
              {agent.description}
            </p>
          </div>

          {/* Scenarios */}
          <div>
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
              Scenarios — click to expand, edit parameters, and run
            </h3>
            <div className="space-y-2">
              {agent.scenarios.map((scenario, i) => (
                <ScenarioCard
                  key={i}
                  scenario={scenario}
                  onRun={(params) => handleRunScenario(i, params)}
                  running={runningIndex === i}
                />
              ))}
            </div>
          </div>

          {/* Results log */}
          {results.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Results
                  {pendingCount > 0 && (
                    <span className="ml-2 inline-flex items-center gap-1 text-amber-500">
                      <Clock className="h-3 w-3 animate-pulse" />
                      {pendingCount} pending
                    </span>
                  )}
                </h3>
                <button
                  onClick={() => {
                    pollRefs.current.forEach(interval => clearInterval(interval));
                    pollRefs.current.clear();
                    setResults([]);
                  }}
                  className="text-[10px] text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
                >
                  Clear all
                </button>
              </div>
              <div className="space-y-2">
                {results.map(entry => (
                  <ResultLogItem
                    key={entry.id}
                    entry={entry}
                    onApprove={(jobId) => handleDecision(jobId, "approve")}
                    onReject={(jobId) => handleDecision(jobId, "reject")}
                    deciding={deciding}
                  />
                ))}
                <div ref={resultsEndRef} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
