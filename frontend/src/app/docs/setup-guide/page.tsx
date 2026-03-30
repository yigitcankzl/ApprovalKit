"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Copy,
  Check,
  Shield,
  Key,
  Smartphone,
  Lock,
  Server,
  Database,
  Globe,
  Terminal,
  Settings,
  Layers,
  Link,
  Rocket,
  AlertTriangle,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  FileCode,
  Box,
  Cloud,
  Users,
  Workflow,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Reusable Components                                                */
/* ------------------------------------------------------------------ */

function CodeBlock({ code, language = "bash" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative rounded-lg bg-zinc-950 text-zinc-100 text-sm font-mono overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800">
        <span className="text-xs text-zinc-500">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-4 overflow-x-auto leading-relaxed whitespace-pre">{code}</pre>
    </div>
  );
}

function Section({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-6">
      {children}
    </section>
  );
}

function StepNumber({ n }: { n: number }) {
  return (
    <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-blue-600 text-white text-xs font-bold shrink-0">
      {n}
    </span>
  );
}

function Callout({ type, children }: { type: "info" | "warning" | "tip"; children: React.ReactNode }) {
  const styles = {
    info: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300",
    warning: "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300",
    tip: "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300",
  };
  const icons = {
    info: <Shield className="h-4 w-4 shrink-0 mt-0.5" />,
    warning: <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />,
    tip: <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />,
  };
  return (
    <div className={`flex items-start gap-3 p-4 rounded-lg border text-sm ${styles[type]}`}>
      {icons[type]}
      <div>{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Navigation                                                         */
/* ------------------------------------------------------------------ */

const NAV = [
  { id: "introduction", label: "Introduction" },
  { id: "prerequisites", label: "Prerequisites" },
  { id: "auth0-setup", label: "Auth0 Setup" },
  { id: "auth0-tenant", label: "  Create Tenant" },
  { id: "auth0-api", label: "  Create API" },
  { id: "auth0-web-app", label: "  Web Application" },
  { id: "auth0-m2m-app", label: "  M2M Application" },
  { id: "auth0-guardian", label: "  Guardian / MFA" },
  { id: "auth0-ciba", label: "  CIBA Setup" },
  { id: "auth0-token-vault", label: "  Token Vault" },
  { id: "auth0-fga", label: "  FGA Setup" },
  { id: "auth0-callbacks", label: "  Callbacks & Origins" },
  { id: "local-dev", label: "Local Development" },
  { id: "local-clone", label: "  Clone & Configure" },
  { id: "local-docker", label: "  Docker Services" },
  { id: "local-migrations", label: "  Migrations" },
  { id: "local-start", label: "  Start Dev Server" },
  { id: "sdk-integration", label: "SDK Integration" },
  { id: "sdk-install", label: "  Install SDK" },
  { id: "sdk-init", label: "  Initialize Client" },
  { id: "sdk-decorators", label: "  Decorators" },
  { id: "sdk-handling", label: "  Handle Responses" },
  { id: "sdk-async", label: "  Async Support" },
  { id: "creating-rules", label: "Creating Rules" },
  { id: "rules-dashboard", label: "  Via Dashboard" },
  { id: "rules-api", label: "  Via API" },
  { id: "rules-conditions", label: "  Conditions" },
  { id: "rules-models", label: "  Approval Models" },
  { id: "connecting-services", label: "Connecting Services" },
  { id: "services-oauth", label: "  OAuth Providers" },
  { id: "services-m2m", label: "  M2M / API Keys" },
  { id: "services-webhooks", label: "  Webhooks" },
];

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function SetupGuidePage() {
  const [activeSection, setActiveSection] = useState("introduction");

  useEffect(() => {
    const observers: IntersectionObserver[] = [];

    NAV.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveSection(id);
        },
        { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
      );
      obs.observe(el);
      observers.push(obs);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <div className="flex gap-8 max-w-6xl mx-auto">
      {/* ---- Sticky sidebar ---- */}
      <aside className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-6 space-y-0.5 max-h-[calc(100vh-3rem)] overflow-y-auto pb-12">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3 px-2">
            Setup Guide
          </p>
          {NAV.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={`block px-2 py-1.5 rounded text-sm transition-all duration-150 ${
                item.label.startsWith("  ") ? "pl-5" : "font-medium"
              } ${
                activeSection === item.id
                  ? "bg-zinc-900 text-white"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              {item.label.trim()}
            </a>
          ))}
        </div>
      </aside>

      {/* ---- Main content ---- */}
      <div className="flex-1 space-y-14 pb-24">

        {/* ============================================================ */}
        {/*  INTRODUCTION                                                 */}
        {/* ============================================================ */}
        <Section id="introduction">
          <a
            href="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 shadow-sm transition-colors mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Dashboard
          </a>
          <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500 mb-2">
            Setup &amp; Integration Guide
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mb-6">
            A complete, step-by-step walkthrough for setting up ApprovalKit from scratch.
            By the end of this guide you will have a fully working approval platform
            with Auth0 authentication, Guardian push notifications, Token Vault credential
            isolation, FGA-based authorization, and the Python SDK integrated into your agent.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { icon: <Settings className="h-5 w-5" />, title: "~30 min setup", desc: "Auth0, Docker, and first rule" },
              { icon: <FileCode className="h-5 w-5" />, title: "2 lines of code", desc: "Add SDK to any Python agent" },
              { icon: <Cloud className="h-5 w-5" />, title: "Docker Compose", desc: "One-command local setup" },
            ].map((c) => (
              <Card key={c.title}>
                <CardContent className="pt-5">
                  <div className="text-zinc-500 dark:text-zinc-400 mb-2">{c.icon}</div>
                  <p className="font-semibold text-zinc-800 dark:text-zinc-200 text-sm">{c.title}</p>
                  <p className="text-zinc-500 dark:text-zinc-400 text-xs mt-1">{c.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* ============================================================ */}
        {/*  PREREQUISITES                                                */}
        {/* ============================================================ */}
        <Section id="prerequisites">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <Box className="h-5 w-5 text-blue-500" /> Prerequisites
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Make sure you have the following installed and accounts created before proceeding.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { name: "Node.js 18+", detail: "Required for the Next.js frontend dashboard.", cmd: "node --version" },
              { name: "Python 3.10+", detail: "Required for the FastAPI backend and SDK.", cmd: "python3 --version" },
              { name: "Docker & Docker Compose", detail: "Runs PostgreSQL, Redis, and the backend.", cmd: "docker compose version" },
              { name: "Auth0 Account", detail: "Free tier works. Sign up at auth0.com.", cmd: null },
              { name: "Git", detail: "To clone the repository.", cmd: "git --version" },
              { name: "pnpm or npm", detail: "Package manager for frontend dependencies.", cmd: "pnpm --version" },
            ].map((item) => (
              <div key={item.name} className="p-4 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg">
                <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{item.name}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{item.detail}</p>
                {item.cmd && (
                  <code className="mt-2 block text-xs font-mono text-zinc-400 bg-zinc-900 px-2 py-1 rounded">
                    $ {item.cmd}
                  </code>
                )}
              </div>
            ))}
          </div>

          <Callout type="info">
            <strong>Optional:</strong> If you plan to use the Auth0 Guardian mobile push notifications,
            install the Auth0 Guardian app on your iOS or Android device before starting the CIBA section.
          </Callout>
        </Section>

        {/* ============================================================ */}
        {/*  AUTH0 SETUP                                                  */}
        {/* ============================================================ */}
        <Section id="auth0-setup">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-500" /> Auth0 Setup
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 is the identity backbone of ApprovalKit. It handles user login for the dashboard,
            machine-to-machine authentication for the backend, CIBA push notifications via Guardian,
            Token Vault for credential isolation, and FGA for fine-grained authorization. This is the
            most important section of the guide -- take your time and complete each step carefully.
          </p>
        </Section>

        {/* --- Auth0: Create Tenant --- */}
        <Section id="auth0-tenant">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={1} /> Create an Auth0 Tenant
          </h3>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">manage.auth0.com</strong> and sign up or log in.</li>
            <li>Click your tenant name in the top-left corner, then <strong className="text-zinc-800 dark:text-zinc-200">Create tenant</strong>.</li>
            <li>Choose a tenant name (e.g. <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">approvalkit-dev</code>). This becomes your domain: <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">approvalkit-dev.us.auth0.com</code>.</li>
            <li>Select <strong className="text-zinc-800 dark:text-zinc-200">Development</strong> as the environment tag (you can create a Production tenant later).</li>
            <li>Choose the region closest to your users (US, EU, or AU).</li>
          </ol>
          <Callout type="tip">
            Note your <strong>Auth0 Domain</strong> -- you will use it in almost every configuration step below.
            It follows the pattern <code>your-tenant.us.auth0.com</code>.
          </Callout>
        </Section>

        {/* --- Auth0: Create API --- */}
        <Section id="auth0-api">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={2} /> Create an API (Resource Server)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            The API resource represents the ApprovalKit backend. Access tokens will be scoped to this audience.
          </p>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>In the Auth0 Dashboard, go to <strong className="text-zinc-800 dark:text-zinc-200">Applications &gt; APIs</strong>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">+ Create API</strong>.</li>
            <li>Fill in:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><strong>Name:</strong> <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">ApprovalKit API</code></li>
                <li><strong>Identifier (Audience):</strong> <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">https://api.approvalkit.dev</code></li>
                <li><strong>Signing Algorithm:</strong> RS256</li>
              </ul>
            </li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Create</strong>.</li>
            <li>Go to the <strong className="text-zinc-800 dark:text-zinc-200">Permissions</strong> tab and add the following scopes:</li>
          </ol>
          <CodeBlock language="text" code={`read:rules          View approval rules
write:rules         Create and update rules
delete:rules        Delete rules
read:jobs           View approval jobs
write:jobs          Submit and manage jobs
read:approvers      View approvers
write:approvers     Manage approvers
read:connections    View connected services
write:connections   Manage service connections
read:agents         View registered agents
write:agents        Register and manage agents
read:audit          View audit logs
admin:all           Full administrative access`} />
          <Callout type="info">
            Save the <strong>API Identifier</strong> (audience) value. You will need it for the
            <code className="mx-1">AUTH0_AUDIENCE</code> environment variable.
          </Callout>
        </Section>

        {/* --- Auth0: Web Application --- */}
        <Section id="auth0-web-app">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={3} /> Create a Web Application (Dashboard)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            This application handles login/logout for the Next.js dashboard where approvers and admins manage rules.
          </p>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Applications &gt; Applications</strong>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">+ Create Application</strong>.</li>
            <li>Name it <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">ApprovalKit Dashboard</code> and select <strong className="text-zinc-800 dark:text-zinc-200">Regular Web Applications</strong>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Create</strong>.</li>
            <li>In the <strong className="text-zinc-800 dark:text-zinc-200">Settings</strong> tab, note down:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><strong>Domain</strong> -- your Auth0 domain</li>
                <li><strong>Client ID</strong> -- for <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">AUTH0_CLIENT_ID</code></li>
                <li><strong>Client Secret</strong> -- for <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">AUTH0_CLIENT_SECRET</code></li>
              </ul>
            </li>
            <li>Scroll to <strong className="text-zinc-800 dark:text-zinc-200">Application URIs</strong> and configure (see Callbacks section below).</li>
            <li>Under <strong className="text-zinc-800 dark:text-zinc-200">Advanced Settings &gt; Grant Types</strong>, ensure <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">Authorization Code</code> and <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">Refresh Token</code> are enabled.</li>
          </ol>
          <CodeBlock language="env" code={`# .env values from this step
AUTH0_DOMAIN=approvalkit-dev.us.auth0.com
AUTH0_CLIENT_ID=aBcDeFgHiJkLmNoPqRsT
AUTH0_CLIENT_SECRET=your-client-secret-here
AUTH0_AUDIENCE=https://api.approvalkit.dev
AUTH0_BASE_URL=http://localhost:3000
AUTH0_SECRET=<run: openssl rand -hex 32>`} />
        </Section>

        {/* --- Auth0: M2M Application --- */}
        <Section id="auth0-m2m-app">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={4} /> Create an M2M Application (Backend)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            The Machine-to-Machine application is used by the FastAPI backend to call Auth0 Management API,
            initiate CIBA requests, and perform token exchanges with Token Vault.
          </p>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Applications &gt; Applications</strong>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">+ Create Application</strong>.</li>
            <li>Name it <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">ApprovalKit Backend</code> and select <strong className="text-zinc-800 dark:text-zinc-200">Machine to Machine Applications</strong>.</li>
            <li>When prompted, authorize it against your <strong>ApprovalKit API</strong> and select all scopes.</li>
            <li>Also authorize it against the <strong>Auth0 Management API</strong> with these scopes:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">read:users</code></li>
                <li><code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">read:user_idp_tokens</code></li>
                <li><code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">create:client_grants</code></li>
              </ul>
            </li>
            <li>Note down the <strong>Client ID</strong> and <strong>Client Secret</strong>.</li>
          </ol>
          <CodeBlock language="env" code={`# .env values for backend M2M
AUTH0_M2M_CLIENT_ID=xYzAbCdEfGhIjKlMnOpQ
AUTH0_M2M_CLIENT_SECRET=your-m2m-secret-here`} />
          <Callout type="warning">
            <strong>Keep the M2M Client Secret secure.</strong> It has elevated permissions including the ability
            to initiate CIBA flows and exchange tokens. Never expose it in frontend code or commit it to version control.
          </Callout>
        </Section>

        {/* --- Auth0: Guardian --- */}
        <Section id="auth0-guardian">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={5} /> Enable Auth0 Guardian (Push Notifications)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Guardian is Auth0's MFA solution. ApprovalKit uses it to send push approval notifications
            to approvers' phones via CIBA (Client-Initiated Backchannel Authentication).
          </p>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>In the Auth0 Dashboard, go to <strong className="text-zinc-800 dark:text-zinc-200">Security &gt; Multi-factor Auth</strong>.</li>
            <li>Under <strong className="text-zinc-800 dark:text-zinc-200">Push Notifications using Auth0 Guardian</strong>, toggle it <strong>ON</strong>.</li>
            <li>Select <strong className="text-zinc-800 dark:text-zinc-200">Auth0 Guardian</strong> as the push provider (not custom).</li>
            <li>Under <strong className="text-zinc-800 dark:text-zinc-200">Policy</strong>, choose:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><strong>Require Multi-factor Auth:</strong> set to <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">Always</code> for production, or <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">Never</code> for dev (CIBA still works).</li>
              </ul>
            </li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Save</strong>.</li>
            <li>Have each approver enroll:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li>They log into the dashboard for the first time.</li>
                <li>Auth0 prompts them to scan a QR code with the Guardian app.</li>
                <li>Once enrolled, they will receive push notifications for CIBA requests.</li>
              </ul>
            </li>
          </ol>
          <Callout type="tip">
            For development, you can test Guardian enrollment by navigating to
            <code className="mx-1">https://YOUR_DOMAIN/mfa/enroll</code> after logging in.
            Each approver only needs to enroll once.
          </Callout>
        </Section>

        {/* --- Auth0: CIBA --- */}
        <Section id="auth0-ciba">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={6} /> Configure CIBA (Client-Initiated Backchannel Authentication)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            CIBA allows the backend to trigger a push notification to a specific user without that
            user being present in a browser. This is how approvers receive "Approve/Deny" prompts
            on their phone.
          </p>

          <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-6 mb-2">
            6a. Enable CIBA on the M2M Application
          </h4>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Applications &gt; Applications</strong> and select the <strong>ApprovalKit Backend</strong> (M2M) app.</li>
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Settings &gt; Advanced Settings &gt; Grant Types</strong>.</li>
            <li>Enable <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">Client Initiated Backchannel Authentication (CIBA)</code>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Save Changes</strong>.</li>
          </ol>

          <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-6 mb-2">
            6b. Configure CIBA Settings
          </h4>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Security &gt; Multi-factor Auth &gt; CIBA</strong> (or <strong>Authentication &gt; Authentication Profile</strong> depending on your dashboard version).</li>
            <li>Set the <strong>Token Delivery Mode</strong> to <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">poll</code>.</li>
            <li>Set the <strong>Default Poll Interval</strong> to <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">5</code> seconds.</li>
            <li>Set the <strong>Default Expiry</strong> to <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">300</code> seconds (5 minutes).</li>
          </ol>
          <CodeBlock language="python" code={`# How ApprovalKit initiates a CIBA request (internal)
import httpx

resp = httpx.post(
    f"https://{AUTH0_DOMAIN}/bc-authorize",
    data={
        "client_id": AUTH0_M2M_CLIENT_ID,
        "client_secret": AUTH0_M2M_CLIENT_SECRET,
        "login_hint": '{"format":"iss_sub","iss":"https://YOUR_DOMAIN/","sub":"auth0|USER_ID"}',
        "scope": "openid",
        "audience": AUTH0_AUDIENCE,
        "binding_message": "Approve $500 charge to Acme Corp",  # max 64 chars
    },
)

auth_req_id = resp.json()["auth_req_id"]
# Backend then polls /oauth/token with this auth_req_id`} />

          <div className="mt-4">
            <CodeBlock language="python" code={`# Polling for the CIBA result
resp = httpx.post(
    f"https://{AUTH0_DOMAIN}/oauth/token",
    data={
        "grant_type": "urn:openid:params:grant-type:ciba",
        "client_id": AUTH0_M2M_CLIENT_ID,
        "client_secret": AUTH0_M2M_CLIENT_SECRET,
        "auth_req_id": auth_req_id,
    },
)

if resp.status_code == 200:
    # Approved! access_token is in resp.json()
    pass
elif resp.json().get("error") == "authorization_pending":
    # Keep polling
    pass
elif resp.json().get("error") == "slow_down":
    # Increase poll interval
    pass
elif resp.json().get("error") == "access_denied":
    # User rejected the request
    pass
elif resp.json().get("error") == "expired_token":
    # Request timed out
    pass`} />
          </div>

          <Callout type="warning">
            The <code>binding_message</code> field is limited to <strong>64 characters</strong>.
            ApprovalKit auto-truncates long messages, but keep your action descriptions concise.
            The full details are visible in the dashboard.
          </Callout>
        </Section>

        {/* --- Auth0: Token Vault / Connected Accounts --- */}
        <Section id="auth0-token-vault">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={7} /> Set Up Token Vault / Connected Accounts
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Token Vault stores OAuth credentials for external services (Stripe, GitHub, Google, Slack, etc.)
            so that your AI agent never has direct access to secrets. After an approval, the platform
            performs an RFC 8693 token exchange to get a fresh access token and execute the action.
          </p>

          <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-6 mb-2">
            7a. Add Social / Enterprise Connections
          </h4>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>In the Auth0 Dashboard, go to <strong className="text-zinc-800 dark:text-zinc-200">Authentication &gt; Social</strong>.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">+ Create Connection</strong>.</li>
            <li>For each service you want to connect, follow the provider-specific steps below.</li>
          </ol>

          <div className="space-y-4 mb-6">
            {[
              {
                name: "Google",
                scopes: "openid email profile https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar",
                steps: [
                  "Go to console.cloud.google.com > APIs & Services > Credentials.",
                  "Create an OAuth 2.0 Client ID (Web Application type).",
                  "Set authorized redirect URI to: https://YOUR_DOMAIN/login/callback",
                  "Copy Client ID and Client Secret into Auth0.",
                ],
              },
              {
                name: "GitHub",
                scopes: "repo read:org admin:repo_hook workflow",
                steps: [
                  "Go to github.com > Settings > Developer settings > OAuth Apps.",
                  "Create a new OAuth App.",
                  "Set callback URL to: https://YOUR_DOMAIN/login/callback",
                  "Copy Client ID and Client Secret into Auth0.",
                ],
              },
              {
                name: "Slack",
                scopes: "chat:write channels:read users:read files:write",
                steps: [
                  "Go to api.slack.com/apps and create a new app.",
                  "Under OAuth & Permissions, add the scopes listed above.",
                  "Set redirect URL to: https://YOUR_DOMAIN/login/callback",
                  "Copy Client ID and Client Secret into Auth0.",
                ],
              },
              {
                name: "Stripe",
                scopes: "read_write (Stripe Connect OAuth)",
                steps: [
                  "Go to dashboard.stripe.com > Settings > Connect settings.",
                  "Enable OAuth for your platform.",
                  "Set redirect URI to: https://YOUR_DOMAIN/login/callback",
                  "Copy Client ID (from Connect) and Secret Key into Auth0 as a custom social connection.",
                ],
              },
            ].map((provider) => (
              <div key={provider.name} className="p-4 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg">
                <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mb-1">{provider.name}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2 font-mono">
                  Scopes: {provider.scopes}
                </p>
                <ol className="list-decimal list-inside text-xs text-zinc-600 dark:text-zinc-400 space-y-1">
                  {provider.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </div>
            ))}
          </div>

          <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-6 mb-2">
            7b. Enable Token Vault for Each Connection
          </h4>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>For each connection you just created, click into its settings.</li>
            <li>Scroll down to the <strong className="text-zinc-800 dark:text-zinc-200">Token Vault</strong> section.</li>
            <li>Toggle <strong className="text-zinc-800 dark:text-zinc-200">Enable Token Vault</strong> to ON.</li>
            <li>This tells Auth0 to store the upstream provider's refresh token so it can be exchanged later.</li>
          </ol>

          <h4 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-6 mb-2">
            7c. Set Up Connected Accounts Flow
          </h4>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Authentication &gt; Social</strong>, then click <strong className="text-zinc-800 dark:text-zinc-200">Connected Accounts</strong> at the top.</li>
            <li>Set the <strong>Flow URL</strong> to your dashboard's connect endpoint:
              <code className="block mt-1 text-xs bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
                https://your-dashboard.vercel.app/api/auth/connect
              </code>
            </li>
            <li>For local dev, use: <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">http://localhost:3000/api/auth/connect</code></li>
          </ol>

          <CodeBlock language="python" code={`# How Token Exchange works after approval (internal)
resp = httpx.post(
    f"https://{AUTH0_DOMAIN}/oauth/token",
    data={
        "grant_type": "urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token",
        "client_id": AUTH0_M2M_CLIENT_ID,
        "client_secret": AUTH0_M2M_CLIENT_SECRET,
        "subject_token": user_refresh_token,   # stored by Auth0
        "subject_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
        "connection": "google-oauth2",          # or github, slack, stripe
    },
)

upstream_access_token = resp.json()["access_token"]
# Platform uses this token to execute the action on behalf of the user
# Token is NEVER sent to the agent`} />
        </Section>

        {/* --- Auth0: FGA --- */}
        <Section id="auth0-fga">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={8} /> Set Up FGA (Fine-Grained Authorization)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Auth0 FGA (based on OpenFGA) provides relationship-based access control. ApprovalKit uses it
            to control who can view/manage which rules, connections, and agents.
          </p>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">dashboard.fga.dev</strong> and log in with your Auth0 account.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Create Store</strong> and name it <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">approvalkit</code>.</li>
            <li>Go to the <strong className="text-zinc-800 dark:text-zinc-200">Model</strong> tab and create an authorization model.</li>
            <li>Paste the following model definition:</li>
          </ol>
          <CodeBlock language="dsl" code={`model
  schema 1.1

type user

type organization
  relations
    define admin: [user]
    define member: [user] or admin

type rule
  relations
    define org: [organization]
    define can_view: member from org
    define can_edit: admin from org
    define can_delete: admin from org

type connection
  relations
    define org: [organization]
    define can_view: member from org
    define can_manage: admin from org

type agent
  relations
    define org: [organization]
    define can_view: member from org
    define can_manage: admin from org

type job
  relations
    define org: [organization]
    define can_view: member from org
    define can_approve: [user]
    define can_reject: can_approve`} />

          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4 mt-4" start={5}>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Save</strong> to create the model.</li>
            <li>Go to <strong className="text-zinc-800 dark:text-zinc-200">Settings</strong> and note down:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><strong>Store ID</strong></li>
                <li><strong>Model ID</strong> (from the model you just created)</li>
              </ul>
            </li>
            <li>Create an API key for the backend:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li>Go to <strong>Settings &gt; API Keys</strong></li>
                <li>Create a new key with read/write permissions</li>
                <li>Note down the <strong>Client ID</strong> and <strong>Client Secret</strong></li>
              </ul>
            </li>
          </ol>
          <CodeBlock language="env" code={`# .env values for FGA
FGA_STORE_ID=01HXYZ...
FGA_MODEL_ID=01HABC...
FGA_CLIENT_ID=your-fga-client-id
FGA_CLIENT_SECRET=your-fga-client-secret
FGA_API_URL=https://api.us1.fga.dev   # or eu1, au1`} />
        </Section>

        {/* --- Auth0: Callbacks --- */}
        <Section id="auth0-callbacks">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={9} /> Configure Callback URLs and Allowed Origins
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Go back to your <strong>ApprovalKit Dashboard</strong> web application settings and configure these URLs.
          </p>
          <CodeBlock language="text" code={`# For local development
Allowed Callback URLs:
  http://localhost:3000/api/auth/callback

Allowed Logout URLs:
  http://localhost:3000

Allowed Web Origins:
  http://localhost:3000

# For production (add these alongside the local ones)
Allowed Callback URLs:
  http://localhost:3000/api/auth/callback,
  https://your-app.vercel.app/api/auth/callback

Allowed Logout URLs:
  http://localhost:3000,
  https://your-app.vercel.app

Allowed Web Origins:
  http://localhost:3000,
  https://your-app.vercel.app`} />
          <Callout type="warning">
            URLs must match <strong>exactly</strong> -- including protocol, port, and trailing slashes.
            A common mistake is using <code>https</code> for localhost or forgetting the port number.
          </Callout>
        </Section>

        {/* ============================================================ */}
        {/*  LOCAL DEVELOPMENT                                            */}
        {/* ============================================================ */}
        <Section id="local-dev">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <Terminal className="h-5 w-5 text-blue-500" /> Local Development Setup
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            With Auth0 fully configured, you can now set up the local development environment.
          </p>
        </Section>

        {/* --- Clone & Configure --- */}
        <Section id="local-clone">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={1} /> Clone the Repository and Configure Environment
          </h3>
          <CodeBlock language="bash" code={`# Clone the repository
git clone https://github.com/your-org/ApprovalKit.git
cd ApprovalKit

# Copy environment template
cp .env.example .env`} />

          <p className="text-zinc-600 dark:text-zinc-400 mt-4 mb-2 text-sm">
            Now open <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">.env</code> and fill in all the Auth0 values you collected above:
          </p>
          <CodeBlock language="env" code={`# === Auth0 Core ===
AUTH0_DOMAIN=approvalkit-dev.us.auth0.com
AUTH0_AUDIENCE=https://api.approvalkit.dev
AUTH0_SECRET=$(openssl rand -hex 32)

# === Auth0 Web App (Dashboard) ===
AUTH0_CLIENT_ID=<from step 3>
AUTH0_CLIENT_SECRET=<from step 3>
AUTH0_BASE_URL=http://localhost:3000

# === Auth0 M2M App (Backend) ===
AUTH0_M2M_CLIENT_ID=<from step 4>
AUTH0_M2M_CLIENT_SECRET=<from step 4>

# === Auth0 FGA ===
FGA_STORE_ID=<from step 8>
FGA_MODEL_ID=<from step 8>
FGA_CLIENT_ID=<from step 8>
FGA_CLIENT_SECRET=<from step 8>
FGA_API_URL=https://api.us1.fga.dev

# === Database ===
DATABASE_URL=postgresql://approvalkit:approvalkit@localhost:5432/approvalkit

# === Redis ===
REDIS_URL=redis://localhost:6379/0

# === Security ===
HMAC_SECRET=$(openssl rand -hex 32)
CREDENTIALS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# === Optional ===
LOG_LEVEL=debug
CORS_ORIGINS=http://localhost:3000`} />
        </Section>

        {/* --- Docker Services --- */}
        <Section id="local-docker">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={2} /> Docker Compose Services
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            The <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">docker-compose.yml</code> includes the following services:
          </p>
          <div className="space-y-2 mb-4">
            {[
              { name: "postgres", port: "5432", desc: "PostgreSQL 15 -- stores rules, jobs, approvers, audit log" },
              { name: "redis", port: "6379", desc: "Redis 7 -- job queue, circuit breaker state, rate limiting" },
              { name: "backend", port: "8000", desc: "FastAPI application -- API server and CIBA worker" },
              { name: "worker", port: "-", desc: "Background worker -- processes CIBA polling and token exchanges" },
            ].map((svc) => (
              <div key={svc.name} className="flex items-start gap-3 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                <code className="text-xs font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded shrink-0">
                  {svc.name}
                </code>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  <span className="text-zinc-400 font-mono text-xs mr-2">:{svc.port}</span>
                  {svc.desc}
                </div>
              </div>
            ))}
          </div>
          <CodeBlock language="bash" code={`# Start all services in the background
docker compose up -d

# Check that everything is running
docker compose ps

# View logs if something goes wrong
docker compose logs -f backend`} />
        </Section>

        {/* --- Migrations --- */}
        <Section id="local-migrations">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={3} /> Run Database Migrations
          </h3>
          <CodeBlock language="bash" code={`# Run Alembic migrations inside the backend container
docker compose exec backend alembic upgrade head

# Or if running the backend locally
cd backend
pip install -r requirements.txt
alembic upgrade head`} />
          <p className="text-zinc-600 dark:text-zinc-400 mt-4 text-sm">
            This creates all required tables: <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">rules</code>,
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">jobs</code>,
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">approvers</code>,
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">connections</code>,
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">agents</code>,
            <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded ml-1">audit_log</code>,
            and supporting tables.
          </p>
        </Section>

        {/* --- Start Dev --- */}
        <Section id="local-start">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={4} /> Start the Development Environment
          </h3>
          <CodeBlock language="bash" code={`# Terminal 1: Start the frontend
cd frontend
pnpm install
pnpm dev
# Dashboard available at http://localhost:3000

# Terminal 2: Backend (if not using Docker)
cd backend
uvicorn main:app --reload --port 8000
# API available at http://localhost:8000

# Terminal 3: Worker (if not using Docker)
cd backend
python worker.py`} />
          <div className="mt-4 space-y-3">
            <p className="text-zinc-600 dark:text-zinc-400 text-sm">
              After starting the dev server:
            </p>
            <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2">
              <li>Open <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">http://localhost:3000</code> in your browser.</li>
              <li>Log in with your Auth0 credentials (first user becomes the admin).</li>
              <li>The <strong>Setup Wizard</strong> will launch automatically for first-time setup.</li>
              <li>The wizard generates your <strong>API key</strong> (<code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">ak_...</code>) and <strong>HMAC secret</strong>.</li>
              <li>Save these -- you will need them for the SDK.</li>
            </ol>
          </div>
          <Callout type="tip">
            The setup wizard also validates your Auth0 connection. If anything is misconfigured,
            it will show you exactly what needs to be fixed.
          </Callout>
        </Section>

        {/* ============================================================ */}
        {/*  SDK INTEGRATION                                              */}
        {/* ============================================================ */}
        <Section id="sdk-integration">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <FileCode className="h-5 w-5 text-blue-500" /> SDK Integration
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            The Python SDK is the primary way to integrate ApprovalKit into your AI agent.
            It handles request signing, polling, error handling, and retry logic.
          </p>
        </Section>

        {/* --- Install SDK --- */}
        <Section id="sdk-install">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={1} /> Install the SDK
          </h3>
          <CodeBlock language="bash" code={`# Install from the local SDK directory
pip install ./sdk

# Or install from PyPI (when published)
pip install approvalkit

# The SDK has minimal dependencies: requests, hmac (stdlib)
# For async support: pip install approvalkit[async]  (adds httpx)`} />
        </Section>

        {/* --- Initialize Client --- */}
        <Section id="sdk-init">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={2} /> Initialize the ApprovalKit Client
          </h3>
          <CodeBlock language="python" code={`from approvalkit import ApprovalKit

kit = ApprovalKit(
    base_url="http://localhost:8000",   # Backend URL
    api_key="ak_...",                   # From dashboard setup wizard
    hmac_secret="your-hmac-secret",     # From dashboard setup wizard
    user_id="my-agent-name",            # Identifier for this agent
    poll_interval=3,                    # Seconds between status checks (default: 3)
    timeout=300,                        # Max seconds to wait for approval (default: 300)
)

# Or load from environment variables
import os

kit = ApprovalKit(
    base_url=os.environ["APPROVALKIT_URL"],
    api_key=os.environ["APPROVALKIT_API_KEY"],
    hmac_secret=os.environ["APPROVALKIT_HMAC_SECRET"],
    user_id=os.environ.get("APPROVALKIT_AGENT_ID", "default-agent"),
)`} />
        </Section>

        {/* --- Decorators --- */}
        <Section id="sdk-decorators">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={3} /> Add Decorators to Agent Functions
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            The <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">@requires_approval</code> decorator
            is the simplest way to gate a function behind human approval. When the function is called,
            the SDK submits a request to ApprovalKit, waits for a human to approve or deny, and then
            either returns the result or raises an exception.
          </p>
          <CodeBlock language="python" code={`# Example 1: Gate a Stripe charge behind approval
@kit.requires_approval(connection="stripe-prod", action="charge")
def charge_customer(amount: int, customer: str, currency: str = "usd"):
    # This body NEVER runs -- Token Vault executes the action.
    # The function signature defines the parameters that approvers see.
    pass

# Call it like a normal function
result = charge_customer(amount=5000, customer="cus_abc123")
# result = {"status": "approved", "final_params": {...}, "job_id": "..."}


# Example 2: Gate a GitHub deployment
@kit.requires_approval(connection="github-main", action="deploy")
def deploy_to_production(ref: str, environment: str):
    pass

deploy_to_production(ref="main", environment="production")


# Example 3: Gate sending an email
@kit.requires_approval(connection="google-workspace", action="send_email")
def send_email(to: str, subject: str, body: str):
    pass

send_email(
    to="customer@example.com",
    subject="Invoice #1234",
    body="Please find your invoice attached."
)


# Example 4: Inline gate (no decorator)
result = kit.gate("slack-workspace", "send_message", {
    "channel": "#alerts",
    "text": "Production deployment complete",
})`} />
        </Section>

        {/* --- Handle Responses --- */}
        <Section id="sdk-handling">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={4} /> Handle Approvals and Rejections
          </h3>
          <CodeBlock language="python" code={`from approvalkit import ApprovalKit, ApprovalDenied, ApprovalTimeout, ApprovalBlocked

kit = ApprovalKit(...)

try:
    result = kit.gate("stripe-prod", "charge", {
        "amount_usd": 500,
        "customer": "cus_abc123",
    })

    # Success -- the action was approved and executed
    print(f"Job ID: {result['job_id']}")
    print(f"Status: {result['status']}")           # "approved"
    print(f"Final params: {result['final_params']}") # may differ if approver modified
    print(f"Approved by: {result['approved_by']}")
    print(f"Executed at: {result['executed_at']}")

except ApprovalDenied as e:
    # An approver explicitly rejected the request
    print(f"Denied by: {e.denied_by}")
    print(f"Reason: {e.reason}")       # Optional denial reason
    print(f"Job ID: {e.job_id}")       # For audit trail

except ApprovalTimeout as e:
    # No approver responded within the timeout window
    print(f"Timed out after {e.timeout}s")
    print(f"Job ID: {e.job_id}")

except ApprovalBlocked as e:
    # A rule blocked this action outright (e.g., blackout window)
    print(f"Blocked by rule: {e.rule_name}")
    print(f"Reason: {e.reason}")`} />
        </Section>

        {/* --- Async Support --- */}
        <Section id="sdk-async">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={5} /> Async Support
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            For asyncio-based agents (LangChain, LlamaIndex, CrewAI, AutoGen), use the async variants.
          </p>
          <CodeBlock language="python" code={`from approvalkit import AsyncApprovalKit, ApprovalDenied

kit = AsyncApprovalKit(
    base_url="http://localhost:8000",
    api_key="ak_...",
    hmac_secret="your-secret",
    user_id="langchain-agent",
)

# Async decorator
@kit.requires_approval(connection="stripe-prod", action="charge")
async def charge_customer(amount: int, customer: str):
    pass

# Async inline gate
result = await kit.gate("github-main", "deploy", {
    "ref": "main",
    "environment": "production",
})

# Works with LangChain tools
from langchain.tools import tool

@tool
@kit.requires_approval(connection="stripe-prod", action="refund")
async def refund_customer(amount: int, customer: str):
    """Refund a customer. Requires human approval."""
    pass

# Non-blocking submission (fire and forget, check later)
job_id = await kit.submit("stripe-prod", "charge", {"amount": 100})
# ... do other work ...
result = await kit.check(job_id)  # poll manually`} />
        </Section>

        {/* ============================================================ */}
        {/*  CREATING RULES                                               */}
        {/* ============================================================ */}
        <Section id="creating-rules">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <Workflow className="h-5 w-5 text-blue-500" /> Creating Rules
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Rules define which actions require approval, who can approve them, and under what conditions.
          </p>
        </Section>

        {/* --- Rules: Dashboard --- */}
        <Section id="rules-dashboard">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={1} /> Create Rules via Dashboard
          </h3>
          <ol className="list-decimal list-inside text-sm text-zinc-600 dark:text-zinc-400 space-y-2 mb-4">
            <li>Navigate to the <strong className="text-zinc-800 dark:text-zinc-200">Rules</strong> page in the dashboard sidebar.</li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">+ New Rule</strong>.</li>
            <li>Fill in:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li><strong>Name:</strong> A descriptive name (e.g. "Stripe charges over $100")</li>
                <li><strong>Connection:</strong> Select the connected service</li>
                <li><strong>Action:</strong> The action name your agent sends (e.g. "charge", "deploy")</li>
                <li><strong>Approval Model:</strong> Who needs to approve (see models below)</li>
                <li><strong>Approvers:</strong> Select one or more approvers</li>
                <li><strong>Conditions:</strong> Optional -- only trigger for matching parameters</li>
                <li><strong>Timeout:</strong> How long to wait (default 300s)</li>
              </ul>
            </li>
            <li>Click <strong className="text-zinc-800 dark:text-zinc-200">Create Rule</strong>.</li>
            <li>Test with <strong className="text-zinc-800 dark:text-zinc-200">Simulate</strong> to verify it matches your expected requests.</li>
          </ol>
        </Section>

        {/* --- Rules: API --- */}
        <Section id="rules-api">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={2} /> Create Rules via API
          </h3>
          <CodeBlock language="bash" code={`# Create a rule via the API
curl -X POST http://localhost:8000/api/v1/rules \\
  -H "Authorization: Bearer ak_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Large Stripe charges",
    "connection": "stripe-prod",
    "action": "charge",
    "model": "specific",
    "approvers": ["approver-uuid-here"],
    "timeout_seconds": 300,
    "conditions": [
      {
        "field": "amount_usd",
        "operator": "gte",
        "value": 100
      }
    ],
    "step_up_model": "all_of_n",
    "step_up_conditions": [
      {
        "field": "amount_usd",
        "operator": "gte",
        "value": 5000
      }
    ],
    "on_timeout": "reject",
    "enabled": true
  }'

# Simulate a request to see which rule matches
curl -X POST http://localhost:8000/api/v1/rules/simulate \\
  -H "Authorization: Bearer ak_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "connection": "stripe-prod",
    "action": "charge",
    "params": {"amount_usd": 250, "customer": "cus_abc"}
  }'`} />
        </Section>

        {/* --- Rules: Conditions --- */}
        <Section id="rules-conditions">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={3} /> Condition Operators
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Conditions let you create rules that only match specific parameter values. If no conditions are set, the rule matches all requests for that connection + action.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-zinc-200 dark:border-zinc-700 rounded-lg overflow-hidden">
              <thead className="bg-zinc-50 dark:bg-zinc-800/50">
                <tr>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Operator</th>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Description</th>
                  <th className="text-left p-3 font-medium text-zinc-700 dark:text-zinc-300">Example</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {[
                  { op: "eq", desc: "Equals", ex: '{"field": "env", "operator": "eq", "value": "production"}' },
                  { op: "neq", desc: "Not equals", ex: '{"field": "env", "operator": "neq", "value": "staging"}' },
                  { op: "gt", desc: "Greater than", ex: '{"field": "amount", "operator": "gt", "value": 1000}' },
                  { op: "gte", desc: "Greater than or equal", ex: '{"field": "amount", "operator": "gte", "value": 100}' },
                  { op: "lt", desc: "Less than", ex: '{"field": "count", "operator": "lt", "value": 10}' },
                  { op: "lte", desc: "Less than or equal", ex: '{"field": "count", "operator": "lte", "value": 5}' },
                  { op: "in", desc: "Value in list", ex: '{"field": "region", "operator": "in", "value": ["us", "eu"]}' },
                  { op: "not_in", desc: "Value not in list", ex: '{"field": "tier", "operator": "not_in", "value": ["free"]}' },
                  { op: "contains", desc: "String contains", ex: '{"field": "email", "operator": "contains", "value": "@acme"}' },
                  { op: "regex", desc: "Regex match", ex: '{"field": "ref", "operator": "regex", "value": "^release/.*"}' },
                ].map((row) => (
                  <tr key={row.op}>
                    <td className="p-3 font-mono text-xs text-zinc-800 dark:text-zinc-200">{row.op}</td>
                    <td className="p-3 text-zinc-600 dark:text-zinc-400">{row.desc}</td>
                    <td className="p-3 font-mono text-xs text-zinc-500 break-all">{row.ex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* --- Rules: Approval Models --- */}
        <Section id="rules-models">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={4} /> Approval Models Explained
          </h3>
          <div className="space-y-3">
            {[
              {
                model: "any_one",
                title: "Any One (First Responder)",
                desc: "The first approver to respond wins. Best for on-call scenarios where speed matters.",
                config: '{"model": "any_one", "approvers": ["alice-id", "bob-id", "charlie-id"]}',
              },
              {
                model: "specific",
                title: "Specific Approver",
                desc: "Only the designated approver can respond. Best for manager-approval workflows.",
                config: '{"model": "specific", "approvers": ["alice-id"]}',
              },
              {
                model: "sequential",
                title: "Sequential Chain",
                desc: "Approvers are notified in order. A must approve before B is notified. Best for escalation chains.",
                config: '{"model": "sequential", "approvers": ["manager-id", "director-id", "vp-id"]}',
              },
              {
                model: "all_of_n",
                title: "All of N (Unanimous)",
                desc: "Every listed approver must approve. A single rejection cancels the request. Best for high-value actions.",
                config: '{"model": "all_of_n", "approvers": ["cfo-id", "cto-id", "ceo-id"]}',
              },
              {
                model: "k_of_n",
                title: "K of N (Quorum)",
                desc: "At least k approvers out of n must approve within a quorum window. Best for committee decisions.",
                config: '{"model": "k_of_n", "approvers": ["member1", "member2", "member3", "member4", "member5"], "k_value": 3, "quorum_window": 120}',
              },
            ].map((item) => (
              <div key={item.model} className="p-4 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <code className="text-xs font-mono bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">
                    {item.model}
                  </code>
                  <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{item.title}</span>
                </div>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">{item.desc}</p>
                <code className="block text-xs font-mono text-zinc-400 bg-zinc-900 px-3 py-2 rounded overflow-x-auto">
                  {item.config}
                </code>
              </div>
            ))}
          </div>
        </Section>

        {/* ============================================================ */}
        {/*  CONNECTING SERVICES                                          */}
        {/* ============================================================ */}
        <Section id="connecting-services">
          <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
            <Link className="h-5 w-5 text-blue-500" /> Connecting Services
          </h2>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            ApprovalKit supports three types of service connections. Each type determines
            how credentials are stored and how actions are executed after approval.
          </p>
        </Section>

        {/* --- Services: OAuth --- */}
        <Section id="services-oauth">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={1} /> OAuth Providers (Token Vault)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            OAuth providers store credentials in Auth0 Token Vault. This is the most secure option
            because the agent never has access to the underlying tokens.
          </p>
          <CodeBlock language="bash" code={`# 1. Register the connection in ApprovalKit
curl -X POST http://localhost:8000/api/v1/connections \\
  -H "Authorization: Bearer ak_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "stripe-prod",
    "type": "oauth",
    "provider": "stripe",
    "display_name": "Stripe Production",
    "auth0_connection_name": "stripe"
  }'

# 2. Get the OAuth connect URL for a user
curl http://localhost:8000/api/v1/connections/stripe-prod/connect-url \\
  -H "Authorization: Bearer ak_..."
# Returns: {"url": "https://your-domain.auth0.com/authorize?..."}

# 3. User visits the URL, authenticates with Stripe, grants access.
#    Auth0 stores the refresh token in Token Vault.
#    The user is redirected back to the dashboard.

# 4. Now when the agent calls:
result = kit.gate("stripe-prod", "charge", {"amount": 500})
# ApprovalKit exchanges the stored token and executes the charge.`} />
        </Section>

        {/* --- Services: M2M --- */}
        <Section id="services-m2m">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={2} /> M2M Credentials (API Keys in Vault)
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            For services that don't support OAuth (internal APIs, legacy systems), you can store
            API keys in ApprovalKit's encrypted credential vault. Keys are encrypted at rest with
            Fernet (AES-128-CBC) using the <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">CREDENTIALS_KEY</code>.
          </p>
          <CodeBlock language="bash" code={`# Register an M2M connection with stored credentials
curl -X POST http://localhost:8000/api/v1/connections \\
  -H "Authorization: Bearer ak_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "internal-billing",
    "type": "m2m",
    "display_name": "Internal Billing API",
    "credentials": {
      "api_key": "sk_live_...",
      "base_url": "https://billing.internal.company.com"
    },
    "action_endpoints": {
      "charge": {
        "method": "POST",
        "path": "/v1/charges",
        "body_template": {
          "amount": "{{amount}}",
          "customer_id": "{{customer}}"
        }
      },
      "refund": {
        "method": "POST",
        "path": "/v1/refunds",
        "body_template": {
          "charge_id": "{{charge_id}}"
        }
      }
    }
  }'`} />
          <Callout type="info">
            The <code>credentials</code> field is encrypted immediately upon receipt and stored as
            ciphertext in PostgreSQL. The plaintext is only decrypted in memory when executing an
            approved action.
          </Callout>
        </Section>

        {/* --- Services: Webhooks --- */}
        <Section id="services-webhooks">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center gap-2">
            <StepNumber n={3} /> Generic Webhook Connections
          </h3>
          <p className="text-zinc-600 dark:text-zinc-400 mb-4">
            Webhook connections forward the approved action to an external URL. Useful for integrating
            with Zapier, Make, n8n, or custom internal services.
          </p>
          <CodeBlock language="bash" code={`# Register a webhook connection
curl -X POST http://localhost:8000/api/v1/connections \\
  -H "Authorization: Bearer ak_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "zapier-notifications",
    "type": "webhook",
    "display_name": "Zapier Notifications",
    "webhook_url": "https://hooks.zapier.com/hooks/catch/12345/abcdef/",
    "webhook_secret": "whsec_...",
    "webhook_headers": {
      "X-Custom-Header": "approvalkit"
    }
  }'

# When an action is approved, ApprovalKit sends:
# POST https://hooks.zapier.com/hooks/catch/12345/abcdef/
# Headers:
#   Content-Type: application/json
#   X-Webhook-Signature: sha256=<hmac of body using webhook_secret>
#   X-Custom-Header: approvalkit
# Body:
#   {
#     "job_id": "...",
#     "connection": "zapier-notifications",
#     "action": "notify",
#     "params": {...},
#     "approved_by": "...",
#     "approved_at": "..."
#   }`} />
        </Section>

        {/* Deployment removed — see SETUP.md for local setup instructions */}
        {/* ---- Footer ---- */}
        <div className="mt-16 pt-8 border-t border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Need help?</p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                Check the <a href="/docs" className="text-blue-500 hover:text-blue-400 underline">API documentation</a> or
                open an issue on GitHub.
              </p>
            </div>
            <a
              href="/docs"
              className="flex items-center gap-2 text-sm text-blue-500 hover:text-blue-400 transition-colors"
            >
              API Docs <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
