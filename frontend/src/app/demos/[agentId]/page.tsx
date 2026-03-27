"use client";

import { useEffect, useState, useCallback } from "react";
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
  MessageSquare, FileText, Zap, TreePine, ExternalLink, Trash2,
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

function resolveIcon(name: string): React.ElementType {
  return ICON_MAP[name] ?? Bot;
}

const CATEGORY_COLORS: Record<string, string> = {
  finance: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  devops: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  hr: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  customer_service: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  healthcare: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
  legal: "bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-400",
};

interface ConnectionStatus {
  slug: string;
  name: string;
  service: string;
  connected: boolean;
  id?: string;
}

export default function DemoAgentPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useUser();
  const agentId = params.agentId as string;

  const [agent, setAgent] = useState<DemoAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupDone, setSetupDone] = useState(false);
  const [settingUp, setSettingUp] = useState(false);
  const [connections, setConnections] = useState<ConnectionStatus[]>([]);
  const [allConnected, setAllConnected] = useState(false);
  const [checkingConns, setCheckingConns] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetItems, setResetItems] = useState<{rules: any[]; approvers: any[]; conns: any[]}>({rules: [], approvers: [], conns: []});
  const [selectedRuleIds, setSelectedRuleIds] = useState<Set<string>>(new Set());
  const [selectedApproverIds, setSelectedApproverIds] = useState<Set<string>>(new Set());
  const [selectedConnIds, setSelectedConnIds] = useState<Set<string>>(new Set());

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
    const agentRuleNames = agent.setupInfo
      .filter(s => s.type === "rule")
      .map(s => s.name.split(" ")[0]);
    if (agentRuleNames.length === 0) return;

    api.getRules().then((rules: any[]) => {
      const ruleNames = rules.map((r: any) => r.name);
      const hasAgentRule = agentRuleNames.some(prefix =>
        ruleNames.some((n: string) => n.includes(prefix))
      );
      setSetupDone(hasAgentRule);
    }).catch(() => {});
  }, [agent]);

  // Check connection status
  const checkConnections = useCallback(async () => {
    if (!agent) return;
    setCheckingConns(true);

    const neededSlugs = agent.setupInfo
      .filter(s => s.type === "connection")
      .map(s => s.name);

    try {
      const allConns = await api.getConnections();
      const statuses: ConnectionStatus[] = neededSlugs.map(slug => {
        const conn = allConns.find((c: any) => c.slug === slug);
        return {
          slug,
          name: conn?.name || slug,
          service: conn?.service || slug.split("-")[0],
          connected: !!conn?.connected_auth0_user_id,
          id: conn?.id,
        };
      });
      setConnections(statuses);
      setAllConnected(statuses.length > 0 && statuses.every(c => c.connected));
    } catch {
      setConnections([]);
    }
    setCheckingConns(false);
  }, [agent]);

  useEffect(() => {
    if (setupDone) checkConnections();
  }, [setupDone, checkConnections]);

  const handleSetup = async () => {
    setSettingUp(true);
    try {
      await api.seedDemoData(agentId, user?.sub || undefined);
      setSetupDone(true);
    } catch {}
    setSettingUp(false);
  };

  const openResetModal = async () => {
    if (!agent) return;
    const prefixes = agent.setupInfo.filter(s => s.type === "rule").map(s => s.name.split(" ")[0]);
    const neededSlugs = new Set(agent.setupInfo.filter(s => s.type === "connection").map(s => s.name));

    try {
      const [allRules, allApprovers, allConns] = await Promise.all([
        api.getRules(),
        api.getApprovers(),
        api.getConnections(),
      ]);
      const agentRules = allRules.filter((r: any) => prefixes.some((p: string) => r.name.includes(p)));
      const demoApprovers = allApprovers.filter((a: any) => a.auth0_user_id?.startsWith("demo|"));
      const agentConns = allConns.filter((c: any) => neededSlugs.has(c.slug));

      setResetItems({ rules: agentRules, approvers: demoApprovers, conns: agentConns });
      setSelectedRuleIds(new Set(agentRules.map((r: any) => r.id)));
      setSelectedApproverIds(new Set(demoApprovers.map((a: any) => a.id)));
      setSelectedConnIds(new Set(agentConns.map((c: any) => c.id)));
    } catch {
      setResetItems({ rules: [], approvers: [], conns: [] });
    }
    setShowResetConfirm(true);
  };

  const toggleId = (set: Set<string>, id: string, setter: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    setter(next);
  };

  const totalSelected = selectedRuleIds.size + selectedApproverIds.size + selectedConnIds.size;

  const handleReset = async () => {
    if (totalSelected === 0) return;
    setResetting(true);
    try {
      await api.clearDemoData({
        agent_id: agentId,
        rule_ids: selectedRuleIds.size > 0 ? Array.from(selectedRuleIds) : undefined,
        approver_ids: selectedApproverIds.size > 0 ? Array.from(selectedApproverIds) : undefined,
        connection_ids: selectedConnIds.size > 0 ? Array.from(selectedConnIds) : undefined,
      });
      if (selectedRuleIds.size > 0) setSetupDone(false);
      if (selectedConnIds.size > 0) { setConnections([]); setAllConnected(false); }
      setShowResetConfirm(false);
    } catch {}
    setResetting(false);
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
        <Button variant="outline" onClick={() => router.push("/demos")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Demos
        </Button>
      </div>
    );
  }

  const Icon = resolveIcon(agent.icon);
  const catColor = CATEGORY_COLORS[agent.category] || CATEGORY_COLORS.finance;

  // Determine current step
  const step = !setupDone ? 1 : !allConnected ? 2 : 3;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="shrink-0 border-b border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/demos")}
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

          {/* Step indicators */}
          <div className="flex items-center gap-2">
            <StepBadge num={1} label="Setup" active={step === 1} done={step > 1} />
            <StepBadge num={2} label="Connect" active={step === 2} done={step > 2} />
            <StepBadge num={3} label="Chat" active={step === 3} done={false} />
            {setupDone && (
              <button
                onClick={openResetModal}
                className="ml-1 p-1.5 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                title="Reset demo"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content based on step */}
      <div className="flex-1 min-h-0">
        {step === 1 && (
          <div className="overflow-y-auto h-full">
            <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
              {/* Agent header */}
              <div className="text-center space-y-3">
                <div className="inline-flex p-4 bg-zinc-100 dark:bg-zinc-800 rounded-2xl">
                  <Icon className="h-10 w-10 text-zinc-500" />
                </div>
                <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{agent.title}</h2>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-lg mx-auto leading-relaxed">
                  {agent.description}
                </p>
              </div>

              {/* Scenarios */}
              <div>
                <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-3">Scenarios</h3>
                <div className="space-y-2">
                  {agent.scenarios.map((s, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50">
                      <Badge variant={s.badge} className="text-[10px] font-mono shrink-0 w-16 justify-center">
                        {s.badgeLabel}
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{s.title}</div>
                        <div className="text-xs text-zinc-400 mt-0.5">{s.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* What setup creates */}
              <div>
                <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-3">What Setup Creates</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50">
                    <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Connections</div>
                    {agent.setupInfo.filter(s => s.type === "connection").map((s, i) => (
                      <div key={i} className="text-xs text-zinc-600 dark:text-zinc-300 py-0.5">{s.name}</div>
                    ))}
                  </div>
                  <div className="p-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50">
                    <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Approvers</div>
                    {agent.setupInfo.filter(s => s.type === "approver").map((s, i) => (
                      <div key={i} className="text-xs text-zinc-600 dark:text-zinc-300 py-0.5">{s.name}</div>
                    ))}
                  </div>
                  <div className="p-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/50">
                    <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Rules</div>
                    {agent.setupInfo.filter(s => s.type === "rule").map((s, i) => (
                      <div key={i} className="text-xs text-zinc-600 dark:text-zinc-300 py-0.5">
                        <span className="font-medium">{s.name.replace(/\[.*?\]\s*/, "")}</span>
                        <span className="text-zinc-400 ml-1">— {s.detail}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Setup button */}
              <div className="text-center pt-2">
                <Button onClick={handleSetup} disabled={settingUp} size="lg">
                  {settingUp ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Setting up...</>
                  ) : (
                    <><Play className="h-4 w-4 mr-2" /> Setup Demo</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="flex flex-col items-center justify-center h-full gap-6 px-4">
            <div className="text-center">
              <h2 className="text-lg font-semibold text-zinc-800 dark:text-zinc-200">Connect Your Accounts</h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-lg">
                This agent needs the following services connected via Auth0 Token Vault.
                Go to Connections to add your service and authorize with your own account — the agent never sees your credentials.
              </p>
            </div>

            <div className="w-full max-w-md space-y-3">
              {connections.map(conn => (
                <div
                  key={conn.slug}
                  className={`flex items-center justify-between p-3 rounded-xl border ${
                    conn.connected
                      ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950/20"
                      : "border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${conn.connected ? "bg-green-500" : "bg-zinc-300 dark:bg-zinc-600"}`} />
                    <div>
                      <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{conn.name}</div>
                      <div className="text-xs text-zinc-400">{conn.slug}</div>
                    </div>
                  </div>
                  {conn.connected ? (
                    <Badge variant="success" className="text-[10px]">
                      <CheckCircle2 className="h-3 w-3 mr-1" /> Connected
                    </Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => router.push(`/connections?highlight=${conn.slug}`)}
                      className="h-7 text-xs"
                    >
                      <ExternalLink className="h-3 w-3 mr-1" /> Go to Connections
                    </Button>
                  )}
                </div>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={checkConnections} disabled={checkingConns}>
                {checkingConns ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Refresh status"}
              </Button>
              {connections.some(c => c.connected) && (
                <p className="text-xs text-zinc-400">
                  {connections.filter(c => c.connected).length}/{connections.length} connected
                </p>
              )}
            </div>
          </div>
        )}

        {step === 3 && (
          <AgentChat agent={agent} />
        )}
      </div>

      {/* Reset confirmation modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowResetConfirm(false)}>
          <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-xl p-6 max-w-md w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 dark:bg-red-950/30 rounded-lg">
                <AlertTriangle className="h-5 w-5 text-red-500" />
              </div>
              <div>
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Reset {agent.title}</h3>
                <p className="text-xs text-zinc-400">Select items to delete</p>
              </div>
            </div>

            {/* Connections */}
            {resetItems.conns.length > 0 && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Connections</span>
                  <button className="text-[10px] text-blue-500" onClick={() => {
                    const allIds = new Set(resetItems.conns.map((c: any) => c.id));
                    setSelectedConnIds(selectedConnIds.size === allIds.size ? new Set() : allIds);
                  }}>{selectedConnIds.size === resetItems.conns.length ? "Deselect all" : "Select all"}</button>
                </div>
                <div className="space-y-1">
                  {resetItems.conns.map((c: any) => (
                    <label key={c.id} className="flex items-center gap-2.5 p-2 rounded-lg border border-zinc-100 dark:border-zinc-800 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                      <input type="checkbox" checked={selectedConnIds.has(c.id)} onChange={() => toggleId(selectedConnIds, c.id, setSelectedConnIds)}
                        className="w-3.5 h-3.5 rounded border-zinc-300 text-red-500 focus:ring-red-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-zinc-700 dark:text-zinc-300">{c.name}</div>
                        <div className="text-[10px] text-zinc-400">{c.slug} — {c.service}</div>
                      </div>
                      {c.connected_user_name && <Badge variant="success" className="text-[9px] shrink-0">OAuth</Badge>}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Approvers */}
            {resetItems.approvers.length > 0 && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Approvers</span>
                  <button className="text-[10px] text-blue-500" onClick={() => {
                    const allIds = new Set(resetItems.approvers.map((a: any) => a.id));
                    setSelectedApproverIds(selectedApproverIds.size === allIds.size ? new Set() : allIds);
                  }}>{selectedApproverIds.size === resetItems.approvers.length ? "Deselect all" : "Select all"}</button>
                </div>
                <div className="space-y-1">
                  {resetItems.approvers.map((a: any) => (
                    <label key={a.id} className="flex items-center gap-2.5 p-2 rounded-lg border border-zinc-100 dark:border-zinc-800 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                      <input type="checkbox" checked={selectedApproverIds.has(a.id)} onChange={() => toggleId(selectedApproverIds, a.id, setSelectedApproverIds)}
                        className="w-3.5 h-3.5 rounded border-zinc-300 text-red-500 focus:ring-red-500" />
                      <div className="text-sm text-zinc-700 dark:text-zinc-300">{a.name}</div>
                      <span className="text-[10px] text-zinc-400 ml-auto">{a.email}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Rules */}
            {resetItems.rules.length > 0 && (
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Rules</span>
                  <button className="text-[10px] text-blue-500" onClick={() => {
                    const allIds = new Set(resetItems.rules.map((r: any) => r.id));
                    setSelectedRuleIds(selectedRuleIds.size === allIds.size ? new Set() : allIds);
                  }}>{selectedRuleIds.size === resetItems.rules.length ? "Deselect all" : "Select all"}</button>
                </div>
                <div className="space-y-1">
                  {resetItems.rules.map((r: any) => (
                    <label key={r.id} className="flex items-center gap-2.5 p-2 rounded-lg border border-zinc-100 dark:border-zinc-800 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors">
                      <input type="checkbox" checked={selectedRuleIds.has(r.id)} onChange={() => toggleId(selectedRuleIds, r.id, setSelectedRuleIds)}
                        className="w-3.5 h-3.5 rounded border-zinc-300 text-red-500 focus:ring-red-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-zinc-700 dark:text-zinc-300">{r.name}</div>
                        <div className="text-[10px] text-zinc-400">{r.model} — {r.connection}/{r.action}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {totalSelected === 0 && (
              <p className="text-sm text-zinc-400 text-center mb-4">No items selected</p>
            )}

            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setShowResetConfirm(false)}>
                Cancel
              </Button>
              <Button
                className="flex-1 bg-red-600 hover:bg-red-700 text-white"
                onClick={handleReset}
                disabled={resetting || totalSelected === 0}
              >
                {resetting ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> Deleting...</>
                ) : (
                  <><Trash2 className="h-3.5 w-3.5 mr-1.5" /> Delete {totalSelected} items</>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StepBadge({ num, label, active, done }: { num: number; label: string; active: boolean; done: boolean }) {
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
      done
        ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
        : active
        ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
        : "bg-zinc-100 dark:bg-zinc-800 text-zinc-400"
    }`}>
      {done ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <span className="w-3.5 h-3.5 rounded-full border border-current flex items-center justify-center text-[9px]">{num}</span>
      )}
      {label}
    </div>
  );
}
