"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DemoAgent } from "@/components/scenario-runner";
import {
  ArrowRight, Banknote, Bot, Building2, CheckCircle2, CreditCard, Database,
  Film, FlaskConical, GitBranch, GraduationCap, Heart, Home, Key, Leaf,
  Loader2, Lock, Mail, Package, Plane, Play, Scale, Server, Shield, ShieldAlert,
  ShoppingCart, Users, Zap, Briefcase, AlertTriangle, FileCheck,
  UserPlus, DoorOpen, ClipboardList, UserCheck, Headphones,
  Clock, Stethoscope, Pill, Microscope, BookOpen, Award, Coins,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, TreePine,
} from "lucide-react";

const ICON_MAP: Record<string, React.ElementType> = {
  ShoppingCart, Users, Server, Package, FlaskConical, CreditCard, Mail, Bot,
  Building2, Heart, GraduationCap, Scale, Home, Film, Leaf, Banknote,
  Briefcase, AlertTriangle, Database, Key, FileCheck, UserPlus, GitBranch,
  DoorOpen, ClipboardList, UserCheck, Headphones, Lock, Clock, Plane,
  Stethoscope, Pill, Microscope, BookOpen, Award, Coins, Shield,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, Zap, TreePine, Play,
};

const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  finance: { label: "Commerce & Finance", color: "bg-emerald-500", icon: CreditCard },
  devops: { label: "DevOps & Software", color: "bg-blue-500", icon: Server },
  hr: { label: "Human Resources", color: "bg-purple-500", icon: Users },
  customer_service: { label: "Customer Service", color: "bg-orange-500", icon: Headphones },
  legal: { label: "Legal & Compliance", color: "bg-slate-500", icon: Scale },
};

const CATEGORY_ORDER = [
  "finance", "devops", "hr", "customer_service", "legal",
];

const CATEGORY_BORDER: Record<string, string> = {
  finance: "border-l-emerald-500",
  devops: "border-l-blue-500",
  hr: "border-l-purple-500",
  customer_service: "border-l-orange-500",
  legal: "border-l-slate-500",
};

const CATEGORY_ICON_BG: Record<string, string> = {
  finance: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  devops: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  hr: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  customer_service: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  legal: "bg-slate-500/10 text-slate-600 dark:text-slate-400",
};

