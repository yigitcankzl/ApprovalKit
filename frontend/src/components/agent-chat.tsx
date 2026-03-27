"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowRight, Bot, CheckCircle2, ChevronRight, Clock, Loader2,
  Play, Send, XCircle, RefreshCw, Zap, Shield, AlertTriangle, KeyRound,
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

function ChatBubble({ msg }: {
  msg: ChatMessage;
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
              {msg.meta.status === "pending" && msg.meta.jobId && (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>Waiting for approval{msg.meta.approvers?.length ? ` from ${msg.meta.approvers.join(" & ")}` : ""}...</span>
                  </div>
                  <a
                    href="/dashboard"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition-colors"
                  >
                    <ArrowRight className="h-3 w-3" />
                    Open Dashboard to approve/reject
                  </a>
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

// ── Typing Indicator ──────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-3">
      <div className="flex items-center gap-1.5 ml-1">
        <Bot className="h-3 w-3 text-blue-500" />
        <div className="flex items-center gap-1 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-2xl rounded-bl-md px-4 py-2.5">
          <div className="flex gap-1">
            <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Suggestion Chip ───────────────────────────────────────────────────────────

function SuggestionChip({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors whitespace-nowrap"
    >
      <Zap className="h-3 w-3" />
      {label}
    </button>
  );
}

// ── Main AgentChat Component ──────────────────────────────────────────────────

let _msgId = 0;
function msgId() { return `msg-${++_msgId}-${Date.now()}`; }

export function AgentChat({ agent }: { agent: DemoAgent }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showScenarios, setShowScenarios] = useState(false);
  const [runningScenario, setRunningScenario] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [hasAIKey, setHasAIKey] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Cleanup
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // Initial welcome + fetch suggestions + check AI key
  useEffect(() => {
    setMessages([{
      id: msgId(),
      type: "agent",
      text: `Hello! I'm the ${agent.title}.\n\n${agent.description}\n\nType a message or pick a suggestion below to get started.`,
      timestamp: new Date(),
    }]);
    api.getAgentSuggestions(agent.id)
      .then((data: { suggestions: string[] }) => setSuggestions(data.suggestions))
      .catch(() => {});
    api.getAIKeyStatus()
      .then((data: { has_ai_api_key: boolean }) => setHasAIKey(data.has_ai_api_key))
      .catch(() => {});
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

  // ── Execute action through ApprovalKit ──────────────────────────────
  const executeAction = async (action: { connection: string; action: string; params: Record<string, unknown> }) => {
    addMsg("system", `Submitting to ApprovalKit: ${action.connection} / ${action.action}`);

    try {
      const res = await api.sendTestRequest(action);

      if (res.status === "auto_approved") {
        await sleep(500);
        addMsg("result", `Auto-approved! Action executed via Token Vault.\n\n${action.connection} / ${action.action} completed successfully.`);
        return;
      }

      if (res.job_id) {
        await sleep(300);
        addMsg("system", "Rule matched - approval request created");

        await sleep(400);
        const approvalMsgId = addMsg("approval", `Waiting for approval...\n\nConnection: ${action.connection}\nAction: ${action.action}`, {
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
                addMsg("result", `Approved! Action executed via Token Vault.`);
              } else if (s.status === "rejected") {
                addMsg("error", `Request was rejected by the approver.`);
              } else if (s.status === "timeout") {
                addMsg("error", `Approval request timed out.`);
              } else {
                addMsg("error", `Request was blocked.`);
              }
              setIsProcessing(false);
            }
          } catch {}
          if (++attempts > 90) { stopPoll(); setIsProcessing(false); }
        }, 2000);
        return; // Don't clear processing yet - poll will handle it
      }
    } catch (e: any) {
      addMsg("error", `Failed: ${e.message}`);
    }
    setIsProcessing(false);
  };

  // ── Handle user chat message ────────────────────────────────────────
  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isProcessing) return;

    const userText = text.trim();
    setInput("");
    setIsProcessing(true);

    // Show user message
    addMsg("user", userText);

    // Show typing indicator
    setIsTyping(true);
    await sleep(600 + Math.random() * 400);

    try {
      // Call chat engine
      const res = await api.chatWithAgent(agent.id, userText, agent.title, sessionId);

      setIsTyping(false);

      // Save session ID for conversation continuity
      if (res.session_id) {
        setSessionId(res.session_id);
      }

      // Show agent response
      addMsg("agent", res.response);

      // Update suggestions
      if (res.suggestions?.length > 0) {
        setSuggestions(res.suggestions);
      }

      // If actions were executed server-side, show the result
      if (res.type === "action" && res.action) {
        const a = res.action;
        if (a.status === "auto_approved") {
          addMsg("result", `Auto-approved! ${a.connection}/${a.action} executed via Token Vault.`);
        } else if (a.status === "pending" && a.job_id) {
          addMsg("approval", `Approval required. Waiting for approval...`, {
            jobId: a.job_id,
            status: "pending",
            params: a.params,
          });
          // Start polling for approval result
          let attempts = 0;
          const approvalMsgId = messages[messages.length - 1]?.id;
          pollRef.current = setInterval(async () => {
            try {
              const s = await api.getJobStatus(a.job_id);
              const terminal = ["approved", "rejected", "timeout", "blocked"];
              if (terminal.includes(s.status)) {
                stopPoll();
                if (approvalMsgId) updateMsg(approvalMsgId, { meta: { status: s.status } });
                if (s.status === "approved") {
                  addMsg("result", `Approved! Action executed via Token Vault.`);
                } else {
                  addMsg("error", `Request ${s.status}.`);
                }
                setIsProcessing(false);
              }
            } catch {}
            if (++attempts > 90) { stopPoll(); setIsProcessing(false); }
          }, 2000);
          return; // Don't clear processing — poll will handle it
        }
      }
    } catch {
      setIsTyping(false);
      addMsg("error", "Failed to process message. Please try again.");
    }

    setIsProcessing(false);
  };

  // ── Handle scenario button ──────────────────────────────────────────
  const handleRunScenario = async (index: number) => {
    const scenario = agent.scenarios[index];
    if (!scenario) return;

    setRunningScenario(index);
    setIsProcessing(true);

    addMsg("user", scenario.title);

    setIsTyping(true);
    await sleep(500);
    setIsTyping(false);

    addMsg("agent", `Processing: ${scenario.description}`);

    await sleep(400);
    await executeAction({
      connection: scenario.connection,
      action: scenario.action,
      params: scenario.params,
    });

    setRunningScenario(null);
  };


  const handleReset = () => {
    stopPoll();
    if (sessionId) {
      api.clearAgentSession(agent.id, sessionId).catch(() => {});
    }
    setSessionId("");
    setRunningScenario(null);
    setIsProcessing(false);
    setIsTyping(false);
    setMessages([{
      id: msgId(),
      type: "agent",
      text: `Hello! I'm the ${agent.title}.\n\n${agent.description}\n\nType a message or pick a suggestion below to get started.`,
      timestamp: new Date(),
    }]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.map(msg => (
          <ChatBubble key={msg.id} msg={msg} />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={chatEndRef} />
      </div>

      {/* Suggestion chips */}
      {suggestions.length > 0 && messages.length <= 3 && (
        <div className="px-4 pb-2">
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <SuggestionChip key={i} label={s} onClick={() => handleSendMessage(s)} />
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3">
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isProcessing ? "Processing..." : `Message ${agent.title}...`}
              disabled={isProcessing}
              className="w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-4 py-2.5 text-sm text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 transition-colors"
            />
          </div>
          <Button
            size="sm"
            onClick={() => handleSendMessage(input)}
            disabled={!input.trim() || isProcessing}
            className="h-10 w-10 p-0 rounded-xl shrink-0"
          >
            {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
          <button
            onClick={() => setShowScenarios(v => !v)}
            className={`h-10 w-10 flex items-center justify-center rounded-xl border transition-colors shrink-0 ${
              showScenarios
                ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 border-zinc-900 dark:border-zinc-100"
                : "border-zinc-200 dark:border-zinc-700 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:border-zinc-300 dark:hover:border-zinc-600"
            }`}
            title="Toggle scenarios"
          >
            <Zap className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowKeyInput(v => !v)}
            className={`h-10 w-10 flex items-center justify-center rounded-xl border transition-colors shrink-0 ${
              hasAIKey
                ? "bg-green-50 dark:bg-green-950/30 border-green-300 dark:border-green-700 text-green-600 dark:text-green-400"
                : showKeyInput
                ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 border-zinc-900 dark:border-zinc-100"
                : "border-amber-300 dark:border-amber-700 text-amber-500 hover:text-amber-600 dark:hover:text-amber-400 hover:border-amber-400 dark:hover:border-amber-600"
            }`}
            title={hasAIKey ? "Gemini API key configured ✓" : "Set Gemini API key"}
          >
            <KeyRound className="h-4 w-4" />
          </button>
          <button
            onClick={handleReset}
            className="h-10 w-10 flex items-center justify-center rounded-xl border border-zinc-200 dark:border-zinc-700 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors shrink-0"
            title="Reset chat"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {/* API Key input */}
        {showKeyInput && (
          <div className="mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800">
            {hasAIKey ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  <span className="text-xs text-green-700 dark:text-green-400 font-medium">Gemini API key configured</span>
                  <span className="text-[10px] text-zinc-400">(encrypted on server)</span>
                </div>
                <button
                  onClick={async () => {
                    await api.deleteAIKey();
                    setHasAIKey(false);
                  }}
                  className="text-xs text-red-500 hover:text-red-600"
                >
                  Remove key
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <input
                      type="password"
                      value={keyInput}
                      onChange={(e) => setKeyInput(e.target.value)}
                      placeholder="Paste your Gemini API key..."
                      className="w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 px-3 py-2 text-xs text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <Button
                    size="sm"
                    disabled={!keyInput.trim() || savingKey}
                    onClick={async () => {
                      setSavingKey(true);
                      try {
                        await api.saveAIKey(keyInput.trim());
                        setHasAIKey(true);
                        setKeyInput("");
                      } catch {}
                      setSavingKey(false);
                    }}
                    className="h-8 px-3 text-xs"
                  >
                    {savingKey ? <Loader2 className="h-3 w-3 animate-spin" /> : "Save"}
                  </Button>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1.5">
                  Free key from <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">aistudio.google.com/apikey</a> — encrypted and stored on the server, never in your browser.
                </p>
              </>
            )}
          </div>
        )}

        {/* Collapsible scenarios panel */}
        {showScenarios && (
          <div className="mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Quick Scenarios</p>
            <div className="space-y-2 max-h-48 overflow-y-auto">
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
        )}
      </div>
    </div>
  );
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)); }
