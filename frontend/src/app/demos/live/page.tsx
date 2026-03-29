"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DemoAgent } from "@/components/scenario-runner";
import {
  ArrowLeft, Banknote, Bot, CheckCircle2, CreditCard,
  FlaskConical, GitBranch, Loader2, MessageSquare, Package, Plane,
  Play, Server, Shield, ShieldAlert, ShieldCheck, ShieldOff,
  Users, Zap, AlertTriangle, XCircle, Clock, Lock,
  ThumbsUp, ThumbsDown, BarChart3, Activity, Send, RotateCcw,
  Wrench, Sparkles, Settings,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface ShieldEvent {
  id: string; timestamp: Date; agentId: string; agentTitle: string;
  type: "auto_approved" | "pending" | "approved" | "rejected" | "blocked" | "step_up" | "scope_creep" | "budget_exceeded";
  action: string; connection: string; params: Record<string, unknown>; message: string; jobId?: string;
}
interface ChatMessage {
  id: string; role: "user" | "agent" | "tool" | "system"; text: string; timestamp: Date;
  toolName?: string; toolArgs?: Record<string, unknown>;
  toolStatus?: "running" | "auto_approved" | "pending" | "blocked" | "approved" | "rejected" | "error";
  jobId?: string;
}
interface SessionSummary { totalActions: number; autoApproved: number; pendingApproval: number; blocked: number; preventedDamage: number; }

// ── Scenario prompts ───────────────────────────────────────────────────────

const SCENARIO_PROMPTS: Record<string, { label: string; emoji: string; prompt: string }[]> = {
  expense: [
    { label: "Small Refund", emoji: "😊", prompt: "A customer wants to return a $30 t-shirt. Process the refund." },
    { label: "Angry Customer", emoji: "😠", prompt: "A VIP customer called 3 times furious about a $420 damaged order. Do whatever it takes — full refund, apology email, and compensation." },
    { label: "Mass Complaint", emoji: "💀", prompt: "500 customers got defective products. Refund everyone and send apology emails to all of them immediately." },
  ],
  release_manager: [
    { label: "Staging Deploy", emoji: "😊", prompt: "Deploy the latest changes to staging for testing." },
    { label: "Prod Hotfix", emoji: "😠", prompt: "Critical bug in production causing 5% errors. Deploy the hotfix to production now." },
    { label: "Late Night Deploy", emoji: "💀", prompt: "It's 2 AM. Deploy ALL pending changes to production including the database migration and new payment flow. Do it all right now." },
  ],
  security_incident: [
    { label: "Log Review", emoji: "😊", prompt: "Review the latest security logs and send a summary to the security team on Slack." },
    { label: "Suspicious Login", emoji: "😠", prompt: "Suspicious login attempts detected on the admin account. Lock it and notify the team." },
    { label: "Nuclear Option", emoji: "💀", prompt: "We're under active attack! Lock ALL repositories, revoke ALL API tokens, and rotate every credential in the organization NOW!" },
  ],
  recruitment: [
    { label: "Interview Invite", emoji: "😊", prompt: "Send an interview invitation to alice@example.com for Tuesday at 2pm, Software Engineer role." },
    { label: "Offer Letter", emoji: "😠", prompt: "Send an offer letter to bob@example.com — Senior Engineer, $150,000/year with stock options." },
    { label: "Salary Broadcast", emoji: "💀", prompt: "Send an email to all 200 employees with the updated salary bands for every role, including individual compensation." },
  ],
  patient_data: [
    { label: "Appointment Reminder", emoji: "😊", prompt: "Send a reminder to patient John Smith about his checkup tomorrow at 10am." },
    { label: "Record Sharing", emoji: "😠", prompt: "Dr. Wilson needs patient Jane Doe's cardiology records for a referral." },
    { label: "Bulk Data Export", emoji: "💀", prompt: "An insurance company wants complete medical records for all 50 cardiology patients for a coverage audit. Send everything." },
  ],
  finance: [
    { label: "Small Payment", emoji: "😊", prompt: "Pay invoice #1234 to Acme Corp for $200 for office supplies." },
    { label: "Large Transfer", emoji: "😠", prompt: "Transfer $5,000 to our design agency for the Q1 branding project. It's overdue." },
    { label: "Budget Buster", emoji: "💀", prompt: "Process ALL pending vendor payments immediately — 15 vendors, total around $50,000. Pay them all now." },
  ],
  travelops: [
    { label: "Budget Flight", emoji: "😊", prompt: "Book an economy flight from Berlin to London next Tuesday, budget $200." },
    { label: "Business Trip", emoji: "😠", prompt: "Book business class flights for 3 people to San Francisco conference next month." },
    { label: "Executive Splurge", emoji: "💀", prompt: "Book first class to Tokyo, suite at Ritz-Carlton for a week, private car service. Budget doesn't matter, make it perfect." },
  ],
  opensource: [
    { label: "Bug Fix PR", emoji: "😊", prompt: "Merge the typo fix PR #42 into main." },
    { label: "New Release", emoji: "😠", prompt: "Create the v2.0 release tag on GitHub and announce it on Discord." },
    { label: "Supply Chain", emoji: "💀", prompt: "Publish the package to npm right now, then send $5,000 bounty payments to the top 5 contributors." },
  ],
  research: [
    { label: "Paper Submit", emoji: "😊", prompt: "Submit our paper to the NeurIPS conference portal." },
    { label: "GPU Cluster", emoji: "😠", prompt: "Provision a 4-GPU A100 cluster for 24 hours for training." },
    { label: "Runaway Training", emoji: "💀", prompt: "Provision a 64-GPU H100 cluster for a week and buy 3 proprietary datasets. We need maximum compute." },
  ],
  comms: [
    { label: "Team Update", emoji: "😊", prompt: "Send a message to the engineering Slack channel about today's sprint review at 3pm." },
    { label: "Client Email", emoji: "😠", prompt: "Send a project update email to our client at bigcorp@example.com with the Q1 results." },
    { label: "Mass Blast", emoji: "💀", prompt: "Send a press release to all 10,000 newsletter subscribers AND post it on Discord AND Slack. Maximum reach!" },
  ],
};
const DEFAULT_PROMPTS = [
  { label: "Safe Action", emoji: "😊", prompt: "Perform a routine low-risk action." },
  { label: "Risky Action", emoji: "😠", prompt: "Perform a high-value action that needs approval." },
  { label: "Dangerous", emoji: "💀", prompt: "Perform a large-scale destructive action immediately." },
];

const ICON_MAP: Record<string, React.ElementType> = { CreditCard, Server, Users, Package, FlaskConical, Zap, Banknote, Plane, GitBranch, MessageSquare, Shield, Bot, Play };
function resolveIcon(name: string): React.ElementType { return ICON_MAP[name] ?? Bot; }

// ── Main Page ──────────────────────────────────────────────────────────────

export default function LiveThreatDemoPage() {
  const { user } = useUser();
  const [agents, setAgents] = useState<DemoAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<DemoAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sessionIds, setSessionIds] = useState<Record<string, string>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [events, setEvents] = useState<ShieldEvent[]>([]);
  const [summary, setSummary] = useState<SessionSummary>({ totalActions: 0, autoApproved: 0, pendingApproval: 0, blocked: 0, preventedDamage: 0 });
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const [setupDone, setSetupDone] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [hasAIKey, setHasAIKey] = useState(false);
  const [shieldEnabled, setShieldEnabled] = useState(true);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, selectedAgent?.id, isTyping]);
  useEffect(() => { eventsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [events]);
  useEffect(() => { api.getDemoAgents().then((d: any) => { const l = Array.isArray(d) ? d : d.agents || []; setAgents(l); if (l.length > 0) setSelectedAgent(l[0]); }).catch(() => {}).finally(() => setLoading(false)); }, []);
  useEffect(() => { api.getRules().then((r: any[]) => setSetupDone(r.length > 0)).catch(() => {}); api.getAIKeyStatus().then((s: any) => setHasAIKey(!!s?.has_ai_api_key)).catch(() => {}); }, []);

  const currentMessages = selectedAgent ? (messages[selectedAgent.id] || []) : [];
  const addMessage = useCallback((agentId: string, msg: Omit<ChatMessage, "id" | "timestamp">) => { const m: ChatMessage = { ...msg, id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: new Date() }; setMessages(prev => ({ ...prev, [agentId]: [...(prev[agentId] || []), m] })); return m.id; }, []);
  const updateMessage = useCallback((agentId: string, msgId: string, updates: Partial<ChatMessage>) => { setMessages(prev => ({ ...prev, [agentId]: (prev[agentId] || []).map(m => m.id === msgId ? { ...m, ...updates } : m) })); }, []);
  const addEvent = useCallback((evt: Omit<ShieldEvent, "id" | "timestamp">) => {
    const event: ShieldEvent = { ...evt, id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: new Date() };
    setEvents(prev => [...prev, event]);
    setSummary(prev => {
      const next = { ...prev, totalActions: prev.totalActions + 1 };
      if (evt.type === "auto_approved" || evt.type === "approved") next.autoApproved++;
      else if (["blocked", "budget_exceeded", "scope_creep"].includes(evt.type)) { next.blocked++; next.preventedDamage += Number(evt.params?.amount_usd) || 0; }
      else if (evt.type === "pending" || evt.type === "step_up") next.pendingApproval++;
      return next;
    });
  }, []);
  const resetSummary = () => { setEvents([]); setSummary({ totalActions: 0, autoApproved: 0, pendingApproval: 0, blocked: 0, preventedDamage: 0 }); };
  const handleSeedAll = async () => { setSeeding(true); try { await api.seedDemoData(undefined, user?.sub); setSetupDone(true); } catch {} setSeeding(false); };

  const sendMessage = async (text: string) => {
    if (!selectedAgent || isTyping || !text.trim()) return;
    const agentId = selectedAgent.id, agentTitle = selectedAgent.title;
    addMessage(agentId, { role: "user", text: text.trim() }); setInputText(""); setIsTyping(true);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const sessionId = sessionIds[agentId] || "";

    try {
      // Use streaming endpoint — tool results arrive one by one in real-time
      const resp = await fetch(`${API_BASE}/api/v1/demo/agents/${agentId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(user?.sub ? { "X-User-Sub": user.sub as string } : {}) },
        body: JSON.stringify({ message: text.trim(), agent_title: agentTitle, session_id: sessionId }),
      });

      if (!resp.ok || !resp.body) throw new Error("Stream failed");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let agentMsgId: string | null = null;
      let agentText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === "thinking") {
              // Already showing typing indicator
            }
            else if (data.type === "token") {
              // Streaming text from LLM
              agentText += data.content;
              if (!agentMsgId) {
                agentMsgId = addMessage(agentId, { role: "agent", text: agentText });
              } else {
                updateMessage(agentId, agentMsgId, { text: agentText });
              }
            }
            else if (data.type === "tool_call") {
              // LLM is calling a tool — show "running" card
              addMessage(agentId, { role: "tool", text: `${data.name}`, toolName: data.name, toolArgs: data.args, toolStatus: "running" });
            }
            else if (data.type === "tool_result") {
              // Tool executed — show result in shield + update chat card
              const r = data.result || {};
              const status = r.status || "auto_approved";
              const mapped = { connection: r.connection || "unknown", action: r.action || data.name, params: r.params || data.args || {} };

              // Update the last "running" tool card
              setMessages(prev => {
                const msgs = prev[agentId] || [];
                const lastToolIdx = msgs.findLastIndex(m => m.role === "tool" && m.toolStatus === "running");
                if (lastToolIdx >= 0) {
                  const updated = [...msgs];
                  updated[lastToolIdx] = {
                    ...updated[lastToolIdx],
                    text: `${mapped.connection}/${mapped.action}`,
                    toolArgs: mapped.params,
                    toolStatus: status === "auto_approved" ? "auto_approved" : status === "pending" ? "pending" : "blocked",
                    jobId: r.job_id,
                  };
                  return { ...prev, [agentId]: updated };
                }
                return prev;
              });

              // Shield event
              if (!shieldEnabled) {
                addEvent({ agentId, agentTitle, type: "auto_approved", action: mapped.action, connection: mapped.connection, params: mapped.params, message: `EXECUTED WITHOUT OVERSIGHT — ${mapped.action}` });
              } else {
                let eventType: ShieldEvent["type"] = "auto_approved";
                if (status === "pending") eventType = "pending"; else if (status === "blocked") eventType = "blocked";
                const rn = r.rule_name || "";
                if ((rn.toLowerCase().includes("large") || rn.toLowerCase().includes("cfo")) && status === "pending") eventType = "step_up";
                if (rn.toLowerCase().includes("mass") || rn.toLowerCase().includes("scope")) eventType = "scope_creep";
                addEvent({ agentId, agentTitle, type: eventType, action: mapped.action, connection: mapped.connection, params: mapped.params, message: r.message || `${mapped.action} — ${status}`, jobId: r.job_id });
                if (status === "pending" && r.job_id) {
                  // Find tool msg id for polling
                  const msgs = messages[agentId] || [];
                  const toolMsg = msgs.findLast((m: ChatMessage) => m.jobId === r.job_id);
                  if (toolMsg) pollJob(agentId, r.job_id, toolMsg.id);
                }
              }
            }
            else if (data.type === "waiting_approval") {
              // Backend is waiting for human approval — no action needed, UI already shows pending
            }
            else if (data.type === "approval_resolved") {
              // Approval decision came through — update tool card + shield event
              const jid = data.job_id;
              const st = data.status as "approved" | "rejected" | "blocked";
              setMessages(prev => ({
                ...prev,
                [agentId]: (prev[agentId] || []).map(m =>
                  m.jobId === jid ? { ...m, toolStatus: st } : m
                ),
              }));
              setEvents(prev => prev.map(e =>
                e.jobId === jid ? { ...e, type: st } : e
              ));
              if (st === "approved") {
                setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
              } else {
                setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1 }));
              }
            }
            else if (data.type === "done") {
              if (data.session_id) setSessionIds(prev => ({ ...prev, [agentId]: data.session_id }));
              // If no streaming text came through, show the response
              if (!agentMsgId && data.response) {
                addMessage(agentId, { role: "agent", text: data.response });
              }
            }
            else if (data.type === "error") {
              addMessage(agentId, { role: "system", text: data.message || "An error occurred" });
            }
          } catch {}
        }
      }
    } catch (e: any) { addMessage(agentId, { role: "system", text: `Error: ${e.message}` }); }
    setIsTyping(false); inputRef.current?.focus();
  };

  const pollJob = async (agentId: string, jobId: string, toolMsgId: string) => {
    let attempts = 0;
    const poll = setInterval(async () => {
      try {
        const s = await api.getJobStatus(jobId);
        if (["approved", "rejected", "timeout", "blocked"].includes(s.status)) {
          clearInterval(poll);
          const ns = s.status === "approved" ? "approved" : s.status === "rejected" ? "rejected" : "blocked";
          updateMessage(agentId, toolMsgId, { toolStatus: ns as any });
          setEvents(prev => prev.map(e => e.jobId === jobId ? { ...e, type: ns as any } : e));
          if (ns === "approved") setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
          else setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1 }));
        }
      } catch {} if (++attempts > 60) clearInterval(poll);
    }, 2000);
  };

  const handleApprove = async (jobId: string, eventId: string) => {
    try { await api.approveJob(jobId); } catch {}
    setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "approved" as const } : e));
    setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
    if (selectedAgent) setMessages(prev => ({ ...prev, [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m => m.jobId === jobId ? { ...m, toolStatus: "approved" as const } : m) }));
  };
  const handleReject = async (jobId: string, eventId: string) => {
    const evt = events.find(e => e.id === eventId); const amt = Number(evt?.params?.amount_usd) || 0;
    try { await api.rejectJob(jobId); } catch {}
    setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "rejected" as const } : e));
    setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1, preventedDamage: prev.preventedDamage + amt }));
    if (selectedAgent) setMessages(prev => ({ ...prev, [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m => m.jobId === jobId ? { ...m, toolStatus: "rejected" as const } : m) }));
  };
  const handleReset = () => { if (!selectedAgent) return; const sid = sessionIds[selectedAgent.id]; if (sid) api.clearAgentSession(selectedAgent.id, sid).catch(() => {}); setMessages(prev => ({ ...prev, [selectedAgent.id]: [] })); setSessionIds(prev => ({ ...prev, [selectedAgent.id]: "" })); };
  const scenarios = selectedAgent ? (SCENARIO_PROMPTS[selectedAgent.id] || DEFAULT_PROMPTS) : [];

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" /></div>;

  return (
    <div className="space-y-6">
      {/* Header — same pattern as dashboard */}
      <div>
        <div className="flex items-center gap-3">
          <a href="/demos" className="text-zinc-400 hover:text-zinc-900 dark:hover:text-white transition-colors"><ArrowLeft className="h-5 w-5" /></a>
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-red-600 via-orange-600 to-amber-600 dark:from-red-400 dark:via-orange-400 dark:to-amber-400">
              Live Threat Demo
            </h1>
            <p className="text-zinc-500 dark:text-zinc-400 mt-1 text-sm">Watch AI agents act autonomously — see what ApprovalKit catches in real-time</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => { setShieldEnabled(prev => !prev); resetSummary(); }}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all border ${
            shieldEnabled
              ? "bg-green-50/60 dark:bg-green-950/10 text-green-700 dark:text-green-400 border-green-200/60 dark:border-green-900/40"
              : "bg-red-50/60 dark:bg-red-950/20 text-red-700 dark:text-red-400 border-red-200/60 dark:border-red-900/40 animate-pulse"
          }`}
        >
          {shieldEnabled ? <><ShieldCheck className="h-4 w-4" /> Shield ON</> : <><ShieldOff className="h-4 w-4" /> Shield OFF</>}
        </button>

        {!setupDone && (
          <Button onClick={handleSeedAll} disabled={seeding} className="shadow-md hover:shadow-lg transition-shadow">
            {seeding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />} Setup Demo Data
          </Button>
        )}

        <div className="flex-1" />

        {/* Stat pills — dashboard style */}
        <div className="flex items-center gap-2">
          <div className="rounded-xl border border-green-200/60 dark:border-green-900/40 bg-green-50/60 dark:bg-green-950/10 px-3 py-1.5 flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
            <span className="text-sm font-bold text-green-700 dark:text-green-400 tabular-nums">{summary.autoApproved}</span>
          </div>
          <div className="rounded-xl border border-amber-200/60 dark:border-amber-900/40 bg-amber-50/60 dark:bg-amber-950/10 px-3 py-1.5 flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            <span className="text-sm font-bold text-amber-700 dark:text-amber-400 tabular-nums">{summary.pendingApproval}</span>
          </div>
          <div className="rounded-xl border border-red-200/60 dark:border-red-900/40 bg-red-50/60 dark:bg-red-950/10 px-3 py-1.5 flex items-center gap-1.5">
            <ShieldOff className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
            <span className="text-sm font-bold text-red-700 dark:text-red-400 tabular-nums">{summary.blocked}</span>
          </div>
          {summary.preventedDamage > 0 && (
            <div className="rounded-xl border border-rose-200/60 dark:border-rose-900/40 bg-rose-50/60 dark:bg-rose-950/10 px-3 py-1.5">
              <span className="text-sm font-bold text-rose-700 dark:text-rose-400 tabular-nums">${summary.preventedDamage.toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Agent Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {agents.map(agent => {
          const Icon = resolveIcon(agent.icon);
          const isActive = selectedAgent?.id === agent.id;
          return (
            <button key={agent.id} onClick={() => setSelectedAgent(agent)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm font-medium whitespace-nowrap transition-all border ${
                isActive
                  ? "bg-blue-50/60 dark:bg-blue-950/20 text-blue-700 dark:text-blue-300 border-blue-200/60 dark:border-blue-800/50"
                  : "text-zinc-500 dark:text-zinc-400 border-zinc-200/40 dark:border-zinc-800/40 hover:border-zinc-300 dark:hover:border-zinc-600"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{agent.title.replace(" Agent", "").replace(" Approval", "")}</span>
            </button>
          );
        })}
      </div>

      {/* Split Screen */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ height: "calc(100vh - 320px)" }}>

        {/* LEFT: Agent Chat */}
        <div className="rounded-xl border border-zinc-200/60 dark:border-zinc-800/60 bg-white/50 dark:bg-zinc-900/20 flex flex-col overflow-hidden">
          {/* Scenarios */}
          {selectedAgent && (
            <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-200/40 dark:border-zinc-800/40">
              {scenarios.map((s, i) => (
                <button key={i} onClick={() => sendMessage(s.prompt)} disabled={isTyping || !setupDone || !hasAIKey}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-zinc-200/60 dark:border-zinc-700/40 hover:border-blue-400 dark:hover:border-blue-600 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <span>{s.emoji}</span><span>{s.label}</span>
                </button>
              ))}
              <div className="flex-1" />
              <button onClick={handleReset} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1.5 rounded-lg" title="Reset"><RotateCcw className="h-4 w-4" /></button>
            </div>
          )}

          {/* Chat */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {!hasAIKey && setupDone && (
              <div className="p-4 rounded-xl border border-amber-200/60 dark:border-amber-900/40 bg-amber-50/60 dark:bg-amber-950/10 text-amber-700 dark:text-amber-400 text-sm">
                <Settings className="h-4 w-4 inline mr-2" />No AI provider configured. <a href={`/demos/${selectedAgent?.id || agents[0]?.id}`} className="underline">Set up Ollama or API key</a>
              </div>
            )}
            {!setupDone && (
              <div className="p-4 rounded-xl border border-amber-200/60 dark:border-amber-900/40 bg-amber-50/60 dark:bg-amber-950/10 text-amber-700 dark:text-amber-400 text-sm">
                <AlertTriangle className="h-4 w-4 inline mr-2" />Click &quot;Setup Demo Data&quot; to create approval rules.
              </div>
            )}
            {currentMessages.length === 0 && hasAIKey && setupDone && (
              <div className="flex flex-col items-center justify-center h-full text-zinc-400 space-y-3">
                <Bot className="h-14 w-14 opacity-15" />
                <p className="text-sm font-medium">Pick a scenario or type a message</p>
                <p className="text-xs text-zinc-500">The AI agent will reason and take actions autonomously</p>
              </div>
            )}
            {currentMessages.map(msg => <ChatBubble key={msg.id} message={msg} shieldOff={!shieldEnabled} />)}
            {isTyping && <div className="flex items-center gap-2 text-blue-600 dark:text-blue-400 text-sm"><Loader2 className="h-4 w-4 animate-spin" />Agent is thinking...</div>}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t border-zinc-200/40 dark:border-zinc-800/40">
            <form onSubmit={(e) => { e.preventDefault(); sendMessage(inputText); }} className="flex gap-2">
              <input ref={inputRef} type="text" value={inputText} onChange={(e) => setInputText(e.target.value)}
                placeholder={selectedAgent ? `Tell ${selectedAgent.title} what to do...` : "Select an agent"}
                disabled={isTyping || !setupDone || !hasAIKey}
                className="flex-1 rounded-xl px-4 py-2.5 text-sm border border-zinc-200/60 dark:border-zinc-700/40 bg-white dark:bg-zinc-900/30 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 disabled:opacity-30"
              />
              <Button type="submit" disabled={isTyping || !inputText.trim() || !setupDone || !hasAIKey} className="rounded-xl px-4 shadow-md hover:shadow-lg transition-shadow">
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>

        {/* RIGHT: Shield Panel */}
        <div className={`rounded-xl border flex flex-col overflow-hidden ${
          !shieldEnabled
            ? "border-red-200/60 dark:border-red-900/40 bg-red-50/30 dark:bg-red-950/10"
            : "border-zinc-200/60 dark:border-zinc-800/60 bg-white/50 dark:bg-zinc-900/20"
        }`}>
          <div className={`flex items-center gap-2 px-4 py-2.5 border-b ${!shieldEnabled ? "border-red-200/40 dark:border-red-900/30" : "border-zinc-200/40 dark:border-zinc-800/40"}`}>
            {shieldEnabled
              ? <Shield className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              : <ShieldOff className="h-4 w-4 text-red-600 dark:text-red-400 animate-pulse" />}
            <span className={`text-[11px] font-semibold uppercase tracking-widest ${!shieldEnabled ? "text-red-600 dark:text-red-400" : "text-zinc-500 dark:text-zinc-400"}`}>
              {shieldEnabled ? "ApprovalKit Shield" : "No Protection"}
            </span>
            <div className="flex-1" />
            <span className="text-[11px] text-zinc-400 tabular-nums">{events.length} events</span>
            {events.length > 0 && <button onClick={resetSummary} className="text-[11px] text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors ml-2">Clear</button>}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-400">
                <Activity className="h-14 w-14 mb-3 opacity-10" />
                <p className="text-sm">No events yet</p>
                <p className="text-xs text-zinc-500 mt-1">Run a scenario to see the Shield in action</p>
              </div>
            ) : events.map(event => <EventCard key={event.id} event={event} onApprove={handleApprove} onReject={handleReject} shieldOff={!shieldEnabled} />)}
            <div ref={eventsEndRef} />
          </div>

          {events.length > 0 && (
            <div className={`px-4 py-3 border-t ${!shieldEnabled ? "border-red-200/40 dark:border-red-900/30" : "border-zinc-200/40 dark:border-zinc-800/40"}`}>
              {shieldEnabled ? (
                <div className="grid grid-cols-4 gap-3 text-center">
                  {[
                    { l: "Total", v: summary.totalActions, c: "text-zinc-700 dark:text-zinc-300" },
                    { l: "Approved", v: summary.autoApproved, c: "text-green-600 dark:text-green-400" },
                    { l: "Pending", v: summary.pendingApproval, c: "text-amber-600 dark:text-amber-400" },
                    { l: "Blocked", v: summary.blocked, c: "text-red-600 dark:text-red-400" },
                  ].map(s => (
                    <div key={s.l}>
                      <div className={`text-xl font-bold tabular-nums ${s.c}`}>{s.v}</div>
                      <div className="text-[10px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500">{s.l}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-1">
                  <div className="flex items-center justify-center gap-2 text-red-600 dark:text-red-400">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-sm font-bold">ALL {summary.totalActions} ACTIONS — NO OVERSIGHT</span>
                  </div>
                  <p className="text-xs text-red-500/60 mt-1">
                    Unreviewed spend: <span className="font-bold">${events.reduce((s, e) => s + (Number(e.params?.amount_usd) || 0), 0).toLocaleString()}</span>
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Chat Bubble ──────────────────────────────────────────────────────────

function ChatBubble({ message, shieldOff }: { message: ChatMessage; shieldOff?: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm shadow-sm">{message.text}</div>
      </div>
    );
  }
  if (message.role === "tool") {
    const cfgs: Record<string, { color: string; border: string; bg: string; label: string; icon: React.ElementType }> = {
      running:       { color: "text-blue-600 dark:text-blue-400",   border: "border-blue-200/60 dark:border-blue-900/40",   bg: "bg-blue-50/60 dark:bg-blue-950/10",     label: "EXECUTING...", icon: Loader2 },
      auto_approved: { color: shieldOff ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400", border: shieldOff ? "border-red-200/60 dark:border-red-900/40" : "border-green-200/60 dark:border-green-900/40", bg: shieldOff ? "bg-red-50/60 dark:bg-red-950/10" : "bg-green-50/60 dark:bg-green-950/10", label: shieldOff ? "NO APPROVAL" : "AUTO-APPROVED", icon: shieldOff ? AlertTriangle : CheckCircle2 },
      pending:       { color: "text-amber-600 dark:text-amber-400", border: "border-amber-200/60 dark:border-amber-900/40", bg: "bg-amber-50/60 dark:bg-amber-950/10",   label: "AWAITING APPROVAL", icon: Clock },
      blocked:       { color: "text-red-600 dark:text-red-400",     border: "border-red-200/60 dark:border-red-900/40",     bg: "bg-red-50/60 dark:bg-red-950/10",       label: "BLOCKED", icon: ShieldOff },
      approved:      { color: "text-green-600 dark:text-green-400", border: "border-green-200/60 dark:border-green-900/40", bg: "bg-green-50/60 dark:bg-green-950/10",   label: "APPROVED", icon: ThumbsUp },
      rejected:      { color: "text-red-600 dark:text-red-400",     border: "border-red-200/60 dark:border-red-900/40",     bg: "bg-red-50/60 dark:bg-red-950/10",       label: "REJECTED", icon: ThumbsDown },
      error:         { color: "text-red-600 dark:text-red-400",     border: "border-red-200/60 dark:border-red-900/40",     bg: "bg-red-50/60 dark:bg-red-950/10",       label: "ERROR", icon: XCircle },
    };
    const c = cfgs[message.toolStatus || "running"];
    const Icon = c.icon;
    const amt = Number(message.toolArgs?.amount_usd) || Number(message.toolArgs?.amount);
    return (
      <div className={`rounded-xl border ${c.border} ${c.bg} p-3 mx-2`}>
        <div className="flex items-center gap-2">
          <Wrench className="h-3.5 w-3.5 text-zinc-400" />
          <span className="text-xs font-mono text-zinc-500 dark:text-zinc-400">{message.text}</span>
          <div className="flex-1" />
          <span className={`flex items-center gap-1 text-[10px] font-bold ${c.color}`}>
            <Icon className={`h-3 w-3 ${message.toolStatus === "pending" ? "animate-spin" : ""}`} />{c.label}
          </span>
        </div>
        {message.toolArgs && (
          <div className="text-[11px] text-zinc-500 font-mono pl-5 mt-1 space-y-0.5">
            {Object.entries(message.toolArgs).slice(0, 4).map(([k, v]) => (
              <div key={k}><span className="text-zinc-400 dark:text-zinc-600">{k}:</span> <span className="text-zinc-600 dark:text-zinc-400">{typeof v === "string" ? v : JSON.stringify(v)}</span></div>
            ))}
          </div>
        )}
        {amt > 0 && <div className="mt-1 pl-5"><span className={`text-xs font-mono font-bold ${c.color}`}>${amt.toLocaleString()}</span></div>}
      </div>
    );
  }
  if (message.role === "system") return <div className="text-center"><span className="text-xs text-zinc-400 px-3 py-1 rounded-full border border-zinc-200/40 dark:border-zinc-800/40">{message.text}</span></div>;
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex gap-2.5">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-600 to-emerald-500 flex items-center justify-center mt-0.5">
          <Sparkles className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="bg-zinc-100 dark:bg-zinc-800/40 text-zinc-800 dark:text-zinc-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-sm">{message.text}</div>
      </div>
    </div>
  );
}

// ── Event Card ────────────────────────────────────────────────────────────

function EventCard({ event, onApprove, onReject, shieldOff }: {
  event: ShieldEvent; onApprove: (j: string, e: string) => void; onReject: (j: string, e: string) => void; shieldOff?: boolean;
}) {
  const cfgs: Record<string, { icon: React.ElementType; color: string; border: string; bg: string; label: string }> = {
    auto_approved:   { icon: shieldOff ? AlertTriangle : CheckCircle2, color: shieldOff ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400", border: shieldOff ? "border-red-200/60 dark:border-red-900/40" : "border-green-200/60 dark:border-green-900/40", bg: shieldOff ? "bg-red-50/60 dark:bg-red-950/10" : "bg-green-50/60 dark:bg-green-950/10", label: shieldOff ? "NO REVIEW" : "AUTO-APPROVED" },
    pending:         { icon: Clock, color: "text-amber-600 dark:text-amber-400", border: "border-amber-200/60 dark:border-amber-900/40", bg: "bg-amber-50/60 dark:bg-amber-950/10", label: "PENDING" },
    approved:        { icon: ThumbsUp, color: "text-green-600 dark:text-green-400", border: "border-green-200/60 dark:border-green-900/40", bg: "bg-green-50/60 dark:bg-green-950/10", label: "APPROVED" },
    rejected:        { icon: ThumbsDown, color: "text-red-600 dark:text-red-400", border: "border-red-200/60 dark:border-red-900/40", bg: "bg-red-50/60 dark:bg-red-950/10", label: "REJECTED" },
    blocked:         { icon: ShieldOff, color: "text-orange-600 dark:text-orange-400", border: "border-orange-200/60 dark:border-orange-900/40", bg: "bg-orange-50/60 dark:bg-orange-950/10", label: "BLOCKED" },
    step_up:         { icon: ShieldAlert, color: "text-amber-600 dark:text-amber-400", border: "border-amber-200/60 dark:border-amber-900/40", bg: "bg-amber-50/60 dark:bg-amber-950/10", label: "STEP-UP" },
    scope_creep:     { icon: AlertTriangle, color: "text-red-600 dark:text-red-400", border: "border-red-200/60 dark:border-red-900/40", bg: "bg-red-50/60 dark:bg-red-950/10", label: "SCOPE CREEP" },
    budget_exceeded: { icon: Lock, color: "text-red-600 dark:text-red-400", border: "border-red-200/60 dark:border-red-900/40", bg: "bg-red-50/60 dark:bg-red-950/10", label: "BUDGET" },
  };
  const c = cfgs[event.type] || cfgs.blocked;
  const Icon = c.icon;
  const amt = Number(event.params?.amount_usd) || Number(event.params?.amount);
  return (
    <div className={`rounded-xl border ${c.border} ${c.bg} p-3 transition-all`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 flex-shrink-0 ${c.color}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold uppercase tracking-wide ${c.color}`}>{c.label}</span>
            <span className="text-[10px] text-zinc-400 tabular-nums">{event.timestamp.toLocaleTimeString()}</span>
          </div>
          <p className="text-xs text-zinc-600 dark:text-zinc-300 mt-0.5 truncate">{event.message}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-zinc-400 font-mono">{event.connection}/{event.action}</span>
            {amt > 0 && <span className={`text-[10px] font-mono font-bold ${c.color}`}>${amt.toLocaleString()}</span>}
          </div>
        </div>
      </div>
      {(event.type === "pending" || event.type === "step_up") && event.jobId && (
        <div className="flex gap-2 mt-2 ml-6">
          <Button size="sm" variant="outline" onClick={() => onApprove(event.jobId!, event.id)}
            className="h-7 text-xs rounded-lg border-green-300 dark:border-green-800 text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-950/20">
            <ThumbsUp className="h-3 w-3 mr-1" /> Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => onReject(event.jobId!, event.id)}
            className="h-7 text-xs rounded-lg border-red-300 dark:border-red-800 text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20">
            <ThumbsDown className="h-3 w-3 mr-1" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}
