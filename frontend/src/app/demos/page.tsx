"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { DemoAgent } from "@/components/agent-chat";
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
  education: { label: "Education", color: "bg-indigo-500", icon: GraduationCap },
  legal: { label: "Legal & Compliance", color: "bg-slate-500", icon: Scale },
  real_estate: { label: "Real Estate", color: "bg-amber-500", icon: Home },
  media: { label: "Media & Content", color: "bg-pink-500", icon: Film },
  energy: { label: "Energy & Environment", color: "bg-lime-500", icon: Leaf },
};

const CATEGORY_ORDER = [
  "finance", "devops", "hr", "customer_service", "healthcare",
  "education", "legal", "real_estate", "media", "energy",
];

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
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Demo Agents</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          36 industry-specific AI agents with interactive approval flows.
          Click &quot;Try this one&quot; to open the chat interface and test any agent live.
        </p>

        {/* Seed all button */}
        <div className="mt-4 flex items-center gap-3">
          {seeded ? (
            <Badge variant="success" className="text-sm py-1 px-3">
              <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" /> All demo data seeded
            </Badge>
          ) : (
            <Button onClick={handleSeedAll} disabled={seedingAll}>
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
      <div className="space-y-10">
        {grouped.map(({ category, meta, agents: catAgents }) => (
          <section key={category}>
            <div className="flex items-center gap-3 mb-4">
              <div className={`p-1.5 rounded-lg ${meta.color} text-white`}>
                <meta.icon className="h-4 w-4" />
              </div>
              <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">{meta.label}</h2>
              <Badge variant="default" className="text-xs">{catAgents.length} agents</Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {catAgents.map(agent => {
                const Icon = ICON_MAP[agent.icon] ?? Bot;
                return (
                  <Card
                    key={agent.id}
                    className="group hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors cursor-pointer"
                    onClick={() => router.push(`/demos/${agent.id}`)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className="p-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg shrink-0">
                          <Icon className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 group-hover:text-zinc-900 dark:group-hover:text-zinc-100 transition-colors">
                            {agent.title}
                          </h3>
                          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-2">
                            {agent.description}
                          </p>
                          <div className="flex items-center gap-2 mt-3">
                            <div className="flex gap-1">
                              {agent.scenarios.slice(0, 3).map((s, i) => (
                                <Badge key={i} variant={s.badge} className="text-[9px] px-1.5 py-0">
                                  {s.badgeLabel}
                                </Badge>
                              ))}
                              {agent.scenarios.length > 3 && (
                                <span className="text-[10px] text-zinc-400">+{agent.scenarios.length - 3}</span>
                              )}
                            </div>
                            <div className="flex-1" />
                            <span className="text-xs font-medium text-blue-600 dark:text-blue-400 group-hover:text-blue-700 dark:group-hover:text-blue-300 flex items-center gap-1 transition-colors">
                              Try this one <ArrowRight className="h-3 w-3" />
                            </span>
                          </div>
                        </div>
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
