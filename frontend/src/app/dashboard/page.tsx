"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { DashboardStats } from "@/types";
import {
  CheckCircle2,
  XCircle,
  ShieldOff,
  Clock,
  KeyRound,
  Users,
  Activity,
  AlertTriangle,
} from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getDashboard()
      .then(setStats)
      .catch(() => {
        // Use mock data when API is unavailable
        setStats({
          total_actions_week: 147,
          approved: 98,
          rejected: 12,
          blocked: 8,
          timed_out: 5,
          active_pre_approvals: 3,
          active_delegations: 1,
          ciba_usage: 234,
          ciba_limit: 500,
          scope_creep_alerts: 2,
        });
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
      </div>
    );
  }

  if (!stats) return null;

  const cibaPercent = Math.round((stats.ciba_usage / stats.ciba_limit) * 100);

  const statCards = [
    { title: "Total Actions (7d)", value: stats.total_actions_week, icon: Activity, color: "text-zinc-600" },
    { title: "Approved", value: stats.approved, icon: CheckCircle2, color: "text-green-600" },
    { title: "Rejected", value: stats.rejected, icon: XCircle, color: "text-red-600" },
    { title: "Blocked", value: stats.blocked, icon: ShieldOff, color: "text-orange-600" },
    { title: "Timed Out", value: stats.timed_out, icon: Clock, color: "text-yellow-600" },
    { title: "Pre-Approvals", value: stats.active_pre_approvals, icon: KeyRound, color: "text-blue-600" },
    { title: "Delegations", value: stats.active_delegations, icon: Users, color: "text-purple-600" },
    { title: "Scope Creep", value: stats.scope_creep_alerts, icon: AlertTriangle, color: "text-red-600" },
  ];

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Permission Dashboard</h1>
        <p className="text-zinc-500 mt-1">Workspace overview — access controlled by FGA role</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-500">{stat.title}</p>
                  <p className="text-3xl font-bold text-zinc-900 mt-1">{stat.value}</p>
                </div>
                <stat.icon className={`h-8 w-8 ${stat.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>CIBA Quota Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">
                  {stats.ciba_usage} / {stats.ciba_limit} requests/hour
                </span>
                <Badge variant={cibaPercent >= 80 ? "danger" : cibaPercent >= 50 ? "warning" : "success"}>
                  {cibaPercent}%
                </Badge>
              </div>
              <div className="w-full bg-zinc-100 rounded-full h-3">
                <div
                  className={`h-3 rounded-full transition-all ${
                    cibaPercent >= 80 ? "bg-red-500" : cibaPercent >= 50 ? "bg-yellow-500" : "bg-green-500"
                  }`}
                  style={{ width: `${Math.min(cibaPercent, 100)}%` }}
                />
              </div>
              <p className="text-xs text-zinc-400">
                Auth0 allows 500 CIBA requests/hour per tenant. Warning at 80%.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Security Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-zinc-100">
                <span className="text-sm text-zinc-600">HMAC Request Signing</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-100">
                <span className="text-sm text-zinc-600">Pydantic Validation</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-100">
                <span className="text-sm text-zinc-600">FGA Access Control</span>
                <Badge variant="success">Active</Badge>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-100">
                <span className="text-sm text-zinc-600">Scope Creep Detection</span>
                <Badge variant={stats.scope_creep_alerts > 0 ? "warning" : "success"}>
                  {stats.scope_creep_alerts > 0 ? `${stats.scope_creep_alerts} alerts` : "Clear"}
                </Badge>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-sm text-zinc-600">Token Isolation</span>
                <Badge variant="success">Enforced</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
