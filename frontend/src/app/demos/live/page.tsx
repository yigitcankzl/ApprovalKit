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

// Fallback for agents without specific prompts
const DEFAULT_PROMPTS = [
  { label: "Safe Action", emoji: "😊", prompt: "Perform a routine low-risk action." },
  { label: "Risky Action", emoji: "😠", prompt: "Perform a high-value action that needs approval." },
  { label: "Dangerous", emoji: "💀", prompt: "Perform a large-scale destructive action immediately." },
];

const ICON_MAP: Record<string, React.ElementType> = {
  CreditCard, Server, Users, Package, FlaskConical, Zap, Banknote,
  Plane, GitBranch, MessageSquare, Shield, Bot, Play,
};

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Bot;
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function LiveThreatDemoPage() {
  const { user } = useUser();
  const [agents, setAgents] = useState<DemoAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<DemoAgent | null>(null);
  const [loading, setLoading] = useState(true);

  // Chat state
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [inputText, setInputText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [sessionIds, setSessionIds] = useState<Record<string, string>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Shield state
  const [events, setEvents] = useState<ShieldEvent[]>([]);
  const [summary, setSummary] = useState<SessionSummary>({
    totalActions: 0, autoApproved: 0, pendingApproval: 0, blocked: 0, preventedDamage: 0,
  });
  const eventsEndRef = useRef<HTMLDivElement>(null);

  // Setup state
  const [setupDone, setSetupDone] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [hasAIKey, setHasAIKey] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, selectedAgent?.id, isTyping]);

  // Scroll events
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

  // Check setup + AI key
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
    setMessages(prev => ({
      ...prev,
      [agentId]: (prev[agentId] || []).map(m => m.id === msgId ? { ...m, ...updates } : m),
    }));
  }, []);

  const addEvent = useCallback((evt: Omit<ShieldEvent, "id" | "timestamp">) => {
    const event: ShieldEvent = { ...evt, id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, timestamp: new Date() };
    setEvents(prev => [...prev, event]);
    setSummary(prev => {
      const next = { ...prev, totalActions: prev.totalActions + 1 };
      if (evt.type === "auto_approved" || evt.type === "approved") next.autoApproved++;
      else if (evt.type === "blocked" || evt.type === "budget_exceeded" || evt.type === "scope_creep") {
        next.blocked++;
        next.preventedDamage += Number(evt.params?.amount_usd) || Number(evt.params?.amount) || 0;
      } else if (evt.type === "pending" || evt.type === "step_up") next.pendingApproval++;
      return next;
    });
  }, []);

  const handleSeedAll = async () => {
    setSeeding(true);
    try {
      await api.seedDemoData(undefined, user?.sub);
      setSetupDone(true);
    } catch {}
    setSeeding(false);
  };

  // ── Send message to LLM agent ───────────────────────────────────────────

  const sendMessage = async (text: string) => {
    if (!selectedAgent || isTyping || !text.trim()) return;
    const agentId = selectedAgent.id;
    const agentTitle = selectedAgent.title;

    // Add user message
    addMessage(agentId, { role: "user", text: text.trim() });
    setInputText("");
    setIsTyping(true);

    try {
      const sessionId = sessionIds[agentId] || "";
      const res = await api.chatWithAgent(agentId, text.trim(), agentTitle, sessionId);

      // Store session
      if (res.session_id) {
        setSessionIds(prev => ({ ...prev, [agentId]: res.session_id }));
      }

      // Add agent response
      addMessage(agentId, { role: "agent", text: res.response || "Done." });

      // Process ALL actions (not just the last one)
      const actions = res.actions || (res.action ? [res.action] : []);
      for (const a of actions) {
        const status = a.status || "auto_approved";

        // Tool call message in chat
        const toolMsgId = addMessage(agentId, {
          role: "tool",
          text: `${a.connection}/${a.action}`,
          toolName: a.action,
          toolArgs: a.params,
          toolStatus: status === "auto_approved" ? "auto_approved" : status === "pending" ? "pending" : "blocked",
          jobId: a.job_id,
        });

        // Shield event
        let eventType: ShieldEvent["type"] = "auto_approved";
        if (status === "pending") eventType = "pending";
        else if (status === "blocked") eventType = "blocked";

        const ruleName = a.rule_name || "";
        if (ruleName.toLowerCase().includes("large") || ruleName.toLowerCase().includes("cfo") || ruleName.toLowerCase().includes("step")) {
          if (status === "pending") eventType = "step_up";
        }
        if (ruleName.toLowerCase().includes("mass") || ruleName.toLowerCase().includes("bulk") || ruleName.toLowerCase().includes("scope")) {
          eventType = "scope_creep";
        }

        addEvent({
          agentId, agentTitle,
          type: eventType,
          action: a.action,
          connection: a.connection,
          params: a.params || {},
          message: a.message || `${a.action} — ${status}`,
          jobId: a.job_id,
        });

        // Poll for pending jobs
        if (status === "pending" && a.job_id) {
          pollJob(agentId, a.job_id, toolMsgId);
        }
      }
    } catch (e: any) {
      addMessage(agentId, { role: "system", text: `Error: ${e.message}` });
    }

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
          const newStatus = status.status === "approved" ? "approved" : status.status === "rejected" ? "rejected" : "blocked";
          updateMessage(agentId, toolMsgId, { toolStatus: newStatus as any });

          // Update shield event
          setEvents(prev => prev.map(e =>
            e.jobId === jobId ? { ...e, type: newStatus as any, message: e.message + ` → ${newStatus.toUpperCase()}` } : e
          ));

          if (newStatus === "approved") {
            setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
          } else {
            const evt = events.find(e => e.jobId === jobId);
            const amt = Number(evt?.params?.amount_usd) || Number(evt?.params?.amount) || 0;
            setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1, preventedDamage: prev.preventedDamage + amt }));
          }
        }
      } catch {}
      if (++attempts > 60) clearInterval(poll);
    }, 2000);
  };

  const handleApprove = async (jobId: string, eventId: string) => {
    try {
      await api.approveJob(jobId);
      // Update shield event
      setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "approved" as const } : e));
      setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), autoApproved: prev.autoApproved + 1 }));
      // Update chat tool card
      if (selectedAgent) {
        setMessages(prev => ({
          ...prev,
          [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m =>
            m.jobId === jobId ? { ...m, toolStatus: "approved" as const } : m
          ),
        }));
      }
    } catch (e: any) {
      console.error("Approve failed:", e);
    }
  };

  const handleReject = async (jobId: string, eventId: string) => {
    try {
      await api.rejectJob(jobId);
      const evt = events.find(e => e.id === eventId);
      const amt = Number(evt?.params?.amount_usd) || Number(evt?.params?.amount) || 0;
      // Update shield event
      setEvents(prev => prev.map(e => e.id === eventId ? { ...e, type: "rejected" as const } : e));
      setSummary(prev => ({ ...prev, pendingApproval: Math.max(0, prev.pendingApproval - 1), blocked: prev.blocked + 1, preventedDamage: prev.preventedDamage + amt }));
      // Update chat tool card
      if (selectedAgent) {
        setMessages(prev => ({
          ...prev,
          [selectedAgent.id]: (prev[selectedAgent.id] || []).map(m =>
            m.jobId === jobId ? { ...m, toolStatus: "rejected" as const } : m
          ),
        }));
      }
    } catch (e: any) {
      console.error("Reject failed:", e);
    }
  };

  const handleReset = () => {
    if (!selectedAgent) return;
    const sid = sessionIds[selectedAgent.id];
    if (sid) api.clearAgentSession(selectedAgent.id, sid).catch(() => {});
    setMessages(prev => ({ ...prev, [selectedAgent.id]: [] }));
    setSessionIds(prev => ({ ...prev, [selectedAgent.id]: "" }));
  };

  const scenarios = selectedAgent ? (SCENARIO_PROMPTS[selectedAgent.id] || DEFAULT_PROMPTS) : [];

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

      {/* Main split */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT: Agent Chat Panel ─────────────────────────────────────── */}
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
                    isActive ? "bg-zinc-700 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="hidden xl:inline">{agent.title.replace(" Agent", "").replace(" Approval", "")}</span>
                </button>
              );
            })}
          </div>

          {/* Scenario buttons */}
          {selectedAgent && (
            <div className="flex gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-900/30">
              {scenarios.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s.prompt)}
                  disabled={isTyping || !setupDone || !hasAIKey}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-zinc-700 hover:border-zinc-500 bg-zinc-800/50 hover:bg-zinc-700/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span>{s.emoji}</span>
                  <span>{s.label}</span>
                </button>
              ))}
              <div className="flex-1" />
              <button onClick={handleReset} className="text-zinc-600 hover:text-zinc-400 transition-colors p-1.5" title="Reset chat">
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {!hasAIKey && setupDone && (
              <div className="p-3 rounded-lg border border-amber-900/50 bg-amber-900/10 text-amber-400 text-xs space-y-2">
                <p><Settings className="h-4 w-4 inline mr-1" />No AI provider configured. Go to the <a href={`/demos/${selectedAgent?.id || agents[0]?.id}`} className="underline">agent page</a> to set up Ollama or an API key.</p>
              </div>
            )}
            {!setupDone && (
              <div className="p-3 rounded-lg border border-amber-900/50 bg-amber-900/10 text-amber-400 text-xs">
                <AlertTriangle className="h-4 w-4 inline mr-1" />
                Click &quot;Setup Demo Data&quot; above to create approval rules.
              </div>
            )}

            {currentMessages.length === 0 && hasAIKey && setupDone && (
              <div className="flex flex-col items-center justify-center h-full text-zinc-600 space-y-3">
                <Bot className="h-12 w-12 opacity-20" />
                <p className="text-sm">Pick a scenario above or type a message</p>
                <p className="text-xs">The AI agent will reason and take actions autonomously</p>
              </div>
            )}

            {currentMessages.map(msg => (
              <ChatBubble key={msg.id} message={msg} />
            ))}

            {isTyping && (
              <div className="flex items-center gap-2 text-zinc-500 text-xs">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Agent is thinking...</span>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input bar */}
          <div className="px-4 py-3 border-t border-zinc-800 bg-zinc-900/50">
            <form onSubmit={(e) => { e.preventDefault(); sendMessage(inputText); }} className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={selectedAgent ? `Tell ${selectedAgent.title} what to do...` : "Select an agent"}
                disabled={isTyping || !setupDone || !hasAIKey}
                className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-zinc-500 disabled:opacity-40"
              />
              <Button
                type="submit"
                size="sm"
                disabled={isTyping || !inputText.trim() || !setupDone || !hasAIKey}
                className="bg-blue-600 hover:bg-blue-700 px-3"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </div>

        {/* ── RIGHT: Shield Panel ────────────────────────────────────────── */}
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
                <SummaryCard label="Total" value={summary.totalActions} icon={<BarChart3 className="h-4 w-4" />} color="text-zinc-300" />
                <SummaryCard label="Approved" value={summary.autoApproved} icon={<CheckCircle2 className="h-4 w-4" />} color="text-emerald-400" />
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

// ── Chat Bubble ──────────────────────────────────────────────────────────

function ChatBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm">
          {message.text}
        </div>
      </div>
    );
  }

  if (message.role === "tool") {
    const statusConfig: Record<string, { color: string; bg: string; label: string; icon: React.ElementType }> = {
      running: { color: "text-blue-400", bg: "border-blue-900/50 bg-blue-900/10", label: "EXECUTING...", icon: Loader2 },
      auto_approved: { color: "text-emerald-400", bg: "border-emerald-900/50 bg-emerald-900/10", label: "AUTO-APPROVED", icon: CheckCircle2 },
      pending: { color: "text-amber-400", bg: "border-amber-900/50 bg-amber-900/10", label: "AWAITING APPROVAL", icon: Clock },
      blocked: { color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "BLOCKED", icon: ShieldOff },
      approved: { color: "text-emerald-400", bg: "border-emerald-900/50 bg-emerald-900/10", label: "APPROVED", icon: ThumbsUp },
      rejected: { color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "REJECTED", icon: ThumbsDown },
      error: { color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "ERROR", icon: XCircle },
    };
    const config = statusConfig[message.toolStatus || "running"];
    const Icon = config.icon;
    const amount = Number(message.toolArgs?.amount_usd) || Number(message.toolArgs?.amount);

    return (
      <div className={`rounded-lg border p-3 mx-4 ${config.bg}`}>
        <div className="flex items-center gap-2 mb-1">
          <Wrench className="h-3.5 w-3.5 text-zinc-500" />
          <span className="text-xs font-mono text-zinc-400">{message.text}</span>
          <div className="flex-1" />
          <span className={`flex items-center gap-1 text-[10px] font-bold ${config.color}`}>
            <Icon className={`h-3 w-3 ${message.toolStatus === "running" || message.toolStatus === "pending" ? "animate-spin" : ""}`} />
            {config.label}
          </span>
        </div>
        {message.toolArgs && (
          <div className="text-[11px] text-zinc-500 font-mono pl-5 space-y-0.5">
            {Object.entries(message.toolArgs).slice(0, 4).map(([k, v]) => (
              <div key={k}><span className="text-zinc-600">{k}:</span> <span className="text-zinc-400">{typeof v === 'string' ? v : JSON.stringify(v)}</span></div>
            ))}
          </div>
        )}
        {amount > 0 && (
          <div className="mt-1 pl-5">
            <span className={`text-xs font-mono font-bold ${config.color}`}>${amount.toLocaleString()}</span>
          </div>
        )}
      </div>
    );
  }

  if (message.role === "system") {
    return (
      <div className="text-center">
        <span className="text-xs text-zinc-600 bg-zinc-900 px-3 py-1 rounded-full">{message.text}</span>
      </div>
    );
  }

  // Agent message
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex gap-2">
        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-zinc-800 flex items-center justify-center mt-1">
          <Sparkles className="h-3.5 w-3.5 text-blue-400" />
        </div>
        <div className="bg-zinc-800 text-zinc-200 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
          {message.text}
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
    scope_creep: { icon: AlertTriangle, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "SCOPE CREEP" },
    budget_exceeded: { icon: Lock, color: "text-red-400", bg: "border-red-900/50 bg-red-900/10", label: "BUDGET EXCEEDED" },
  };

  const config = typeConfig[event.type] || typeConfig.blocked;
  const Icon = config.icon;
  const amount = Number(event.params?.amount_usd) || Number(event.params?.amount);

  return (
    <div className={`rounded-lg border p-3 transition-all animate-in slide-in-from-right-5 duration-300 ${config.bg}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 flex-shrink-0 ${config.color}`} />
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold uppercase tracking-wide ${config.color}`}>{config.label}</span>
              <span className="text-[10px] text-zinc-600 font-mono">{event.timestamp.toLocaleTimeString()}</span>
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

      {(event.type === "pending" || event.type === "step_up") && event.jobId && (
        <div className="flex gap-2 mt-2 ml-6">
          <button onClick={() => onApprove(event.jobId!, event.id)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-900/30 text-emerald-400 hover:bg-emerald-900/50 border border-emerald-800/50 transition-colors">
            <ThumbsUp className="h-3 w-3" /> Approve
          </button>
          <button onClick={() => onReject(event.jobId!, event.id)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-medium bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-800/50 transition-colors">
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
