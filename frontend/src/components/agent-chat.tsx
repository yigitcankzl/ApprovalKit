"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight, Bot, CheckCircle2, ChevronRight, Clock, Loader2,
  Play, Send, XCircle, RefreshCw, Zap, Shield, AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

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

// ── Chat Message Types ────────────────────────────────────────────────────────

type MsgType = "agent" | "system" | "approval" | "result" | "error" | "user";

interface ChatMessage {
  id: string;
  type: MsgType;
  text: string;
  timestamp: Date;
  meta?: {
    jobId?: string;
    status?: string;
    rule?: string;
    model?: string;
    approvers?: string[];
    params?: Record<string, unknown>;
  };
}

// ── Flow Diagram ──────────────────────────────────────────────────────────────

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

// ── Chat Bubble ───────────────────────────────────────────────────────────────

function ChatBubble({ msg, onApprove, onReject, deciding }: {
  msg: ChatMessage;
  onApprove?: (jobId: string) => void;
  onReject?: (jobId: string) => void;
  deciding?: boolean;
}) {
  const isUser = msg.type === "user";
  const isApproval = msg.type === "approval";
  const isError = msg.type === "error";
  const isResult = msg.type === "result";
  const isSystem = msg.type === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-zinc-400 dark:text-zinc-500 bg-zinc-100 dark:bg-zinc-800/50 px-3 py-1 rounded-full">
          {msg.text}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div className={`max-w-[85%] ${isUser ? "order-1" : ""}`}>
        {/* Sender label */}
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1 ml-1">
            {isApproval ? (
              <Shield className="h-3 w-3 text-amber-500" />
            ) : isError ? (
              <AlertTriangle className="h-3 w-3 text-red-500" />
            ) : isResult ? (
              <CheckCircle2 className="h-3 w-3 text-green-500" />
            ) : (
              <Bot className="h-3 w-3 text-blue-500" />
            )}
            <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">
              {isApproval ? "Approval Required" : isError ? "Error" : isResult ? "Result" : "Agent"}
            </span>
          </div>
        )}

        {/* Message body */}
        <div className={`rounded-2xl px-4 py-2.5 text-sm ${
          isUser
            ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-br-md"
            : isApproval
            ? "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 rounded-bl-md"
            : isError
            ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 rounded-bl-md"
            : isResult
            ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300 rounded-bl-md"
            : "bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 rounded-bl-md"
        }`}>
          <div className="whitespace-pre-wrap">{msg.text}</div>

          {/* Approval details */}
          {isApproval && msg.meta && (
            <div className="mt-2 space-y-1.5">
              {msg.meta.rule && (
                <div className="text-xs"><span className="font-semibold">Rule:</span> {msg.meta.rule}</div>
              )}
              {msg.meta.model && (
                <div className="text-xs"><span className="font-semibold">Model:</span> {msg.meta.model}</div>
              )}
              {msg.meta.approvers && msg.meta.approvers.length > 0 && (
                <div className="text-xs"><span className="font-semibold">Approvers:</span> {msg.meta.approvers.join(", ")}</div>
              )}
              {msg.meta.status === "pending" && msg.meta.jobId && onApprove && onReject && (
                <div className="flex gap-2 mt-3">
                  <Button
                    size="sm"
                    onClick={() => onApprove(msg.meta!.jobId!)}
                    disabled={deciding}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white h-8 text-xs"
                  >
                    {deciding ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <CheckCircle2 className="h-3 w-3 mr-1" />}
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReject(msg.meta!.jobId!)}
                    disabled={deciding}
                    className="flex-1 border-red-200 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 h-8 text-xs"
                  >
                    {deciding ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <XCircle className="h-3 w-3 mr-1" />}
                    Reject
                  </Button>
                </div>
              )}
              {msg.meta.status === "approved" && (
                <Badge variant="success" className="mt-1"><CheckCircle2 className="h-3 w-3 mr-1" /> Approved</Badge>
              )}
              {msg.meta.status === "rejected" && (
                <Badge variant="danger" className="mt-1"><XCircle className="h-3 w-3 mr-1" /> Rejected</Badge>
              )}
              {msg.meta.status === "timeout" && (
                <Badge variant="warning" className="mt-1"><Clock className="h-3 w-3 mr-1" /> Timed out</Badge>
              )}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div className={`text-[10px] text-zinc-400 mt-0.5 ${isUser ? "text-right mr-1" : "ml-1"}`}>
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
}

// ── Scenario Quick Action ─────────────────────────────────────────────────────

