"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import {
  CheckCircle2, ArrowRight, Shield, Link2, GitBranch, Users, Plug,
  Copy, Check, Loader2, LogOut, Bot,
} from "lucide-react";
import { api, setUserSub } from "@/lib/api";

export default function SetupPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [done, setDone] = useState(false);
  const [tenant, setTenant] = useState("");
  const [m2mClientId, setM2mClientId] = useState("");
  const [m2mClientSecret, setM2mClientSecret] = useState("");
  const [webClientId, setWebClientId] = useState("");
  const [webClientSecret, setWebClientSecret] = useState("");
  const [fgaStoreId, setFgaStoreId] = useState("");
  const [fgaClientId, setFgaClientId] = useState("");
  const [fgaClientSecret, setFgaClientSecret] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [hmacSecret, setHmacSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedHmac, setCopiedHmac] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/auth/login?returnTo=/setup"); return; }
    setUserSub(user.sub ?? null);
    api.getWorkspace()
      .then(() => router.replace("/dashboard"))
      .catch(() => setChecking(false));
  }, [authLoading, user]);

  const handleSetup = async () => {
    if (!tenant.trim()) { setError("Auth0 tenant name is required."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.setupWorkspace({
        name: user?.name ? `${user.name}'s Workspace` : "My Workspace",
        auth0_tenant: tenant,
        auth0_domain: tenant,
        auth0_m2m_client_id: m2mClientId || undefined,
        auth0_m2m_client_secret: m2mClientSecret || undefined,
        auth0_web_client_id: webClientId || undefined,
        auth0_web_client_secret: webClientSecret || undefined,
        fga_store_id: fgaStoreId || undefined,
        fga_client_id: fgaClientId || undefined,
        fga_client_secret: fgaClientSecret || undefined,
      });
      if (res.api_key) setApiKey(res.api_key);
      if (res.hmac_secret) setHmacSecret(res.hmac_secret);
      setDone(true);
    } catch (err: any) {
      setError(err.message || "Failed to connect. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-2xl">
        {/* Logo + title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            {done ? "Workspace Ready!" : "Set up your workspace"}
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1 text-sm">
            {user?.email && (
              <>
                Signed in as <strong>{user.email}</strong>
                {" · "}
                <a href="/auth/logout" className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
                  <LogOut className="h-3 w-3" /> Logout
                </a>
              </>
            )}
          </p>
        </div>

        {/* Setup Form */}
        {!done && (
          <Card>
            <CardHeader>
              <CardTitle>Connect Auth0</CardTitle>
              <CardDescription>Paste credentials from your Auth0 Dashboard. All secrets are stored in HashiCorp Vault.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">

              {/* Auth0 Domain */}
              <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-xs text-blue-700 dark:text-blue-300 font-medium mb-1">Auth0 Dashboard &rarr; Settings &rarr; General &rarr; Tenant Name</p>
                <p className="text-xs text-blue-600 dark:text-blue-400">Enter your tenant name. The <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">.us.auth0.com</code> suffix is added automatically.</p>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Auth0 Tenant Name *</label>
                <div className="flex items-center gap-0 mt-1">
                  <Input
                    placeholder="dev-xxxxxxxx"
                    value={tenant.replace(/\.us\.auth0\.com$/, "")}
                    onChange={(e) => {
                      const raw = e.target.value.replace(/\.us\.auth0\.com$/, "").trim();
                      setTenant(raw ? `${raw}.us.auth0.com` : "");
                    }}
                    className="rounded-r-none font-mono text-xs"
                  />
                  <span className="px-3 py-2 bg-zinc-100 dark:bg-zinc-800 border border-l-0 border-zinc-200 dark:border-zinc-700 rounded-r-md text-xs text-zinc-500 dark:text-zinc-400 whitespace-nowrap">.us.auth0.com</span>
                </div>
              </div>

              {/* M2M Application */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg mb-3">
                  <p className="text-xs text-blue-700 dark:text-blue-300 font-medium">Applications &rarr; Create Application &rarr; Machine to Machine</p>
                  <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">Popup: &quot;Select an API&quot; &rarr; <strong>Auth0 Management API</strong> &rarr; check: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">read:users</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">update:users</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">read:connections</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">create:connections</code> &rarr; Authorize</p>
                  <p className="text-xs text-green-700 dark:text-green-400 font-medium mt-1">Copy Client ID + Client Secret (click Reveal):</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client ID</label>
                    <Input placeholder="PsP2e0l..." value={m2mClientId} onChange={(e) => setM2mClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client Secret</label>
                    <Input type="password" placeholder="JgHrS7TD..." value={m2mClientSecret} onChange={(e) => setM2mClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                </div>
              </div>

              {/* Web Application */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg mb-3">
                  <p className="text-xs text-blue-700 dark:text-blue-300 font-medium">Applications &rarr; Create Application &rarr; Regular Web Application</p>
                  <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">Settings tab:</p>
                  <ul className="text-xs text-blue-600 dark:text-blue-400 mt-1 ml-3 list-disc space-y-0.5">
                    <li>Allowed Callback URLs: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">http://localhost:3000/auth/callback</code></li>
                    <li>Allowed Logout URLs: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">http://localhost:3000</code></li>
                    <li>Advanced Settings &rarr; Grant Types &rarr; Enable <strong>CIBA</strong> + <strong>Token Exchange</strong></li>
                  </ul>
                  <p className="text-xs text-green-700 dark:text-green-400 font-medium mt-1">Copy Client ID + Client Secret:</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web App Client ID</label>
                    <Input placeholder="GVNbXp..." value={webClientId} onChange={(e) => setWebClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web App Client Secret</label>
                    <Input type="password" placeholder="KRLgl7..." value={webClientSecret} onChange={(e) => setWebClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                </div>
              </div>

              {/* Token Vault + Guardian reminder */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">Don&apos;t forget in Auth0 Dashboard:</p>
                  <ul className="text-xs text-amber-600 dark:text-amber-400 mt-1 ml-3 list-disc space-y-0.5">
                    <li><strong>Token Vault:</strong> Authentication &rarr; Social &rarr; each connection &rarr; Advanced &rarr; Enable Token Vault</li>
                    <li><strong>Guardian:</strong> Security &rarr; Multi-factor Auth &rarr; Push via Auth0 Guardian &rarr; Enable</li>
                  </ul>
                </div>
              </div>

              {/* FGA */}
              <details className="group">
                <summary className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-300">
                  FGA — Fine-Grained Authorization (Optional)
                </summary>
                <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1 mb-3">Without FGA, all authenticated users get full access.</p>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs text-zinc-600 dark:text-zinc-400">Store ID</label>
                    <Input placeholder="01KMG6..." value={fgaStoreId} onChange={(e) => setFgaStoreId(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-600 dark:text-zinc-400">Client ID</label>
                    <Input value={fgaClientId} onChange={(e) => setFgaClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-600 dark:text-zinc-400">Client Secret</label>
                    <Input type="password" value={fgaClientSecret} onChange={(e) => setFgaClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                </div>
              </details>

              <FormError message={error} />

              <div className="flex justify-end">
                <Button onClick={handleSetup} disabled={!tenant.trim() || loading} size="lg">
                  {loading ? "Connecting..." : "Create Workspace"}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Success — credentials + next steps */}
        {done && (
          <div className="space-y-6">
            {/* Credentials (shown once) */}
            {(apiKey || hmacSecret) && (
              <Card className="border-green-200 dark:border-green-800">
                <CardContent className="pt-6 space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <p className="text-sm font-medium text-green-800 dark:text-green-300">
                      Workspace created! Save these credentials — they won&apos;t be shown again.
                    </p>
                  </div>
                  {apiKey && (
                    <div>
                      <label className="text-xs font-semibold text-green-700 dark:text-green-400">Workspace API Key</label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 text-xs bg-white dark:bg-zinc-900 border rounded px-3 py-2 font-mono truncate">{apiKey}</code>
                        <button onClick={() => { navigator.clipboard.writeText(apiKey); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                          className="p-2 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400">
                          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}
                  {hmacSecret && (
                    <div>
                      <label className="text-xs font-semibold text-green-700 dark:text-green-400">HMAC Secret</label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 text-xs bg-white dark:bg-zinc-900 border rounded px-3 py-2 font-mono truncate">{hmacSecret}</code>
                        <button onClick={() => { navigator.clipboard.writeText(hmacSecret); setCopiedHmac(true); setTimeout(() => setCopiedHmac(false), 2000); }}
                          className="p-2 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400">
                          {copiedHmac ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-red-600 dark:text-red-400 font-medium">These credentials will NOT be shown again. Copy them now.</p>
                </CardContent>
              </Card>
            )}

            {/* What to do next */}
            <Card>
              <CardHeader>
                <CardTitle>What to do next</CardTitle>
                <CardDescription>Your workspace is configured. Here&apos;s how to get started:</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  <button onClick={() => router.push("/connections")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/50 dark:hover:bg-blue-950/20 transition-colors text-left">
                    <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Plug className="h-4 w-4 text-blue-700 dark:text-blue-300" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Connect Services</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Link Stripe, GitHub, Slack, Gmail via OAuth. Credentials stored in Auth0 Token Vault — your agents never see raw API keys.</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                  </button>

                  <button onClick={() => router.push("/rules/new")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-purple-300 dark:hover:border-purple-700 hover:bg-purple-50/50 dark:hover:bg-purple-950/20 transition-colors text-left">
                    <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <GitBranch className="h-4 w-4 text-purple-700 dark:text-purple-300" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Create Approval Rules</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Define when human approval is needed. Example: &quot;Stripe charges over $500 require manager approval via Guardian push.&quot;</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                  </button>

                  <button onClick={() => router.push("/approvers")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-amber-300 dark:hover:border-amber-700 hover:bg-amber-50/50 dark:hover:bg-amber-950/20 transition-colors text-left">
                    <div className="w-8 h-8 rounded-full bg-amber-100 dark:bg-amber-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Users className="h-4 w-4 text-amber-700 dark:text-amber-300" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Add Approvers</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Add team members who will approve agent actions. They&apos;ll receive push notifications via Auth0 Guardian on their phone.</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                  </button>

                  <button onClick={() => router.push("/connect")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-green-300 dark:hover:border-green-700 hover:bg-green-50/50 dark:hover:bg-green-950/20 transition-colors text-left">
                    <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Bot className="h-4 w-4 text-green-700 dark:text-green-300" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Connect Your Agent</p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Get your SDK code snippet, test the approval flow live, and register your agent with a unique API key.</p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                  </button>
                </div>

                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                  <Button className="w-full" onClick={() => router.push("/dashboard")}>
                    Go to Dashboard <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
