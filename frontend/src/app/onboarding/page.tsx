"use client";

import { useState } from "react";
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
  { id: "stripe",     name: "Stripe",     slug: "stripe-prod", actions: ["charge", "refund", "payout"] },
  { id: "github",     name: "GitHub",     slug: "github-main", actions: ["deploy", "rollback", "merge_pr"] },
  { id: "gmail",      name: "Gmail",      slug: "gmail",       actions: ["send_email", "delete_email"] },
  { id: "slack",      name: "Slack",      slug: "slack",       actions: ["send_message", "create_channel"] },
  { id: "salesforce", name: "Salesforce", slug: "salesforce",  actions: ["create_deal", "update_contact"] },
  { id: "aws",        name: "AWS",        slug: "aws",         actions: ["launch_instance", "terminate_instance"] },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [tenant, setTenant] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspaceApiKey, setWorkspaceApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const toggleService = (id: string) => {
    setSelectedServices((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handleStep1 = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.setupWorkspace({ name: "My Workspace", auth0_tenant: tenant });
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
      setCurrentStep(3);
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
        <h1 className="text-3xl font-bold text-zinc-900">Welcome to ApprovalKit</h1>
        <p className="text-zinc-500 mt-2">
          Set up human approval middleware for your AI agents in 3 steps
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
      {currentStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Connect Auth0</CardTitle>
            <CardDescription>
              Enter your Auth0 tenant credentials. The platform will validate the connection
              and create your workspace.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-zinc-700">Auth0 Domain</label>
              <Input
                placeholder="your-tenant.auth0.com"
                value={tenant}
                onChange={(e) => setTenant(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700">Client ID</label>
              <Input
                placeholder="your-client-id"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700">Client Secret</label>
              <Input
                type="password"
                placeholder="your-client-secret"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                className="mt-1"
              />
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                Token Vault must be enabled on your tenant. CIBA and Guardian push must be configured.
                FGA store should be created with the ApprovalKit authorization model.
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