function ScenarioButton({ scenario, onRun, running }: {
  scenario: AgentScenario;
  onRun: () => void;
  running: boolean;
}) {
  const [showFlow, setShowFlow] = useState(false);

  return (
    <div className="border border-zinc-200 dark:border-zinc-700 rounded-xl bg-white dark:bg-zinc-800/50 overflow-hidden">
      <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Badge variant={scenario.badge} className="text-[10px] font-mono shrink-0">
            {scenario.badgeLabel}
          </Badge>
          <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">{scenario.title}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2">
          <button
            onClick={() => setShowFlow(v => !v)}
            className="p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
            title="Show flow"
          >
            <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showFlow ? "rotate-90" : ""}`} />
          </button>
          <Button size="sm" onClick={onRun} disabled={running} className="h-7 px-2.5 text-xs">
            {running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
          </Button>
        </div>
      </div>
      {showFlow && (
        <div className="px-3 pb-3 border-t border-zinc-100 dark:border-zinc-700/50 pt-2">
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">{scenario.description}</p>
          <div className="overflow-x-auto pb-1">
            <FlowDiagram steps={scenario.flow} />
          </div>
          <pre className="mt-2 bg-zinc-900 text-zinc-100 text-[10px] rounded-lg p-2 overflow-x-auto">
            {JSON.stringify({ connection: scenario.connection, action: scenario.action, params: scenario.params }, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main AgentChat Component ──────────────────────────────────────────────────

let _msgId = 0;
function msgId() { return `msg-${++_msgId}-${Date.now()}`; }

export function AgentChat({ agent }: { agent: DemoAgent }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [runningScenario, setRunningScenario] = useState<number | null>(null);
  const [deciding, setDeciding] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Cleanup
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Initial welcome message
  useEffect(() => {
    setMessages([{
      id: msgId(),
      type: "agent",
      text: `Welcome! I'm the ${agent.title}.\n\n${agent.description}\n\nSelect a scenario below to see the approval flow in action.`,
      timestamp: new Date(),
    }]);
  }, [agent.id]);

  const addMsg = (type: MsgType, text: string, meta?: ChatMessage["meta"]) => {
    const msg: ChatMessage = { id: msgId(), type, text, timestamp: new Date(), meta };
    setMessages(prev => [...prev, msg]);
    return msg.id;
  };

  const updateMsg = (id: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...updates, meta: { ...m.meta, ...updates.meta } } : m));
  };

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const handleRunScenario = async (index: number) => {
    const scenario = agent.scenarios[index];
    if (!scenario) return;

    setRunningScenario(index);

    // User message
    addMsg("user", scenario.title);

    // Processing
    await sleep(400);
    addMsg("agent", `Processing: ${scenario.description}`);

    await sleep(600);
    addMsg("system", `Submitting to ApprovalKit: ${scenario.connection} / ${scenario.action}`);

    try {
      const res = await api.sendTestRequest({
        connection: scenario.connection,
        action: scenario.action,
        params: scenario.params,
      });

      if (res.status === "auto_approved") {
        await sleep(500);
        if (scenario.badge === "success") {
          addMsg("result", `Auto-approved! No rule matched for this request.\n\nAction executed successfully via Token Vault.`);
        } else {
          addMsg("error", `No matching rule found. Click "Setup Demo" on the Agents page first to create the required rules, approvers, and connections.`);
        }
        setRunningScenario(null);
        return;
      }

      if (res.job_id) {
        await sleep(300);
        addMsg("system", "Rule matched - approval request created");

        await sleep(500);
        const approvalMsgId = addMsg("approval", `Waiting for approval...\n\nConnection: ${scenario.connection}\nAction: ${scenario.action}`, {
          jobId: res.job_id,
          status: "pending",
          rule: res.rule_name,
          model: res.model,
          approvers: res.approvers?.map((a: any) => a.name) || [],
        });

        // Poll for result
        let attempts = 0;
        pollRef.current = setInterval(async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            const terminal = ["approved", "rejected", "timeout", "blocked"];
            if (terminal.includes(s.status)) {
              stopPoll();
              updateMsg(approvalMsgId, { meta: { status: s.status } });
              await sleep(300);
              if (s.status === "approved") {
                addMsg("result", `Approved! Action executed via Token Vault.\n\nThe ${scenario.connection} / ${scenario.action} was completed successfully.`);
              } else if (s.status === "rejected") {
                addMsg("error", `Request was rejected by the approver.`);
              } else if (s.status === "timeout") {
                addMsg("error", `Approval request timed out.`);
              } else {
                addMsg("error", `Request was blocked.`);
              }
              setRunningScenario(null);
            }
          } catch {}
          if (++attempts > 90) { stopPoll(); setRunningScenario(null); }
        }, 2000);
      }
    } catch (e: any) {
      addMsg("error", `Failed to submit request: ${e.message}`);
      setRunningScenario(null);
    }
  };

  const handleApprove = async (jobId: string) => {
    setDeciding(true);
    try {
      await api.submitDecision(jobId, { decision: "approve" });
      // Poll will pick up the change
    } catch {}
    setDeciding(false);
  };

  const handleReject = async (jobId: string) => {
    setDeciding(true);
    try {
      await api.submitDecision(jobId, { decision: "reject" });
    } catch {}
    setDeciding(false);
  };

  const handleReset = () => {
    stopPoll();
    setRunningScenario(null);
    setMessages([{
      id: msgId(),
      type: "agent",
      text: `Welcome! I'm the ${agent.title}.\n\n${agent.description}\n\nSelect a scenario below to see the approval flow in action.`,
      timestamp: new Date(),
    }]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.map(msg => (
          <ChatBubble
            key={msg.id}
            msg={msg}
            onApprove={handleApprove}
            onReject={handleReject}
            deciding={deciding}
          />
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Scenarios panel */}
      <div className="border-t border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/50 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-zinc-400" />
            <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Scenarios</span>
          </div>
          <button
            onClick={handleReset}
            className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
          >
            <RefreshCw className="h-3 w-3" /> Reset
          </button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {agent.scenarios.map((scenario, i) => (
            <ScenarioButton
              key={i}
              scenario={scenario}
              onRun={() => handleRunScenario(i)}
              running={runningScenario === i}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)); }
