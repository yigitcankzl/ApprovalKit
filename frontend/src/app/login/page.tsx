"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Shield, ArrowRight, Loader2, Info } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const [tenantInput, setTenantInput] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (useDefault: boolean) => {
    setLoading(true);
    setError("");

    try {
      let domain = "";
      let cid = "";
      let csecret = "";

      if (useDefault) {
        // Fetch default tenant config
        const res = await fetch(`${API_BASE}/api/v1/workspace/tenant-config`);
        const data = await res.json();
        domain = data.domain;
        cid = data.client_id;
        // Default tenant uses .env secret — cookie set to "default"
      } else {
        // Custom tenant
        const raw = tenantInput.trim().replace(/\.us\.auth0\.com$/, "");
        if (!raw) { setError("Enter your Auth0 tenant name."); setLoading(false); return; }
        domain = `${raw}.us.auth0.com`;

        if (clientId && clientSecret) {
          cid = clientId;
          csecret = clientSecret;
        } else {
          // Try to look up from existing workspace
          const res = await fetch(`${API_BASE}/api/v1/workspace/tenant-config?domain=${domain}`);
          const data = await res.json();
          if (data.found) {
            cid = data.client_id;
          } else {
            setError("Tenant not found. Enter your Web App Client ID and Client Secret.");
            setShowAdvanced(true);
            setLoading(false);
            return;
          }
        }
      }

      // Set tenant cookie via API route
      const cookieRes = await fetch("/api/set-tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          clientId: cid,
          clientSecret: csecret,
          useDefault,
        }),
      });

      if (!cookieRes.ok) {
        setError("Failed to set tenant configuration.");
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
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Sign In</h1>
          <p className="text-sm text-zinc-500 mt-1">Human approval middleware for AI agents</p>
        </div>

        <Card>
          <CardContent className="pt-6 space-y-4">
            {/* Quick login with default tenant */}
            <Button
              onClick={() => handleLogin(true)}
              disabled={loading}
              size="lg"
              className="w-full"
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Signing in...</>
              ) : (
                <><ArrowRight className="h-4 w-4 mr-2" /> Sign in with Default Tenant</>
              )}
            </Button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-zinc-200 dark:border-zinc-700" /></div>
              <div className="relative flex justify-center text-xs"><span className="bg-white dark:bg-zinc-900 px-2 text-zinc-400">or use your own Auth0 tenant</span></div>
            </div>

            {/* Custom tenant */}
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

            {/* Advanced: client credentials */}
            {showAdvanced && (
              <div className="space-y-3 pt-2 border-t border-zinc-200 dark:border-zinc-700">
                <div className="p-2.5 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                  <p className="text-[10px] text-blue-600 dark:text-blue-400">
                    <Info className="h-3 w-3 inline mr-1" />
                    Create a Regular Web Application in your Auth0 Dashboard.
                    Add <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">http://localhost:3000/auth/callback</code> to Allowed Callback URLs.
                  </p>
                </div>
                <div>
                  <label className="text-xs text-zinc-600 dark:text-zinc-400">Web App Client ID</label>
                  <Input value={clientId} onChange={(e) => setClientId(e.target.value)} className="mt-1 font-mono text-xs" placeholder="GVNbXp..." />
                </div>
                <div>
                  <label className="text-xs text-zinc-600 dark:text-zinc-400">Web App Client Secret</label>
                  <Input type="password" value={clientSecret} onChange={(e) => setClientSecret(e.target.value)} className="mt-1 font-mono text-xs" placeholder="KRLgl7..." />
                </div>
              </div>
            )}

            {!showAdvanced && (
              <button
                onClick={() => setShowAdvanced(true)}
                className="text-xs text-blue-500 hover:text-blue-600"
              >
                Enter credentials manually
              </button>
            )}

            {error && (
              <p className="text-xs text-red-500 bg-red-50 dark:bg-red-950/30 p-2 rounded">{error}</p>
            )}

            <Button
              onClick={() => handleLogin(false)}
              disabled={loading || !tenantInput.trim()}
              variant="outline"
              className="w-full"
            >
              Sign in with Custom Tenant
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
