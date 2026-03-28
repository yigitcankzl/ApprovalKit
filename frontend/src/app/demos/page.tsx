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
  ArrowRight, Bot, Building2, CheckCircle2, CreditCard, Database,
  Film, FlaskConical, GraduationCap, Heart, Home, Key, Leaf,
  Loader2, Lock, Mail, Package, Play, Scale, Server, Shield,
  ShoppingCart, Users, Zap, Briefcase, AlertTriangle, FileCheck,
  UserPlus, DoorOpen, ClipboardList, UserCheck, Headphones,
  Clock, Stethoscope, Pill, Microscope, BookOpen, Award, Coins,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, TreePine,
} from "lucide-react";

const ICON_MAP: Record<string, React.ElementType> = {
  ShoppingCart, Users, Server, Package, FlaskConical, CreditCard, Mail, Bot,
  Building2, Heart, GraduationCap, Scale, Home, Film, Leaf,
  Briefcase, AlertTriangle, Database, Key, FileCheck, UserPlus,
  DoorOpen, ClipboardList, UserCheck, Headphones, Lock, Clock,
  Stethoscope, Pill, Microscope, BookOpen, Award, Coins, Shield,
  FileSignature, ShieldCheck, Lightbulb, Wrench, UserSearch,
  MessageSquare, FileText, Zap, TreePine, Play,
};

const CATEGORY_META: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  finance: { label: "Commerce & Finance", color: "bg-emerald-500", icon: CreditCard },
  devops: { label: "DevOps & Software", color: "bg-blue-500", icon: Server },
  hr: { label: "Human Resources", color: "bg-purple-500", icon: Users },
  customer_service: { label: "Customer Service", color: "bg-orange-500", icon: Headphones },
  healthcare: { label: "Healthcare & Clinical", color: "bg-red-500", icon: Heart },
  legal: { label: "Legal & Compliance", color: "bg-slate-500", icon: Scale },
};

const CATEGORY_ORDER = [
  "finance", "devops", "hr", "customer_service", "healthcare", "legal",
];

const CATEGORY_BORDER: Record<string, string> = {
  finance: "border-l-emerald-500",
  devops: "border-l-blue-500",
  hr: "border-l-purple-500",
  customer_service: "border-l-orange-500",
  healthcare: "border-l-red-500",
  legal: "border-l-slate-500",
};

const CATEGORY_ICON_BG: Record<string, string> = {
  finance: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  devops: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  hr: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
  customer_service: "bg-orange-500/10 text-orange-600 dark:text-orange-400",
  healthcare: "bg-red-500/10 text-red-600 dark:text-red-400",
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
          10 industry-specific AI agents powered by Claude. Each agent has a conversational chat interface
          that triggers real ApprovalKit approval flows. Click any agent to start chatting.
        </p>

        {/* Seed all button */}
        <div className="mt-6 flex items-center gap-4">
          {seeded ? (
            <Badge variant="success" className="text-sm py-1.5 px-4">
              <CheckCircle2 className="h-4 w-4 mr-2" /> All demo data seeded
            </Badge>
          ) : (
            <Button
              onClick={handleSeedAll}
              disabled={seedingAll}
              className="bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-all duration-200 px-6 py-2.5 text-sm font-semibold"
            >
              {seedingAll ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Seeding all demo data...</>
              ) : (
                <><Play className="h-4 w-4 mr-2" /> Setup All Demos</>
              )}
            </Button>
          )}
          <span className="text-xs text-zinc-400">
            Creates connections, approvers, and rules for all agents
          </span>
        </div>
      </div>

      {/* Category sections */}
      <div className="space-y-14">
        {grouped.map(({ category, meta, agents: catAgents }) => (
          <section key={category}>
            <div className="flex items-center gap-3 mb-6">
              <div className={`p-2 rounded-xl ${meta.color} text-white`}>
                <meta.icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500">
                  Category
                </p>
                <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-200 -mt-0.5">
                  {meta.label}
                </h2>
              </div>
              <Badge variant="default" className="text-xs ml-1">{catAgents.length} agents</Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {catAgents.map(agent => {
                const Icon = ICON_MAP[agent.icon] ?? Bot;
                return (
                  <Card
                    key={agent.id}
                    className={`group border-l-4 ${CATEGORY_BORDER[category]} hover:shadow-lg hover:shadow-zinc-200/50 dark:hover:shadow-zinc-900/50 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer`}
                    onClick={() => router.push(`/demos/${agent.id}`)}
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start gap-4">
                        <div className={`p-2.5 rounded-xl shrink-0 ${CATEGORY_ICON_BG[category]}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-200 group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">
                            {agent.title}
                          </h3>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 line-clamp-2 leading-relaxed">
                            {agent.description}
                          </p>
                        </div>
                      </div>

                      {/* Scenario badges */}
                      <div className="mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                        <p className="text-[9px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-2">
                          Scenarios
                        </p>
                        <div className="flex flex-wrap items-center gap-1.5">
                          {agent.scenarios.slice(0, 3).map((s, i) => (
                            <Badge key={i} variant={s.badge} className="text-[10px] px-2 py-0.5 font-medium">
                              {s.badgeLabel}
                            </Badge>
                          ))}
                          {agent.scenarios.length > 3 && (
                            <span className="text-[10px] text-zinc-400 font-medium">+{agent.scenarios.length - 3} more</span>
                          )}
                        </div>
                      </div>

                      {/* CTA */}
                      <div className="mt-4 flex justify-end">
                        <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 group-hover:text-blue-700 dark:group-hover:text-blue-300 flex items-center gap-1.5 transition-all group-hover:gap-2">
                          Try this agent <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
