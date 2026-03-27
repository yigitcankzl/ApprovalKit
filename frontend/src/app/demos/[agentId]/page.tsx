"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { AgentChat, DemoAgent } from "@/components/agent-chat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import {
  ArrowLeft, Bot, CheckCircle2, CreditCard, FlaskConical, Loader2,
  Mail, Package, Server, Shield, ShoppingCart, Users, Play,
  Building2, Heart, GraduationCap, Scale, Home, Film, Leaf,
  Briefcase, AlertTriangle, Database, Key, FileCheck, UserPlus,
  DoorOpen, ClipboardList, UserCheck, Headphones, Lock, Clock,
  Stethoscope, Pill, Microscope, BookOpen, Award, Coins,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, Zap, TreePine,
} from "lucide-react";

// Icon resolver
const ICON_MAP: Record<string, React.ElementType> = {
  ShoppingCart, Users, Server, Package, FlaskConical, CreditCard, Mail, Bot,
  Building2, Heart, GraduationCap, Scale, Home, Film, Leaf,
  Briefcase, AlertTriangle, Database, Key, FileCheck, UserPlus,
  DoorOpen, ClipboardList, UserCheck, Headphones, Lock, Clock,
  Stethoscope, Pill, Microscope, BookOpen, Award, Coins, Shield,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, Zap, TreePine, Play,
};

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Bot;
}

// Category colors
const CATEGORY_COLORS: Record<string, string> = {
  finance: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  devops: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  hr: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  customer_service: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  healthcare: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  education: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400",
  legal: "bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-400",
  real_estate: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  media: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400",
  energy: "bg-lime-100 text-lime-800 dark:bg-lime-900/30 dark:text-lime-400",
};

export default function DemoAgentPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useUser();
  const agentId = params.agentId as string;

  const [agent, setAgent] = useState<DemoAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupDone, setSetupDone] = useState(false);
  const [settingUp, setSettingUp] = useState(false);

  useEffect(() => {
    api.getDemoAgents()
      .then((agents: DemoAgent[]) => {
        const found = agents.find(a => a.id === agentId);
        if (found) setAgent(found);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [agentId]);

  // Check if setup is done
  useEffect(() => {
    if (!agent) return;
    api.getRules().then((rules: any[]) => {
      const ruleNames = rules.map((r: any) => r.name);
      const hasRule = agent.setupInfo
        .filter(s => s.type === "rule")
        .some(s => ruleNames.some((n: string) => n.includes(s.name.split(" ")[0])));
      setSetupDone(hasRule || rules.length > 0);
    }).catch(() => {});
  }, [agent]);

  const handleSetup = async () => {
    setSettingUp(true);
    try {
      await api.seedDemoData(agentId, user?.sub || undefined);
      setSetupDone(true);
    } catch {}
    setSettingUp(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <Bot className="h-12 w-12 text-zinc-300 mb-4" />
        <p className="text-zinc-500 mb-4">Agent not found</p>
        <Button variant="outline" onClick={() => router.push("/agents")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Agents
        </Button>
      </div>
    );
  }

  const Icon = resolveIcon(agent.icon);
  const catColor = CATEGORY_COLORS[agent.category] || CATEGORY_COLORS.finance;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="shrink-0 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/agents")}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
              <Icon className="h-5 w-5 text-zinc-700 dark:text-zinc-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{agent.title}</h1>
                <Badge className={`text-[10px] ${catColor}`}>{agent.categoryLabel}</Badge>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-xl truncate">{agent.description}</p>
            </div>
          </div>

          {!setupDone ? (
            <Button size="sm" onClick={handleSetup} disabled={settingUp}>
              {settingUp ? (
                <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Setting up...</>
              ) : (
                <><Play className="h-3.5 w-3.5 mr-1.5" /> Setup Demo</>
              )}
            </Button>
          ) : (
            <Badge variant="success" className="text-xs">
              <CheckCircle2 className="h-3 w-3 mr-1" /> Ready
            </Badge>
          )}
        </div>
      </div>

      {/* Chat */}
      <div className="flex-1 min-h-0">
        <AgentChat agent={agent} />
      </div>
    </div>
  );
}
