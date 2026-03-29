"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { DemoAgent, AgentScenario } from "@/components/scenario-runner";
import {
  ArrowLeft, Banknote, Bot, CheckCircle2, ChevronDown, CreditCard,
  FlaskConical, GitBranch, Loader2, MessageSquare, Package, Plane,
  Play, Server, Shield, ShieldAlert, ShieldCheck, ShieldOff,
  Users, Zap, AlertTriangle, XCircle, Clock, Lock,
  ThumbsUp, ThumbsDown, Eye, BarChart3, Activity,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface ShieldEvent {
  id: string;
  timestamp: Date;
  agentId: string;
  agentTitle: string;
  type: "auto_approved" | "pending" | "approved" | "rejected" | "blocked" | "step_up" | "scope_creep" | "budget_exceeded";
  action: string;
  connection: string;
  params: Record<string, unknown>;
  message: string;
  jobId?: string;
  approver?: string;
}

interface SessionSummary {
  totalActions: number;
  autoApproved: number;
  pendingApproval: number;
  blocked: number;
  preventedDamage: number;
}

const ICON_MAP: Record<string, React.ElementType> = {
  CreditCard, Server, Users, Package, FlaskConical, Zap, Banknote,
  Plane, GitBranch, MessageSquare, Shield, Bot, Play,
};

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Bot;
}

const BADGE_STYLES: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  danger: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  default: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300",
};

// ── Main Page ──────────────────────────────────────────────────────────────

