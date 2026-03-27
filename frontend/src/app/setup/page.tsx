"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FormError } from "@/components/ui/form-error";
import { CheckCircle2, ArrowRight, Shield, Link2, GitBranch, Copy, Check, Loader2, LogOut } from "lucide-react";
import { api, setUserSub } from "@/lib/api";

const steps = [
  { number: 1, title: "Connect Auth0", icon: Shield },
  { number: 2, title: "Add Connections", icon: Link2 },
  { number: 3, title: "Start Building", icon: GitBranch },
];

const services = [
  { id: "stripe",     name: "Stripe",        slug: "stripe-prod",  actions: ["charge", "refund", "payout"] },
  { id: "github",     name: "GitHub",        slug: "github-main",  actions: ["deploy", "rollback", "merge_pr"] },
  { id: "google",     name: "Google",        slug: "google",       actions: ["send_email", "create_event"] },
  { id: "slack",      name: "Slack",         slug: "slack",        actions: ["send_message", "create_channel"] },
  { id: "salesforce", name: "Salesforce",    slug: "salesforce",   actions: ["create_deal", "update_contact"] },
  { id: "microsoft",  name: "Microsoft",     slug: "microsoft",    actions: ["send_email", "upload_file"] },
  { id: "notion",     name: "Notion",        slug: "notion",       actions: ["create_page", "update_database"] },
  { id: "jira",       name: "Jira",          slug: "jira",         actions: ["create_issue", "update_issue"] },
  { id: "discord",    name: "Discord",       slug: "discord",      actions: ["send_message"] },
  { id: "dropbox",    name: "Dropbox",       slug: "dropbox",      actions: ["upload_file", "share_folder"] },
  { id: "shopify",    name: "Shopify",       slug: "shopify",      actions: ["create_order", "update_product"] },
  { id: "hubspot",    name: "HubSpot",       slug: "hubspot",      actions: ["create_contact", "create_deal"] },
  { id: "linear",     name: "Linear",        slug: "linear",       actions: ["create_issue", "update_status"] },
  { id: "paypal",     name: "PayPal",        slug: "paypal",       actions: ["send_payment", "create_invoice"] },
];

