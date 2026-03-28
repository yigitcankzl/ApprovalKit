"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  Copy, Check, Eye, EyeOff, Loader2, CheckCircle2, Plug, Plus,
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

  const codeSnippet = (agentName: string) =>
`from approvalkit import ApprovalKit
import os

kit = ApprovalKit(
    base_url=os.environ["APPROVALKIT_URL"],
    api_key=os.environ["APPROVALKIT_API_KEY"],
    hmac_secret=os.environ["APPROVALKIT_HMAC_SECRET"],
    user_id="${agentName}",
)

# One line per action — Token Vault executes after approval
kit.gate("your-connection", "your-action", {"key": "value"})`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-zinc-900 dark:bg-zinc-100 rounded-lg">
            <Plug className="h-5 w-5 text-white dark:text-zinc-900" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Connect Your Agent</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Create an agent, set env vars, call kit.gate(). Three steps.</p>
          </div>
        </div>
      </div>

      {/* Step 1: Create agent */}
      <Card className="mb-4">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-1">1. Create an agent</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">Each agent gets its own API key.</p>
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

      {/* Step 2: Set env vars */}
      <Card className="mb-4">
        <CardContent className="p-5">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-3">2. Set environment variables</h2>
          <CopyBlock code={envSnippet} />
        </CardContent>
      </Card>

      {/* Step 3: Install + use */}
      <Card className="mb-4">
        <CardContent className="p-5 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-1">3. Install SDK and call gate()</h2>
          <CopyBlock code={`pip install "approvalkit @ git+https://github.com/yigitcankzl/ApprovalKit.git#subdirectory=sdk"`} />
          <CopyBlock code={codeSnippet(newAgent?.name || "my-agent")} />
          <p className="text-xs text-zinc-400">
            Set up rules and connections from the <a href="/rules" className="text-blue-500 hover:underline">Rules</a> and <a href="/connections" className="text-blue-500 hover:underline">Connections</a> pages.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
