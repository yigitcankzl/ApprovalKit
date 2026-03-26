"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FormError } from "@/components/ui/form-error";
import { CheckCircle2, Shield, AlertCircle, Save, Loader2 } from "lucide-react";
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

      {/* Setup Guide */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Shield className="h-5 w-5 text-blue-600" /> Setup Guide</CardTitle>
          <CardDescription>Follow these steps in your Auth0 Dashboard before filling in the fields below.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-4 text-sm text-zinc-700 dark:text-zinc-300">
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center">1</span>
              <div>
                <p className="font-medium">Create an M2M Application</p>
                <p className="text-zinc-500 dark:text-zinc-400 mt-0.5">Auth0 Dashboard &rarr; Applications &rarr; Create Application &rarr; Machine to Machine &rarr; Select <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">Auth0 Management API</code> &rarr; Select scopes: read:users, update:users, read:connections, create:connections &rarr; Authorize</p>
                <p className="text-green-700 dark:text-green-400 text-xs font-medium mt-1">Copy from the app page: <strong>Client ID</strong> and <strong>Client Secret</strong> (click Reveal) &rarr; paste below as M2M credentials</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center">2</span>
              <div>
                <p className="font-medium">Create a Web Application</p>
                <p className="text-zinc-500 dark:text-zinc-400 mt-0.5">Applications &rarr; Create Application &rarr; Regular Web Application. In Settings tab:</p>
                <ul className="text-zinc-500 dark:text-zinc-400 mt-1 ml-3 space-y-0.5 list-disc text-xs">
                  <li>Allowed Callback URLs: <code className="bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">http://localhost:3000/auth/callback</code></li>
                  <li>Allowed Logout URLs: <code className="bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">http://localhost:3000</code></li>
                  <li>Advanced Settings &rarr; Grant Types &rarr; Enable <strong>CIBA</strong> + <strong>Token Exchange</strong></li>
                </ul>
                <p className="text-green-700 dark:text-green-400 text-xs font-medium mt-1">Copy from this app page: <strong>Client ID</strong> and <strong>Client Secret</strong> &rarr; paste below as Web App credentials</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center">3</span>
              <div>
                <p className="font-medium">Enable Token Vault</p>
                <p className="text-zinc-500 dark:text-zinc-400 mt-0.5">For each social connection (Stripe, GitHub, etc.): Authentication &rarr; Social &rarr; [Connection] &rarr; Advanced &rarr; Enable Token Vault. This lets ApprovalKit exchange tokens via RFC 8693.</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center">4</span>
              <div>
                <p className="font-medium">Enable Guardian (for CIBA push approvals)</p>
                <p className="text-zinc-500 dark:text-zinc-400 mt-0.5">Security &rarr; Multi-factor Auth &rarr; Push via Auth0 Guardian &rarr; Enable. Each approver must install the Guardian app and enroll via the Approvers page.</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400 text-xs font-bold flex items-center justify-center">5</span>
              <div>
                <p className="font-medium text-zinc-500 dark:text-zinc-400">FGA (Optional)</p>
                <p className="text-zinc-400 dark:text-zinc-500 mt-0.5">For fine-grained role-based access: Auth0 FGA Dashboard &rarr; Create Store &rarr; copy Store ID, Client ID, Client Secret. Without FGA, all authenticated users have full access.</p>
              </div>
            </li>
          </ol>
        </CardContent>
      </Card>

      {/* Edit credentials */}
      <Card>
        <CardHeader>
          <CardTitle>Auth0 Credentials</CardTitle>
          <CardDescription>Paste the values from the steps above. Only changed fields will be updated.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Auth0 Domain *</label>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-1">Your Auth0 tenant domain. Find it at Settings &rarr; General &rarr; Domain.</p>
            <Input placeholder="your-tenant.us.auth0.com" value={tenant} onChange={(e) => setTenant(e.target.value)} />
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">M2M Application (Step 1)</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-3">Used for Token Vault exchange and Management API calls.</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client ID</label>
                <Input placeholder="From Applications > Your M2M App > Settings" value={m2mClientId} onChange={(e) => setM2mClientId(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client Secret</label>
                <Input type="password" placeholder="Click 'Reveal' in Auth0 to copy" value={m2mClientSecret} onChange={(e) => setM2mClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
            </div>
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">Web Application (Step 2)</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-3">Used for user login, CIBA push notifications, and Connected Accounts OAuth flow.</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web App Client ID</label>
                <Input placeholder="From Applications > Your Web App > Settings" value={webClientId} onChange={(e) => setWebClientId(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web App Client Secret</label>
                <Input type="password" placeholder="Click 'Reveal' in Auth0 to copy" value={webClientSecret} onChange={(e) => setWebClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
            </div>
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-1">FGA — Fine-Grained Authorization (Step 5, Optional)</p>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-3">Leave blank to allow all authenticated users full access. Configure for role-based permissions.</p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-zinc-600 dark:text-zinc-400">Store ID</label>
                <Input placeholder="01KMG..." value={fgaStoreId} onChange={(e) => setFgaStoreId(e.target.value)} className="mt-1 font-mono text-xs" />
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
          </div>

          <FormError message={error} />

          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4" /> Credentials updated successfully.
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