export default function DemosPage() {
  const router = useRouter();
  const { user } = useUser();
  const [agents, setAgents] = useState<DemoAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [seedingAll, setSeedingAll] = useState(false);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    api.getDemoAgents()
      .then((data: DemoAgent[]) => setAgents(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSeedAll = async () => {
    setSeedingAll(true);
    try {
      await api.seedDemoData(undefined, user?.sub || undefined);
      setSeeded(true);
    } catch {}
    setSeedingAll(false);
  };

  // Group agents by category
  const grouped = CATEGORY_ORDER
    .map(cat => ({
      category: cat,
      meta: CATEGORY_META[cat],
      agents: agents.filter(a => a.category === cat),
    }))
    .filter(g => g.agents.length > 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
          Demo Agents
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-2 max-w-2xl text-sm leading-relaxed">
          8 AI agents across 5 domains. Each has a conversational chat interface
          that triggers real ApprovalKit approval flows via Auth0 Token Vault.
        </p>
      </div>

      {/* AI Orchestrator — Hero */}
      <div className="mb-12">
        <Card
          className="group border-2 border-purple-300 dark:border-purple-700 bg-gradient-to-r from-purple-50/50 to-blue-50/50 dark:from-purple-950/20 dark:to-blue-950/20 hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
          onClick={() => router.push("/demos/live?chain=orchestrator")}
        >
          <CardContent className="p-8">
            <div className="flex items-start gap-6">
              <div className="p-4 rounded-2xl bg-gradient-to-br from-purple-600 to-blue-500 text-white shrink-0">
                <Bot className="h-8 w-8" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h2 className="text-xl font-bold text-zinc-800 dark:text-zinc-200">AI Orchestrator</h2>
                  <Badge variant="default" className="text-xs">Multi-Agent</Badge>
                </div>
                <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed mb-4">
                  Describe any business situation in plain text. The AI orchestrator analyzes your request,
                  selects the right specialized agents, assigns each one specific tools (least-privilege),
                  and runs them in sequence — each agent reacts to previous results.
                </p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {["Customer Incidents", "Security Breaches", "Employee Onboarding", "Fraud Detection", "Product Launches", "Vendor Payments"].map(s => (
                    <span key={s} className="text-[10px] px-2.5 py-1 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 font-medium">{s}</span>
                  ))}
                </div>
                <div className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
                  <span>8 specialized agents</span>
                  <span>30 Token Vault services</span>
                  <span>Per-tool least privilege</span>
                  <span>Context-driven decisions</span>
                </div>
              </div>
              <ArrowRight className="h-6 w-6 text-purple-400 group-hover:text-purple-600 dark:group-hover:text-purple-300 transition-colors shrink-0 mt-2" />
            </div>
          </CardContent>
        </Card>
        {/* Architecture Docs Link */}
        <Card
          className="group border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/10 hover:bg-purple-100/50 dark:hover:bg-purple-950/20 hover:shadow-md transition-all cursor-pointer mt-4"
          onClick={() => router.push("/docs/demo-architecture")}
        >
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-900/40">
              <FileText className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-purple-800 dark:text-purple-200">Demo Architecture Docs</h3>
              <p className="text-xs text-purple-600/80 dark:text-purple-400/70 mt-0.5">
                Deep dive: AI Orchestrator, defense-in-depth, 7 sub-agents, adversarial validation, parallel execution, and more
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-purple-400 group-hover:text-purple-600 dark:group-hover:text-purple-300 transition-colors shrink-0" />
          </CardContent>
        </Card>
      </div>

      {/* Setup All Demos — prominent card */}
      <div className="mb-12">
        <Card className="border-2 border-dashed border-blue-300 dark:border-blue-700 bg-gradient-to-r from-blue-50/50 to-emerald-50/50 dark:from-blue-950/20 dark:to-emerald-950/20">
          <CardContent className="p-6 flex flex-col sm:flex-row items-center gap-5">
            <div className="p-3 rounded-2xl bg-gradient-to-br from-blue-600 to-emerald-500 text-white shrink-0">
              <Zap className="h-6 w-6" />
            </div>
            <div className="flex-1 text-center sm:text-left">
              <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-200">
                Quick Start: Setup All Demos
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                Creates connections, approvers, and rules for all 8 agents in one click.
                Run this first so every demo works out of the box.
              </p>
            </div>
            <div className="shrink-0">
              {seeded ? (
                <Badge variant="success" className="text-sm py-2 px-5">
                  <CheckCircle2 className="h-4 w-4 mr-2" /> All demo data seeded
                </Badge>
              ) : (
                <Button
                  onClick={handleSeedAll}
                  disabled={seedingAll}
                  size="lg"
                  className="bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-200 px-8 py-3 text-sm font-semibold"
                >
                  {seedingAll ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Seeding all demo data...</>
                  ) : (
                    <><Play className="h-4 w-4 mr-2" /> Setup All Demos</>
                  )}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Available Agents — info only, not clickable */}
      <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-2">
        Available Specialized Agents
      </p>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        The orchestrator automatically selects from these agents based on your request. Each agent has specific tools and approval rules.
      </p>
      <div className="space-y-10">
        {grouped.map(({ category, meta, agents: catAgents }) => (
          <section key={category}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`p-1.5 rounded-lg ${meta.color} text-white`}>
                <meta.icon className="h-3.5 w-3.5" />
              </div>
              <h2 className="text-sm font-bold text-zinc-700 dark:text-zinc-300">{meta.label}</h2>
              <Badge variant="default" className="text-[10px]">{catAgents.length}</Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {catAgents.map(agent => {
                const Icon = ICON_MAP[agent.icon] ?? Bot;
                return (
                  <div key={agent.id} className={`rounded-xl border-l-4 ${CATEGORY_BORDER[category]} border border-zinc-200/60 dark:border-zinc-800/60 p-4`}>
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg shrink-0 ${CATEGORY_ICON_BG[category]}`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">{agent.title}</h3>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed">{agent.description}</p>
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {agent.scenarios.slice(0, 4).map((s: any, i: number) => (
                            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400">{s.title || s.badgeLabel}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
