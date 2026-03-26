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

      {/* Edit credentials */}
      <Card>
        <CardHeader>
          <CardTitle>Update Credentials</CardTitle>
          <CardDescription>Only changed fields will be updated. Leave blank to keep current values.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Auth0 Domain</label>
            <Input placeholder="your-tenant.us.auth0.com" value={tenant} onChange={(e) => setTenant(e.target.value)} className="mt-1" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client ID</label>
              <Input placeholder="Leave blank to keep current" value={m2mClientId} onChange={(e) => setM2mClientId(e.target.value)} className="mt-1 font-mono text-xs" />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">M2M Client Secret</label>
              <Input type="password" placeholder="Leave blank to keep current" value={m2mClientSecret} onChange={(e) => setM2mClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web Client ID</label>
              <Input placeholder="Leave blank to keep current" value={webClientId} onChange={(e) => setWebClientId(e.target.value)} className="mt-1 font-mono text-xs" />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Web Client Secret</label>
              <Input type="password" placeholder="Leave blank to keep current" value={webClientSecret} onChange={(e) => setWebClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
            </div>
          </div>

          <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
            <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3">FGA</p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-zinc-600 dark:text-zinc-400">Store ID</label>
                <Input value={fgaStoreId} onChange={(e) => setFgaStoreId(e.target.value)} className="mt-1 font-mono text-xs" />
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
