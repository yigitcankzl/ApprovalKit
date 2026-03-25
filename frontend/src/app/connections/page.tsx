"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { CheckCircle2, Link2, Unlink, X, AlertCircle, Info, Trash2, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";

interface Connection {
  id: string;
  name: string;
  service: string;
  slug: string;
  actions: string[];
  has_credentials: boolean;
  connected_via: "auth0" | null;
  connected_user_name: string | null;
  is_active: boolean;
  is_auth0_configured: boolean;
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
  const [connecting, setConnecting] = useState<string | null>(null);
  const [successSlug, setSuccessSlug] = useState<string | null>(null);
  const [infoPopup, setInfoPopup] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.getConnections(),
      api.getConsent().catch(() => null),
    ])
      .then(([c, con]) => { setConnections(c); setConsent(con); })
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

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Connections</h1>
        <p className="text-zinc-500 mt-1">
          Connect services via Auth0 Token Vault — no API keys stored, ever.
        </p>
      </div>

      {successSlug && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex justify-between items-center">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <strong>{successSlug}</strong> connected successfully via Auth0 Token Vault.
          </span>
          <button onClick={() => setSuccessSlug(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between items-center">
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
          <CardContent className="py-12 text-center">
            <Link2 className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
            <p className="text-zinc-500 mb-4">No connections yet.</p>
            <Button onClick={() => router.push("/onboarding")}>Set Up Connections</Button>
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
              <div key={conn.id} className="border border-zinc-200 rounded-xl overflow-hidden hover:border-zinc-300 transition-colors">
                {/* Header — click to expand */}
                <div className="p-4 flex items-center justify-between">
                  <button className="flex items-center gap-4 flex-1 text-left" onClick={() => setExpandedId(isExpanded ? null : conn.id)}>
                    <ChevronRight className={`h-4 w-4 text-zinc-400 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                    <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-sm font-bold text-zinc-700 uppercase">
                      {conn.service.slice(0, 2)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-zinc-900">{conn.name}</span>
                        <code className="text-xs text-zinc-400 bg-zinc-50 px-1.5 py-0.5 rounded">{conn.slug}</code>
                      </div>
                      <div className="text-sm text-zinc-500 mt-0.5">
                        {conn.actions.join(", ")}
                      </div>
                      {conn.connected_user_name && (
                        <div className="text-xs text-zinc-400 mt-0.5">
                          Connected as: <span className="font-medium text-zinc-600">{conn.connected_user_name}</span>
                        </div>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-3">
                    {conn.connected_via === "auth0" ? (
                      <>
                        <Badge variant="success">
                          <CheckCircle2 className="h-3 w-3 mr-1" /> Auth0 Token Vault
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-700 hover:bg-red-50"
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
                        <button onClick={() => setInfoPopup(conn.id)} className="text-zinc-400 hover:text-zinc-600">
                          <Info className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-zinc-400 hover:text-red-600 hover:bg-red-50"
                      onClick={() => handleDelete(conn)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-4 pb-4 border-t border-zinc-100 bg-zinc-50/50 space-y-4 pt-3">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">OAuth Scopes</p>
                        <div className="flex gap-1 flex-wrap">
                          {(consentSvc?.oauth_scopes || "openid profile email").split(" ").map((scope: string) => (
                            <span key={scope} className="text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded font-mono">{scope}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Actions</p>
                        <div className="flex gap-1 flex-wrap">
                          {conn.actions.map((a) => (
                            <code key={a} className="text-xs bg-zinc-800 text-zinc-100 px-2 py-0.5 rounded">{a}</code>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-400 uppercase tracking-wide mb-1">Status</p>
                        <p className="text-sm text-zinc-600">
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
                            <div key={r.id} className="flex items-center gap-3 text-xs py-1 px-2 bg-white rounded border border-zinc-200">
                              <span className="font-medium text-zinc-700 flex-1">{r.name}</span>
                              <code className="bg-zinc-100 px-1.5 py-0.5 rounded">{r.action}</code>
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
                            <div key={j.job_id} className="flex items-center gap-3 text-xs py-1 px-2 bg-white rounded border border-zinc-200">
                              <code className="text-zinc-500 font-mono">{j.agent_user_id}</code>
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

      <div className="mt-8 p-5 bg-zinc-50 rounded-lg border border-zinc-200">
        <p className="text-xs font-semibold text-zinc-700 mb-3 uppercase tracking-wide">How Auth0 Token Vault works</p>
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {[
            { label: "AI Agent", sub: null, highlight: false },
            { label: "ApprovalKit", sub: "CIBA push", highlight: false },
            { label: "Human approves", sub: null, highlight: false },
            { label: "Auth0 Token Vault", sub: "retrieves token", highlight: true },
            { label: "Action executed", sub: null, highlight: false },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 rounded-lg px-3 py-2 border ${step.highlight ? "bg-blue-50 border-blue-200" : "bg-white border-zinc-200"}`}>
                <span className={`font-medium ${step.highlight ? "text-blue-700" : "text-zinc-700"}`}>{step.label}</span>
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
        const label = conn ? (SERVICE_LABEL[conn.service.toLowerCase()] || conn.service) : "";
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setInfoPopup(null)}>
            <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-zinc-900">Configure {label}</h3>
                <button onClick={() => setInfoPopup(null)} className="text-zinc-400 hover:text-zinc-600"><X className="h-4 w-4" /></button>
              </div>
              <p className="text-sm text-zinc-600 mb-4">
                <strong>{label}</strong> requires a Social Connection in your Auth0 tenant. Once configured, the OAuth connect button will appear here.
              </p>
              <ol className="text-sm text-zinc-600 space-y-2 mb-5">
                <li className="flex gap-2"><span className="font-bold text-zinc-400">1.</span> Open Auth0 Dashboard</li>
                <li className="flex gap-2"><span className="font-bold text-zinc-400">2.</span> Go to <em>Authentication → Social</em></li>
                <li className="flex gap-2"><span className="font-bold text-zinc-400">3.</span> Add <strong>{label}</strong> connection</li>
                <li className="flex gap-2"><span className="font-bold text-zinc-400">4.</span> Enable it for this application</li>
              </ol>
              <a
                href={`https://manage.auth0.com/dashboard/us/${(process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "").replace(".us.auth0.com", "")}/connections/social`}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center bg-zinc-900 text-white text-sm font-medium py-2 rounded-lg hover:bg-zinc-800 transition-colors"
              >
                Open Auth0 Dashboard →
              </a>
            </div>
          </div>
        );
      })()}
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
