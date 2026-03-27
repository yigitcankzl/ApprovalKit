"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import {
  CheckCircle2, ArrowRight, Shield, GitBranch, Users, Plug,
  Copy, Check, Loader2, LogOut, Bot, Rocket,
} from "lucide-react";
import { api, setUserSub } from "@/lib/api";

export default function SetupPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAuth0, setShowAuth0] = useState(false);
  const [m2mClientId, setM2mClientId] = useState("");
  const [m2mClientSecret, setM2mClientSecret] = useState("");
  const [webClientId, setWebClientId] = useState("");
  const [webClientSecret, setWebClientSecret] = useState("");
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [hmacSecret, setHmacSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedHmac, setCopiedHmac] = useState(false);
  const [checking, setChecking] = useState(true);
  const [tenantDomain, setTenantDomain] = useState("");
  const [tenantClientId, setTenantClientId] = useState("");

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/login"); return; }
    setUserSub(user.sub ?? null);

    // Read tenant info from cookie (set at /login)
    fetch("/api/get-tenant").then(r => r.json()).then(data => {
      if (data.domain) setTenantDomain(data.domain);
      if (data.clientId) setTenantClientId(data.clientId);
    }).catch(() => {});

    api.getWorkspace()
      .then(() => router.replace("/dashboard"))
      .catch(() => setChecking(false));
  }, [authLoading, user]);

  const handleSetup = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.setupWorkspace({
        name: user?.name ? `${user.name}'s Workspace` : "My Workspace",
        auth0_domain: tenantDomain || undefined,
        auth0_tenant: tenantDomain || undefined,
        auth0_web_client_id: webClientId || tenantClientId || undefined,
        auth0_web_client_secret: webClientSecret || undefined,
        auth0_m2m_client_id: m2mClientId || undefined,
        auth0_m2m_client_secret: m2mClientSecret || undefined,
      });
      if (res.api_key) setApiKey(res.api_key);
      if (res.hmac_secret) setHmacSecret(res.hmac_secret);
      setDone(true);
    } catch (err: any) {
      setError(err.message || "Failed to create workspace.");
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
      <div className="w-full max-w-lg">
        {/* Logo + title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            {done ? "Workspace Ready!" : "Welcome to ApprovalKit"}
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

        {/* Setup */}
        {!done && (
          <Card>
            <CardContent className="pt-6 space-y-5">
              <div className="text-center">
                <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
                  ApprovalKit is a human approval middleware for AI agents.
                  Create your workspace to start building approval flows with
                  Auth0 Token Vault, CIBA push notifications, and fine-grained access control.
                </p>
              </div>

              <div className="space-y-2.5">
                <div className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">Auth0 Token Vault — agents never see credentials</span>
                </div>
                <div className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">Connect Slack, GitHub, Stripe, Gmail via OAuth</span>
                </div>
                <div className="flex items-center gap-3 p-2.5 rounded-lg bg-zinc-50 dark:bg-zinc-800/50">
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">10 demo agents with AI-powered chat</span>
                </div>
              </div>

              {/* Optional Auth0 credentials */}
              <details className="group" open={showAuth0}>
                <summary
                  onClick={(e) => { e.preventDefault(); setShowAuth0(!showAuth0); }}
                  className="text-xs font-semibold text-zinc-500 cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-300"
                >
                  {showAuth0 ? "Hide" : "Show"} Auth0 Credentials (for your own tenant)
                </summary>
                {showAuth0 && (
                  <div className="mt-3 space-y-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                    <p className="text-xs text-zinc-400">
                      If you logged in with your own Auth0 tenant, enter your M2M and Web App credentials here.
                      Skip this if you used the default tenant.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-zinc-500">M2M Client ID</label>
                        <input value={m2mClientId} onChange={e => setM2mClientId(e.target.value)} className="w-full mt-0.5 rounded border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1.5 text-xs font-mono" placeholder="n5NycPD..." />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">M2M Client Secret</label>
                        <input type="password" value={m2mClientSecret} onChange={e => setM2mClientSecret(e.target.value)} className="w-full mt-0.5 rounded border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1.5 text-xs font-mono" />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">Web App Client ID</label>
                        <input value={webClientId} onChange={e => setWebClientId(e.target.value)} className="w-full mt-0.5 rounded border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1.5 text-xs font-mono" placeholder="fkcfkNQ..." />
                      </div>
                      <div>
                        <label className="text-[10px] text-zinc-500">Web App Client Secret</label>
                        <input type="password" value={webClientSecret} onChange={e => setWebClientSecret(e.target.value)} className="w-full mt-0.5 rounded border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1.5 text-xs font-mono" />
                      </div>
                    </div>
                  </div>
                )}
              </details>

              <FormError message={error} />

              <Button onClick={handleSetup} disabled={loading} size="lg" className="w-full">
                {loading ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Creating workspace...</>
                ) : (
                  <><Rocket className="h-4 w-4 mr-2" /> Create Workspace</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Success */}
        {done && (
          <div className="space-y-6">
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
                      <label className="text-xs font-semibold text-green-700 dark:text-green-400">API Key (for SDK / MCP)</label>
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
                      <label className="text-xs font-semibold text-green-700 dark:text-green-400">HMAC Secret (for SDK / MCP)</label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 text-xs bg-white dark:bg-zinc-900 border rounded px-3 py-2 font-mono truncate">{hmacSecret}</code>
                        <button onClick={() => { navigator.clipboard.writeText(hmacSecret); setCopiedHmac(true); setTimeout(() => setCopiedHmac(false), 2000); }}
                          className="p-2 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400">
                          {copiedHmac ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-zinc-500">These are for the Python SDK and MCP Server. You don&apos;t need them for the demo agents.</p>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle>Get Started</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <button onClick={() => router.push("/demos")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/50 dark:hover:bg-blue-950/20 transition-colors text-left">
                  <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot className="h-4 w-4 text-blue-700 dark:text-blue-300" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Try Demo Agents</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">10 AI agents across finance, devops, HR, healthcare, and legal. Connect your accounts and start chatting.</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                </button>

                <button onClick={() => router.push("/connections")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-green-300 dark:hover:border-green-700 hover:bg-green-50/50 dark:hover:bg-green-950/20 transition-colors text-left">
                  <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Plug className="h-4 w-4 text-green-700 dark:text-green-300" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Connect Services</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Link Slack, GitHub, Stripe, Gmail via OAuth. Credentials stored in Auth0 Token Vault.</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                </button>

                <button onClick={() => router.push("/dashboard")} className="w-full flex items-start gap-3 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-purple-300 dark:hover:border-purple-700 hover:bg-purple-50/50 dark:hover:bg-purple-950/20 transition-colors text-left">
                  <div className="w-8 h-8 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <GitBranch className="h-4 w-4 text-purple-700 dark:text-purple-300" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Go to Dashboard</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">Create rules, add approvers, monitor approval flows in real-time.</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-zinc-400 mt-1 flex-shrink-0" />
                </button>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
