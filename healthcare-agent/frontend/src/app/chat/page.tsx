"use client";

import { useEffect, useRef, useState } from "react";
import { apiPost } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  actions?: ActionResult[];
  timestamp: Date;
}

interface ActionResult {
  tool: string;
  args: Record<string, unknown>;
  result: { status: string; action?: string; message?: string };
}

const SUGGESTIONS = [
  "Prescribe Metformin 500mg to patient Ali Yilmaz (MRN-00001)",
  "Patient MRN-00003 needs emergency access — cardiac arrest",
  "Process $12,000 billing for knee surgery for patient MRN-00002",
  "Share patient MRN-00001 records with City Heart Clinic for cardiology referral",
  "Prescribe Adderall 30mg to patient MRN-00005 (controlled substance)",
  "Send discharge summary email to patient MRN-00001",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiPost("/api/chat", {
        message: text.trim(),
        session_id: sessionId,
      });

      if (res.session_id) setSessionId(res.session_id);

      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: res.response || "",
        actions: res.actions || [],
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: `e-${Date.now()}`,
        role: "system",
        content: `Error: ${e.message}`,
        timestamp: new Date(),
      }]);
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const toolLabels: Record<string, string> = {
    prescribe_medication: "Prescription",
    process_billing: "Billing",
    share_patient_records: "Record Sharing",
    emergency_access: "Emergency Access",
    send_notification: "Email",
  };

  const statusColors: Record<string, string> = {
    approved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    sent: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    denied: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    error: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    simulated_approved: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="shrink-0 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
              Healthcare AI Agent
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              MedCore General Hospital — All actions gated by ApprovalKit
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 px-2 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              ApprovalKit connected
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200 mb-2">
                Healthcare AI Agent
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md mx-auto mb-6">
                Tell me what you need — prescriptions, billing, record sharing, emergency access.
                Every sensitive action goes through ApprovalKit for human approval.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg mx-auto">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => send(s)}
                    className="text-xs text-left px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] ${msg.role === "user" ? "" : ""}`}>
                {/* Role label */}
                {msg.role !== "user" && (
                  <p className="text-[10px] text-zinc-400 mb-1 ml-1 uppercase tracking-wider font-semibold">
                    {msg.role === "assistant" ? "Agent" : "System"}
                  </p>
                )}

                {/* Bubble */}
                <div className={`rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-br-md"
                    : msg.role === "system"
                    ? "bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-bl-md"
                    : "bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 rounded-bl-md"
                }`}>
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>

                {/* Action results */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="mt-2 space-y-1.5 ml-1">
                    {msg.actions.map((a, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className={`shrink-0 px-2 py-0.5 rounded-full font-medium ${statusColors[a.result.status] || "bg-zinc-100 text-zinc-600"}`}>
                          {a.result.status}
                        </span>
                        <span className="text-zinc-500 dark:text-zinc-400">
                          {toolLabels[a.tool] || a.tool}: {a.result.action || a.result.message || JSON.stringify(a.args)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-[10px] text-zinc-400 mt-1 ml-1">
                  {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* Input */}
      <div className="shrink-0 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-6 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send(input)}
            placeholder="e.g. Prescribe Metformin 500mg to patient Ali Yilmaz..."
            disabled={loading}
            className="flex-1 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="px-5 py-3 rounded-xl bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-sm font-medium hover:bg-zinc-700 dark:hover:bg-zinc-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
