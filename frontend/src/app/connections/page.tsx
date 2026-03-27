"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import { CheckCircle2, Link2, Unlink, X, AlertCircle, Info, Trash2, ChevronRight, Plus, Webhook, Globe } from "lucide-react";
import { useRouter } from "next/navigation";

interface Connection {
  id: string;
  name: string;
  service: string;
  slug: string;
  actions: string[];
  has_credentials: boolean;
  connected_via: "auth0" | "webhook" | null;
  connected_user_name: string | null;
  is_active: boolean;
  is_auth0_configured: boolean;
  has_webhook?: boolean;
  webhook_method?: string;
}

const SERVICE_LABEL: Record<string, string> = {
  github:     "GitHub",
  stripe:     "Stripe Connect",
  slack:      "Slack",
  salesforce: "Salesforce",
  google:     "Google",
  gmail:      "Google",
  microsoft:  "Microsoft",
  outlook:    "Microsoft Outlook",
  notion:     "Notion",
  jira:       "Jira",
  discord:    "Discord",
  dropbox:    "Dropbox",
  box:        "Box",
  figma:      "Figma",
  shopify:    "Shopify",
  hubspot:    "HubSpot",
  linear:     "Linear",
  bitbucket:  "Bitbucket",
  asana:      "Asana",
  freshbooks: "FreshBooks",
  paypal:     "PayPal",
  spotify:    "Spotify",
};

function ConnectionsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [consent, setConsent] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auth0Domain, setAuth0Domain] = useState("");
  const [connecting, setConnecting] = useState<string | null>(null);
  const [successSlug, setSuccessSlug] = useState<string | null>(null);
  const [infoPopup, setInfoPopup] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Add connection modal
  const [showAdd, setShowAdd] = useState(false);
  const [addSaving, setAddSaving] = useState<string | null>(null);

  // Custom connection modal
  const [showCustom, setShowCustom] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customSlug, setCustomSlug] = useState("");
  const [customActions, setCustomActions] = useState("");
  const [customUrl, setCustomUrl] = useState("");
  const [customMethod, setCustomMethod] = useState("POST");
  const [customHeaders, setCustomHeaders] = useState('{"Authorization": "Bearer {{token}}"}');
  const [customBody, setCustomBody] = useState("");
  const [customSaving, setCustomSaving] = useState(false);
  const [customError, setCustomError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.getConnections(),
      api.getConsent().catch(() => null),
      api.getWorkspace().catch(() => null),
    ])
      .then(([c, con, ws]) => {
        setConnections(c);
        setConsent(con);
        if (ws?.auth0_tenant) setAuth0Domain(ws.auth0_tenant);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const connected = searchParams.get("connected");
    const err = searchParams.get("error");
    if (connected) setSuccessSlug(connected);
    if (err) setError(`OAuth connect failed: ${err.replace(/_/g, " ")}`);
  }, []);

  const handleConnect = async (conn: Connection) => {
    setConnecting(conn.id);
    setError(null);
    try {
      // Try to get user token for Connected Accounts flow
      let userToken: string | null = null;
      let refreshToken: string | null = null;
      try {
        const tokenRes = await fetch("/api/token");
        if (tokenRes.ok) {
          const data = await tokenRes.json();
          userToken = data.accessToken;
          refreshToken = data.refreshToken;
        }
      } catch {}
      const { url } = await api.getConnectUrl(conn.id, userToken, refreshToken);
      window.location.href = url;
    } catch (e: any) {
      setError(e.message || "Failed to get connect URL");
      setConnecting(null);
    }
  };

  const handleDisconnect = async (conn: Connection) => {
    if (!confirm(`Disconnect ${conn.name} from Auth0 Token Vault?`)) return;
    try {
      await api.disconnectAuth(conn.id);
      load();
    } catch (e: any) {
      setError(e.message || "Failed to disconnect");
    }
  };

  const handleDelete = async (conn: Connection) => {
    if (!confirm(`Delete ${conn.name}? This cannot be undone.`)) return;
    try {
      await api.deleteConnection(conn.id);
      load();
    } catch (e: any) {
      setError(e.message || "Failed to delete");
    }
  };

  const PREDEFINED_SERVICES = [
    { id: "stripe", name: "Stripe", slug: "stripe-prod", actions: ["charge", "refund", "payout"] },
    { id: "github", name: "GitHub", slug: "github-main", actions: ["deploy", "rollback", "merge_pr"] },
    { id: "slack", name: "Slack", slug: "slack", actions: ["send_message", "create_channel"] },
    { id: "google", name: "Google (Gmail/Calendar)", slug: "google", actions: ["send_email", "create_event", "read_drive"] },
    { id: "microsoft", name: "Microsoft (Outlook/OneDrive)", slug: "microsoft", actions: ["send_email", "create_event", "upload_file"] },
    { id: "salesforce", name: "Salesforce", slug: "salesforce", actions: ["create_deal", "update_contact"] },
    { id: "notion", name: "Notion", slug: "notion", actions: ["create_page", "update_database"] },
    { id: "jira", name: "Jira", slug: "jira", actions: ["create_issue", "update_issue", "transition"] },
    { id: "discord", name: "Discord", slug: "discord", actions: ["send_message"] },
    { id: "linear", name: "Linear", slug: "linear", actions: ["create_issue", "update_status"] },
    { id: "hubspot", name: "HubSpot", slug: "hubspot", actions: ["create_contact", "create_deal"] },
    { id: "shopify", name: "Shopify", slug: "shopify", actions: ["create_order", "update_product"] },
    { id: "paypal", name: "PayPal", slug: "paypal", actions: ["send_payment", "create_invoice"] },
    { id: "dropbox", name: "Dropbox", slug: "dropbox", actions: ["upload_file", "share_folder"] },
    { id: "asana", name: "Asana", slug: "asana", actions: ["create_task", "complete_task"] },
  ];

  const existingSlugs = new Set(connections.map(c => c.slug));

  const handleAddService = async (svc: typeof PREDEFINED_SERVICES[0]) => {
    setAddSaving(svc.id);
    try {
      await api.createConnection({ name: svc.name, service: svc.id, slug: svc.slug, actions: svc.actions });
      load();
    } catch (e: any) {
      setError(e.message || "Failed to add connection");
    } finally {
      setAddSaving(null);
    }
  };

  const handleSaveCustom = async () => {
    if (!customName.trim()) { setCustomError("Name is required."); return; }
    if (!customSlug.trim()) { setCustomError("Slug is required."); return; }
    if (!customUrl.trim()) { setCustomError("Webhook URL is required."); return; }

    let headersObj: Record<string, string> = {};
    let bodyObj: Record<string, string> | undefined;
    try {
      headersObj = customHeaders.trim() ? JSON.parse(customHeaders) : {};
    } catch { setCustomError("Headers must be valid JSON."); return; }
    try {
      bodyObj = customBody.trim() ? JSON.parse(customBody) : undefined;
    } catch { setCustomError("Body template must be valid JSON."); return; }

    setCustomSaving(true);
    setCustomError(null);
    try {
      await api.createConnection({
        name: customName,
        service: "custom",
        slug: customSlug.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
        actions: customActions.split(",").map(a => a.trim()).filter(Boolean),
        webhook_url: customUrl,
        webhook_method: customMethod,
        webhook_headers: headersObj,
        webhook_body_template: bodyObj,
      });
      setShowCustom(false);
      setCustomName(""); setCustomSlug(""); setCustomActions(""); setCustomUrl(""); setCustomBody("");
      load();
    } catch (e: any) {
      setCustomError(e.message || "Failed to create connection.");
    } finally {
      setCustomSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Connections</h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1">
            Connect services via Auth0 Token Vault — no API keys stored, ever.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAdd(true)}>
            <Plus className="h-4 w-4 mr-2" /> Add Service
          </Button>
          <Button onClick={() => setShowCustom(true)}>
            <Webhook className="h-4 w-4 mr-2" /> Custom Webhook
          </Button>
        </div>
      </div>

      {successSlug && (
        <div className="mb-4 p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-700 dark:text-green-400 flex justify-between items-center">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <strong>{successSlug}</strong> connected successfully via Auth0 Token Vault.
          </span>
          <button onClick={() => setSuccessSlug(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 rounded-lg text-sm text-red-700 dark:text-red-400 flex justify-between items-center">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : connections.length === 0 ? (
        <Card>
          <CardContent className="py-10">
            <div className="text-center mb-6">
              <Link2 className="h-12 w-12 text-zinc-300 dark:text-zinc-600 mx-auto mb-4" />
              <p className="text-lg font-medium text-zinc-900 dark:text-zinc-100">No connections yet</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Connect your first service to start gating agent actions with approvals.</p>
            </div>
            <div className="max-w-md mx-auto space-y-3">
              <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-xs text-blue-700 dark:text-blue-300 font-medium">How connections work:</p>
                <ol className="text-xs text-blue-600 dark:text-blue-400 mt-1 ml-3 list-decimal space-y-1">
                  <li>Enable <strong>Token Vault</strong> for a social connection in Auth0 (Authentication &rarr; Social &rarr; Advanced &rarr; Enable Token Vault)</li>
                  <li>Click <strong>&quot;Add Connection&quot;</strong> below to register it here</li>
                  <li>Click <strong>&quot;Connect&quot;</strong> to link your account via OAuth — credentials stored in Auth0 Token Vault</li>
                </ol>
              </div>
              <Button className="w-full" onClick={() => setShowAdd(true)}>
                <Link2 className="h-4 w-4 mr-2" /> Add Your First Connection
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {connections.map((conn) => {
            const label = SERVICE_LABEL[conn.service.toLowerCase()] || conn.service;
            const configured = conn.is_auth0_configured;
            const isConnecting = connecting === conn.id;

            const consentSvc = consent?.services?.find((s: any) => s.slug === conn.slug);
            const isExpanded = expandedId === conn.id;

            return (
              <div key={conn.id} className="border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden hover:border-zinc-300 transition-colors">
                {/* Header — click to expand */}
                <div className="p-4 flex items-center justify-between">
                  <button className="flex items-center gap-4 flex-1 text-left" onClick={() => setExpandedId(isExpanded ? null : conn.id)}>
                    <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                    <div className="w-10 h-10 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 uppercase">
                      {conn.service.slice(0, 2)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-zinc-900 dark:text-zinc-100">{conn.name}</span>
                        <code className="text-xs text-zinc-400 bg-zinc-50 dark:bg-zinc-800/50 px-1.5 py-0.5 rounded">{conn.slug}</code>
                      </div>
                      <div className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
                        {conn.actions.join(", ")}
                      </div>
                      {conn.connected_user_name && (
                        <div className="text-xs text-zinc-400 mt-0.5">
                          Connected as: <span className="font-medium text-zinc-600 dark:text-zinc-400">{conn.connected_user_name}</span>
                        </div>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-3">
                    {conn.has_webhook && conn.connected_via === "webhook" ? (
                      <Badge variant="info">
                        <Globe className="h-3 w-3 mr-1" /> Webhook {conn.webhook_method || "POST"}
                      </Badge>
                    ) : conn.connected_via === "auth0" ? (
                      <>
                        <Badge variant="success">
                          <CheckCircle2 className="h-3 w-3 mr-1" /> Auth0 Token Vault
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-700 dark:text-red-400 hover:bg-red-50 dark:bg-red-950/30"
                          onClick={() => handleDisconnect(conn)}
                        >
                          <Unlink className="h-4 w-4 mr-1" /> Disconnect
                        </Button>
                      </>
                    ) : configured ? (
                      <>
                        <Badge variant="warning">Not connected</Badge>
                        <Button
                          size="sm"
                          disabled={isConnecting}
                          onClick={() => handleConnect(conn)}
                        >
                          <Link2 className="h-4 w-4 mr-2" />
                          {isConnecting ? "Redirecting…" : `Connect with ${label}`}
                        </Button>
                      </>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Badge variant="default">Setup required</Badge>
                        <button onClick={() => setInfoPopup(conn.id)} className="text-zinc-400 hover:text-zinc-600 dark:text-zinc-400">
                          <Info className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:bg-red-950/30"
                      onClick={() => handleDelete(conn)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-4 pb-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/50/50 space-y-4 pt-3">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">OAuth Scopes</p>
                        <div className="flex gap-1 flex-wrap">
                          {(consentSvc?.oauth_scopes || "openid profile email").split(" ").map((scope: string) => (
                            <span key={scope} className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded font-mono">{scope}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Actions</p>
                        <div className="flex gap-1 flex-wrap items-center">
                          {conn.actions.map((a) => (
                            <span key={a} className="inline-flex items-center gap-1 text-xs bg-zinc-800 text-zinc-100 pl-2 pr-1 py-0.5 rounded">
                              {a}
                              <button
                                onClick={async () => {
                                  const updated = conn.actions.filter(x => x !== a);
                                  try {
                                    await api.updateConnection(conn.id, { actions: updated });
                                    load();
                                  } catch {}
                                }}
                                className="hover:text-red-400 ml-0.5"
                                title={`Remove ${a}`}
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </span>
                          ))}
                          <form
                            onSubmit={async (e) => {
                              e.preventDefault();
                              const input = (e.target as HTMLFormElement).elements.namedItem("newAction") as HTMLInputElement;
                              const val = input.value.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
                              if (!val || conn.actions.includes(val)) { input.value = ""; return; }
                              try {
                                await api.updateConnection(conn.id, { actions: [...conn.actions, val] });
                                input.value = "";
                                load();
                              } catch {}
                            }}
                            className="inline-flex"
                          >
                            <input
                              name="newAction"
                              placeholder="+ add action"
                              className="w-24 text-xs bg-transparent border border-dashed border-zinc-300 dark:border-zinc-600 rounded px-2 py-0.5 text-zinc-600 dark:text-zinc-400 placeholder:text-zinc-400 focus:outline-none focus:border-zinc-500"
                            />
                          </form>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Status</p>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400">
                          {conn.connected_via === "auth0" ? "Connected via Token Vault" : configured ? "Auth0 connection ready" : "Auth0 social connection not configured"}
                        </p>
                      </div>
                    </div>

                    {/* Rules for this connection */}
                    {consentSvc?.rules && consentSvc.rules.length > 0 && (
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-2">Approval Rules</p>
                        <div className="space-y-1">
                          {consentSvc.rules.map((r: any) => (
                            <div key={r.id} className="flex items-center gap-3 text-xs py-1 px-2 bg-white dark:bg-zinc-900 rounded border border-zinc-200 dark:border-zinc-700">
                              <span className="font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 flex-1">{r.name}</span>
                              <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">{r.action}</code>
                              <Badge variant="info" className="text-xs">{r.model}</Badge>
                              {r.step_up_model && <Badge variant="warning" className="text-xs">Step-up</Badge>}
                              <span className="text-zinc-400">{r.approver_count} approver{r.approver_count > 1 ? "s" : ""}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recent access */}
                    {consentSvc?.recent_access && consentSvc.recent_access.length > 0 && (
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-2">Recent Agent Access</p>
                        <div className="space-y-1">
                          {consentSvc.recent_access.slice(0, 5).map((j: any) => (
                            <div key={j.job_id} className="flex items-center gap-3 text-xs py-1 px-2 bg-white dark:bg-zinc-900 rounded border border-zinc-200 dark:border-zinc-700">
                              <code className="text-zinc-500 dark:text-zinc-400 font-mono">{j.agent_user_id}</code>
                              <code className="bg-zinc-800 text-zinc-100 px-1.5 py-0.5 rounded">{j.action}</code>
                              <Badge variant={j.state === "approved" ? "success" : j.state === "rejected" ? "danger" : "default"} className="text-xs">{j.state}</Badge>
                              <span className="text-zinc-400 ml-auto">{new Date(j.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-8 p-5 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700">
        <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-3 uppercase tracking-wide">How Auth0 Token Vault works</p>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {[
            { label: "AI Agent", sub: null, highlight: false },
            { label: "ApprovalKit", sub: "CIBA push", highlight: false },
            { label: "Human approves", sub: null, highlight: false },
            { label: "Auth0 Token Vault", sub: "retrieves token", highlight: true },
            { label: "Action executed", sub: null, highlight: false },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 rounded-lg px-3 py-2 border ${step.highlight ? "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800" : "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-700"}`}>
                <span className={`font-medium ${step.highlight ? "text-blue-700 dark:text-blue-400" : "text-zinc-700 dark:text-zinc-300 dark:text-zinc-600"}`}>{step.label}</span>
                {step.sub && <span className={`${step.highlight ? "text-blue-400" : "text-zinc-400"}`}>({step.sub})</span>}
              </div>
              {i < arr.length - 1 && <span className="text-zinc-400">→</span>}
            </div>
          ))}
        </div>
        <p className="text-xs text-zinc-400 mt-3">
          ApprovalKit never stores your credentials. Tokens live exclusively in Auth0 Token Vault and are retrieved only after human approval.
        </p>
      </div>

      {infoPopup && (() => {
        const conn = connections.find(c => c.id === infoPopup);
        const service = conn?.service?.toLowerCase() || "";
        const label = conn ? (SERVICE_LABEL[service] || conn.service) : "";
        const tenantSlug = auth0Domain.replace(".us.auth0.com", "").replace(".auth0.com", "");
        const dashboardUrl = `https://manage.auth0.com/dashboard/us/${tenantSlug}/connections/social`;

        const SERVICE_GUIDES: Record<string, { provider_url: string; provider_label: string; steps: string[]; scopes?: string; redirect_note?: string }> = {
          slack: {
            provider_url: "https://api.slack.com/apps",
            provider_label: "Slack App Dashboard",
            steps: [
              "Go to api.slack.com/apps → Create New App → From scratch → name it and select your workspace",
              "OAuth & Permissions → Bot Token Scopes → add: chat:write, channels:read, users:read (this also creates the Bot User automatically)",
              "OAuth & Permissions → User Token Scopes → add: identity.basic, identity.email",
              "OAuth & Permissions → Redirect URLs → add: https://" + auth0Domain + "/login/callback",
              "Basic Information → App Credentials → copy Client ID and Client Secret (click Show to reveal secret)",
              "Auth0 Dashboard → Authentication → Social → Create Connection → Sign in with Slack",
              "Paste Client ID and Client Secret from Slack App",
              "Purpose: select 'Connected Accounts for Token Vault'",
              "Applications tab → enable your Regular Web Application → Save Changes",
            ],
            scopes: "Bot: chat:write, channels:read, users:read | User: identity.basic, identity.email",
          },
          github: {
            provider_url: "https://github.com/settings/developers",
            provider_label: "GitHub Developer Settings",
            steps: [
              "Go to github.com/settings/developers → OAuth Apps → New OAuth App",
              "Authorization callback URL: https://" + auth0Domain + "/login/callback",
              "Copy Client ID and generate Client Secret",
              "Auth0 Dashboard → Authentication → Social → GitHub → enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab → enable your web application → Save Changes",
            ],
            scopes: "repo, read:org, read:user",
          },
          gmail: {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Go to console.cloud.google.com → APIs & Services → Credentials → Create OAuth Client ID",
              "Application type: Web application",
              "Authorized redirect URI: https://" + auth0Domain + "/login/callback",
              "Copy Client ID and Client Secret",
              "Auth0 Dashboard → Authentication → Social → Google → enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab → enable your web application → Save Changes",
            ],
            scopes: "gmail.send, gmail.readonly",
          },
          google: {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Go to console.cloud.google.com → APIs & Services → Credentials → Create OAuth Client ID",
              "Authorized redirect URI: https://" + auth0Domain + "/login/callback",
              "Enable Google Drive API in APIs & Services → Library",
              "Auth0 Dashboard → Authentication → Social → Google → enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab → enable your web application → Save Changes",
            ],
            scopes: "drive.file, drive.readonly",
          },
          "google-drive": {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Uses the same Google OAuth connection — if Google is already configured, this works automatically",
              "Make sure Google Drive API is enabled: APIs & Services → Library → Google Drive API → Enable",
              "Auth0 → Social → Google connection → verify drive scope is included",
            ],
            scopes: "drive.file, drive.readonly",
          },
          stripe: {
            provider_url: "https://dashboard.stripe.com/settings/connect",
            provider_label: "Stripe Dashboard",
            steps: [
              "Go to dashboard.stripe.com → Settings → Connect (or Platform) settings",
              "Redirect URI: https://" + auth0Domain + "/login/callback",
              "Copy Client ID (starts with ca_) from Connect settings",
              "Copy Secret Key from Developers → API Keys",
              "Auth0 Dashboard → Authentication → Social → Create Custom → set up as OAuth2",
              "Authorization URL: https://connect.stripe.com/oauth/authorize",
              "Token URL: https://connect.stripe.com/oauth/token",
              "Applications tab → enable your web application → Save Changes",
            ],
            scopes: "read_write",
          },
          salesforce: {
            provider_url: "https://login.salesforce.com/",
            provider_label: "Salesforce Setup",
            steps: [
              "Salesforce → Setup → App Manager → New Connected App",
              "Enable OAuth Settings → Callback URL: https://" + auth0Domain + "/login/callback",
              "Select scopes: Full access (full), Perform requests (api)",
              "Copy Consumer Key and Consumer Secret",
              "Auth0 Dashboard → Authentication → Social → Salesforce → enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab → enable your web application → Save Changes",
            ],
            scopes: "full, api",
          },
        };

        const guide = SERVICE_GUIDES[service] || null;

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setInfoPopup(null)}>
            <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl p-6 max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Configure {label}</h3>
                <button onClick={() => setInfoPopup(null)} className="text-zinc-400 hover:text-zinc-600"><X className="h-4 w-4" /></button>
              </div>

              {guide ? (
                <>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
                    Connect <strong>{label}</strong> to Auth0 Token Vault so the agent can execute actions on your behalf without ever seeing your credentials.
                  </p>

                  <div className="space-y-2 mb-4">
                    {guide.steps.map((step, i) => (
                      <div key={i} className="flex gap-2.5 text-sm">
                        <span className="font-bold text-zinc-300 dark:text-zinc-600 shrink-0 w-5 text-right">{i + 1}.</span>
                        <span className="text-zinc-600 dark:text-zinc-400">{step}</span>
                      </div>
                    ))}
                  </div>

                  {guide.scopes && (
                    <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-3 mb-4">
                      <div className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-1">Required Scopes</div>
                      <code className="text-xs text-zinc-600 dark:text-zinc-300">{guide.scopes}</code>
                    </div>
                  )}

                  <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-4">
                    <div className="text-[10px] text-blue-500 font-semibold uppercase tracking-wider mb-1">Required URLs</div>
                    <p className="text-[10px] text-blue-400 mb-1.5">
                      Add these to <strong>two places</strong> in your Auth0 Dashboard:
                    </p>
                    <div className="space-y-2">
                      <div>
                        <div className="text-[10px] text-blue-600 dark:text-blue-300 font-medium">1. Regular Web Application → Settings → Allowed Callback URLs:</div>
                        <div className="space-y-0.5 mt-0.5">
                          {[
                            "http://localhost:3000/auth/callback",
                            "http://localhost:8000/api/v1/connections/oauth/callback",
                            "http://localhost:8000/api/v1/connections/connected-accounts/callback",
                          ].map((url, i) => (
                            <code key={i} className="block text-[10px] text-blue-700 dark:text-blue-300 break-all">{url}</code>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-blue-600 dark:text-blue-300 font-medium">2. Slack App → OAuth &amp; Permissions → Redirect URLs:</div>
                        <code className="block text-[10px] text-blue-700 dark:text-blue-300 break-all mt-0.5">
                          {`https://${auth0Domain}/login/callback`}
                        </code>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <a href={guide.provider_url} target="_blank" rel="noopener noreferrer"
                      className="flex-1 text-center bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 text-sm font-medium py-2 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors">
                      {guide.provider_label} ↗
                    </a>
                    <a href={dashboardUrl} target="_blank" rel="noopener noreferrer"
                      className="flex-1 text-center bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-sm font-medium py-2 rounded-lg hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors">
                      Auth0 Dashboard ↗
                    </a>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
                    <strong>{label}</strong> requires a Social Connection in your Auth0 tenant.
                  </p>
                  <ol className="text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-5">
                    <li className="flex gap-2"><span className="font-bold text-zinc-400">1.</span> Create OAuth credentials at the service provider</li>
                    <li className="flex gap-2"><span className="font-bold text-zinc-400">2.</span> Add redirect URL: https://{auth0Domain}/login/callback</li>
                    <li className="flex gap-2"><span className="font-bold text-zinc-400">3.</span> Auth0 Dashboard → Authentication → Social → add connection</li>
                    <li className="flex gap-2"><span className="font-bold text-zinc-400">4.</span> Select &apos;Connected Accounts for Token Vault&apos; as purpose</li>
                    <li className="flex gap-2"><span className="font-bold text-zinc-400">5.</span> Applications tab → enable your web app → Save Changes</li>
                  </ol>
                  <a href={dashboardUrl} target="_blank" rel="noopener noreferrer"
                    className="block w-full text-center bg-zinc-900 text-white text-sm font-medium py-2 rounded-lg hover:bg-zinc-800 transition-colors">
                    Open Auth0 Dashboard ↗
                  </a>
                </>
              )}
            </div>
          </div>
        );
      })()}

      {/* Add Service Modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowAdd(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Add Service Connection</h3>
              <button onClick={() => setShowAdd(false)} className="text-zinc-400 hover:text-zinc-600"><X className="h-4 w-4" /></button>
            </div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
              Select a service to connect via Auth0 Token Vault. Built-in handlers execute actions automatically after approval.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {PREDEFINED_SERVICES.map(svc => {
                const exists = existingSlugs.has(svc.slug);
                return (
                  <button
                    key={svc.id}
                    disabled={exists || addSaving === svc.id}
                    onClick={() => handleAddService(svc)}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      exists
                        ? "border-zinc-100 dark:border-zinc-800 opacity-50 cursor-not-allowed"
                        : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm text-zinc-900 dark:text-zinc-100">{svc.name}</span>
                      {exists && <Badge variant="default" className="text-[10px]">Added</Badge>}
                      {addSaving === svc.id && <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-zinc-900 dark:border-zinc-100" />}
                    </div>
                    <div className="flex gap-1 mt-1.5 flex-wrap">
                      {svc.actions.map(a => (
                        <span key={a} className="text-[10px] bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 px-1.5 py-0.5 rounded">{a}</span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="mt-4 pt-3 border-t border-zinc-200 dark:border-zinc-700 text-center">
              <button onClick={() => { setShowAdd(false); setShowCustom(true); }} className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300">
                Need a different service? <span className="underline">Add Custom Webhook</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Custom Connection Modal */}
      {showCustom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowCustom(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <Webhook className="h-5 w-5" /> Add Custom Connection
              </h3>
              <button onClick={() => setShowCustom(false)} className="text-zinc-400 hover:text-zinc-600"><X className="h-4 w-4" /></button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Name *</label>
                  <Input placeholder="My CRM" value={customName} onChange={e => { setCustomName(e.target.value); if (!customSlug || customSlug === customName.toLowerCase().replace(/[^a-z0-9]/g, "-")) setCustomSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "-")); }} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Slug *</label>
                  <Input placeholder="my-crm" value={customSlug} onChange={e => setCustomSlug(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Actions</label>
                <Input placeholder="create_deal, update_contact, notify" value={customActions} onChange={e => setCustomActions(e.target.value)} className="mt-1" />
                <p className="text-xs text-zinc-400 mt-1">Comma-separated list of actions this connection supports</p>
              </div>

              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5" /> Webhook Execution Config
                </p>

                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Webhook URL *</label>
                  <Input placeholder="https://api.example.com/{{action}}" value={customUrl} onChange={e => setCustomUrl(e.target.value)} className="mt-1 font-mono text-xs" />
                  <p className="text-xs text-zinc-400 mt-1">Use {"{{action}}"}, {"{{token}}"}, {"{{param_name}}"} as placeholders</p>
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Method</label>
                  <div className="flex gap-1.5 mt-1">
                    {["GET", "POST", "PUT", "PATCH", "DELETE"].map(m => (
                      <button key={m} onClick={() => setCustomMethod(m)}
                        className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors ${
                          customMethod === m
                            ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                            : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                        }`}>{m}</button>
                    ))}
                  </div>
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Headers (JSON)</label>
                  <textarea
                    value={customHeaders}
                    onChange={e => setCustomHeaders(e.target.value)}
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 dark:text-zinc-100 px-3 py-2 text-xs font-mono focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                    placeholder='{"Authorization": "Bearer {{token}}"}'
                  />
                </div>

                <div className="mt-3">
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Body Template (JSON, optional)</label>
                  <textarea
                    value={customBody}
                    onChange={e => setCustomBody(e.target.value)}
                    rows={4}
                    className="mt-1 w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 dark:text-zinc-100 px-3 py-2 text-xs font-mono focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
                    placeholder='{"amount": "{{amount}}", "customer": "{{customer}}"}'
                  />
                  <p className="text-xs text-zinc-400 mt-1">If empty, raw request params are sent as the body</p>
                </div>
              </div>

              <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg text-xs text-blue-700 dark:text-blue-400">
                After approval, Token Vault replaces <code className="bg-blue-100 dark:bg-blue-900/50 px-1 rounded">{"{{token}}"}</code> with the real OAuth token and <code className="bg-blue-100 dark:bg-blue-900/50 px-1 rounded">{"{{param}}"}</code> with request values, then executes the HTTP call. Your agent never sees the token.
              </div>

              <FormError message={customError} />

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowCustom(false)}>Cancel</Button>
                <Button onClick={handleSaveCustom} disabled={customSaving}>
                  {customSaving ? "Creating..." : "Create Connection"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ConnectionsPage() {
  return (
    <Suspense>
      <ConnectionsContent />
    </Suspense>
  );
}