export default function LiveThreatDemoPage() {
  const { user } = useUser();
  const [agents, setAgents] = useState<DemoAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<DemoAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState<ShieldEvent[]>([]);
  const [summary, setSummary] = useState<SessionSummary>({
    totalActions: 0, autoApproved: 0, pendingApproval: 0, blocked: 0, preventedDamage: 0,
  });
  const [runningScenario, setRunningScenario] = useState<number | null>(null);
  const [setupDone, setSetupDone] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const eventsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  // Load agents
  useEffect(() => {
    api.getDemoAgents()
      .then((data: DemoAgent[] | { agents: DemoAgent[] }) => {
        const list = Array.isArray(data) ? data : data.agents || [];
        setAgents(list);
        if (list.length > 0) setSelectedAgent(list[0]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Check setup
  useEffect(() => {
    api.getRules().then((rules: any[]) => {
      setSetupDone(rules.length > 0);
    }).catch(() => {});
  }, []);

  const handleSeedAll = async () => {
    setSeeding(true);
    try {
      await api.seedDemoData(undefined, user?.sub);
      setSetupDone(true);
    } catch {}
    setSeeding(false);
  };

  const addEvent = useCallback((evt: Omit<ShieldEvent, "id" | "timestamp">) => {
    const event: ShieldEvent = {
      ...evt,
      id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date(),
    };
    setEvents(prev => [...prev, event]);
    setSummary(prev => {
      const next = { ...prev, totalActions: prev.totalActions + 1 };
      if (evt.type === "auto_approved") next.autoApproved++;
      else if (evt.type === "blocked" || evt.type === "budget_exceeded" || evt.type === "scope_creep") {
        next.blocked++;
        const amount = Number(evt.params?.amount_usd) || 0;
        next.preventedDamage += amount;
      } else if (evt.type === "pending" || evt.type === "step_up") next.pendingApproval++;
      return next;
    });
  }, []);

  const handleRunScenario = async (scenarioIdx: number) => {
    if (!selectedAgent || runningScenario !== null) return;
    const scenario = selectedAgent.scenarios[scenarioIdx];
    if (!scenario) return;

    setRunningScenario(scenarioIdx);

    try {
      const result = await api.testRequest({
        connection: scenario.connection,
        action: scenario.action,
        params: scenario.params,
      });

      const status = result.status || "auto_approved";
      let eventType: ShieldEvent["type"] = "auto_approved";
      if (status === "pending") eventType = "pending";
      else if (status === "blocked") eventType = "blocked";
      else if (status === "rejected") eventType = "rejected";

      // Check for step-up indicators
      if (result.rule_name?.toLowerCase().includes("step-up") || result.rule_name?.toLowerCase().includes("large") || result.rule_name?.toLowerCase().includes("cfo")) {
        eventType = status === "pending" ? "step_up" : eventType;
      }
      if (result.rule_name?.toLowerCase().includes("mass") || result.rule_name?.toLowerCase().includes("bulk") || result.rule_name?.toLowerCase().includes("scope")) {
        eventType = "scope_creep";
      }

      addEvent({
        agentId: selectedAgent.id,
        agentTitle: selectedAgent.title,
        type: eventType,
        action: scenario.action,
        connection: scenario.connection,
        params: scenario.params,
        message: result.message || `${scenario.title} — ${status}`,
        jobId: result.job_id,
        approver: result.approver,
      });
    } catch (e: any) {
      addEvent({
        agentId: selectedAgent.id,
        agentTitle: selectedAgent.title,
        type: "blocked",
        action: scenario.action,
        connection: scenario.connection,
        params: scenario.params,
        message: `Error: ${e.message}`,
      });
    }

    setRunningScenario(null);
  };

  const handleApprove = async (jobId: string, eventId: string) => {
    try {
      await api.approveJob(jobId);
      setEvents(prev => prev.map(e =>
        e.id === eventId ? { ...e, type: "approved" as const, message: e.message.replace("pending", "APPROVED") } : e
      ));
      setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
    } catch {}
  };

  const handleReject = async (jobId: string, eventId: string) => {
    try {
      await api.rejectJob(jobId);
      const targetEvent = events.find(ev => ev.id === eventId);
      const rejectedAmount = Number(targetEvent?.params?.amount_usd) || 0;
      setEvents(prev => prev.map(e =>
        e.id === eventId ? { ...e, type: "rejected" as const, message: e.message.replace("pending", "REJECTED") } : e
      ));
      setSummary(prev => ({
        ...prev,
        pendingApproval: Math.max(0, prev.pendingApproval - 1),
        blocked: prev.blocked + 1,
        preventedDamage: prev.preventedDamage + rejectedAmount,
      }));
    } catch {}
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-zinc-950 text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <a href="/demos" className="text-zinc-400 hover:text-white transition-colors">
            <ArrowLeft className="h-4 w-4" />
          </a>
          <ShieldAlert className="h-5 w-5 text-red-500" />
          <h1 className="text-sm font-bold tracking-wide">LIVE THREAT DEMO</h1>
          <span className="text-[10px] text-zinc-500 font-mono">ApprovalKit Shield</span>
        </div>
        <div className="flex items-center gap-4">
          {/* Summary counters */}
          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="flex items-center gap-1 text-emerald-400">
              <CheckCircle2 className="h-3 w-3" /> {summary.autoApproved}
            </span>
            <span className="flex items-center gap-1 text-amber-400">
              <Clock className="h-3 w-3" /> {summary.pendingApproval}
            </span>
            <span className="flex items-center gap-1 text-red-400">
              <ShieldOff className="h-3 w-3" /> {summary.blocked}
            </span>
          </div>
          <div className="h-4 w-px bg-zinc-700" />
          <div className="text-xs font-mono">
            <span className="text-zinc-500">Prevented: </span>
            <span className="text-red-400 font-bold">${summary.preventedDamage.toLocaleString()}</span>
          </div>
          {!setupDone && (
            <Button size="sm" onClick={handleSeedAll} disabled={seeding} className="h-7 text-xs bg-blue-600 hover:bg-blue-700">
              {seeding ? <Loader2 className="h-3 w-3 animate-spin" /> : "Setup Demo Data"}
            </Button>
          )}
        </div>
      </div>

      {/* Main content: split screen */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT: Agent Panel */}
        <div className="w-1/2 border-r border-zinc-800 flex flex-col">
          {/* Agent tabs */}
          <div className="flex gap-1 px-3 py-2 border-b border-zinc-800 overflow-x-auto scrollbar-hide bg-zinc-900/50">
            {agents.map(agent => {
              const Icon = resolveIcon(agent.icon);
              const isActive = selectedAgent?.id === agent.id;
              return (
                <button
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-all ${
                    isActive
                      ? "bg-zinc-700 text-white shadow-sm"
                      : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                  }`}
                  title={agent.title}
                >
                  <Icon className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="hidden xl:inline">{agent.title.replace(" Agent", "").replace(" Approval", "")}</span>
                </button>
              );
            })}
          </div>

          {/* Selected agent info + scenarios */}
          {selectedAgent && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  {(() => { const Icon = resolveIcon(selectedAgent.icon); return <Icon className="h-5 w-5 text-blue-400" />; })()}
                  {selectedAgent.title}
                </h2>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed line-clamp-3">{selectedAgent.description}</p>
              </div>

              {/* Scenario cards */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Scenarios</h3>
                {selectedAgent.scenarios.map((scenario, i) => (
                  <button
                    key={i}
                    onClick={() => handleRunScenario(i)}
                    disabled={runningScenario !== null || !setupDone}
                    className="w-full text-left p-3 rounded-lg border border-zinc-800 hover:border-zinc-600 bg-zinc-900/50 hover:bg-zinc-800/50 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${BADGE_STYLES[scenario.badge || "default"]}`}>
                          {scenario.badgeLabel}
                        </span>
                        <span className="text-sm font-medium text-zinc-200">{scenario.title}</span>
                      </div>
                      {runningScenario === i ? (
                        <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
                      ) : (
                        <Play className="h-4 w-4 text-zinc-600 group-hover:text-blue-400 transition-colors" />
                      )}
                    </div>
                    <p className="text-xs text-zinc-500 mt-1">{scenario.description}</p>
                  </button>
                ))}
              </div>

              {!setupDone && (
                <div className="p-3 rounded-lg border border-amber-900/50 bg-amber-900/10 text-amber-400 text-xs">
                  <AlertTriangle className="h-4 w-4 inline mr-1" />
                  Click "Setup Demo Data" above to create the approval rules, connections, and approvers needed for the demo.
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT: Shield Panel (real-time events) */}
        <div className="w-1/2 flex flex-col">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
            <Shield className="h-4 w-4 text-blue-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400">ApprovalKit Shield</h2>
            <div className="flex-1" />
            <span className="text-[10px] text-zinc-600 font-mono">{events.length} events</span>
            {events.length > 0 && (
              <button
                onClick={() => { setEvents([]); setSummary({ totalActions: 0, autoApproved: 0, pendingApproval: 0, blocked: 0, preventedDamage: 0 }); }}
                className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {/* Events feed */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600">
                <Activity className="h-12 w-12 mb-3 opacity-20" />
                <p className="text-sm">No events yet</p>
                <p className="text-xs mt-1">Run a scenario to see the Shield in action</p>
              </div>
            ) : (
              events.map(event => (
                <EventCard key={event.id} event={event} onApprove={handleApprove} onReject={handleReject} />
              ))
            )}
            <div ref={eventsEndRef} />
          </div>

          {/* Summary bar */}
          {events.length > 0 && (
            <div className="px-4 py-3 border-t border-zinc-800 bg-zinc-900/80">
              <div className="grid grid-cols-4 gap-3 text-center">
                <SummaryCard label="Total Actions" value={summary.totalActions} icon={<BarChart3 className="h-4 w-4" />} color="text-zinc-300" />
                <SummaryCard label="Auto-Approved" value={summary.autoApproved} icon={<CheckCircle2 className="h-4 w-4" />} color="text-emerald-400" />
                <SummaryCard label="Pending" value={summary.pendingApproval} icon={<Clock className="h-4 w-4" />} color="text-amber-400" />
                <SummaryCard label="Blocked" value={summary.blocked} icon={<ShieldOff className="h-4 w-4" />} color="text-red-400" />
              </div>
              {summary.preventedDamage > 0 && (
                <div className="mt-2 text-center">
                  <span className="text-xs text-zinc-500">Total prevented damage: </span>
                  <span className="text-lg font-bold text-red-400 font-mono">${summary.preventedDamage.toLocaleString()}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Event Card ────────────────────────────────────────────────────────────

function EventCard({ event, onApprove, onReject }: {
  event: ShieldEvent;
  onApprove: (jobId: string, eventId: string) => void;
  onReject: (jobId: string, eventId: string) => void;
}) {
  const typeConfig: Record<string, { icon: React.ElementType; color: string; bg: string; label: string }> = {
    auto_approved: { icon: CheckCircle2, color: "text-emerald-400", bg: "border-emerald-900/50 bg-emerald-900/10", label: "AUTO-APPROVED" },
    pending: { icon: Clock, color: "text-amber-400", bg: "border-amber-900/50 bg-amber-900/10", label: "PENDING APPROVAL" },
    approved: { icon: ThumbsUp, color: "text-emerald-400", bg: "border-emerald-900/50 bg-emerald-900/10", label: "APPROVED" },
    rejected: { icon: ThumbsDown, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "REJECTED" },
    blocked: { icon: ShieldOff, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "BLOCKED" },
    step_up: { icon: ShieldAlert, color: "text-amber-400", bg: "border-amber-900/50 bg-amber-900/10", label: "STEP-UP REQUIRED" },
    scope_creep: { icon: AlertTriangle, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "SCOPE CREEP DETECTED" },
    budget_exceeded: { icon: Lock, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "BUDGET EXCEEDED" },
  };

  const config = typeConfig[event.type] || typeConfig.blocked;
  const Icon = config.icon;
  const amount = Number(event.params?.amount_usd);

  return (
    <div className={`rounded-lg border p-3 transition-all animate-in slide-in-from-right-5 duration-300 ${config.bg}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 flex-shrink-0 ${config.color}`} />
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold uppercase tracking-wide ${config.color}`}>{config.label}</span>
              <span className="text-[10px] text-zinc-600 font-mono">
                {event.timestamp.toLocaleTimeString()}
              </span>
            </div>
            <p className="text-xs text-zinc-300 mt-0.5">{event.message}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] text-zinc-500 font-mono">{event.connection}/{event.action}</span>
              {amount > 0 && <span className="text-[10px] font-mono text-zinc-400">${amount.toLocaleString()}</span>}
              <span className="text-[10px] text-zinc-600">{event.agentTitle}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Approve / Reject buttons for pending events */}
      {(event.type === "pending" || event.type === "step_up") && event.jobId && (
        <div className="flex gap-2 mt-2 ml-6">
          <button
            onClick={() => onApprove(event.jobId!, event.id)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-900/30 text-emerald-400 hover:bg-emerald-900/50 border border-emerald-800/50 transition-colors"
          >
            <ThumbsUp className="h-3 w-3" /> Approve
          </button>
          <button
            onClick={() => onReject(event.jobId!, event.id)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-800/50 transition-colors"
          >
            <ThumbsDown className="h-3 w-3" /> Reject
          </button>
        </div>
      )}
    </div>
  );
}

// ── Summary Card ──────────────────────────────────────────────────────────

function SummaryCard({ label, value, icon, color }: { label: string; value: number; icon: React.ReactNode; color: string }) {
  return (
    <div className="space-y-1">
      <div className={`flex items-center justify-center gap-1 ${color}`}>
        {icon}
        <span className="text-xl font-bold font-mono">{value}</span>
      </div>
      <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</p>
    </div>
  );
}
