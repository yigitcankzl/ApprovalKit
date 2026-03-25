"use client";

import { useEffect, useRef, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ShoppingCart, Server, Package, FlaskConical, CreditCard, Mail, Users,
  Play, CheckCircle2, XCircle, Clock, ChevronRight, ArrowRight, Loader2, Send,
  Bot, Trash2, Plus, Plug, RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface FlowStep {
  type: "agent" | "platform" | "approver" | "gate" | "action";
  label: string;
  sub?: string;
}

interface Scenario {
  title: string;
  description: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
  flow: FlowStep[];
  badge: "success" | "info" | "warning" | "danger" | "default";
  badgeLabel: string;
}

interface SetupItem {
  type: "connection" | "approver" | "rule";
  name: string;
  detail: string;
}

interface AgentRaw {
  id: string;
  title: string;
  icon: string;
  description: string;
  scenarios: Scenario[];
  setupInfo: SetupItem[];
}

interface Agent extends Omit<AgentRaw, "icon"> {
  icon: React.ElementType;
}

// ── Removed: AGENTS was hardcoded here (490 lines). Now fetched from GET /api/v1/demo/agents ──
// PLACEHOLDER_REMOVED_AGENTS

// ── Flow diagram ──────────────────────────────────────────────────────────────

function FlowDiagram({ steps }: { steps: FlowStep[] }) {
  const colors: Record<string, string> = {
    agent:    "bg-zinc-800 text-white",
    platform: "bg-blue-600 text-white",
    approver: "bg-amber-500 text-white",
    gate:     "bg-purple-600 text-white",
    action:   "bg-green-600 text-white",
  };
  return (
    <div className="flex flex-wrap items-center gap-1 mt-3">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-1">
          <div className={`rounded-lg px-3 py-2 text-xs ${colors[step.type]}`}>
            <div className="font-semibold whitespace-nowrap">{step.label}</div>
            {step.sub && <div className="opacity-75 mt-0.5 whitespace-nowrap">{step.sub}</div>}
          </div>
          {i < steps.length - 1 && <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600 shrink-0" />}
        </div>
      ))}
    </div>
  );
}

// ── Seed banner ───────────────────────────────────────────────────────────────

interface SeedState {
  status: "idle" | "loading" | "done" | "error";
  created?: number;
  skipped?: number;
  items?: string[];
  error?: string;
}

