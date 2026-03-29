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
  metadata?: Record<string, string> | null;
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

const SERVICE_COLORS: Record<string, { border: string; bg: string; text: string }> = {
  github:     { border: "border-l-zinc-800",    bg: "bg-zinc-800",    text: "text-white" },
  stripe:     { border: "border-l-violet-500",   bg: "bg-violet-500",  text: "text-white" },
  slack:      { border: "border-l-amber-500",    bg: "bg-amber-500",   text: "text-white" },
  salesforce: { border: "border-l-sky-500",      bg: "bg-sky-500",     text: "text-white" },
  google:     { border: "border-l-red-500",      bg: "bg-red-500",     text: "text-white" },
  gmail:      { border: "border-l-red-500",      bg: "bg-red-500",     text: "text-white" },
  microsoft:  { border: "border-l-blue-600",     bg: "bg-blue-600",    text: "text-white" },
  outlook:    { border: "border-l-blue-600",     bg: "bg-blue-600",    text: "text-white" },
  notion:     { border: "border-l-zinc-900",     bg: "bg-zinc-900",    text: "text-white" },
  jira:       { border: "border-l-blue-500",     bg: "bg-blue-500",    text: "text-white" },
  discord:    { border: "border-l-indigo-500",   bg: "bg-indigo-500",  text: "text-white" },
  dropbox:    { border: "border-l-blue-400",     bg: "bg-blue-400",    text: "text-white" },
  linear:     { border: "border-l-violet-600",   bg: "bg-violet-600",  text: "text-white" },
  hubspot:    { border: "border-l-orange-500",   bg: "bg-orange-500",  text: "text-white" },
  shopify:    { border: "border-l-green-600",    bg: "bg-green-600",   text: "text-white" },
  paypal:     { border: "border-l-blue-700",     bg: "bg-blue-700",    text: "text-white" },
  asana:      { border: "border-l-rose-500",     bg: "bg-rose-500",    text: "text-white" },
  figma:      { border: "border-l-purple-500",   bg: "bg-purple-500",  text: "text-white" },
  box:        { border: "border-l-blue-500",     bg: "bg-blue-500",    text: "text-white" },
  bitbucket:  { border: "border-l-blue-600",     bg: "bg-blue-600",    text: "text-white" },
  freshbooks: { border: "border-l-emerald-500",  bg: "bg-emerald-500", text: "text-white" },
  spotify:    { border: "border-l-green-500",    bg: "bg-green-500",   text: "text-white" },
  custom:     { border: "border-l-zinc-400",     bg: "bg-zinc-400",    text: "text-white" },
};

