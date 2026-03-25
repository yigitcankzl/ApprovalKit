"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Shield, KeyRound, Unplug, Activity, CheckCircle2, AlertTriangle } from "lucide-react";

interface ConsentRule {
  id: string;
  name: string;
  model: string;
  action: string;
  approver_count: number;
  step_up_model: string | null;
}

interface RecentAccess {
  job_id: string;
  agent_user_id: string;
  action: string;
  state: string;
  created_at: string;
}

interface ConsentService {
  connection_id: string;
  name: string;
  service: string;
  slug: string;
  connected_user: string | null;
  connected_auth0_user_id: string | null;
  oauth_scopes: string;
  actions: string[];
  rules: ConsentRule[];
  recent_access: RecentAccess[];
  can_revoke: boolean;
}

interface ConsentData {
  services: ConsentService[];
  total_agents: number;
  total_rules: number;
}

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

const stateBadge: Record<string, "success" | "danger" | "warning" | "info" | "default"> = {
  approved: "success",
  rejected: "danger",
  blocked: "danger",
  timeout: "warning",
  pending: "info",
  ciba_sent: "info",
};

export default function ConsentPage() {
  const [data, setData] = useState<ConsentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.getConsent()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleRevoke = async (connectionId: string) => {
    if (!confirm("Revoke OAuth access for this service? The agent will no longer be able to execute actions.")) return;
    setRevoking(connectionId);
    try {
      await api.disconnectAuth(connectionId);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRevoking(null);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
    </div>
  );

  if (error) return (
    <div className="flex items-center justify-center h-64">
      <p className="text-red-500">{error}</p>
    </div>
  );

  if (!data) return null;

  const connectedCount = data.services.filter(s => s.connected_auth0_user_id).length;

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Consent &amp; Permissions</h1>
        <p className="text-zinc-500 mt-1">
          What agents can access, which services are connected, and how to revoke
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500">Connected Services</p>
                <p className="text-3xl font-bold text-zinc-900 mt-1">{connectedCount} / {data.services.length}</p>
              </div>
              <KeyRound className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500">Active Rules</p>
                <p className="text-3xl font-bold text-zinc-900 mt-1">{data.total_rules}</p>
              </div>
              <Shield className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-zinc-500">Known Agents</p>
                <p className="text-3xl font-bold text-zinc-900 mt-1">{data.total_agents}</p>
              </div>
              <Activity className="h-8 w-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Per-service cards */}
      <div className="space-y-6">
        {data.services.map((svc) => (
          <Card key={svc.connection_id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CardTitle>{svc.name}</CardTitle>
                  {svc.connected_user ? (
                    <Badge variant="success">
                      <CheckCircle2 className="h-3 w-3 mr-1" /> Token Vault
                    </Badge>
                  ) : (
                    <Badge variant="default">Not connected</Badge>
                  )}
                </div>
                {svc.can_revoke && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-500 hover:text-red-700 hover:bg-red-50"
                    disabled={revoking === svc.connection_id}
                    onClick={() => handleRevoke(svc.connection_id)}
                  >
                    <Unplug className="h-4 w-4 mr-1" />
                    {revoking === svc.connection_id ? "Revoking..." : "Revoke Access"}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* OAuth Info */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Connected As</p>
                  <p className="text-sm text-zinc-700 font-medium">{svc.connected_user || "Not connected"}</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">OAuth Scopes</p>
                  <div className="flex gap-1 flex-wrap">
                    {svc.oauth_scopes.split(" ").map((scope) => (
                      <span key={scope} className="text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded font-mono">{scope}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Actions</p>
                  <div className="flex gap-1 flex-wrap">
                    {svc.actions.map((a) => (
                      <code key={a} className="text-xs bg-zinc-800 text-zinc-100 px-2 py-0.5 rounded">{a}</code>
                    ))}
                  </div>
                </div>
              </div>

              {/* Rules governing this service */}
              {svc.rules.length > 0 && (
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wide mb-2">Approval Rules</p>
                  <div className="border border-zinc-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-zinc-50 border-b border-zinc-200">
                          <th className="text-left p-3 font-medium text-zinc-500">Rule</th>
                          <th className="text-left p-3 font-medium text-zinc-500">Action</th>
                          <th className="text-left p-3 font-medium text-zinc-500">Model</th>
                          <th className="text-left p-3 font-medium text-zinc-500">Approvers</th>
                        </tr>
                      </thead>
                      <tbody>
                        {svc.rules.map((r) => (
                          <tr key={r.id} className="border-b border-zinc-100">
                            <td className="p-3 text-zinc-700 font-medium">{r.name}</td>
                            <td className="p-3"><code className="text-xs bg-zinc-100 px-1.5 py-0.5 rounded">{r.action}</code></td>
                            <td className="p-3">
                              <span className="text-zinc-600">{modelLabels[r.model] || r.model}</span>
                              {r.step_up_model && (
                                <Badge variant="info" className="ml-2 text-xs">
                                  <AlertTriangle className="h-3 w-3 mr-0.5" />
                                  Step-up: {modelLabels[r.step_up_model] || r.step_up_model}
                                </Badge>
                              )}
                            </td>
                            <td className="p-3 text-zinc-600">{r.approver_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Recent access */}
              {svc.recent_access.length > 0 && (
                <div>
                  <p className="text-xs text-zinc-400 uppercase tracking-wide mb-2">Recent Agent Access</p>
                  <div className="space-y-1">
                    {svc.recent_access.slice(0, 5).map((j) => (
                      <div key={j.job_id} className="flex items-center gap-3 text-xs py-1.5 px-2 rounded hover:bg-zinc-50">
                        <code className="text-zinc-500 font-mono">{j.agent_user_id}</code>
                        <code className="bg-zinc-800 text-zinc-100 px-1.5 py-0.5 rounded">{j.action}</code>
                        <Badge variant={stateBadge[j.state] || "default"} className="text-xs">
                          {j.state}
                        </Badge>
                        <span className="text-zinc-400 ml-auto">
                          {new Date(j.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {svc.rules.length === 0 && svc.recent_access.length === 0 && (
                <p className="text-sm text-zinc-400 text-center py-4">No rules or access history for this service yet.</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
