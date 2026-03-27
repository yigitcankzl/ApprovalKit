"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Shield, ArrowRight, Loader2, ExternalLink, Copy, Check } from "lucide-react";

function CopyText({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
      className="inline-flex items-center gap-1 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[10px] font-mono hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors"
    >
      {text}
      {copied ? <Check className="h-2.5 w-2.5 text-green-500" /> : <Copy className="h-2.5 w-2.5 text-zinc-400" />}
    </button>
  );
}

export default function LoginPage() {
  const [tenantInput, setTenantInput] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [m2mClientId, setM2mClientId] = useState("");
  const [m2mClientSecret, setM2mClientSecret] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setLoading(true);
    setError("");

    const raw = tenantInput.trim().replace(/\.us\.auth0\.com$/, "").replace(/\.auth0\.com$/, "");
    if (!raw) { setError("Enter your Auth0 tenant name."); setLoading(false); return; }
    if (!clientId.trim()) { setError("Enter your Web App Client ID."); setLoading(false); return; }
    if (!clientSecret.trim()) { setError("Enter your Web App Client Secret."); setLoading(false); return; }
    if (!m2mClientId.trim()) { setError("Enter your M2M Client ID."); setLoading(false); return; }
    if (!m2mClientSecret.trim()) { setError("Enter your M2M Client Secret."); setLoading(false); return; }

    const domain = `${raw}.us.auth0.com`;

    try {
      const res = await fetch("/api/set-tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          clientId: clientId.trim(),
          clientSecret: clientSecret.trim(),
          m2mClientId: m2mClientId.trim() || undefined,
          m2mClientSecret: m2mClientSecret.trim() || undefined,
        }),
      });

      if (!res.ok) {
        setError("Failed to save tenant configuration.");
        setLoading(false);
        return;
      }

      window.location.href = "/auth/login?returnTo=/setup";
    } catch (e: any) {
      setError(e.message || "Something went wrong.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Connect Your Auth0 Tenant</h1>
          <p className="text-sm text-zinc-500 mt-1">Each user brings their own Auth0 tenant for full Token Vault integration</p>
        </div>

        <div className="space-y-4">
          {/* Step 1: Create Auth0 Account */}
          <Card>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">1</div>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Create an Auth0 Account</h3>
                  <p className="text-xs text-zinc-500 mt-1">
                    Sign up for a free Auth0 account. You&apos;ll get a tenant with Token Vault, Connected Accounts, and CIBA support during the trial period.
                  </p>
                  <a
                    href="https://auth0.com/signup"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium mt-2 hover:underline"
                  >
                    auth0.com/signup <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step 2: Create Application */}
          <Card>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">2</div>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Create a Regular Web Application</h3>
                  <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
                    In your Auth0 Dashboard:
                  </p>
                  <ol className="text-xs text-zinc-500 mt-2 space-y-1.5 ml-1">
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">a.</span>
                      <span>Go to <strong>Applications → Create Application → Regular Web Application</strong></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">b.</span>
                      <div>
                        <span><strong>Allowed Callback URLs</strong> — paste this exactly:</span>
                        <div className="mt-1">
                          <CopyText text="http://localhost:3000/auth/callback, http://localhost:8000/api/v1/connections/oauth/callback, http://localhost:8000/api/v1/connections/connected-accounts/callback" />
                        </div>
                      </div>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">c.</span>
                      <span><strong>Allowed Logout URLs</strong>: <CopyText text="http://localhost:3000" /></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">d.</span>
                      <span><strong>Allowed Web Origins</strong>: <CopyText text="http://localhost:3000" /></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">e.</span>
                      <span><strong>Advanced Settings → Grant Types</strong> → enable <strong>Token Vault</strong></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">f.</span>
                      <span>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> below</span>
                    </li>
                  </ol>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step 3: Create M2M Application */}
          <Card>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">3</div>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Create a Machine to Machine Application</h3>
                  <ol className="text-xs text-zinc-500 mt-2 space-y-1.5 ml-1">
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">a.</span>
                      <span>Go to <strong>Applications → Create Application → Machine to Machine</strong></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">b.</span>
                      <span>Select API: <strong>Auth0 Management API</strong></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">c.</span>
                      <span>Check permissions: <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">read:users</code> <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">update:users</code> <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">read:connections</code> <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">create:connections</code> <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">update:connections</code></span>
                    </li>
                    <li className="flex gap-2">
                      <span className="text-zinc-400 font-bold">d.</span>
                      <span>Click <strong>Authorize</strong> → copy Client ID and Client Secret</span>
                    </li>
                  </ol>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step 4: Enter Credentials */}
          <Card>
            <CardContent className="pt-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">4</div>
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Enter Credentials</h3>
                  <p className="text-xs text-zinc-500 mt-1">Tenant name is in the top-left of your Auth0 Dashboard.</p>
                </div>
              </div>

              {/* Tenant domain */}
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Auth0 Tenant</label>
                <div className="flex items-center gap-0 mt-1">
                  <Input
                    placeholder="dev-xxxxxxxx"
                    value={tenantInput}
                    onChange={(e) => setTenantInput(e.target.value)}
                    className="rounded-r-none font-mono text-xs"
                  />
                  <span className="px-2.5 py-2 bg-zinc-100 dark:bg-zinc-800 border border-l-0 border-zinc-200 dark:border-zinc-700 rounded-r-md text-xs text-zinc-500 whitespace-nowrap">.us.auth0.com</span>
                </div>
              </div>

              <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider pt-1">Web Application (Step 2)</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-zinc-500">Client ID</label>
                  <Input value={clientId} onChange={(e) => setClientId(e.target.value)} className="mt-0.5 font-mono text-xs" placeholder="GVNbXp..." />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-500">Client Secret</label>
                  <Input type="password" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} className="mt-0.5 font-mono text-xs" placeholder="KRLgl7..." />
                </div>
              </div>

              <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider pt-1">Machine to Machine (Step 3)</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-zinc-500">M2M Client ID</label>
                  <Input value={m2mClientId} onChange={(e) => setM2mClientId(e.target.value)} className="mt-0.5 font-mono text-xs" placeholder="n5NycP..." />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-500">M2M Client Secret</label>
                  <Input type="password" value={m2mClientSecret} onChange={(e) => setM2mClientSecret(e.target.value)} className="mt-0.5 font-mono text-xs" placeholder="8dMjot..." />
                </div>
              </div>

              {error && (
                <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950/30 p-2 rounded">{error}</p>
              )}

              <Button
                onClick={handleLogin}
                disabled={loading || !tenantInput.trim() || !clientId.trim() || !clientSecret.trim() || !m2mClientId.trim() || !m2mClientSecret.trim()}
                size="lg"
                className="w-full"
              >
                {loading ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Connecting...</>
                ) : (
                  <><ArrowRight className="h-4 w-4 mr-2" /> Sign In</>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