function getServiceColor(service: string) {
  return SERVICE_COLORS[service.toLowerCase()] || SERVICE_COLORS.custom;
}

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
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
            Connections
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1.5 text-sm">
            Connect services via Auth0 Token Vault -- no API keys stored, ever.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAdd(true)} className="rounded-lg">
            <Plus className="h-4 w-4 mr-2" /> Add Service
          </Button>
          <Button onClick={() => setShowCustom(true)} className="rounded-lg bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white border-0">
            <Webhook className="h-4 w-4 mr-2" /> Custom Webhook
          </Button>
        </div>
      </div>

      {/* Success banner */}
      {successSlug && (
        <div className="mb-5 p-3.5 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-xl text-sm text-emerald-700 dark:text-emerald-400 flex justify-between items-center shadow-sm">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <strong>{successSlug}</strong> connected successfully via Auth0 Token Vault.
          </span>
          <button onClick={() => setSuccessSlug(null)} className="text-emerald-400 hover:text-emerald-600 transition-colors"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="mb-5 p-3.5 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-400 flex justify-between items-center shadow-sm">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 transition-colors"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : connections.length === 0 ? (
        /* Empty state */
        <Card className="border border-zinc-200 dark:border-zinc-700 rounded-2xl shadow-sm">
          <CardContent className="py-12">
            <div className="text-center mb-8">
              <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-blue-100 to-emerald-100 dark:from-blue-950/50 dark:to-emerald-950/50 flex items-center justify-center">
                <Link2 className="h-8 w-8 text-blue-500" />
              </div>
              <p className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">No connections yet</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Connect your first service to start gating agent actions with approvals.</p>
            </div>
            <div className="max-w-md mx-auto space-y-4">
              <div className="p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-500 mb-2">How connections work</p>
                <ol className="text-xs text-blue-600 dark:text-blue-400 ml-3 list-decimal space-y-1.5">
                  <li>Enable <strong>Token Vault</strong> for a social connection in Auth0 (Authentication &rarr; Social &rarr; Advanced &rarr; Enable Token Vault)</li>
                  <li>Click <strong>&quot;Add Connection&quot;</strong> below to register it here</li>
                  <li>Click <strong>&quot;Connect&quot;</strong> to link your account via OAuth -- credentials stored in Auth0 Token Vault</li>
                </ol>
              </div>
              <Button className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white border-0" onClick={() => setShowAdd(true)}>
                <Link2 className="h-4 w-4 mr-2" /> Add Your First Connection
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        /* Connection list */
        <div className="space-y-3">
          {connections.map((conn) => {
            const label = SERVICE_LABEL[conn.service.toLowerCase()] || conn.service;
            const configured = conn.is_auth0_configured;
            const isConnecting = connecting === conn.id;
            const colors = getServiceColor(conn.service);
            const consentSvc = consent?.services?.find((s: any) => s.slug === conn.slug);
            const isExpanded = expandedId === conn.id;

            const isConnected = conn.connected_via === "auth0" || (conn.has_webhook && conn.connected_via === "webhook");

            return (
              <div
                key={conn.id}
                className={`border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden border-l-4 ${colors.border} bg-white dark:bg-zinc-900 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200`}
              >
                {/* Header */}
                <div className="p-4 flex items-center justify-between">
                  <button className="flex items-center gap-4 flex-1 text-left" onClick={() => setExpandedId(isExpanded ? null : conn.id)}>
                    <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`} />
                    <div className={`w-10 h-10 rounded-lg ${colors.bg} ${colors.text} flex items-center justify-center text-xs font-bold uppercase tracking-wide shadow-sm`}>
                      {conn.service.slice(0, 2)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2.5">
                        <span className="font-semibold text-zinc-900 dark:text-zinc-100">{conn.name}</span>
                        <code className="text-[11px] text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded font-mono">{conn.slug}</code>
                        {isConnected ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            Connected
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-zinc-100 dark:bg-zinc-800 text-zinc-400 border border-zinc-200 dark:border-zinc-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400" />
                            Not connected
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                        {conn.actions.join(", ")}
                      </div>
                      {conn.connected_user_name && (
                        <div className="text-xs text-zinc-400 mt-0.5">
                          Connected as: <span className="font-medium text-zinc-600 dark:text-zinc-400">{conn.connected_user_name}</span>
                        </div>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-2">
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
                          className="text-red-500 hover:text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg"
                          onClick={() => handleDisconnect(conn)}
                        >
                          <Unlink className="h-4 w-4 mr-1" /> Disconnect
                        </Button>
                      </>
                    ) : configured ? (
                      <>
                        <Button
                          size="sm"
                          disabled={isConnecting}
                          onClick={() => handleConnect(conn)}
                          className="rounded-lg"
                        >
                          <Link2 className="h-4 w-4 mr-2" />
                          {isConnecting ? "Redirecting..." : `Connect with ${label}`}
                        </Button>
                      </>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Badge variant="default">Setup required</Badge>
                        <button onClick={() => setInfoPopup(conn.id)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
                          <Info className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg"
                      onClick={() => handleDelete(conn)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-5 pb-5 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-800/30 space-y-5 pt-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1.5">OAuth Scopes</p>
                        <div className="flex gap-1 flex-wrap">
                          {(consentSvc?.oauth_scopes || "openid profile email").split(" ").map((scope: string) => (
                            <span key={scope} className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded font-mono">{scope}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1.5">Actions</p>
                        <div className="flex gap-1 flex-wrap items-center">
                          {conn.actions.map((a) => (
                            <span key={a} className="inline-flex items-center gap-1 text-xs bg-zinc-800 dark:bg-zinc-700 text-zinc-100 pl-2 pr-1 py-0.5 rounded">
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
                              className="w-24 text-xs bg-transparent border border-dashed border-zinc-300 dark:border-zinc-600 rounded px-2 py-0.5 text-zinc-600 dark:text-zinc-400 placeholder:text-zinc-400 focus:outline-none focus:border-blue-500"
                            />
                          </form>
                        </div>
                      </div>
                      {conn.service.toLowerCase() === "github" && (
                        <div>
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1.5">Repository</p>
                          <form
                            onSubmit={async (e) => {
                              e.preventDefault();
                              const form = e.target as HTMLFormElement;
                              const ownerInput = form.elements.namedItem("owner") as HTMLInputElement;
                              const repoInput = form.elements.namedItem("repo") as HTMLInputElement;
                              const owner = ownerInput.value.trim();
                              const repo = repoInput.value.trim();
                              if (!owner || !repo) return;
                              try {
                                await api.updateConnection(conn.id, { metadata: { owner, repo } });
                                load();
                              } catch {}
                            }}
                            className="flex gap-1.5 items-center"
                          >
                            <input
                              name="owner"
                              placeholder="owner"
                              defaultValue={conn.metadata?.owner || ""}
                              className="w-24 text-xs bg-transparent border border-zinc-300 dark:border-zinc-600 rounded px-2 py-1 text-zinc-600 dark:text-zinc-300 placeholder:text-zinc-400 focus:outline-none focus:border-blue-500"
                            />
                            <span className="text-zinc-400 text-xs">/</span>
                            <input
                              name="repo"
                              placeholder="repo"
                              defaultValue={conn.metadata?.repo || ""}
                              className="w-24 text-xs bg-transparent border border-zinc-300 dark:border-zinc-600 rounded px-2 py-1 text-zinc-600 dark:text-zinc-300 placeholder:text-zinc-400 focus:outline-none focus:border-blue-500"
                            />
                            <button type="submit" className="text-xs text-emerald-500 hover:text-emerald-400 font-medium">Save</button>
                          </form>
                        </div>
                      )}
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1.5">Status</p>
                        <p className="text-sm text-zinc-600 dark:text-zinc-400">
                          {conn.connected_via === "auth0" ? "Connected via Token Vault" : configured ? "Auth0 connection ready" : "Auth0 social connection not configured"}
                        </p>
                      </div>
                    </div>

                    {/* Rules for this connection */}
                    {consentSvc?.rules && consentSvc.rules.length > 0 && (
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">Approval Rules</p>
                        <div className="space-y-1.5">
                          {consentSvc.rules.map((r: any) => (
                            <div key={r.id} className="flex items-center gap-3 text-xs py-1.5 px-3 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors">
                              <span className="font-medium text-zinc-700 dark:text-zinc-300 flex-1">{r.name}</span>
                              <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-600 dark:text-zinc-400">{r.action}</code>
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
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">Recent Agent Access</p>
                        <div className="space-y-1.5">
                          {consentSvc.recent_access.slice(0, 5).map((j: any) => (
                            <div key={j.job_id} className="flex items-center gap-3 text-xs py-1.5 px-3 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors">
                              <code className="text-zinc-500 dark:text-zinc-400 font-mono">{j.agent_user_id}</code>
                              <code className="bg-zinc-800 dark:bg-zinc-700 text-zinc-100 px-1.5 py-0.5 rounded">{j.action}</code>
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

      {/* How it works footer */}
      <div className="mt-10 p-5 bg-gradient-to-r from-zinc-50 to-blue-50/30 dark:from-zinc-800/50 dark:to-blue-950/20 rounded-xl border border-zinc-200 dark:border-zinc-700">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3">How Auth0 Token Vault works</p>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {[
            { label: "AI Agent", sub: null, highlight: false },
            { label: "ApprovalKit", sub: "CIBA push", highlight: false },
            { label: "Human approves", sub: null, highlight: false },
            { label: "Auth0 Token Vault", sub: "retrieves token", highlight: true },
            { label: "Action executed", sub: null, highlight: false },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 rounded-lg px-3 py-2 border transition-all ${step.highlight ? "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800 shadow-sm" : "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-700"}`}>
                <span className={`font-medium ${step.highlight ? "text-blue-700 dark:text-blue-400" : "text-zinc-700 dark:text-zinc-300"}`}>{step.label}</span>
                {step.sub && <span className={`${step.highlight ? "text-blue-400" : "text-zinc-400"}`}>({step.sub})</span>}
              </div>
              {i < arr.length - 1 && <span className="text-zinc-300 dark:text-zinc-600 font-medium">--&gt;</span>}
            </div>
          ))}
        </div>
        <p className="text-xs text-zinc-400 mt-3">
          ApprovalKit never stores your credentials. Tokens live exclusively in Auth0 Token Vault and are retrieved only after human approval.
        </p>
      </div>

      {/* Info popup modal */}
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
              "Go to api.slack.com/apps -> Create New App -> From scratch -> name it and select your workspace",
              "OAuth & Permissions -> Bot Token Scopes -> add: chat:write, channels:read, users:read (this also creates the Bot User automatically)",
              "OAuth & Permissions -> User Token Scopes -> add: identity.basic, identity.email",
              "OAuth & Permissions -> Redirect URLs -> add: https://" + auth0Domain + "/login/callback",
              "Basic Information -> App Credentials -> copy Client ID and Client Secret (click Show to reveal secret)",
              "Auth0 Dashboard -> Authentication -> Social -> Create Connection -> Sign in with Slack",
              "Paste Client ID and Client Secret from Slack App",
              "Permissions -> check identity.basic and identity.email -> Additional Scopes -> add: chat:write,channels:read,users:read",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your Regular Web Application -> Save Changes",
            ],
            scopes: "Bot: chat:write, channels:read, users:read | User: identity.basic, identity.email",
          },
          github: {
            provider_url: "https://github.com/settings/developers",
            provider_label: "GitHub Developer Settings",
            steps: [
              "Go to github.com/settings/developers -> OAuth Apps -> New OAuth App",
              "Homepage URL: http://localhost:3000",
              "Authorization callback URL: https://" + auth0Domain + "/login/callback",
              "Copy Client ID and generate Client Secret",
              "Auth0 Dashboard -> Authentication -> Social -> GitHub -> enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your web application -> Save Changes",
            ],
            scopes: "repo, read:org, read:user",
          },
          gmail: {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Go to console.cloud.google.com -> APIs & Services -> Credentials -> Create OAuth Client ID",
              "Application type: Web application",
              "Authorized redirect URI: https://" + auth0Domain + "/login/callback",
              "Copy Client ID and Client Secret",
              "Auth0 Dashboard -> Authentication -> Social -> Google -> enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your web application -> Save Changes",
            ],
            scopes: "gmail.send, gmail.readonly",
          },
          google: {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Go to console.cloud.google.com -> APIs & Services -> Credentials -> Create OAuth Client ID",
              "Authorized redirect URI: https://" + auth0Domain + "/login/callback",
              "Enable Google Drive API in APIs & Services -> Library",
              "Auth0 Dashboard -> Authentication -> Social -> Google -> enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your web application -> Save Changes",
            ],
            scopes: "drive.file, drive.readonly",
          },
          "google-drive": {
            provider_url: "https://console.cloud.google.com/apis/credentials",
            provider_label: "Google Cloud Console",
            steps: [
              "Uses the same Google OAuth connection -- if Google is already configured, this works automatically",
              "Make sure Google Drive API is enabled: APIs & Services -> Library -> Google Drive API -> Enable",
              "Auth0 -> Social -> Google connection -> verify drive scope is included",
            ],
            scopes: "drive.file, drive.readonly",
          },
          stripe: {
            provider_url: "https://dashboard.stripe.com/settings/connect/onboarding-options/oauth",
            provider_label: "Stripe Connect OAuth",
            steps: [
              "Go to dashboard.stripe.com -> Settings -> Connect -> Onboarding options -> OAuth",
              "Toggle 'Enable OAuth' to ON",
              "Add Redirect URI: https://" + auth0Domain + "/login/callback",
              "Copy the Client ID (starts with ca_) from this page",
              "Go to Developers -> API Keys -> copy the Secret key (starts with sk_test_ or sk_live_)",
              "Auth0 Dashboard -> Authentication -> Social -> Create Connection -> Stripe Connect",
              "Paste the ca_ Client ID and sk_ Secret key",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your Regular Web Application -> Save Changes",
            ],
            scopes: "read_write",
          },
          salesforce: {
            provider_url: "https://login.salesforce.com/",
            provider_label: "Salesforce Setup",
            steps: [
              "Salesforce -> Setup -> App Manager -> New Connected App",
              "Enable OAuth Settings -> Callback URL: https://" + auth0Domain + "/login/callback",
              "Select scopes: Full access (full), Perform requests (api)",
              "Copy Consumer Key and Consumer Secret",
              "Auth0 Dashboard -> Authentication -> Social -> Salesforce -> enter credentials",
              "Purpose: select 'Authentication and Connected Accounts for Token Vault'",
              "Applications tab -> enable your web application -> Save Changes",
            ],
            scopes: "full, api",
          },
        };

        const guide = SERVICE_GUIDES[service] || null;

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setInfoPopup(null)}>
            <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl p-6 max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto border border-zinc-200 dark:border-zinc-700" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Configure {label}</h3>
                <button onClick={() => setInfoPopup(null)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"><X className="h-4 w-4" /></button>
              </div>

              {guide ? (
                <>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-5">
                    Connect <strong>{label}</strong> to Auth0 Token Vault so the agent can execute actions on your behalf without ever seeing your credentials.
                  </p>

                  <div className="space-y-2.5 mb-5">
                    {guide.steps.map((step, i) => (
                      <div key={i} className="flex gap-3 text-sm">
                        <span className="font-bold text-zinc-300 dark:text-zinc-600 shrink-0 w-5 text-right tabular-nums">{i + 1}.</span>
                        <span className="text-zinc-600 dark:text-zinc-400">{step}</span>
                      </div>
                    ))}
                  </div>

                  {guide.scopes && (
                    <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-3.5 mb-5 border border-zinc-200 dark:border-zinc-700">
                      <div className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1">Required Scopes</div>
                      <code className="text-xs text-zinc-600 dark:text-zinc-300">{guide.scopes}</code>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <a href={guide.provider_url} target="_blank" rel="noopener noreferrer"
                      className="flex-1 text-center bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 text-sm font-medium py-2.5 rounded-xl hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors border border-zinc-200 dark:border-zinc-700">
                      {guide.provider_label} ↗
                    </a>
                    <a href={dashboardUrl} target="_blank" rel="noopener noreferrer"
                      className="flex-1 text-center bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-sm font-medium py-2.5 rounded-xl hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors">
                      Auth0 Dashboard ↗
                    </a>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-5">
                    <strong>{label}</strong> requires a Social Connection in your Auth0 tenant.
                  </p>
                  <ol className="text-sm text-zinc-600 dark:text-zinc-400 space-y-2.5 mb-5">
                    <li className="flex gap-3"><span className="font-bold text-zinc-400">1.</span> Create OAuth credentials at the service provider</li>
                    <li className="flex gap-3"><span className="font-bold text-zinc-400">2.</span> Add redirect URL: https://{auth0Domain}/login/callback</li>
                    <li className="flex gap-3"><span className="font-bold text-zinc-400">3.</span> Auth0 Dashboard -&gt; Authentication -&gt; Social -&gt; add connection</li>
                    <li className="flex gap-3"><span className="font-bold text-zinc-400">4.</span> Select &apos;Connected Accounts for Token Vault&apos; as purpose</li>
                    <li className="flex gap-3"><span className="font-bold text-zinc-400">5.</span> Applications tab -&gt; enable your web app -&gt; Save Changes</li>
                  </ol>
                  <a href={dashboardUrl} target="_blank" rel="noopener noreferrer"
                    className="block w-full text-center bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-sm font-medium py-2.5 rounded-xl hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowAdd(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto border border-zinc-200 dark:border-zinc-700" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Add Service Connection</h3>
              <button onClick={() => setShowAdd(false)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"><X className="h-4 w-4" /></button>
            </div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-5">
              Select a service to connect via Auth0 Token Vault. Built-in handlers execute actions automatically after approval.
            </p>
            <div className="grid grid-cols-2 gap-2.5">
              {PREDEFINED_SERVICES.map(svc => {
                const exists = existingSlugs.has(svc.slug);
                const colors = getServiceColor(svc.id);
                return (
                  <button
                    key={svc.id}
                    disabled={exists || addSaving === svc.id}
                    onClick={() => handleAddService(svc)}
                    className={`p-3.5 rounded-xl border text-left transition-all duration-200 ${
                      exists
                        ? "border-zinc-100 dark:border-zinc-800 opacity-40 cursor-not-allowed"
                        : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500 hover:-translate-y-0.5 hover:shadow-md"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-7 h-7 rounded-md ${colors.bg} ${colors.text} flex items-center justify-center text-[10px] font-bold uppercase`}>
                          {svc.id.slice(0, 2)}
                        </div>
                        <span className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{svc.name}</span>
                      </div>
                      {exists && <Badge variant="default" className="text-[10px]">Added</Badge>}
                      {addSaving === svc.id && <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-zinc-900 dark:border-zinc-100" />}
                    </div>
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {svc.actions.map(a => (
                        <span key={a} className="text-[10px] bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 px-1.5 py-0.5 rounded">{a}</span>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="mt-5 pt-4 border-t border-zinc-200 dark:border-zinc-700 text-center">
              <button onClick={() => { setShowAdd(false); setShowCustom(true); }} className="text-sm text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors">
                Need a different service? <span className="underline font-medium">Add Custom Webhook</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Custom Connection Modal */}
      {showCustom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowCustom(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto border border-zinc-200 dark:border-zinc-700" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center">
                  <Webhook className="h-4 w-4 text-white" />
                </div>
                Add Custom Connection
              </h3>
              <button onClick={() => setShowCustom(false)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"><X className="h-4 w-4" /></button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Name *</label>
                  <Input placeholder="My CRM" value={customName} onChange={e => { setCustomName(e.target.value); if (!customSlug || customSlug === customName.toLowerCase().replace(/[^a-z0-9]/g, "-")) setCustomSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "-")); }} className="mt-1.5 rounded-lg" />
                </div>
                <div>
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Slug *</label>
                  <Input placeholder="my-crm" value={customSlug} onChange={e => setCustomSlug(e.target.value)} className="mt-1.5 font-mono text-xs rounded-lg" />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Actions</label>
                <Input placeholder="create_deal, update_contact, notify" value={customActions} onChange={e => setCustomActions(e.target.value)} className="mt-1.5 rounded-lg" />
                <p className="text-xs text-zinc-400 mt-1">Comma-separated list of actions this connection supports</p>
              </div>

              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5" /> Webhook Execution Config
                </p>

                <div>
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Webhook URL *</label>
                  <Input placeholder="https://api.example.com/{{action}}" value={customUrl} onChange={e => setCustomUrl(e.target.value)} className="mt-1.5 font-mono text-xs rounded-lg" />
                  <p className="text-xs text-zinc-400 mt-1">Use {"{{action}}"}, {"{{token}}"}, {"{{param_name}}"} as placeholders</p>
                </div>

                <div className="mt-3">
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Method</label>
                  <div className="flex gap-1.5 mt-1.5">
                    {["GET", "POST", "PUT", "PATCH", "DELETE"].map(m => (
                      <button key={m} onClick={() => setCustomMethod(m)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                          customMethod === m
                            ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 shadow-sm"
                            : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                        }`}>{m}</button>
                    ))}
                  </div>
                </div>

                <div className="mt-3">
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Headers (JSON)</label>
                  <textarea
                    value={customHeaders}
                    onChange={e => setCustomHeaders(e.target.value)}
                    rows={3}
                    className="mt-1.5 w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 dark:text-zinc-100 px-3 py-2 text-xs font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder='{"Authorization": "Bearer {{token}}"}'
                  />
                </div>

                <div className="mt-3">
                  <label className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Body Template (JSON, optional)</label>
                  <textarea
                    value={customBody}
                    onChange={e => setCustomBody(e.target.value)}
                    rows={4}
                    className="mt-1.5 w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 dark:text-zinc-100 px-3 py-2 text-xs font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder='{"amount": "{{amount}}", "customer": "{{customer}}"}'
                  />
                  <p className="text-xs text-zinc-400 mt-1">If empty, raw request params are sent as the body</p>
                </div>
              </div>

              <div className="p-3.5 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-xl text-xs text-blue-700 dark:text-blue-400">
                After approval, Token Vault replaces <code className="bg-blue-100 dark:bg-blue-900/50 px-1 rounded font-mono">{"{{token}}"}</code> with the real OAuth token and <code className="bg-blue-100 dark:bg-blue-900/50 px-1 rounded font-mono">{"{{param}}"}</code> with request values, then executes the HTTP call. Your agent never sees the token.
              </div>

              <FormError message={customError} />

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowCustom(false)} className="rounded-lg">Cancel</Button>
                <Button onClick={handleSaveCustom} disabled={customSaving} className="rounded-lg bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white border-0">
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