function SeedBanner() {
  const [state, setState] = useState<SeedState>({ status: "idle" });
  const [showLog, setShowLog] = useState(false);

  const handleSeed = async () => {
    setState({ status: "loading" });
    try {
      const res = await api.seedDemoData();
      setState({ status: "done", created: res.created_count, skipped: res.skipped_count, items: res.created });
    } catch (e: any) {
      setState({ status: "error", error: e.message });
    }
  };

  if (state.status === "done") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/30 px-4 py-3">
        <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-green-800 dark:text-green-300">
            Demo data seeded — {state.created} created, {state.skipped} skipped
          </p>
          <p className="text-xs text-green-700 dark:text-green-400 mt-0.5">
            Connections, approvers and rules are now in your database. Hit Check Rule on any scenario below.
          </p>
          {state.items && state.items.length > 0 && (
            <button className="text-xs text-green-600 underline mt-1" onClick={() => setShowLog((v) => !v)}>
              {showLog ? "Hide" : "Show"} created items ({state.items.length})
            </button>
          )}
          {showLog && state.items && (
            <ul className="mt-2 space-y-0.5 max-h-40 overflow-y-auto">
              {state.items.map((item, i) => (
                <li key={i} className="text-xs text-green-700 dark:text-green-400 font-mono">+ {item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/30 px-4 py-3">
        <XCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-red-800">Seed failed</p>
          <p className="text-xs text-red-700 dark:text-red-400 mt-0.5">{state.error}</p>
          <button className="mt-2 text-xs text-red-600 underline" onClick={() => setState({ status: "idle" })}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 flex items-center gap-4 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 px-4 py-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">No rules configured yet?</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          Seed all demo connections, approvers, and rules into your database in one click.
          Check Rule will then show real rule matches instead of &quot;no rule found&quot;.
        </p>
      </div>
      <Button onClick={handleSeed} disabled={state.status === "loading"} size="sm" className="shrink-0">
        {state.status === "loading"
          ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Seeding…</>
          : <><Play className="h-3.5 w-3.5 mr-1.5" />Seed Demo Data</>}
      </Button>
    </div>
  );
}

// ── Scenario card ─────────────────────────────────────────────────────────────

interface RunResult {
  status: "running" | "matched" | "no_rule" | "no_match" | "error";
  rule?: string;
  model?: string;
  approvers?: { name: string }[];
  detail?: string;
}

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  const [result, setResult] = useState<RunResult | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [sending, setSending] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<string[]>([]);

  const handleCheckRule = async () => {
    setResult({ status: "running" });
    setLiveStatus(null);
    try {
      const res = await api.simulateRule({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.matched) {
        setResult({ status: "matched", rule: res.rule_name, model: res.model, approvers: res.approvers, detail: res.timeout_seconds ? `Timeout: ${res.timeout_seconds}s` : undefined });
      } else {
        if (scenario.badge === "success") {
          setResult({ status: "no_match", detail: "No rule configured — auto-approved as expected." });
        } else {
          setResult({ status: "no_rule", detail: `No matching rule found for "${scenario.connection} / ${scenario.action}". Click Setup Demo above.` });
        }
      }
    } catch (e: any) {
      setResult({ status: "error", detail: e.message });
    }
  };

  const handleSendReal = async () => {
    setSending(true);
    setLiveStatus("submitting");
    setLiveSteps(["submitting"]);
    try {
      const res = await api.sendTestRequest({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.status === "auto_approved" && scenario.badge !== "success") {
        // No rule found but this scenario SHOULD have a rule — setup not done
        setLiveStatus("no_setup");
        setLiveSteps(["submitting", "no_setup"]);
        return;
      }
      if (res.status === "auto_approved") {
        setLiveStatus("auto_approved");
        setLiveSteps(["submitting", "rule_matched", "auto_approved"]);
      } else if (res.job_id) {
        setLiveStatus("rule_matched");
        setLiveSteps(["submitting", "rule_matched"]);
        // Small delay to show rule matched step
        await new Promise(r => setTimeout(r, 800));
        setLiveStatus("ciba_sent");
        setLiveSteps(["submitting", "rule_matched", "ciba_sent"]);
        // Poll for result
        let attempts = 0;
        const poll = async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            if (["approved", "rejected", "timeout", "blocked"].includes(s.status)) {
              setLiveStatus(s.status);
              setLiveSteps(prev => [...prev, s.status]);
              return;
            }
          } catch {}
          if (++attempts < 60) setTimeout(poll, 2000);
        };
        poll();
      }
    } catch (e: any) {
      setLiveStatus("error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <button className="w-full text-left p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800 dark:bg-zinc-800/50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge variant={scenario.badge} className="text-xs font-mono w-20 justify-center shrink-0">
              {scenario.badgeLabel}
            </Badge>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 ml-[92px]">{scenario.description}</p>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50/50 space-y-4">
          {/* Flow diagram */}
          <div>
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mt-3 mb-1">Approval Flow</p>
            <div className="overflow-x-auto pb-1">
              <FlowDiagram steps={scenario.flow} />
            </div>
            <div className="flex gap-3 mt-2 flex-wrap">
              {[
                { color: "bg-zinc-800", label: "Agent" },
                { color: "bg-blue-600", label: "ApprovalKit" },
                { color: "bg-amber-500", label: "Approver" },
                { color: "bg-purple-600", label: "Gate" },
                { color: "bg-green-600", label: "Action" },
              ].map((l) => (
                <div key={l.label} className="flex items-center gap-1">
                  <div className={`h-2 w-2 rounded-sm ${l.color}`} />
                  <span className="text-xs text-zinc-400">{l.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Params */}
          <div>
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Request Params</p>
            <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">
              {JSON.stringify({ connection: scenario.connection, action: scenario.action, params: scenario.params }, null, 2)}
            </pre>
          </div>

          {/* Actions */}
          <div className="flex items-start gap-3 flex-wrap">
            <Button size="sm" variant="outline" onClick={handleCheckRule} disabled={result?.status === "running"} className="shrink-0">
              {result?.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Running…</>
                : <><FlaskConical className="h-3.5 w-3.5 mr-1.5" />Check Rule</>}
            </Button>
            <Button size="sm" onClick={handleSendReal} disabled={sending || liveStatus === "ciba_sent"} className="shrink-0">
              {sending
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending…</>
                : <><Send className="h-3.5 w-3.5 mr-1.5" />Run Live</>}
            </Button>
            {liveSteps.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <LiveStep done={liveSteps.includes("submitting")} active={liveStatus === "submitting"} label="Submitted" />
                <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                {liveStatus === "no_setup" ? (
                  <LiveStep done={true} error={true} label="No rules configured — click Setup Demo first" />
                ) : (
                <LiveStep done={liveSteps.includes("rule_matched") || liveSteps.includes("auto_approved")} active={liveStatus === "rule_matched"} label={liveStatus === "auto_approved" ? "Auto-approved" : "Rule matched"} />
                )}
                {liveStatus !== "auto_approved" && liveStatus !== "no_setup" && <>
                  <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                  <LiveStep done={liveSteps.includes("ciba_sent")} active={liveStatus === "ciba_sent"} label="Guardian push sent" />
                  <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600" />
                  <LiveStep
                    done={liveSteps.includes("approved") || liveSteps.includes("rejected") || liveSteps.includes("timeout")}
                    active={liveStatus === "ciba_sent"}
                    error={liveStatus === "rejected" || liveStatus === "timeout"}
                    label={
                      liveStatus === "approved" ? "Approved" :
                      liveStatus === "rejected" ? "Rejected" :
                      liveStatus === "timeout" ? "Timed out" :
                      "Waiting..."
                    }
                  />
                </>}
              </div>
            )}

            {result && result.status !== "running" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                result.status === "matched"  ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800" :
                result.status === "no_match" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
                result.status === "no_rule"  ? "bg-amber-50 border border-amber-200 text-amber-800" :
                "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800"
              }`}>
                {result.status === "matched" && (
                  <>
                    <div className="flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Rule matched
                    </div>
                    {result.rule && <div className="mt-0.5">Rule: <strong>{result.rule}</strong></div>}
                    <div>
                      Model: <strong>{result.model}</strong>
                      {result.approvers && result.approvers.length > 0 && <> · Approvers: {result.approvers.map((a) => a.name).join(", ")}</>}
                      {result.detail && <> · {result.detail}</>}
                    </div>
                  </>
                )}
                {result.status === "no_match" && (
                  <div className="flex items-center gap-1 font-semibold">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {result.detail}
                  </div>
                )}
                {result.status === "no_rule" && (
                  <div className="flex items-start gap-1.5">
                    <Clock className="h-3.5 w-3.5 mt-0.5 shrink-0" /> <span>{result.detail}</span>
                  </div>
                )}
                {result.status === "error" && (
                  <div className="flex items-center gap-1">
                    <XCircle className="h-3.5 w-3.5" /> {result.detail}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Icon resolver for registered agents ──────────────────────────────────────

const ICON_MAP: Record<string, React.ElementType> = {
  "bot":           Bot,
  "shopping-cart": ShoppingCart,
  "users":         Users,
  "server":        Server,
  "package":       Package,
  "flask":         FlaskConical,
  "credit-card":   CreditCard,
  "mail":          Mail,
  // Backend demo agents use PascalCase icon names
  "ShoppingCart":  ShoppingCart,
  "Users":         Users,
  "Server":        Server,
  "Package":       Package,
  "FlaskConical":  FlaskConical,
  "CreditCard":    CreditCard,
  "Mail":          Mail,
  "Bot":           Bot,
};
function AgentIcon({ icon }: { icon: string }) {
  const Icon = ICON_MAP[icon] ?? Bot;
  return <Icon className="h-5 w-5 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600" />;
}

// ── My Agent scenario card (live test inline) ─────────────────────────────────

interface MyAgentScenario {
  id: string;
  title: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
}

interface LiveState {
  status: "idle" | "running" | "pending" | "approved" | "rejected" | "auto_approved" | "timeout" | "error";
  jobId?: string;
  message?: string;
  error?: string;
}

function MyScenarioCard({ scenario }: { scenario: MyAgentScenario }) {
  const [expanded, setExpanded] = useState(false);
  const [live, setLive] = useState<LiveState>({ status: "idle" });
  const [deciding, setDeciding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPoll = (id: string) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getJobStatus(id);
        const terminal = ["approved", "rejected", "timeout", "blocked"];
        setLive((prev) => ({ ...prev, status: terminal.includes(s.status) ? s.status : "pending", jobId: id }));
        if (terminal.includes(s.status)) stopPoll();
      } catch {}
    }, 2000);
  };

  const handleTest = async () => {
    setLive({ status: "running" });
    try {
      const res = await api.sendTestRequest({ connection: scenario.connection, action: scenario.action, params: scenario.params });
      if (res.job_id) {
        setLive({ status: "pending", jobId: res.job_id, message: res.message });
        startPoll(res.job_id);
      } else {
        setLive({ status: res.status, message: res.message });
      }
    } catch (e: any) {
      setLive({ status: "error", error: e.message });
    }
  };

  const handleDecide = async (decision: "approve" | "reject") => {
    if (!live.jobId) return;
    setDeciding(true);
    try {
      await api.submitDecision(live.jobId, { decision });
      const s = await api.getJobStatus(live.jobId);
      setLive((prev) => ({ ...prev, status: s.status }));
      stopPoll();
    } catch {}
    setDeciding(false);
  };

  const isPending = live.status === "pending";
  const isDone = ["approved", "rejected", "auto_approved", "timeout", "error"].includes(live.status);

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <button className="w-full text-left p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800 dark:bg-zinc-800/50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 px-2 py-0.5 rounded font-mono">
              {scenario.connection} / {scenario.action}
            </code>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50/50 space-y-3">
          <pre className="mt-3 bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(scenario.params, null, 2)}
          </pre>

          <div className="flex items-start gap-3">
            <Button size="sm" onClick={handleTest} disabled={live.status === "running" || isPending} className="shrink-0">
              {live.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending…</>
                : <><Play className="h-3.5 w-3.5 mr-1.5" />Live Test</>}
            </Button>

            {live.status !== "idle" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                live.status === "approved" || live.status === "auto_approved" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
                live.status === "rejected" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800" :
                isPending ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800" :
                live.status === "error" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 text-red-800" :
                "bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
              }`}>
                {isPending && (
                  <div className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Waiting for approval… {live.message && <span className="opacity-70">— {live.message}</span>}</span>
                  </div>
                )}
                {(live.status === "approved" || live.status === "auto_approved") && (
                  <div className="flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" /> {live.status === "auto_approved" ? "Auto-approved (no rule)" : "Approved"}</div>
                )}
                {live.status === "rejected" && <div className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5" /> Rejected</div>}
                {live.status === "error" && <div className="flex items-center gap-1"><XCircle className="h-3.5 w-3.5" /> {live.error}</div>}
              </div>
            )}
          </div>

          {isPending && live.jobId && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => handleDecide("approve")} disabled={deciding} className="flex-1 bg-green-600 hover:bg-green-700 text-white">
                {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5 mr-1" />} Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => handleDecide("reject")} disabled={deciding} className="flex-1 border-red-200 text-red-600 hover:bg-red-50 dark:bg-red-950/30">
                {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <XCircle className="h-3.5 w-3.5 mr-1" />} Reject
              </Button>
            </div>
          )}

          {isDone && (
            <button className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-600 dark:text-zinc-400" onClick={() => setLive({ status: "idle" })}>
              <RefreshCw className="h-3 w-3" /> Test again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── My Agents tab ─────────────────────────────────────────────────────────────

interface MyAgent {
  id: string;
  name: string;
  description?: string;
  icon: string;
  created_at: string;
  scenarios: MyAgentScenario[];
}

function MyAgentsTab() {
  const [agents, setAgents] = useState<MyAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getMyAgents();
      setAgents(data);
      if (data.length > 0 && !activeId) setActiveId(data[0].id);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await api.deleteMyAgent(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      if (activeId === id) setActiveId(agents.find((a) => a.id !== id)?.id ?? null);
    } catch {}
    setDeleting(null);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-16 justify-center text-zinc-400">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading your agents…
      </div>
    );
  }

  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-2xl mb-4">
          <Bot className="h-10 w-10 text-zinc-400" />
        </div>
        <h3 className="text-base font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-1">No agents yet</h3>
        <p className="text-sm text-zinc-400 mb-4 max-w-xs">
          Go to Connect Agent, configure your connection and action, then save it as an agent.
        </p>
        <a
          href="/connect"
          className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-900 text-white rounded-lg text-sm font-medium hover:bg-zinc-800 transition-colors"
        >
          <Plug className="h-4 w-4" /> Connect Your Agent
        </a>
      </div>
    );
  }

  const active = agents.find((a) => a.id === activeId) ?? agents[0];

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <aside className="w-52 shrink-0">
        <div className="space-y-1 sticky top-6">
          {agents.map((a) => (
            <button
              key={a.id}
              onClick={() => setActiveId(a.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                activeId === a.id ? "bg-zinc-900 text-white" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800"
              }`}
            >
              <AgentIcon icon={a.icon} />
              <span className="truncate">{a.name}</span>
            </button>
          ))}
          <a
            href="/connect"
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800 hover:text-zinc-600 dark:text-zinc-400 transition-colors"
          >
            <Plus className="h-4 w-4 shrink-0" /> Add agent
          </a>
        </div>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                  <AgentIcon icon={active.icon} />
                </div>
                <div>
                  <CardTitle>{active.name}</CardTitle>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{active.description || "No description"}</p>
                </div>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDelete(active.id)}
                disabled={deleting === active.id}
                className="border-red-200 text-red-600 hover:bg-red-50 dark:bg-red-950/30"
              >
                {deleting === active.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              </Button>
            </div>
          </CardHeader>
        </Card>

        {active.scenarios.length === 0 ? (
          <div className="border border-dashed border-zinc-200 dark:border-zinc-700 rounded-xl p-8 text-center text-zinc-400">
            <p className="text-sm">No scenarios yet.</p>
            <a href="/connect" className="text-xs text-zinc-500 dark:text-zinc-400 underline mt-1 inline-block">
              Add a scenario from the Connect Agent page
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {active.scenarios.map((scenario) => (
              <MyScenarioCard key={scenario.id} scenario={scenario} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Bot;
}

export default function AgentsPage() {
  const { user } = useUser();
  const [tab, setTab] = useState<"demo" | "my">("my");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string>("");
  const [settingUp, setSettingUp] = useState<string | null>(null);
  const [setupDone, setSetupDone] = useState<Record<string, boolean>>({});

  const agent = agents.find((a) => a.id === activeId);

  // Fetch demo agents from backend
  useEffect(() => {
    api.getDemoAgents()
      .then((raw: AgentRaw[]) => {
        const resolved = raw.map((a) => ({ ...a, icon: resolveIcon(a.icon) }));
        setAgents(resolved);
        if (resolved.length > 0) setActiveId(resolved[0].id);
      })
      .catch(() => {})
      .finally(() => setAgentsLoading(false));
  }, []);

  // Check which agents are already configured on mount
  useEffect(() => {
    api.getRules().then((rules: any[]) => {
      const ruleNames = rules.map((r: any) => r.name);
      const done: Record<string, boolean> = {};
      for (const [agentId, prefixes] of Object.entries({
        ecommerce: ["[Demo] Stripe charge"],
        hr: ["[Demo] Gmail offer"],
        devops: ["[Demo] GitHub deploy"],
        opensource: ["[Demo] PR merge"],
        research: ["[Demo] AWS compute"],
        fintech: ["[Demo] Payout"],
        comms: ["[Demo] Gmail mass email"],
      })) {
        done[agentId] = (prefixes as string[]).some((p) => ruleNames.some((n: string) => n.startsWith(p)));
      }
      setSetupDone(done);
    }).catch(() => {});
  }, []);

  const handleSetupAgent = async (agentId: string) => {
    setSettingUp(agentId);
    try {
      await api.seedDemoData(agentId, user?.sub || undefined);
      setSetupDone((prev) => ({ ...prev, [agentId]: true }));
    } catch {}
    setSettingUp(null);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Agents</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Seven real-world agents with interactive approval flow diagrams.
          Expand any scenario to see the chain, then hit Check Rule to test against your rules.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-6 border-b border-zinc-200 dark:border-zinc-700">
        <button
          onClick={() => setTab("demo")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === "demo" ? "border-zinc-900 text-zinc-900 dark:text-zinc-100" : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
          }`}
        >
          Demo Agents
        </button>
        <button
          onClick={() => setTab("my")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === "my" ? "border-zinc-900 text-zinc-900 dark:text-zinc-100" : "border-transparent text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"
          }`}
        >
          My Agents
        </button>
      </div>

      {tab === "my" && <MyAgentsTab />}

      {tab === "demo" && agentsLoading && (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
        </div>
      )}

      {tab === "demo" && !agentsLoading && agents.length === 0 && (
        <Card><CardContent className="py-12 text-center">
          <p className="text-zinc-500 dark:text-zinc-400">Failed to load demo agents.</p>
        </CardContent></Card>
      )}

      {tab === "demo" && !agentsLoading && agent && <div className="flex gap-6">
        {/* Sidebar */}
        <aside className="w-52 shrink-0">
          <div className="space-y-1 sticky top-6">
            {agents.map((a) => (
              <button
                key={a.id}
                onClick={() => setActiveId(a.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                  activeId === a.id ? "bg-zinc-900 text-white" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800"
                }`}
              >
                <a.icon className="h-4 w-4 shrink-0" />
                {a.title}
              </button>
            ))}
          </div>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                    <agent.icon className="h-5 w-5 text-zinc-700 dark:text-zinc-300 dark:text-zinc-600" />
                  </div>
                  <div>
                    <CardTitle>{agent.title}</CardTitle>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{agent.description}</p>
                  </div>
                </div>
                {setupDone[agent.id] ? (
                  <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> Ready</Badge>
                ) : (
                <Button
                  size="sm"
                  disabled={settingUp === agent.id}
                  onClick={() => handleSetupAgent(agent.id)}
                >
                  {settingUp === agent.id ? (
                    <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Creating rules &amp; approvers...</>
                  ) : (
                    <>Setup Demo</>
                  )}
                </Button>
                )}
              </div>
            </CardHeader>
            {/* Setup Details */}
            {agent.setupInfo && (
              <CardContent className="border-t border-zinc-100 dark:border-zinc-800 pt-4">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-3">Setup Demo will create:</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <p className="text-xs font-medium text-blue-600 mb-1.5">Connections</p>
                    {agent.setupInfo.filter(s => s.type === "connection").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">{s.name}</code>
                        <span className="text-zinc-400 ml-1">{s.detail}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-amber-600 mb-1.5">Approvers</p>
                    {agent.setupInfo.filter(s => s.type === "approver").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <span className="font-medium">{s.name}</span>
                        <span className="text-zinc-400 ml-1">— {s.detail}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-green-600 mb-1.5">Rules</p>
                    {agent.setupInfo.filter(s => s.type === "rule").map(s => (
                      <div key={s.name} className="text-xs text-zinc-600 dark:text-zinc-400 mb-1">
                        <span className="font-medium">{s.name}</span>
                        <span className="text-zinc-400 ml-1">— {s.detail}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            )}
          </Card>

          <div className="space-y-3">
            {agent.scenarios.map((scenario) => (
              <ScenarioCard key={scenario.title} scenario={scenario} />
            ))}
          </div>
        </div>
      </div>}
    </div>
  );
}

function LiveStep({ done, active, label, error }: { done: boolean; active?: boolean; label: string; error?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
      error ? "bg-red-100 text-red-700 dark:text-red-400" :
      done ? "bg-green-100 text-green-700 dark:text-green-400" :
      active ? "bg-blue-100 text-blue-700 dark:text-blue-400" :
      "bg-zinc-100 dark:bg-zinc-800 text-zinc-400"
    }`}>
      {active && <Loader2 className="h-3 w-3 animate-spin" />}
      {error && <XCircle className="h-3 w-3" />}
      {done && !error && <CheckCircle2 className="h-3 w-3" />}
      {label}
    </span>
  );
}
