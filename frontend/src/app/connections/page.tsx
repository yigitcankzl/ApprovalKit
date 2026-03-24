"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { CheckCircle2, KeyRound, Trash2, X, Plus } from "lucide-react";
import { useRouter } from "next/navigation";

interface Connection {
  id: string;
  name: string;
  service: string;
  slug: string;
  actions: string[];
  has_credentials: boolean;
  is_active: boolean;
}

const credentialFields: Record<string, { key: string; label: string; placeholder: string; secret?: boolean }[]> = {
  stripe: [
    { key: "api_key", label: "Stripe Secret Key", placeholder: "sk_live_...", secret: true },
  ],
  github: [
    { key: "token", label: "GitHub Token", placeholder: "ghp_...", secret: true },
    { key: "owner", label: "Owner (org or user)", placeholder: "my-org" },
    { key: "repo", label: "Repository", placeholder: "my-repo" },
  ],
  gmail: [
    { key: "access_token", label: "OAuth Access Token", placeholder: "ya29...", secret: true },
  ],
  slack: [
    { key: "bot_token", label: "Bot Token", placeholder: "xoxb-...", secret: true },
  ],
  salesforce: [
    { key: "access_token", label: "Access Token", placeholder: "00D...", secret: true },
    { key: "instance_url", label: "Instance URL", placeholder: "https://myorg.salesforce.com" },
  ],
  aws: [
    { key: "access_key_id", label: "Access Key ID", placeholder: "AKIA..." },
    { key: "secret_access_key", label: "Secret Access Key", placeholder: "...", secret: true },
    { key: "region", label: "Region", placeholder: "us-east-1" },
  ],
};

export default function ConnectionsPage() {
  const router = useRouter();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.getConnections()
      .then(setConnections)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openForm = (conn: Connection) => {
    setActiveId(conn.id);
    setFormValues({});
  };

  const closeForm = () => {
    setActiveId(null);
    setFormValues({});
  };

  const handleStore = async (conn: Connection) => {
    const fields = credentialFields[conn.service.toLowerCase()] || [];
    const missing = fields.filter((f) => !formValues[f.key]);
    if (missing.length > 0) {
      setError(`Required: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.storeCredentials(conn.id, formValues);
      closeForm();
      load();
    } catch (e: any) {
      setError(e.message || "Failed to save credentials");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (conn: Connection) => {
    if (!confirm(`Remove credentials for ${conn.name}?`)) return;
    try {
      await api.deleteCredentials(conn.id);
      load();
    } catch (e: any) {
      setError(e.message || "Failed to remove credentials");
    }
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Connections</h1>
          <p className="text-zinc-500 mt-1">
            Store service credentials — Token Vault executes actions after approval
          </p>
        </div>
        <Button variant="outline" onClick={() => router.push("/onboarding")}>
          <Plus className="h-4 w-4 mr-2" /> Add Connection
        </Button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between">
          {error}
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : connections.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <KeyRound className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
            <p className="text-zinc-500 mb-4">No connections yet.</p>
            <Button onClick={() => router.push("/onboarding")}>
              <Plus className="h-4 w-4 mr-2" /> Set Up Connections
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {connections.map((conn) => {
            const fields = credentialFields[conn.service.toLowerCase()] || [];
            const isOpen = activeId === conn.id;

            return (
              <Card key={conn.id} className="hover:border-zinc-300 transition-colors">
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-sm font-bold text-zinc-700 uppercase">
                        {conn.service.slice(0, 2)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-zinc-900">{conn.name}</span>
                          <code className="text-xs text-zinc-400 bg-zinc-50 px-1.5 py-0.5 rounded">{conn.slug}</code>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-sm text-zinc-500">{conn.actions.join(", ")}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {conn.has_credentials ? (
                        <Badge variant="success">
                          <CheckCircle2 className="h-3 w-3 mr-1" /> Credentials stored
                        </Badge>
                      ) : (
                        <Badge variant="warning">No credentials</Badge>
                      )}
                      {conn.has_credentials ? (
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm" onClick={() => openForm(conn)}>
                            Update
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDelete(conn)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <Button size="sm" onClick={() => openForm(conn)}>
                          <KeyRound className="h-4 w-4 mr-2" /> Enter Credentials
                        </Button>
                      )}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="mt-4 pt-4 border-t border-zinc-100">
                      {fields.length === 0 ? (
                        <p className="text-sm text-zinc-400">No credential fields defined for service &quot;{conn.service}&quot;.</p>
                      ) : (
                        <div className="space-y-3">
                          <p className="text-sm font-medium text-zinc-700">
                            {conn.has_credentials ? "Update credentials" : "Enter credentials"} for {conn.name}
                          </p>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {fields.map((field) => (
                              <div key={field.key}>
                                <label className="text-xs text-zinc-500">{field.label}</label>
                                <Input
                                  type={field.secret ? "password" : "text"}
                                  placeholder={field.placeholder}
                                  value={formValues[field.key] || ""}
                                  onChange={(e) => setFormValues({ ...formValues, [field.key]: e.target.value })}
                                  className="mt-1 font-mono text-sm"
                                />
                              </div>
                            ))}
                          </div>
                          <p className="text-xs text-zinc-400">
                            Credentials are encrypted with Fernet before storage. Never exposed in any response.
                          </p>
                          <div className="flex gap-2">
                            <Button size="sm" disabled={saving} onClick={() => handleStore(conn)}>
                              {saving ? "Saving…" : "Save Credentials"}
                            </Button>
                            <Button variant="outline" size="sm" onClick={closeForm}>Cancel</Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
