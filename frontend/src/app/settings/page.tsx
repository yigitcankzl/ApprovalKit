"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, ArrowRight, Shield, Link2, GitBranch, Copy, Check, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

const steps = [
  {
    number: 1,
    title: "Connect Auth0",
    description: "Enter your tenant credentials. Platform auto-fetches Token Vault connections.",
    icon: Shield,
  },
  {
    number: 2,
    title: "Define Connections",
    description: "Select services and define their available actions.",
    icon: Link2,
  },
  {
    number: 3,
    title: "Write First Rule",
    description: "Use the Rule Builder with live preview. Save. Done.",
    icon: GitBranch,
  },
];

const services = [
  { id: "stripe",     name: "Stripe",        slug: "stripe-prod",  actions: ["charge", "refund", "payout"] },
  { id: "github",     name: "GitHub",        slug: "github-main",  actions: ["deploy", "rollback", "merge_pr"] },
  { id: "google",     name: "Google",        slug: "google",       actions: ["send_email", "create_event", "read_drive"] },
  { id: "slack",      name: "Slack",         slug: "slack",        actions: ["send_message", "create_channel"] },
  { id: "salesforce", name: "Salesforce",    slug: "salesforce",   actions: ["create_deal", "update_contact"] },
  { id: "microsoft",  name: "Microsoft",     slug: "microsoft",    actions: ["send_email", "create_event", "upload_file"] },
  { id: "notion",     name: "Notion",        slug: "notion",       actions: ["create_page", "update_database"] },
  { id: "jira",       name: "Jira",          slug: "jira",         actions: ["create_issue", "update_issue", "transition"] },
  { id: "discord",    name: "Discord",       slug: "discord",      actions: ["send_message", "create_channel"] },
  { id: "dropbox",    name: "Dropbox",       slug: "dropbox",      actions: ["upload_file", "share_folder"] },
  { id: "box",        name: "Box",           slug: "box",          actions: ["upload_file", "share_folder"] },
  { id: "figma",      name: "Figma",         slug: "figma",        actions: ["export_assets", "get_comments"] },
  { id: "shopify",    name: "Shopify",       slug: "shopify",      actions: ["create_order", "update_product"] },
  { id: "hubspot",    name: "HubSpot",       slug: "hubspot",      actions: ["create_contact", "create_deal"] },
  { id: "linear",     name: "Linear",        slug: "linear",       actions: ["create_issue", "update_status"] },
  { id: "bitbucket",  name: "Bitbucket",     slug: "bitbucket",    actions: ["create_pr", "merge_pr"] },
  { id: "asana",      name: "Asana",         slug: "asana",        actions: ["create_task", "complete_task"] },
  { id: "freshbooks", name: "FreshBooks",    slug: "freshbooks",   actions: ["create_invoice", "send_invoice"] },
  { id: "paypal",     name: "PayPal",        slug: "paypal",       actions: ["send_payment", "create_invoice"] },
  { id: "spotify",    name: "Spotify",       slug: "spotify",      actions: ["create_playlist", "add_track"] },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
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
  const [workspaceApiKey, setWorkspaceApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [existingWorkspace, setExistingWorkspace] = useState<any>(null);
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    api.getWorkspace().then((ws) => {
      setExistingWorkspace(ws);
      if (ws.auth0_tenant) setTenant(ws.auth0_tenant);
    }).catch(() => {});
  }, []);

  const toggleService = (id: string) => {
    setSelectedServices((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handleStep1 = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.setupWorkspace({
        name: "My Workspace",
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
      if (res.api_key) {
        setWorkspaceApiKey(res.api_key);
      }
      setCurrentStep(2);
    } catch (err: any) {
      setError(err.message || "Failed to connect to Auth0. Check your credentials.");
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
          api.createConnection({
            name: svc.name,
            service: svc.id,
            slug: svc.slug,
            actions: svc.actions,
          })
        )
      );
      router.push("/connections");
    } catch (err: any) {
      setError(err.message || "Failed to create connections.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (workspaceApiKey) {
      navigator.clipboard.writeText(workspaceApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-zinc-900">Settings</h1>
        <p className="text-zinc-500 mt-2">
          Configure your Auth0 credentials and service connections
        </p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center justify-center gap-4 mb-10">
        {steps.map((step) => (
          <div key={step.number} className="flex items-center gap-2">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${
                currentStep > step.number
                  ? "bg-green-500 text-white"
                  : currentStep === step.number
                  ? "bg-zinc-900 text-white"
                  : "bg-zinc-200 text-zinc-500"
              }`}
            >
              {currentStep > step.number ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : (
                step.number
              )}
            </div>
            <span
              className={`text-sm font-medium ${
                currentStep >= step.number ? "text-zinc-900" : "text-zinc-400"
              }`}
            >
              {step.title}
            </span>
            {step.number < 3 && <ArrowRight className="h-4 w-4 text-zinc-300 mx-2" />}
          </div>
        ))}
      </div>

      {/* Step 1: Connect Auth0 */}
      {currentStep === 1 && existingWorkspace && !editMode ? (
        <Card>
          <CardHeader>
            <CardTitle>Workspace Already Configured</CardTitle>
            <CardDescription>
              Your organization <strong>{existingWorkspace.name}</strong> is set up with Auth0 tenant <code className="text-xs bg-zinc-100 px-1.5 py-0.5 rounded">{existingWorkspace.auth0_tenant}</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              {existingWorkspace.has_auth0_credentials && (
                <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> Auth0 Connected</Badge>
              )}
              {existingWorkspace.has_fga_credentials && (
                <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" /> FGA Configured</Badge>
              )}
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setEditMode(true)}>
                Edit Credentials
              </Button>
              <Button onClick={() => setCurrentStep(2)}>
                Continue to Connections <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : currentStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>{editMode ? "Update Credentials" : "Connect Auth0"}</CardTitle>
            <CardDescription>
              {editMode
                ? "Update your Auth0 and FGA credentials. Only changed fields will be updated."
                : "Enter your Auth0 tenant credentials. The platform will validate the connection and create your workspace."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-zinc-700">Auth0 Domain</label>
              <Input placeholder="your-tenant.us.auth0.com" value={tenant} onChange={(e) => setTenant(e.target.value)} className="mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-zinc-700">M2M Client ID</label>
                <Input placeholder="Machine to Machine app" value={m2mClientId} onChange={(e) => setM2mClientId(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">M2M Client Secret</label>
                <Input type="password" placeholder="Client secret" value={m2mClientSecret} onChange={(e) => setM2mClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Web App Client ID</label>
                <Input placeholder="Regular Web Application" value={webClientId} onChange={(e) => setWebClientId(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Web App Client Secret</label>
                <Input type="password" placeholder="Client secret" value={webClientSecret} onChange={(e) => setWebClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
              </div>
            </div>
            <div className="border-t border-zinc-200 pt-4">
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">FGA (Optional)</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Store ID</label>
                  <Input placeholder="01KMG6..." value={fgaStoreId} onChange={(e) => setFgaStoreId(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">Client ID</label>
                  <Input placeholder="FGA client" value={fgaClientId} onChange={(e) => setFgaClientId(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">Client Secret</label>
                  <Input type="password" value={fgaClientSecret} onChange={(e) => setFgaClientSecret(e.target.value)} className="mt-1 font-mono text-xs" />
                </div>
              </div>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                All credentials are stored securely in the database — no .env files needed. Token Vault and CIBA must be enabled on your Auth0 tenant.
              </p>
            </div>
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg text-red-700 text-sm">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}
            <div className="flex justify-end">
              <Button onClick={handleStep1} disabled={!tenant || loading}>
                {loading ? "Connecting..." : "Connect"} <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Define Connections */}
      {currentStep === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Define Connections</CardTitle>
            <CardDescription>
              Select which services your agents will interact with.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {workspaceApiKey && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm font-medium text-green-800 mb-2">
                  Workspace created. Save your API key — shown only once.
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-xs bg-white border border-green-200 rounded px-3 py-2 font-mono truncate">
                    {workspaceApiKey}
                  </code>
                  <button
                    onClick={handleCopy}
                    className="p-2 rounded hover:bg-green-100 transition-colors text-green-700"
                    title="Copy API key"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              {services.map((svc) => (
                <button
                  key={svc.id}
                  onClick={() => toggleService(svc.id)}
                  className={`p-4 rounded-lg border text-left transition-colors ${
                    selectedServices.includes(svc.id)
                      ? "border-zinc-900 bg-zinc-50"
                      : "border-zinc-200 hover:border-zinc-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-zinc-900">{svc.name}</span>
                    {selectedServices.includes(svc.id) && (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    )}
                  </div>
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {svc.actions.map((a) => (
                      <Badge key={a} variant="default">
                        {a}
                      </Badge>
                    ))}
                  </div>
                </button>
              ))}
            </div>
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg text-red-700 text-sm">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(1)}>
                Back
              </Button>
              <Button onClick={handleStep2} disabled={selectedServices.length === 0 || loading}>
                {loading ? "Creating connections..." : "Continue"} <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Create First Rule */}
      {currentStep === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Write Your First Rule</CardTitle>
            <CardDescription>
              The Rule Builder is ready. Create an approval rule with live preview.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="p-6 bg-zinc-50 rounded-lg text-center">
              <GitBranch className="h-12 w-12 text-zinc-400 mx-auto mb-4" />
              <p className="text-zinc-600 mb-4">
                Your workspace is configured with {selectedServices.length} service
                {selectedServices.length > 1 ? "s" : ""}. Now create your first approval rule.
              </p>
              <Button size="lg" onClick={() => router.push("/rules/new")}>
                Open Rule Builder <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setCurrentStep(2)}>
                Back
              </Button>
              <Button variant="ghost" onClick={() => router.push("/dashboard")}>
                Skip to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