export default function SetupPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useUser();
  const [step, setStep] = useState(1);
  const [tenant, setTenant] = useState("");
  const [m2mClientId, setM2mClientId] = useState("");
  const [m2mClientSecret, setM2mClientSecret] = useState("");
  const [webClientId, setWebClientId] = useState("");
  const [webClientSecret, setWebClientSecret] = useState("");
  const [fgaStoreId, setFgaStoreId] = useState("");
  const [fgaClientId, setFgaClientId] = useState("");
  const [fgaClientSecret, setFgaClientSecret] = useState("");
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [checking, setChecking] = useState(true);

  // If user already has a workspace, redirect to dashboard
  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push("/auth/login?returnTo=/setup"); return; }
    // Set user sub before any API call (setup page bypasses ConditionalLayout auth guard)
    setUserSub(user.sub ?? null);
    api.getWorkspace()
      .then(() => router.replace("/dashboard"))
      .catch(() => setChecking(false));
  }, [authLoading, user]);

  const handleStep1 = async () => {
    if (!tenant.trim()) { setError("Auth0 domain is required."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.setupWorkspace({
        name: user?.name ? `${user.name}'s Workspace` : "My Workspace",
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
      if (res.api_key) setApiKey(res.api_key);
      setStep(2);
    } catch (err: any) {
      setError(err.message || "Failed to connect. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleStep2 = async () => {
    setLoading(true);
    setError(null);
    try {
      const selected = services.filter((s) => selectedServices.includes(s.id));
      await Promise.all(
        selected.map((svc) =>
          api.createConnection({ name: svc.name, service: svc.id, slug: svc.slug, actions: svc.actions })
        )
      );
      setStep(3);
    } catch (err: any) {
      setError(err.message || "Failed to create connections.");
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-2xl">
        {/* Logo + title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
            <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Set up your workspace</h1>
          <p className="text-zinc-500 dark:text-zinc-400 mt-1 text-sm">
            {user?.email && (
              <>
                Signed in as <strong>{user.email}</strong>
                {" · "}
                <a href="/auth/logout" className="inline-flex items-center gap-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
                  <LogOut className="h-3 w-3" />
                  Logout
                </a>
              </>
            )}
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-3 mb-8">
          {steps.map((s) => (
            <div key={s.number} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                step > s.number
                  ? "bg-green-500 text-white"
                  : step === s.number
                  ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                  : "bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400"
              }`}>
                {step > s.number ? <CheckCircle2 className="h-4 w-4" /> : s.number}
              </div>
              <span className={`text-sm font-medium hidden sm:inline ${
                step >= s.number ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-400"
              }`}>{s.title}</span>
              {s.number < 3 && <ArrowRight className="h-3 w-3 text-zinc-300 dark:text-zinc-600 mx-1" />}
            </div>
          ))}
        </div>

        {/* Step 1: Auth0 credentials */}
        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Connect Auth0</CardTitle>
              <CardDescription>
                Follow the steps below in your Auth0 Dashboard, then paste the credentials.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">

              {/* Auth0 Domain */}
              <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-xs text-blue-700 dark:text-blue-300 font-medium mb-1">Auth0 Dashboard &rarr; Settings &rarr; General &rarr; Tenant Name</p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mb-2">Enter your tenant name below. The <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">.us.auth0.com</code> suffix is added automatically.</p>
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
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4 space-y-2">
                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">Don&apos;t forget these two steps in Auth0 Dashboard:</p>
                  <ul className="text-xs text-amber-600 dark:text-amber-400 mt-1 ml-3 list-disc space-y-0.5">
                    <li><strong>Token Vault:</strong> Authentication &rarr; Social &rarr; each connection &rarr; Advanced &rarr; Enable Token Vault</li>
                    <li><strong>Guardian:</strong> Security &rarr; Multi-factor Auth &rarr; Push via Auth0 Guardian &rarr; Enable</li>
                  </ul>
                </div>
              </div>

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
                    <Input value={fgaClientId} onChange={(e) => setFgaClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                  <div>
                    <label className="text-xs text-zinc-600 dark:text-zinc-400">Client Secret</label>
                    <Input type="password" value={fgaClientSecret} onChange={(e) => setFgaClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                  </div>
                </div>
              </details>

              <FormError message={error} />

              <div className="flex justify-end">
                <Button onClick={handleStep1} disabled={!tenant.trim() || loading}>
                  {loading ? "Connecting..." : "Connect & Continue"}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Choose connections */}
        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Add Service Connections</CardTitle>
              <CardDescription>Select services your agents will interact with.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {apiKey && (
                <div className="p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg">
                  <p className="text-sm font-medium text-green-800 dark:text-green-300 mb-2">
                    Workspace created! Save your API key:
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-white dark:bg-zinc-900 border rounded px-3 py-2 font-mono truncate">{apiKey}</code>
                    <button onClick={() => { navigator.clipboard.writeText(apiKey); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
                      className="p-2 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400">
                      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                {services.map((svc) => (
                  <button key={svc.id} onClick={() => setSelectedServices((p) => p.includes(svc.id) ? p.filter((s) => s !== svc.id) : [...p, svc.id])}
                    className={`p-3 rounded-lg border text-left transition-colors ${
                      selectedServices.includes(svc.id)
                        ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800"
                        : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-300"
                    }`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm text-zinc-900 dark:text-zinc-100">{svc.name}</span>
                      {selectedServices.includes(svc.id) && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                    </div>
                    <div className="flex gap-1 mt-1.5 flex-wrap">
                      {svc.actions.map((a) => <Badge key={a} variant="default" className="text-[10px]">{a}</Badge>)}
                    </div>
                  </button>
                ))}
              </div>

              <FormError message={error} />

              <div className="flex justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => setStep(3)}>Skip</Button>
                  <Button onClick={handleStep2} disabled={selectedServices.length === 0 || loading}>
                    {loading ? "Creating..." : `Add ${selectedServices.length} connection${selectedServices.length !== 1 ? "s" : ""}`}
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Done */}
        {step === 3 && (
          <Card>
            <CardHeader className="text-center">
              <div className="mx-auto w-16 h-16 rounded-full bg-green-50 dark:bg-green-950/30 flex items-center justify-center mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-500" />
              </div>
              <CardTitle>All set!</CardTitle>
              <CardDescription>
                Your workspace is ready. Create approval rules, connect agents, and start approving actions.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Button variant="outline" className="w-full" onClick={() => router.push("/rules/new")}>
                  <GitBranch className="h-4 w-4 mr-2" /> Create First Rule
                </Button>
                <Button variant="outline" className="w-full" onClick={() => router.push("/connect")}>
                  <Link2 className="h-4 w-4 mr-2" /> Connect an Agent
                </Button>
              </div>
              <Button className="w-full" onClick={() => router.push("/dashboard")}>
                Go to Dashboard <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
