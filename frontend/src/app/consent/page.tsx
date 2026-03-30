"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  Shield,
  Eye,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Lock,
  Unlock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

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
  oauth_scopes: string[];
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

const SERVICE_ICONS: Record<string, string> = {
  stripe: "💳",
  github: "🐙",
  slack: "💬",
  google: "📧",
  microsoft: "📨",
  salesforce: "☁️",
  notion: "📝",
  jira: "🎯",
  discord: "🎮",
  linear: "📐",
  hubspot: "🔶",
  shopify: "🛍️",
  paypal: "💰",
  dropbox: "📦",
  amadeus: "✈️",
};

const STATE_COLORS: Record<string, string> = {
  approved: "text-emerald-600 dark:text-emerald-400",
  rejected: "text-red-600 dark:text-red-400",
  blocked: "text-red-600 dark:text-red-400",
  timeout: "text-amber-600 dark:text-amber-400",
  pending: "text-blue-600 dark:text-blue-400",
  ciba_sent: "text-blue-600 dark:text-blue-400",
  waiting_approval: "text-blue-600 dark:text-blue-400",
  pre_approved: "text-emerald-600 dark:text-emerald-400",
};

const MODEL_LABELS: Record<string, string> = {
  any_one: "Any One Approver",
  specific: "Specific Approver",
  all_of_n: "All Approvers",
  k_of_n: "K-of-N Quorum",
  sequential: "Sequential Chain",
  fga_dynamic: "FGA Dynamic",
};

