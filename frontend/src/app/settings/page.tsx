"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FormError } from "@/components/ui/form-error";
import { CheckCircle2, Shield, Save, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [tenant, setTenant] = useState("");
  const [m2mClientId, setM2mClientId] = useState("");
  const [m2mClientSecret, setM2mClientSecret] = useState("");
  const [webClientId, setWebClientId] = useState("");
  const [webClientSecret, setWebClientSecret] = useState("");
  const [fgaStoreId, setFgaStoreId] = useState("");
  const [fgaClientId, setFgaClientId] = useState("");
  const [fgaClientSecret, setFgaClientSecret] = useState("");

  useEffect(() => {
    api.getWorkspace()
      .then((ws) => {
        setWorkspace(ws);
        if (ws.auth0_tenant) setTenant(ws.auth0_tenant);
      })
      .catch(() => router.replace("/setup"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await api.setupWorkspace({
        name: workspace?.name || "My Workspace",
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
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to update.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
    </div>
  );

  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Settings</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">Manage your workspace credentials</p>
      </div>

      {/* Current status */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-zinc-900 dark:text-zinc-100">{workspace?.name}</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
                Tenant: <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">{workspace?.auth0_tenant}</code>
              </p>
            </div>
            <div className="flex gap-2">
              {workspace?.has_auth0_credentials && <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> Auth0</Badge>}
              {workspace?.has_fga_credentials && <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> FGA</Badge>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Edit credentials */}
      <Card>
        <CardHeader>
          <CardTitle>Auth0 Credentials</CardTitle>
          <CardDescription>Only changed fields will be updated. Secrets are stored in HashiCorp Vault.</CardDescription>
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
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">A popup asks &quot;Select an API&quot; &rarr; pick <strong>Auth0 Management API</strong>. Check permissions: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">read:users</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">update:users</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">read:connections</code> <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">create:connections</code> &rarr; Authorize</p>
              <p className="text-xs text-green-700 dark:text-green-400 font-medium mt-1">On the next page, copy Client ID and Client Secret (click Reveal):</p>
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
              <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">In Settings tab set:</p>
              <ul className="text-xs text-blue-600 dark:text-blue-400 mt-1 ml-3 list-disc space-y-0.5">
                <li>Allowed Callback URLs: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">http://localhost:3000/auth/callback</code></li>
                <li>Allowed Logout URLs: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">http://localhost:3000</code></li>
                <li>Advanced Settings &rarr; Grant Types &rarr; Enable <strong>CIBA</strong> + <strong>Token Exchange</strong></li>
              </ul>
              <p className="text-xs text-green-700 dark:text-green-400 font-medium mt-1">Copy Client ID and Client Secret from the Settings tab:</p>
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
              <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">Don&apos;t forget these two steps in Auth0 Dashboard:</p>
              <ul className="text-xs text-amber-600 dark:text-amber-400 mt-1 ml-3 list-disc space-y-0.5">
                <li><strong>Token Vault:</strong> Authentication &rarr; Social &rarr; each connection &rarr; Advanced &rarr; Enable Token Vault</li>
                <li><strong>Guardian:</strong> Security &rarr; Multi-factor Auth &rarr; Push via Auth0 Guardian &rarr; Enable</li>
              </ul>
            </div>
          </div>

          {/* FGA */}
          <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
            <details className="group">
              <summary className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-300">
                FGA — Fine-Grained Authorization (Optional)
              </summary>
              <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1 mb-3">Without FGA, all authenticated users get full access. Add FGA for role-based permissions.</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-zinc-600 dark:text-zinc-400">Store ID</label>
                  <Input placeholder="01KMG6..." value={fgaStoreId} onChange={(e) => setFgaStoreId(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-xs text-zinc-600 dark:text-zinc-400">Client ID</label>
                  <Input placeholder="FAYoXr..." value={fgaClientId} onChange={(e) => setFgaClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-xs text-zinc-600 dark:text-zinc-400">Client Secret</label>
                  <Input type="password" placeholder="7SaTTI..." value={fgaClientSecret} onChange={(e) => setFgaClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
              </div>
            </details>
          </div>

          <FormError message={error} />

          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4" /> Credentials updated successfully. Secrets stored in Vault.
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              <Save className="h-4 w-4 mr-2" />
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
