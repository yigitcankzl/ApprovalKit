"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  Copy, Check, Eye, EyeOff, Terminal, Plug, Play, Loader2,
  CheckCircle2, XCircle, Clock, Send, RefreshCw, BookMarked,
  ShoppingCart, Server, Package, FlaskConical, CreditCard, Mail, Users, Bot,
} from "lucide-react";
import { FormError } from "@/components/ui/form-error";

// ── Helpers ───────────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={copy} className="p-1.5 rounded hover:bg-zinc-700 transition-colors text-zinc-400 hover:text-zinc-200">
      {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

function SecretField({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  const display = visible ? value : "•".repeat(Math.min(value.length, 40));
  return (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">{label}</label>
      <div className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-2">
        <span className={`flex-1 text-sm text-zinc-100 ${mono ? "font-mono" : ""} break-all`}>{display}</span>
        <button onClick={() => setVisible((v) => !v)} className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200">
          {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
        <button onClick={copy} className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200">
          {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}

// ── Step indicator ────────────────────────────────────────────────────────────

function Step({ n, title, active }: { n: number; title: string; active?: boolean }) {
  return (
    <div className={`flex items-center gap-3 mb-4 ${active ? "" : "opacity-60"}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${active ? "bg-zinc-900 text-white" : "bg-zinc-200 text-zinc-500"}`}>
        {n}
      </div>
      <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
    </div>
  );
}

// ── Code block ────────────────────────────────────────────────────────────────

function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  return (
    <div className="relative group">
      <pre className="bg-zinc-900 text-zinc-100 text-xs rounded-lg p-4 overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <CopyButton text={code} />
      </div>
    </div>
  );
}

// ── Live test flow step ───────────────────────────────────────────────────────

function FlowStep({ done, active, label, sub }: { done: boolean; active?: boolean; label: string; sub?: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 w-3 h-3 rounded-full shrink-0 ${done ? "bg-green-500" : active ? "bg-blue-500 animate-pulse" : "bg-zinc-200"}`} />
      <div>
        <span className={`text-sm ${done ? "text-zinc-800 font-medium" : active ? "text-blue-600 font-medium" : "text-zinc-400"}`}>{label}</span>
        {sub && <p className="text-xs text-zinc-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Connection + action selects ───────────────────────────────────────────────

interface Conn { id: string; name: string; slug: string; actions: string[] }

// ── Main page ─────────────────────────────────────────────────────────────────

const ICON_OPTIONS = [
  { value: "bot",          label: "Bot",         Icon: Bot },
  { value: "shopping-cart",label: "E-Commerce",  Icon: ShoppingCart },
  { value: "users",        label: "HR",          Icon: Users },
  { value: "server",       label: "DevOps",      Icon: Server },
  { value: "package",      label: "Open Source", Icon: Package },
  { value: "flask",        label: "Research",    Icon: FlaskConical },
  { value: "credit-card",  label: "Fintech",     Icon: CreditCard },
  { value: "mail",         label: "Comms",       Icon: Mail },
];

interface Credentials { api_key: string; hmac_secret: string; workspace_id: string; name: string }
interface JobState { status: string; final_params?: any; completed_at?: string }

export default function ConnectPage() {
  const router = useRouter();
  const [creds, setCreds] = useState<Credentials | null>(null);
  const [credsLoading, setCredsLoading] = useState(true);

  const [connections, setConnections] = useState<Conn[]>([]);
  const [conn, setConn] = useState("");
  const [action, setAction] = useState("");
  const [paramsText, setParamsText] = useState('{\n  "amount_usd": 349,\n  "customer": "demo@example.com",\n  "description": "Test charge"\n}');
  const [agentName, setAgentName] = useState("my-agent");

  const [sending, setSending] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<JobState | null>(null);
  const [sendMsg, setSendMsg] = useState<string | null>(null);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Save as Agent state
  const [saveAgentName, setSaveAgentName] = useState("");
  const [saveAgentDesc, setSaveAgentDesc] = useState("");
  const [saveAgentIcon, setSaveAgentIcon] = useState("bot");
  const [saveScenarioTitle, setSaveScenarioTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [savedApiKey, setSavedApiKey] = useState<string | null>(null);

  useEffect(() => {
    api.getCredentials()
      .then((c: Credentials) => setCreds(c))
      .catch(() => setCreds(null))
      .finally(() => setCredsLoading(false));

    api.getConnections()
      .then((list: Conn[]) => {
        setConnections(list);
        if (list.length) {
          setConn(list[0].slug);
          if (list[0].actions?.length) setAction(list[0].actions[0]);
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveAgent = async () => {
    if (!saveAgentName.trim()) { setSaveErr("Agent name is required"); return; }
    setSaving(true);
    setSaveErr(null);
    try {
      let params: Record<string, unknown> = {};
      try { params = JSON.parse(paramsText); } catch {}
      const scenarios = conn && action ? [{
        title: saveScenarioTitle || `${action} on ${conn}`,
        connection: conn,
        action,
        params,
      }] : [];
      const res = await api.createMyAgent({
        name: saveAgentName,
        description: saveAgentDesc || undefined,
        icon: saveAgentIcon,
        allowed_connections: conn ? [conn] : undefined,
        scenarios,
      });
      setSavedId(res.id);
      if (res.api_key) setSavedApiKey(res.api_key);
    } catch (e: any) {
      setSaveErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleConnChange = (slug: string) => {
    setConn(slug);
    const c = connections.find((x) => x.slug === slug);
    setAction(c?.actions?.[0] ?? "");
  };

  const stopPoll = () => {
    if (pollRef.current) { clearTimeout(pollRef.current as unknown as number); pollRef.current = null; }
  };

  const startPoll = (id: string) => {
    stopPoll();
    let delay = 2000;
    const poll = async () => {
      try {
        const s = await api.getJobStatus(id);
        setJobState(s);
        const terminal = ["approved", "rejected", "timeout", "blocked"];
        if (terminal.includes(s.status)) { stopPoll(); return; }
      } catch {}
      delay = Math.min(delay * 1.5, 15000);
      pollRef.current = setTimeout(poll, delay) as unknown as ReturnType<typeof setInterval>;
    };
    pollRef.current = setTimeout(poll, delay) as unknown as ReturnType<typeof setInterval>;
  };

  const handleSend = async () => {
    setSending(true);
    setSendErr(null);
    setSendMsg(null);
    setJobId(null);
    setJobState(null);
    stopPoll();
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(paramsText);
    } catch {
      setSendErr("Invalid JSON in parameters. Check your syntax.");
      setSending(false);
      return;
    }
    try {
      const res = await api.sendTestRequest({ connection: conn, action, params });
      setSendMsg(res.message);
      if (res.job_id) {
        setJobId(res.job_id);
        setJobState({ status: "pending" });
        startPoll(res.job_id);
      } else {
        setJobState({ status: res.status });
      }
    } catch (e: any) {
      setSendErr(e.message);
    } finally {
      setSending(false);
    }
  };

  const handleDecide = async (decision: "approve" | "reject") => {
    if (!jobId) return;
    setDeciding(true);
    try {
      await api.submitDecision(jobId, { decision });
      const s = await api.getJobStatus(jobId);
      setJobState(s);
      stopPoll();
    } catch (e: any) {
      setSendErr(e.message);
    } finally {
      setDeciding(false);
    }
  };

  const status = jobState?.status ?? null;
  const isDone = status && ["approved", "rejected", "timeout", "blocked", "auto_approved"].includes(status);
  const isPending = status === "pending" || status === "ciba_sent" || status === "waiting_approval";

  const baseUrl = typeof window !== "undefined" ? (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") : "http://localhost:8000";

  const sdkSnippet = `pip install approvalkit`;

  const configSnippet = `from approvalkit import ApprovalKit

kit = ApprovalKit(
    base_url="${baseUrl}",
    api_key="<save agent below to get your ak_* key>",
    hmac_secret="${creds?.hmac_secret ?? "<YOUR_HMAC_SECRET>"}",
)`;

  const tpl = "Charge ${amount_usd} for {customer}";
  const decoratorSnippet = `@kit.requires_approval(
    connection="${conn || "stripe-prod"}",
    action="${action || "charge"}",
    context_template="${tpl}",
)
def ${agentName.replace(/[^a-z0-9_]/gi, "_")}_${action || "charge"}(amount_usd: int, customer: str):
    # Your code here — executed only after approval
    pass`;

  const selectedConn = connections.find((c) => c.slug === conn);

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-zinc-900 rounded-lg">
            <Plug className="h-5 w-5 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-zinc-900">Connect Your Agent</h1>
        </div>
        <p className="text-zinc-500">
          Three steps to hook any Python function into the approval system.
          Paste your credentials, add one decorator, and you&apos;re live.
        </p>
      </div>

      {/* ── Step 1: Credentials ── */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <Step n={1} title="Get your credentials" active />
        </CardHeader>
        <CardContent className="space-y-4">
          {credsLoading ? (
            <div className="flex items-center gap-2 text-zinc-400 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading credentials…
            </div>
          ) : creds ? (
            <>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Base URL</label>
                <div className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-2">
                  <span className="flex-1 text-sm text-zinc-100 font-mono">{baseUrl}</span>
                  <CopyButton text={baseUrl} />
                </div>
              </div>
              <SecretField label="HMAC Secret" value={creds.hmac_secret} />
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-800">
                Each agent gets its own API key. Save your agent below (Step 5) to generate a unique <code className="bg-blue-100 px-1 rounded">ak_*</code> key.
              </div>
            </>
          ) : (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
              No workspace found. Go to{" "}
              <a href="/onboarding" className="underline font-medium">Onboarding</a> to set one up first.
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Step 2: Install & configure ── */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <Step n={2} title="Install the SDK & configure" active />
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-zinc-500 mb-2">Install once:</p>
            <CodeBlock code={sdkSnippet} language="bash" />
          </div>
          <div>
            <p className="text-xs text-zinc-500 mb-2">
              Initialize with your credentials{creds ? " (pre-filled above)" : ""}:
            </p>
            <CodeBlock code={configSnippet} />
          </div>
        </CardContent>
      </Card>

      {/* ── Step 3: Protect any function ── */}
      <Card className="mb-6">
        <CardHeader className="pb-3">
          <Step n={3} title="Add a decorator to any function" active />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-0">
              <label className="text-xs text-zinc-500 block mb-1">Connection</label>
              <select
                value={conn}
                onChange={(e) => handleConnChange(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm"
              >
                {connections.map((c) => (
                  <option key={c.slug} value={c.slug}>{c.name} ({c.slug})</option>
                ))}
                {connections.length === 0 && <option value="">No connections — seed demo data first</option>}
              </select>
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-xs text-zinc-500 block mb-1">Action</label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm"
              >
                {(selectedConn?.actions ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-xs text-zinc-500 block mb-1">Function / agent name</label>
              <input
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="my_agent"
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-mono"
              />
            </div>
          </div>
          <CodeBlock code={decoratorSnippet} />
          <p className="text-xs text-zinc-400">
            The function body runs <strong>only after the approver taps Approve</strong> in Guardian.
            Everything else — CIBA push, waiting, retry — is handled by the SDK.
          </p>
        </CardContent>
      </Card>

      {/* ── Step 4: Live test ── */}
      <Card>
        <CardHeader className="pb-3">
          <Step n={4} title="Send a live test request" active />
          <p className="text-sm text-zinc-500 -mt-1">
            Fires the real approval flow — matching your rules, sending CIBA push.
            No HMAC needed from the dashboard.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-500 block mb-1">Connection</label>
              <select
                value={conn}
                onChange={(e) => handleConnChange(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm"
              >
                {connections.map((c) => (
                  <option key={c.slug} value={c.slug}>{c.name} ({c.slug})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-zinc-500 block mb-1">Action</label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value)}
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm"
              >
                {(selectedConn?.actions ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs text-zinc-500 block mb-1">Parameters (JSON)</label>
            <textarea
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
              rows={5}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-zinc-400"
            />
          </div>

          <FormError message={sendErr} />

          <Button onClick={handleSend} disabled={sending || !conn || !action} className="w-full">
            {sending
              ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Sending…</>
              : <><Send className="h-4 w-4 mr-2" />Send Test Request</>}
          </Button>

          {/* Live flow */}
          {(jobId || jobState) && (
            <div className="border border-zinc-200 rounded-xl p-4 space-y-4 bg-zinc-50/50">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Live Flow</p>
                {isPending && (
                  <div className="flex items-center gap-1.5 text-xs text-blue-600">
                    <Loader2 className="h-3 w-3 animate-spin" /> Polling…
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <FlowStep done label="Request submitted" sub={sendMsg ?? undefined} />
                <FlowStep
                  done={!!status && status !== "pending"}
                  active={status === "pending"}
                  label="Rule evaluated"
                  sub={status === "auto_approved" ? "No rule — auto-approved" : undefined}
                />
                <FlowStep
                  done={["ciba_sent", "waiting_approval", "approved", "rejected"].includes(status ?? "")}
                  active={status === "pending"}
                  label="CIBA push sent to approver(s)"
                />
                <FlowStep
                  done={status === "approved"}
                  active={status === "ciba_sent" || status === "waiting_approval"}
                  label="Waiting for Guardian approval"
                />
                {status === "approved" && (
                  <FlowStep done label="Token Vault executes action" sub="Action ran with approved params" />
                )}
                {status === "rejected" && (
                  <FlowStep done label="Rejected" sub="Approver denied the request" />
                )}
                {(status === "timeout" || status === "blocked") && (
                  <FlowStep done label="Timed out / blocked" sub="No approval received in time" />
                )}
              </div>

              {/* Status badge */}
              <div className="flex items-center gap-2 pt-1">
                <div className={`h-2 w-2 rounded-full ${
                  status === "approved" ? "bg-green-500" :
                  status === "rejected" ? "bg-red-500" :
                  status === "auto_approved" ? "bg-green-400" :
                  isPending ? "bg-blue-500 animate-pulse" :
                  "bg-zinc-400"
                }`} />
                <span className="text-sm font-medium capitalize text-zinc-700">
                  {status?.replace(/_/g, " ")}
                </span>
                {jobId && <span className="text-xs text-zinc-400 font-mono ml-auto">{jobId.slice(0, 8)}…</span>}
              </div>

              {/* Manual approve/reject for demo */}
              {isPending && jobId && (
                <div className="border-t border-zinc-200 pt-3">
                  <p className="text-xs text-zinc-400 mb-2">
                    No Guardian app? Approve or reject directly from here:
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleDecide("approve")}
                      disabled={deciding}
                      className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                    >
                      {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />}
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDecide("reject")}
                      disabled={deciding}
                      className="flex-1 border-red-200 text-red-600 hover:bg-red-50"
                    >
                      {deciding ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5 mr-1.5" />}
                      Reject
                    </Button>
                  </div>
                </div>
              )}

              {isDone && !isPending && (
                <button
                  onClick={() => { setJobId(null); setJobState(null); setSendMsg(null); }}
                  className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-600"
                >
                  <RefreshCw className="h-3 w-3" /> Send another
                </button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Step 5: Save as Agent ── */}
      <Card className="mt-6">
        <CardHeader className="pb-3">
          <Step n={5} title="Save as My Agent" active />
          <p className="text-sm text-zinc-500 -mt-1">
            Name your agent and save it so it shows up in the Agents page alongside the built-in demos.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {savedId ? (
            <div className="space-y-3">
              <div className="flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-semibold text-green-800">Agent created with unique API key!</p>
                  <p className="text-xs text-green-700 mt-0.5">
                    Save this key — it is shown only once.
                  </p>
                </div>
              </div>
              {savedApiKey && (
                <SecretField label="Agent API Key" value={savedApiKey} />
              )}
              {creds && (
                <SecretField label="HMAC Secret (shared)" value={creds.hmac_secret} />
              )}
              <div className="bg-zinc-950 rounded-lg p-4">
                <p className="text-xs text-zinc-400 mb-2">Use in your agent:</p>
                <pre className="text-xs text-zinc-100 font-mono overflow-x-auto">{`from approvalkit import ApprovalKit

kit = ApprovalKit(
    base_url="${typeof window !== 'undefined' ? window.location.origin.replace(':3000', ':8000') : 'http://localhost:8000'}",
    api_key="${savedApiKey || '<your-agent-key>'}",
    hmac_secret="${creds?.hmac_secret || '<hmac-secret>'}",
    user_id="${saveAgentName || 'my-agent'}",
)`}</pre>
              </div>
              <button
                onClick={() => router.push("/agents")}
                className="text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                Go to Agents →
              </button>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Agent name *</label>
                  <input
                    value={saveAgentName}
                    onChange={(e) => setSaveAgentName(e.target.value)}
                    placeholder="My Shopping Bot"
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-400"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">Description</label>
                  <input
                    value={saveAgentDesc}
                    onChange={(e) => setSaveAgentDesc(e.target.value)}
                    placeholder="What does this agent do?"
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-400"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-500 block mb-2">Icon</label>
                <div className="flex gap-2 flex-wrap">
                  {ICON_OPTIONS.map(({ value, label, Icon }) => (
                    <button
                      key={value}
                      onClick={() => setSaveAgentIcon(value)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                        saveAgentIcon === value
                          ? "border-zinc-900 bg-zinc-900 text-white"
                          : "border-zinc-200 text-zinc-600 hover:bg-zinc-50"
                      }`}
                    >
                      <Icon className="h-3.5 w-3.5" /> {label}
                    </button>
                  ))}
                </div>
              </div>

              {conn && action && (
                <div>
                  <label className="text-xs text-zinc-500 block mb-1">First scenario title</label>
                  <input
                    value={saveScenarioTitle}
                    onChange={(e) => setSaveScenarioTitle(e.target.value)}
                    placeholder={`${action} on ${conn}`}
                    className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-400"
                  />
                  <p className="text-xs text-zinc-400 mt-1">
                    Current connection/action/params will be saved as the first scenario.
                  </p>
                </div>
              )}

              <FormError message={saveErr} />

              <Button onClick={handleSaveAgent} disabled={saving || !saveAgentName.trim()} className="w-full">
                {saving
                  ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving…</>
                  : <><BookMarked className="h-4 w-4 mr-2" />Save as My Agent</>}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