export default function ConsentPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [data, setData] = useState<ConsentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedServices, setExpandedServices] = useState<Set<string>>(new Set());
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  const fetchData = () => {
    if (authLoading || !user) return;
    setLoading(true);
    api.getConsent()
      .then((result: ConsentData) => setData(result))
      .catch((err: Error) => setError(err.message || "Failed to load consent data"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, [authLoading, user]);

  const toggleExpand = (id: string) => {
    setExpandedServices((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRevoke = async (connectionId: string) => {
    if (!confirm("Are you sure you want to revoke this connection? The agent will no longer be able to perform actions through this service.")) return;
    setRevoking(connectionId);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/connections/${connectionId}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      fetchData();
    } catch {
      // silently fail
    } finally {
      setRevoking(null);
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 dark:border-zinc-100" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-8 w-8 text-red-500 mx-auto mb-3" />
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const connectedCount = data.services.filter((s) => s.connected_auth0_user_id).length;
  const totalScopes = data.services.reduce((acc, s) => acc + s.oauth_scopes.length, 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-3">
          <Shield className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
          Consent & Permissions
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1.5 text-sm">
          Complete visibility into what agents can access, granted scopes, and recent activity.
          Revoke access at any time.
        </p>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                <Lock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{data.services.length}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Connected Services</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30">
                <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{connectedCount}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Token Vault Linked</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/30">
                <Eye className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{totalScopes}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">OAuth Scopes Granted</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30">
                <Shield className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{data.total_rules}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Active Approval Rules</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Count Banner */}
      {data.total_agents > 0 && (
        <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 px-4 py-3 flex items-center gap-3">
          <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
          <p className="text-sm text-blue-800 dark:text-blue-300">
            <strong>{data.total_agents} distinct agent{data.total_agents > 1 ? "s" : ""}</strong> have interacted with your workspace.
            All actions are gated by approval rules — agents never hold your credentials.
          </p>
        </div>
      )}

      {/* Service Cards */}
      {data.services.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Unlock className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
            <p className="text-zinc-500 dark:text-zinc-400 text-lg font-medium">No connected services</p>
            <p className="text-zinc-400 dark:text-zinc-500 text-sm mt-1">
              Connect services in the Connections page to see consent details here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {data.services.map((service) => {
            const isExpanded = expandedServices.has(service.connection_id);
            const icon = SERVICE_ICONS[service.service.toLowerCase()] || "🔗";
            const isVaultLinked = !!service.connected_auth0_user_id;

            return (
              <Card key={service.connection_id} className="overflow-hidden">
                {/* Service Header */}
                <div
                  className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors"
                  onClick={() => toggleExpand(service.connection_id)}
                >
                  <div className="flex items-center gap-4">
                    <span className="text-2xl">{icon}</span>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{service.name}</h3>
                        <Badge variant={isVaultLinked ? "success" : "warning"}>
                          {isVaultLinked ? "Token Vault" : "Not Linked"}
                        </Badge>
                      </div>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                        {service.service} &middot; {service.actions.length} action{service.actions.length !== 1 ? "s" : ""} &middot;{" "}
                        {service.rules.length} rule{service.rules.length !== 1 ? "s" : ""}
                        {service.connected_user && ` · Connected as ${service.connected_user}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {service.can_revoke && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRevoke(service.connection_id);
                        }}
                        disabled={revoking === service.connection_id}
                      >
                        {revoking === service.connection_id ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <XCircle className="h-3 w-3" />
                        )}
                        <span className="ml-1.5">Revoke</span>
                      </Button>
                    )}
                    {isExpanded ? (
                      <ChevronUp className="h-5 w-5 text-zinc-400" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-zinc-400" />
                    )}
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="border-t border-zinc-100 dark:border-zinc-800">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-zinc-100 dark:divide-zinc-800">
                      {/* OAuth Scopes */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Lock className="h-3.5 w-3.5" />
                          OAuth Scopes
                        </h4>
                        <div className="space-y-1.5">
                          {service.oauth_scopes.map((scope) => (
                            <div
                              key={scope}
                              className="text-xs font-mono px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300"
                            >
                              {scope}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Approval Rules */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Shield className="h-3.5 w-3.5" />
                          Approval Rules
                        </h4>
                        {service.rules.length === 0 ? (
                          <p className="text-xs text-zinc-400 italic">No rules configured</p>
                        ) : (
                          <div className="space-y-2">
                            {service.rules.map((rule) => (
                              <div
                                key={rule.id}
                                className="text-xs p-2 rounded border border-zinc-100 dark:border-zinc-800"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="font-medium text-zinc-900 dark:text-zinc-100">
                                    {rule.name}
                                  </span>
                                  <Badge variant="default">
                                    {MODEL_LABELS[rule.model] || rule.model}
                                  </Badge>
                                </div>
                                <div className="mt-1 text-zinc-500 dark:text-zinc-400">
                                  Action: <span className="font-mono">{rule.action}</span>
                                  {" · "}{rule.approver_count} approver{rule.approver_count !== 1 ? "s" : ""}
                                  {rule.step_up_model && (
                                    <span className="text-amber-600 dark:text-amber-400">
                                      {" · "}Step-up → {MODEL_LABELS[rule.step_up_model] || rule.step_up_model}
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Recent Access */}
                      <div className="p-5">
                        <h4 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          Recent Access
                        </h4>
                        {service.recent_access.length === 0 ? (
                          <p className="text-xs text-zinc-400 italic">No recent activity</p>
                        ) : (
                          <div className="space-y-1.5">
                            {service.recent_access.slice(0, 5).map((access) => (
                              <div
                                key={access.job_id}
                                className="text-xs flex items-center justify-between"
                              >
                                <span className="font-mono text-zinc-700 dark:text-zinc-300">
                                  {access.action}
                                </span>
                                <div className="flex items-center gap-2">
                                  <span className={STATE_COLORS[access.state] || "text-zinc-500"}>
                                    {access.state}
                                  </span>
                                  <span className="text-zinc-400">
                                    {new Date(access.created_at).toLocaleDateString()}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Security Footer */}
      <div className="rounded-lg bg-zinc-100 dark:bg-zinc-800/50 px-5 py-4">
        <div className="flex items-start gap-3">
          <Shield className="h-5 w-5 text-zinc-500 mt-0.5 shrink-0" />
          <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Zero credential exposure:</strong>{" "}
              All agent actions are executed through Auth0 Token Vault. Agents never see or hold your API keys, OAuth tokens, or credentials.
            </p>
            <p>
              <strong className="text-zinc-700 dark:text-zinc-300">Human-in-the-loop:</strong>{" "}
              Every action matching an approval rule requires explicit human consent via CIBA push notification before execution.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
