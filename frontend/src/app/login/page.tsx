"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Shield, ArrowRight, Loader2, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [tenantInput, setTenantInput] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setLoading(true);
    setError("");

    const raw = tenantInput.trim().replace(/\.us\.auth0\.com$/, "").replace(/\.auth0\.com$/, "");
    if (!raw) { setError("Enter your Auth0 tenant name."); setLoading(false); return; }
    if (!clientId.trim()) { setError("Enter your Web App Client ID."); setLoading(false); return; }
    if (!clientSecret.trim()) { setError("Enter your Web App Client Secret."); setLoading(false); return; }

    const domain = `${raw}.us.auth0.com`;

    try {
      // Set tenant cookie
      const res = await fetch("/api/set-tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain, clientId: clientId.trim(), clientSecret: clientSecret.trim() }),
      });

      if (!res.ok) {
        setError("Failed to save tenant configuration.");
        setLoading(false);
        return;
      }

      // Redirect to Auth0 login
      window.location.href = "/auth/login?returnTo=/setup";
    } catch (e: any) {
      setError(e.message || "Something went wrong.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Sign In</h1>
          <p className="text-sm text-zinc-500 mt-1">Connect your Auth0 tenant to get started</p>
        </div>

        <Card>
          <CardContent className="pt-6 space-y-4">
            {/* Info box */}
            <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
              <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
                Each user connects their own Auth0 tenant. This enables Token Vault
                for secure credential management — your agents never see API keys.
              </p>
              <a
                href="https://auth0.com/signup"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium mt-1.5 hover:underline"
              >
                Create a free Auth0 account <ExternalLink className="h-3 w-3" />
              </a>
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

            {/* Web App credentials */}
            <div className="space-y-3">
              <div className="p-2.5 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                <p className="text-[10px] text-zinc-500 leading-relaxed">
                  Auth0 Dashboard → Applications → Regular Web Application → Settings
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Client ID</label>
                <Input
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="mt-1 font-mono text-xs"
                  placeholder="GVNbXpKSDzU28Xh9..."
                />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-400">Client Secret</label>
                <Input
                  type="password"
                  value={clientSecret}
                  onChange={(e) => setClientSecret(e.target.value)}
                  className="mt-1 font-mono text-xs"
                  placeholder="KRLgl7Tn8-VM4onf..."
                />
              </div>
            </div>

            {/* Required setup reminder */}
            <div className="p-2.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
              <p className="text-[10px] text-amber-700 dark:text-amber-300 font-medium">Before signing in, ensure:</p>
              <ul className="text-[10px] text-amber-600 dark:text-amber-400 mt-1 ml-3 list-disc space-y-0.5">
                <li>Allowed Callback URLs: <code className="bg-amber-100 dark:bg-amber-900 px-1 rounded">http://localhost:3000/auth/callback</code></li>
                <li>Allowed Logout URLs: <code className="bg-amber-100 dark:bg-amber-900 px-1 rounded">http://localhost:3000</code></li>
                <li>Grant Types: Token Vault enabled</li>
              </ul>
            </div>

            {error && (
              <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950/30 p-2 rounded">{error}</p>
            )}

            <Button
              onClick={handleLogin}
              disabled={loading || !tenantInput.trim() || !clientId.trim() || !clientSecret.trim()}
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
  );
}
