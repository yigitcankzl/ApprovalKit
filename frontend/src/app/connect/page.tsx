"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  Copy, Check, Eye, EyeOff, Loader2, CheckCircle2, Plug, Plus, FileCode, Terminal,
} from "lucide-react";

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
      <div className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-2.5">
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

interface Agent {
  id: string;
  name: string;
  api_key?: string;
  is_active: boolean;
  created_at: string;
}

export default function ConnectPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [hmacSecret, setHmacSecret] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");

  // Create agent
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newAgent, setNewAgent] = useState<{ id: string; api_key: string; name: string } | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setBaseUrl(process.env.NEXT_PUBLIC_API_URL || window.location.origin.replace(":3000", ":8000"));
    }
    Promise.all([
      api.getMyAgents().then((a: Agent[]) => setAgents(a)).catch(() => {}),
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
      setAgents(prev => [res, ...prev]);
      setName("");
    } catch {}
    setCreating(false);
  };

  const envSnippet = `export APPROVALKIT_URL=${baseUrl}
export APPROVALKIT_API_KEY=ak_...
export APPROVALKIT_HMAC_SECRET=...`;

  const manualSnippet = (agentName: string) =>
`from approvalkit import ApprovalKit
import os

kit = ApprovalKit(
    base_url=os.environ["APPROVALKIT_URL"],
    api_key=os.environ["APPROVALKIT_API_KEY"],
    hmac_secret=os.environ["APPROVALKIT_HMAC_SECRET"],
    user_id="${agentName}",
)

kit.gate("your-connection", "your-action", {"key": "value"})`;

  const yamlTemplate = `agent:
  name: ${newAgent?.name || "my-agent"}

connections:
  - slug: stripe-prod
    service: stripe
    actions: [charge, refund]
  - slug: gmail-prod
    service: gmail
    actions: [send_email]

approvers:
  - name: Manager
    email: manager@company.com
    role: manager

rules:
  - name: Charges over $500
    connection: stripe-prod
    action: charge
    model: specific
    approvers: [manager]
    conditions:
      - field: amount
        operator: gte
        value: 500
  - name: All emails
    connection: gmail-prod
    action: send_email
    model: any_one
    approvers: [manager]`;

  const fromConfigSnippet = `from approvalkit import ApprovalKit

kit = ApprovalKit.from_config("approvalkit.yaml")

kit.gate("stripe-prod", "charge", {"amount": 349, "customer": "alice@example.com"})`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-zinc-900 dark:bg-zinc-100 rounded-lg">
            <Plug className="h-5 w-5 text-white dark:text-zinc-900" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Connect Your Agent</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Two ways to integrate — pick whichever fits your workflow.</p>
          </div>
        </div>
      </div>

      {/* Step 0: Create agent + get key */}
      <Card className="mb-6">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-1">First, create an agent and get your API key</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">Each agent gets its own key. You can manage them on the <a href="/agents" className="text-blue-500 hover:underline">Agents</a> page.</p>
          <div className="flex gap-2">
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreate()}
              placeholder="e.g. shopping-bot, deploy-agent, hr-assistant"
              className="flex-1 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400"
            />
            <Button onClick={handleCreate} disabled={creating || !name.trim()}>
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <><Plus className="h-4 w-4 mr-1.5" /> Create</>
              )}
            </Button>
          </div>

          {/* Show key after creation */}
          {newAgent && (
            <div className="mt-4 p-4 rounded-xl border border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20 space-y-3">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-green-800 dark:text-green-300">
                    Agent &ldquo;{newAgent.name}&rdquo; created
                  </p>
                  <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">
                    Save this API key — it is shown only once.
                  </p>
                </div>
              </div>
              <SecretField label="API Key" value={newAgent.api_key} />
              {hmacSecret && <SecretField label="HMAC Secret" value={hmacSecret} />}
            </div>
          )}

          {/* Existing agents */}
          {agents.length > 0 && !newAgent && (
            <div className="mt-4 space-y-1.5">
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Your agents</p>
              {agents.map(a => (
                <div key={a.id} className="flex items-center justify-between p-2.5 rounded-lg border border-zinc-100 dark:border-zinc-800">
                  <div className="flex items-center gap-2.5">
                    <div className={`w-2 h-2 rounded-full ${a.is_active ? "bg-green-500" : "bg-zinc-300"}`} />
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">{a.name}</span>
                  </div>
                  <span className="text-[10px] text-zinc-400 font-mono">{a.id.slice(0, 8)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Install SDK */}
      <Card className="mb-6">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-3">Install SDK</h2>
          <CopyBlock code={`pip install "approvalkit @ git+https://github.com/yigitcankzl/ApprovalKit.git#subdirectory=sdk"`} />
        </CardContent>
      </Card>

      {/* Two paths side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Path A: Manual / inline */}
        <Card className="border-zinc-300 dark:border-zinc-600">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                <Terminal className="h-4 w-4 text-zinc-600 dark:text-zinc-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Manual Setup</h2>
                <p className="text-xs text-zinc-400">Set env vars, call kit.gate() directly</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">1. Set env vars</p>
              <CopyBlock code={envSnippet} />
            </div>

            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">2. Use in your agent</p>
              <CopyBlock code={manualSnippet(newAgent?.name || "my-agent")} />
            </div>

            <p className="text-xs text-zinc-400">
              Create rules and connections from the dashboard.
            </p>
          </CardContent>
        </Card>

        {/* Path B: from_config YAML */}
        <Card className="border-blue-200 dark:border-blue-700">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <FileCode className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">YAML Config</h2>
                <p className="text-xs text-zinc-400">Define everything in a file, bootstrap in one line</p>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">1. Set env vars (same as manual)</p>
              <CopyBlock code={envSnippet} />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">2. Create approvalkit.yaml</p>
                <button
                  onClick={() => {
                    const blob = new Blob([yamlTemplate], { type: "text/yaml" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "approvalkit.yaml";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="text-[10px] text-blue-500 hover:text-blue-600 font-medium"
                >
                  Download template
                </button>
              </div>
              <CopyBlock code={yamlTemplate} />
            </div>

            <div>
              <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">3. Use in your agent</p>
              <CopyBlock code={fromConfigSnippet} />
            </div>

            <p className="text-xs text-zinc-400">
              Connections, approvers, and rules are auto-created on first run. No dashboard needed.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
