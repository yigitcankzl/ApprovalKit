"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Bot, CheckCircle2, XCircle, Loader2, Plus, Trash2, RefreshCw, Play,
  Copy, Check, Eye, EyeOff, ChevronRight, ChevronDown, Plug, Code2,
  Clock, Activity,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

function SecretField({ label, value }: { label: string; value: string }) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">{label}</label>
      <div className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-2">
        <span className="flex-1 text-sm text-zinc-100 font-mono break-all">
          {visible ? value : "\u2022".repeat(Math.min(value.length, 32))}
        </span>
        <button onClick={() => setVisible(v => !v)} className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200">
          {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
        <button onClick={copy} className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200">
          {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

function CopyBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative group">
      <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-4 overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
      <button onClick={copy} className="absolute top-2 right-2 p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

// ── Types ────────────────────────────────────────────────────────────────────

interface MyAgent {
  id: string;
  name: string;
  description?: string;
  icon: string;
  is_active: boolean;
  created_at: string;
  api_key?: string;
  scenarios: MyAgentScenario[];
  trust_score?: number;
  trust_level?: string;
}

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

// ── Scenario card ────────────────────────────────────────────────────────────

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
      <button className="w-full text-left p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors" onClick={() => setExpanded((v) => !v)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded font-mono">
              {scenario.connection} / {scenario.action}
            </code>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{scenario.title}</span>
          </div>
          <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/30 space-y-3">
          <pre className="mt-3 bg-zinc-900 text-zinc-100 text-xs rounded-lg p-3 overflow-x-auto">
            {JSON.stringify(scenario.params, null, 2)}
          </pre>

          <div className="flex items-start gap-3">
            <Button size="sm" onClick={handleTest} disabled={live.status === "running" || isPending} className="shrink-0">
              {live.status === "running"
                ? <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />Sending...</>
                : <><Play className="h-3.5 w-3.5 mr-1.5" />Live Test</>}
            </Button>

            {live.status !== "idle" && (
              <div className={`flex-1 rounded-lg px-3 py-2 text-xs ${
                live.status === "approved" || live.status === "auto_approved" ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300" :
                live.status === "rejected" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300" :
                isPending ? "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300" :
                live.status === "error" ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300" :
                "bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300"
              }`}>
                {isPending && <div className="flex items-center gap-1.5"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Waiting for approval...</div>}
                {(live.status === "approved" || live.status === "auto_approved") && <div className="flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" /> {live.status === "auto_approved" ? "Auto-approved" : "Approved"}</div>}
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
              <Button size="sm" variant="outline" onClick={() => handleDecide("reject")} disabled={deciding} className="flex-1 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30">
                {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <XCircle className="h-3.5 w-3.5 mr-1" />} Reject
              </Button>
            </div>
          )}

          {isDone && (
            <button className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300" onClick={() => setLive({ status: "idle" })}>
              <RefreshCw className="h-3 w-3" /> Test again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  const [agents, setAgents] = useState<MyAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [hmacSecret, setHmacSecret] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  // Create agent
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newAgent, setNewAgent] = useState<{ id: string; api_key: string; name: string } | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setBaseUrl(process.env.NEXT_PUBLIC_API_URL || window.location.origin.replace(":3000", ":8000"));
    }
    Promise.all([
      api.getMyAgents().then((a: MyAgent[]) => {
        setAgents(a);
        if (a.length > 0) setActiveId(a[0].id);
      }).catch(() => {}),
      api.getCredentials().then((c: any) => {
        if (c?.hmac_secret) setHmacSecret(c.hmac_secret);
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await api.createMyAgent({ name: name.trim() });
      setNewAgent({ id: res.id, api_key: res.api_key, name: name.trim() });
      const updated = await api.getMyAgents();
      setAgents(updated);
      setActiveId(res.id);
      setName("");
    } catch {}
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await api.deleteMyAgent(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
      if (activeId === id) setActiveId(agents.find((a) => a.id !== id)?.id ?? null);
    } catch {}
    setDeleting(null);
  };

  const envSnippet = `export APPROVALKIT_URL=${baseUrl}
export APPROVALKIT_API_KEY=ak_...
export APPROVALKIT_HMAC_SECRET=...`;

  const codeSnippet = (agentName: string) =>
`from approvalkit import ApprovalKit
import os

kit = ApprovalKit(
    base_url=os.environ["APPROVALKIT_URL"],
    api_key=os.environ["APPROVALKIT_API_KEY"],
    hmac_secret=os.environ["APPROVALKIT_HMAC_SECRET"],
    user_id="${agentName}",
)

kit.gate("your-connection", "your-action", {"key": "value"})`;

  const [showHowTo, setShowHowTo] = useState(false);
  const [timeline, setTimeline] = useState<any>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);

  const active = agents.find((a) => a.id === activeId);

  // Load timeline when active agent changes
  useEffect(() => {
    if (!activeId) { setTimeline(null); return; }
    setTimelineLoading(true);
    api.getAgentTimeline(activeId, 30)
      .then(setTimeline)
      .catch(() => setTimeline(null))
      .finally(() => setTimelineLoading(false));
  }, [activeId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
          Agents
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-2 text-sm">
          Create agents, get API keys, and test approval flows.
        </p>
      </div>

      {/* Create & Connect — collapsible */}
      <Card className="mb-6">
        <button
          onClick={() => setShowHowTo(v => !v)}
          className="w-full flex items-center justify-between p-5 text-left"
        >
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
              <Plug className="h-4 w-4 text-zinc-600 dark:text-zinc-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Create &amp; Connect Agent</h2>
              <p className="text-xs text-zinc-400">Get an API key and integrate in 3 steps</p>
            </div>
          </div>
          <ChevronDown className={`h-4 w-4 text-zinc-400 transition-transform ${showHowTo ? "rotate-180" : ""}`} />
        </button>
        {showHowTo && (
          <CardContent className="pt-0 px-5 pb-5 space-y-4 border-t border-zinc-100 dark:border-zinc-800">
            {/* Create agent */}
            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">1. Create agent</p>
              <div className="flex gap-2">
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleCreate()}
                  placeholder="e.g. shopping-bot, deploy-agent, hr-assistant"
                  className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
                />
                <Button onClick={handleCreate} disabled={creating || !name.trim()}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Plus className="h-4 w-4 mr-1.5" /> Create</>}
                </Button>
              </div>
              {newAgent && (
                <div className="mt-3 p-3 rounded-xl border border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20 space-y-3">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-sm font-semibold text-green-800 dark:text-green-300">
                        Agent &ldquo;{newAgent.name}&rdquo; created — save this key, shown only once.
                      </p>
                    </div>
                  </div>
                  <SecretField label="API Key" value={newAgent.api_key} />
                  {hmacSecret && <SecretField label="HMAC Secret" value={hmacSecret} />}
                </div>
              )}
            </div>

            {/* Install SDK */}
            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">2. Install SDK</p>
              <CopyBlock code={`pip install "approvalkit @ git+https://github.com/yigitcankzl/ApprovalKit.git#subdirectory=sdk"`} />
            </div>

            {/* Env vars */}
            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">3. Set env vars &amp; use</p>
              <CopyBlock code={envSnippet} />
              <div className="mt-2" />
              <CopyBlock code={codeSnippet(newAgent?.name || active?.name || "my-agent")} />
              <p className="text-xs text-zinc-400 mt-2">
                Set up rules and connections from the <a href="/rules" className="text-blue-500 hover:underline">Rules</a> and <a href="/connections" className="text-blue-500 hover:underline">Connections</a> pages.
              </p>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Agent list + detail */}
      {agents.length === 0 && !newAgent ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="p-4 bg-zinc-100 dark:bg-zinc-800 rounded-2xl mb-4">
            <Bot className="h-10 w-10 text-zinc-400" />
          </div>
          <h3 className="text-base font-semibold text-zinc-700 dark:text-zinc-300 mb-1">No agents yet</h3>
          <p className="text-sm text-zinc-400 max-w-xs">
            Create your first agent above to get an API key and start gating actions.
          </p>
        </div>
      ) : agents.length > 0 && (
        <div className="flex gap-6">
          {/* Sidebar */}
          <aside className="w-52 shrink-0">
            <div className="space-y-1 sticky top-6">
              {agents.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setActiveId(a.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-left transition-colors ${
                    activeId === a.id ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  }`}
                >
                  <div className={`w-2 h-2 rounded-full shrink-0 ${a.is_active ? "bg-green-500" : "bg-zinc-300"}`} />
                  <span className="truncate">{a.name}</span>
                </button>
              ))}
            </div>
          </aside>

          {/* Content */}
          {active && (
            <div className="flex-1 min-w-0">
              <Card className="mb-6">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <CardTitle>{active.name}</CardTitle>
                        {active.trust_score !== undefined && (
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                            active.trust_level === "high"
                              ? "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
                              : active.trust_level === "medium"
                              ? "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800"
                              : "bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800"
                          }`}>
                            Trust {active.trust_score}/100
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">{active.description || "No description"}</p>
                      <p className="text-xs text-zinc-400 font-mono mt-1">{active.id}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDelete(active.id)}
                      disabled={deleting === active.id}
                      className="border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
                    >
                      {deleting === active.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                </CardHeader>
              </Card>

              {active.scenarios && active.scenarios.length > 0 ? (
                <div className="space-y-3">
                  {active.scenarios.map((scenario) => (
                    <MyScenarioCard key={scenario.id} scenario={scenario} />
                  ))}
                </div>
              ) : (
                <div className="border border-dashed border-zinc-200 dark:border-zinc-700 rounded-xl p-8 text-center text-zinc-400">
                  <p className="text-sm">No scenarios configured for this agent.</p>
                  <p className="text-xs mt-1">Use <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">kit.gate()</code> to trigger approvals from your code.</p>
                </div>
              )}

              {/* Agent Activity Timeline */}
              <Card className="mt-6">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-indigo-500" />
                    Activity Timeline
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {timelineLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
                    </div>
                  ) : !timeline || !timeline.timeline || timeline.timeline.length === 0 ? (
                    <div className="text-center py-8 text-zinc-400">
                      <Clock className="h-8 w-8 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">No activity yet</p>
                    </div>
                  ) : (
                    <>
                      {/* Stats Summary */}
                      <div className="grid grid-cols-4 gap-3 mb-4">
                        <div className="rounded-lg bg-zinc-50 dark:bg-zinc-800/50 p-2.5 text-center">
                          <p className="text-lg font-bold text-zinc-900 dark:text-zinc-100">{timeline.stats.total}</p>
                          <p className="text-[10px] text-zinc-400">Total</p>
                        </div>
                        <div className="rounded-lg bg-green-50 dark:bg-green-950/20 p-2.5 text-center">
                          <p className="text-lg font-bold text-green-600 dark:text-green-400">{timeline.stats.approval_rate}%</p>
                          <p className="text-[10px] text-zinc-400">Approval Rate</p>
                        </div>
                        <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 p-2.5 text-center">
                          <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{timeline.stats.avg_risk_score}</p>
                          <p className="text-[10px] text-zinc-400">Avg Risk</p>
                        </div>
                        <div className="rounded-lg bg-purple-50 dark:bg-purple-950/20 p-2.5 text-center">
                          <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
                            {timeline.stats.avg_duration_seconds > 60
                              ? `${Math.round(timeline.stats.avg_duration_seconds / 60)}m`
                              : `${timeline.stats.avg_duration_seconds}s`}
                          </p>
                          <p className="text-[10px] text-zinc-400">Avg Duration</p>
                        </div>
                      </div>

                      {/* Timeline entries */}
                      <div className="relative pl-6 space-y-0">
                        {/* Vertical line */}
                        <div className="absolute left-[9px] top-2 bottom-2 w-px bg-zinc-200 dark:bg-zinc-700" />

                        {timeline.timeline.map((entry: any, i: number) => {
                          const stateColor = entry.state === "approved" || entry.state === "pre_approved" ? "bg-green-500"
                            : entry.state === "rejected" ? "bg-red-500"
                            : entry.state === "blocked" ? "bg-orange-500"
                            : entry.state === "timeout" ? "bg-yellow-500"
                            : "bg-blue-500";
                          const riskColor = entry.risk_level === "critical" ? "text-red-500"
                            : entry.risk_level === "high" ? "text-orange-500"
                            : entry.risk_level === "medium" ? "text-yellow-500"
                            : "text-green-500";

                          return (
                            <div key={entry.job_id} className="relative flex items-start gap-3 pb-3">
                              {/* Dot on timeline */}
                              <div className={`absolute left-[-18px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-white dark:border-zinc-900 ${stateColor}`} />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <code className="text-[10px] bg-zinc-100 dark:bg-zinc-800 rounded px-1.5 py-0.5 text-zinc-600 dark:text-zinc-400">
                                    {entry.connection}:{entry.action}
                                  </code>
                                  <Badge variant={
                                    entry.state === "approved" || entry.state === "pre_approved" ? "success"
                                    : entry.state === "rejected" ? "danger"
                                    : entry.state === "blocked" ? "warning"
                                    : "default"
                                  } className="text-[9px]">
                                    {entry.state.replace(/_/g, " ")}
                                  </Badge>
                                  <span className={`text-[10px] font-mono ${riskColor}`}>
                                    Risk {entry.risk_score}
                                  </span>
                                  {entry.duration_seconds !== null && (
                                    <span className="text-[10px] text-zinc-400">
                                      {entry.duration_seconds > 60
                                        ? `${Math.round(entry.duration_seconds / 60)}m`
                                        : `${entry.duration_seconds}s`}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="text-[10px] text-zinc-400">
                                    {new Date(entry.timestamp).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                                  </span>
                                  {entry.rejection_reason && (
                                    <span className="text-[10px] text-red-400 truncate max-w-xs">
                                      {entry.rejection_reason}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
