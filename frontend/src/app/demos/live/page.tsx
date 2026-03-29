"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { DemoAgent } from "@/components/scenario-runner";
import {
  ArrowLeft, Banknote, Bot, CheckCircle2, CreditCard,
  FlaskConical, GitBranch, Loader2, MessageSquare, Package, Plane,
  Play, Server, Shield, ShieldAlert, ShieldCheck, ShieldOff,
  Users, Zap, AlertTriangle, XCircle, Clock, Lock,
  ThumbsUp, ThumbsDown, BarChart3, Activity, Send, RotateCcw,
  Wrench, Sparkles, Settings, Eye,
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
}

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "tool" | "system";
  text: string;
  timestamp: Date;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolStatus?: "running" | "auto_approved" | "pending" | "blocked" | "approved" | "rejected" | "error";
  jobId?: string;
}

interface SessionSummary {
  totalActions: number;
  autoApproved: number;
  pendingApproval: number;
  blocked: number;
  preventedDamage: number;
}

// ── Scenario prompts per agent ─────────────────────────────────────────────

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

const ICON_MAP: Record<string, React.ElementType> = {
  CreditCard, Server, Users, Package, FlaskConical, Zap, Banknote,
  Plane, GitBranch, MessageSquare, Shield, Bot, Play,
};
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

  useEffect(() => {
    api.getDemoAgents()
      .then((data: DemoAgent[] | { agents: DemoAgent[] }) => { const list = Array.isArray(data) ? data : data.agents || []; setAgents(list); if (list.length > 0) setSelectedAgent(list[0]); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api.getRules().then((rules: any[]) => setSetupDone(rules.length > 0)).catch(() => {});
    api.getAIKeyStatus().then((s: any) => setHasAIKey(!!s?.has_ai_api_key)).catch(() => {});
  }, []);

  const currentMessages = selectedAgent ? (messages[selectedAgent.id] || []) : [];

  const addMessage = useCallback((agentId: string, msg: Omit<ChatMessage, "id" | "timestamp">) => {
    const m: ChatMessage = { ...msg, id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: new Date() };
    setMessages(prev => ({ ...prev, [agentId]: [...(prev[agentId] || []), m] }));
    return m.id;
  }, []);

  const updateMessage = useCallback((agentId: string, msgId: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => ({ ...prev, [agentId]: (prev[agentId] || []).map(m => m.id === msgId ? { ...m, ...updates } : m) }));
  }, []);

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
    const agentId = selectedAgent.id;
    const agentTitle = selectedAgent.title;
    addMessage(agentId, { role: "user", text: text.trim() });
    setInputText("");
    setIsTyping(true);

    try {
      const sessionId = sessionIds[agentId] || "";
      const res = await api.chatWithAgent(agentId, text.trim(), agentTitle, sessionId);
      if (res.session_id) setSessionIds(prev => ({ ...prev, [agentId]: res.session_id }));
      addMessage(agentId, { role: "agent", text: res.response || "Done." });

      const actions = res.actions || (res.action ? [res.action] : []);
      for (const a of actions) {
        const realStatus = a.status || "auto_approved";
        if (!shieldEnabled) {
          addMessage(agentId, { role: "tool", text: `${a.connection}/${a.action}`, toolName: a.action, toolArgs: a.params, toolStatus: "auto_approved" });
          addEvent({ agentId, agentTitle, type: "auto_approved", action: a.action, connection: a.connection, params: a.params || {}, message: `EXECUTED WITHOUT OVERSIGHT — ${a.action}` });
        } else {
          const toolMsgId = addMessage(agentId, { role: "tool", text: `${a.connection}/${a.action}`, toolName: a.action, toolArgs: a.params, toolStatus: realStatus === "auto_approved" ? "auto_approved" : realStatus === "pending" ? "pending" : "blocked", jobId: a.job_id });
          let eventType: ShieldEvent["type"] = "auto_approved";
          if (realStatus === "pending") eventType = "pending";
          else if (realStatus === "blocked") eventType = "blocked";
          const rn = a.rule_name || "";
          if ((rn.toLowerCase().includes("large") || rn.toLowerCase().includes("cfo")) && realStatus === "pending") eventType = "step_up";
          if (rn.toLowerCase().includes("mass") || rn.toLowerCase().includes("scope")) eventType = "scope_creep";
          addEvent({ agentId, agentTitle, type: eventType, action: a.action, connection: a.connection, params: a.params || {}, message: a.message || `${a.action} — ${realStatus}`, jobId: a.job_id });
          if (realStatus === "pending" && a.job_id) pollJob(agentId, a.job_id, toolMsgId);
        }
      }
    } catch (e: any) { addMessage(agentId, { role: "system", text: `Error: ${e.message}` }); }
    setIsTyping(false);
    inputRef.current?.focus();
  };

  const pollJob = async (agentId: string, jobId: string, toolMsgId: string) => {
    let attempts = 0;
    const poll = setInterval(async () => {
      try {
        const status = await api.getJobStatus(jobId);
        if (["approved", "rejected", "timeout", "blocked"].includes(status.status)) {
          clearInterval(poll);
          const ns = status.status === "approved" ? "approved" : status.status === "rejected" ? "rejected" : "blocked";
          updateMessage(agentId, toolMsgId, { toolStatus: ns as any });
          setEvents(prev => prev.map(e => e.jobId === jobId ? { ...e, type: ns as any } : e));
          if (ns === "approved") setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
          else setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1 }));
        }
      } catch {}
      if (++attempts > 60) clearInterval(poll);
    }, 2000);
  };

  const handleApprove = async (jobId: string, eventId: string) => {
    try { await api.approveJob(jobId); } catch {}
    setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "approved" as const } : e));
    setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
    if (selectedAgent) setMessages(prev => ({ ...prev, [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m => m.jobId === jobId ? { ...m, toolStatus: "approved" as const } : m) }));
  };

  const handleReject = async (jobId: string, eventId: string) => {
    const evt = events.find(e => e.id === eventId);
    const amt = Number(evt?.params?.amount_usd) || 0;
    try { await api.rejectJob(jobId); } catch {}
    setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "rejected" as const } : e));
    setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1, preventedDamage: prev.preventedDamage + amt }));
    if (selectedAgent) setMessages(prev => ({ ...prev, [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m => m.jobId === jobId ? { ...m, toolStatus: "rejected" as const } : m) }));
  };

  const handleReset = () => {
    if (!selectedAgent) return;
    const sid = sessionIds[selectedAgent.id];
    if (sid) api.clearAgentSession(selectedAgent.id, sid).catch(() => {});
    setMessages(prev => ({ ...prev, [selectedAgent.id]: [] }));
    setSessionIds(prev => ({ ...prev, [selectedAgent.id]: "" }));
  };

  const scenarios = selectedAgent ? (SCENARIO_PROMPTS[selectedAgent.id] || DEFAULT_PROMPTS) : [];

  if (loading) return <div className="flex items-center justify-center h-[80vh]"><Loader2 className="h-8 w-8 animate-spin text-zinc-400" /></div>;

  return (
    <div className="min-h-screen">
      {/* ── Page Header ── */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <a href="/demos" className="text-zinc-400 hover:text-white transition-colors"><ArrowLeft className="h-5 w-5" /></a>
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-amber-500">
              Live Threat Demo
            </h1>
            <p className="text-zinc-400 text-sm mt-1">Watch AI agents act autonomously — see what ApprovalKit catches in real-time</p>
          </div>
        </div>

        {/* Controls bar */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Shield Toggle */}
          <button
            onClick={() => { setShieldEnabled(prev => !prev); resetSummary(); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all border shadow-md hover:shadow-lg ${
              shieldEnabled
                ? "bg-emerald-900/20 text-emerald-400 border-emerald-700/50 hover:bg-emerald-900/40"
                : "bg-red-900/20 text-red-400 border-red-700/50 hover:bg-red-900/40 animate-pulse"
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

          {/* Stats pills */}
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-900/20 border border-emerald-800/30 text-emerald-400 text-xs font-mono">
              <CheckCircle2 className="h-3.5 w-3.5" /> {summary.autoApproved}
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-900/20 border border-amber-800/30 text-amber-400 text-xs font-mono">
              <Clock className="h-3.5 w-3.5" /> {summary.pendingApproval}
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-900/20 border border-red-800/30 text-red-400 text-xs font-mono">
              <ShieldOff className="h-3.5 w-3.5" /> {summary.blocked}
            </span>
            {summary.preventedDamage > 0 && (
              <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-900/30 border border-red-700/50 text-red-400 text-xs font-bold font-mono">
                ${summary.preventedDamage.toLocaleString()} prevented
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Agent Tabs ── */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        {agents.map(agent => {
          const Icon = resolveIcon(agent.icon);
          const isActive = selectedAgent?.id === agent.id;
          return (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all border ${
                isActive
                  ? "bg-blue-900/30 text-blue-300 border-blue-700/50 shadow-md"
                  : "bg-zinc-900 text-zinc-500 border-zinc-800 hover:text-zinc-300 hover:border-zinc-600"
              }`}
            >
              <Icon className="h-4 w-4" />
              {agent.title.replace(" Agent", "").replace(" Approval", "")}
            </button>
          );
        })}
      </div>

      {/* ── Split Screen ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ height: "calc(100vh - 280px)" }}>

        {/* LEFT: Agent Chat */}
        <Card className="bg-zinc-900 border-zinc-800 flex flex-col overflow-hidden">
          {/* Scenario buttons */}
          {selectedAgent && (
            <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800">
              {scenarios.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s.prompt)}
                  disabled={isTyping || !setupDone || !hasAIKey}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-zinc-700 hover:border-blue-600 bg-zinc-800 hover:bg-blue-900/20 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <span>{s.emoji}</span>
                  <span>{s.label}</span>
                </button>
              ))}
              <div className="flex-1" />
              <button onClick={handleReset} className="text-zinc-600 hover:text-zinc-300 transition-colors p-1.5 rounded-lg hover:bg-zinc-800" title="Reset chat">
                <RotateCcw className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Chat area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {!hasAIKey && setupDone && (
              <div className="p-4 rounded-xl border border-amber-800/50 bg-amber-900/10 text-amber-400 text-sm">
                <Settings className="h-4 w-4 inline mr-2" />No AI provider configured.
                <a href={`/demos/${selectedAgent?.id || agents[0]?.id}`} className="underline ml-1">Set up Ollama or API key</a>
              </div>
            )}
            {!setupDone && (
              <div className="p-4 rounded-xl border border-amber-800/50 bg-amber-900/10 text-amber-400 text-sm">
                <AlertTriangle className="h-4 w-4 inline mr-2" />Click &quot;Setup Demo Data&quot; to create approval rules.
              </div>
            )}
            {currentMessages.length === 0 && hasAIKey && setupDone && (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600 space-y-3">
                <Bot className="h-16 w-16 opacity-10" />
                <p className="text-sm font-medium">Pick a scenario or type a message</p>
                <p className="text-xs text-zinc-500">The AI agent will reason and take actions autonomously</p>
              </div>
            )}
            {currentMessages.map(msg => <ChatBubble key={msg.id} message={msg} shieldOff={!shieldEnabled} />)}
            {isTyping && (
              <div className="flex items-center gap-2 text-blue-400 text-sm"><Loader2 className="h-4 w-4 animate-spin" /><span>Agent is thinking...</span></div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t border-zinc-800">
            <form onSubmit={(e) => { e.preventDefault(); sendMessage(inputText); }} className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={selectedAgent ? `Tell ${selectedAgent.title} what to do...` : "Select an agent"}
                disabled={isTyping || !setupDone || !hasAIKey}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600/50 disabled:opacity-30"
              />
              <Button type="submit" disabled={isTyping || !inputText.trim() || !setupDone || !hasAIKey} className="rounded-xl px-4 shadow-md hover:shadow-lg">
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </Card>

        {/* RIGHT: Shield Panel */}
        <Card className={`flex flex-col overflow-hidden ${!shieldEnabled ? "bg-red-950/10 border-red-900/50" : "bg-zinc-900 border-zinc-800"}`}>
          <div className={`flex items-center gap-2 px-4 py-3 border-b ${!shieldEnabled ? "border-red-900/50" : "border-zinc-800"}`}>
            {shieldEnabled
              ? <Shield className="h-4 w-4 text-blue-400" />
              : <ShieldOff className="h-4 w-4 text-red-400 animate-pulse" />}
            <h2 className={`text-sm font-bold ${!shieldEnabled ? "text-red-400" : "text-zinc-300"}`}>
              {shieldEnabled ? "ApprovalKit Shield" : "NO PROTECTION"}
            </h2>
            <div className="flex-1" />
            <span className="text-xs text-zinc-600 font-mono">{events.length} events</span>
            {events.length > 0 && (
              <button onClick={resetSummary} className="text-xs text-zinc-600 hover:text-zinc-300 transition-colors">Clear</button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600">
                <Activity className="h-16 w-16 mb-3 opacity-10" />
                <p className="text-sm">No events yet</p>
                <p className="text-xs mt-1 text-zinc-500">Run a scenario to see the Shield in action</p>
              </div>
            ) : events.map(event => (
              <EventCard key={event.id} event={event} onApprove={handleApprove} onReject={handleReject} shieldOff={!shieldEnabled} />
            ))}
            <div ref={eventsEndRef} />
          </div>

          {/* Summary */}
          {events.length > 0 && (
            <div className={`px-4 py-3 border-t ${!shieldEnabled ? "border-red-900/50 bg-red-950/20" : "border-zinc-800"}`}>
              {shieldEnabled ? (
                <>
                  <div className="grid grid-cols-4 gap-3 text-center">
                    <MiniStat label="Total" value={summary.totalActions} color="text-zinc-300" />
                    <MiniStat label="Approved" value={summary.autoApproved} color="text-emerald-400" />
                    <MiniStat label="Pending" value={summary.pendingApproval} color="text-amber-400" />
                    <MiniStat label="Blocked" value={summary.blocked} color="text-red-400" />
                  </div>
                  {summary.preventedDamage > 0 && (
                    <div className="mt-2 text-center">
                      <span className="text-xs text-zinc-500">Prevented damage: </span>
                      <span className="text-lg font-bold text-red-400 font-mono">${summary.preventedDamage.toLocaleString()}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-1">
                  <div className="flex items-center justify-center gap-2 text-red-400">
                    <AlertTriangle className="h-5 w-5" />
                    <span className="text-sm font-bold">ALL {summary.totalActions} ACTIONS — NO OVERSIGHT</span>
                  </div>
                  <p className="text-xs text-red-400/60 mt-1">
                    No approval required. No human review. Unreviewed spend: <span className="font-bold">${events.reduce((s, e) => s + (Number(e.params?.amount_usd) || 0), 0).toLocaleString()}</span>
                  </p>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ── Chat Bubble ──────────────────────────────────────────────────────────

function ChatBubble({ message, shieldOff }: { message: ChatMessage; shieldOff?: boolean }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm shadow-md">{message.text}</div>
      </div>
    );
  }

  if (message.role === "tool") {
    const cfgs: Record<string, { color: string; bg: string; label: string; icon: React.ElementType }> = {
      running: { color: "text-blue-400", bg: "border-blue-800/50 bg-blue-900/10", label: "EXECUTING...", icon: Loader2 },
      auto_approved: { color: shieldOff ? "text-red-400" : "text-emerald-400", bg: shieldOff ? "border-red-800/50 bg-red-900/10" : "border-emerald-800/50 bg-emerald-900/10", label: shieldOff ? "NO APPROVAL" : "AUTO-APPROVED", icon: shieldOff ? AlertTriangle : CheckCircle2 },
      pending: { color: "text-amber-400", bg: "border-amber-800/50 bg-amber-900/10", label: "AWAITING APPROVAL", icon: Clock },
      blocked: { color: "text-red-400", bg: "border-red-800/50 bg-red-900/10", label: "BLOCKED", icon: ShieldOff },
      approved: { color: "text-emerald-400", bg: "border-emerald-800/50 bg-emerald-900/10", label: "APPROVED", icon: ThumbsUp },
      rejected: { color: "text-red-400", bg: "border-red-800/50 bg-red-900/10", label: "REJECTED", icon: ThumbsDown },
      error: { color: "text-red-400", bg: "border-red-800/50 bg-red-900/10", label: "ERROR", icon: XCircle },
    };
    const c = cfgs[message.toolStatus || "running"];
    const Icon = c.icon;
    const amt = Number(message.toolArgs?.amount_usd) || Number(message.toolArgs?.amount);

    return (
      <div className={`rounded-xl border p-3 mx-2 ${c.bg}`}>
        <div className="flex items-center gap-2">
          <Wrench className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-xs font-mono text-zinc-400">{message.text}</span>
          <div className="flex-1" />
          <span className={`flex items-center gap-1 text-[10px] font-bold ${c.color}`}>
            <Icon className={`h-3 w-3 ${message.toolStatus === "pending" ? "animate-spin" : ""}`} />
            {c.label}
          </span>
        </div>
        {message.toolArgs && (
          <div className="text-[11px] text-zinc-500 font-mono pl-5 mt-1 space-y-0.5">
            {Object.entries(message.toolArgs).slice(0, 4).map(([k, v]) => (
              <div key={k}><span className="text-zinc-600">{k}:</span> <span className="text-zinc-400">{typeof v === "string" ? v : JSON.stringify(v)}</span></div>
            ))}
          </div>
        )}
        {amt > 0 && <div className="mt-1 pl-5"><span className={`text-xs font-mono font-bold ${c.color}`}>${amt.toLocaleString()}</span></div>}
      </div>
    );
  }

  if (message.role === "system") {
    return <div className="text-center"><span className="text-xs text-zinc-600 bg-zinc-800 px-3 py-1 rounded-full">{message.text}</span></div>;
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex gap-2.5">
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-600 to-emerald-500 flex items-center justify-center mt-0.5">
          <Sparkles className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="bg-zinc-800 text-zinc-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-md">{message.text}</div>
      </div>
    </div>
  );
}

// ── Event Card ────────────────────────────────────────────────────────────

function EventCard({ event, onApprove, onReject, shieldOff }: {
  event: ShieldEvent;
  onApprove: (jobId: string, eventId: string) => void;
  onReject: (jobId: string, eventId: string) => void;
  shieldOff?: boolean;
}) {
  const cfgs: Record<string, { icon: React.ElementType; color: string; bg: string; label: string }> = {
    auto_approved: { icon: shieldOff ? AlertTriangle : CheckCircle2, color: shieldOff ? "text-red-400" : "text-emerald-400", bg: shieldOff ? "border-red-800/40 bg-red-900/10" : "border-emerald-800/40 bg-emerald-900/10", label: shieldOff ? "EXECUTED — NO REVIEW" : "AUTO-APPROVED" },
    pending: { icon: Clock, color: "text-amber-400", bg: "border-amber-800/40 bg-amber-900/10", label: "PENDING APPROVAL" },
    approved: { icon: ThumbsUp, color: "text-emerald-400", bg: "border-emerald-800/40 bg-emerald-900/10", label: "APPROVED" },
    rejected: { icon: ThumbsDown, color: "text-red-400", bg: "border-red-800/40 bg-red-900/10", label: "REJECTED" },
    blocked: { icon: ShieldOff, color: "text-red-400", bg: "border-red-800/40 bg-red-900/10", label: "BLOCKED" },
    step_up: { icon: ShieldAlert, color: "text-amber-400", bg: "border-amber-800/40 bg-amber-900/10", label: "STEP-UP REQUIRED" },
    scope_creep: { icon: AlertTriangle, color: "text-red-400", bg: "border-red-800/40 bg-red-900/10", label: "SCOPE CREEP" },
    budget_exceeded: { icon: Lock, color: "text-red-400", bg: "border-red-800/40 bg-red-900/10", label: "BUDGET EXCEEDED" },
  };
  const c = cfgs[event.type] || cfgs.blocked;
  const Icon = c.icon;
  const amt = Number(event.params?.amount_usd) || Number(event.params?.amount);

  return (
    <div className={`rounded-xl border p-3 transition-all ${c.bg}`}>
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 flex-shrink-0 ${c.color}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold uppercase tracking-wide ${c.color}`}>{c.label}</span>
            <span className="text-[10px] text-zinc-600 font-mono">{event.timestamp.toLocaleTimeString()}</span>
          </div>
          <p className="text-xs text-zinc-300 mt-0.5 truncate">{event.message}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-zinc-500 font-mono">{event.connection}/{event.action}</span>
            {amt > 0 && <span className={`text-[10px] font-mono font-bold ${c.color}`}>${amt.toLocaleString()}</span>}
          </div>
        </div>
      </div>
      {(event.type === "pending" || event.type === "step_up") && event.jobId && (
        <div className="flex gap-2 mt-2 ml-6">
          <Button size="sm" variant="outline" onClick={() => onApprove(event.jobId!, event.id)}
            className="h-7 text-xs bg-emerald-900/20 text-emerald-400 border-emerald-800/50 hover:bg-emerald-900/40">
            <ThumbsUp className="h-3 w-3 mr-1" /> Approve
          </Button>
          <Button size="sm" variant="outline" onClick={() => onReject(event.jobId!, event.id)}
            className="h-7 text-xs bg-red-900/20 text-red-400 border-red-800/50 hover:bg-red-900/40">
            <ThumbsDown className="h-3 w-3 mr-1" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className={`text-xl font-bold font-mono ${color}`}>{value}</div>
      <div className="text-[10px] text-zinc-500 uppercase">{label}</div>
    </div>
  );
}
