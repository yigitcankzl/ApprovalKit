"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ApprovalFlow } from "@/components/rule-graph/approval-flow";
import { api } from "@/lib/api";
import type { Rule } from "@/types";

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

export default function RuleDetailPage() {
  const params = useParams();
  const [rule, setRule] = useState<Rule | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ruleId = params.id as string;
    api
      .getRule(ruleId)
      .then(setRule)
      .catch(() => {
        setRule({
          id: ruleId,
          name: "High-value Stripe charges",
          connection: "stripe-prod",
          action: "charge",
          conditions: [{ field: "amount", operator: "gt", value: 100 }],
          model: "sequential",
          approver_ids: ["a1", "a2"],
          k_value: null,
          timeout_seconds: 300,
          on_timeout: "escalate",
          escalate_to: "a3",
          cooldown_max: null,
          blackout_start: null,
          blackout_end: null,
          pre_approval: null,
          context_template: "Charge of ${{amount}} for {{customer}}",
          partial_approval: true,
          quorum_window: null,
          priority: 10,
          is_active: true,
          created_at: "2026-03-20T10:00:00Z",
          updated_at: "2026-03-20T10:00:00Z",
        });
      })
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
      </div>
    );
  }

  if (!rule) return <p>Rule not found</p>;

  const approverNames: Record<string, string> = {
    a1: "CFO",
    a2: "Finance Lead",
    a3: "CEO",
  };

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-zinc-900">{rule.name}</h1>
            <Badge variant={rule.is_active ? "success" : "default"}>
              {rule.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          <p className="text-zinc-500 mt-1">
            {rule.connection}:{rule.action} — {modelLabels[rule.model]}
          </p>
        </div>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Approval Flow Graph</CardTitle>
          </CardHeader>
          <CardContent>
            <ApprovalFlow rule={rule} approverNames={approverNames} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-zinc-500">Model</dt>
                  <dd className="font-medium">{modelLabels[rule.model]}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500">Timeout</dt>
                  <dd className="font-medium">{rule.timeout_seconds}s</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500">On Timeout</dt>
                  <dd className="font-medium capitalize">{rule.on_timeout}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500">Partial Approval</dt>
                  <dd className="font-medium">{rule.partial_approval ? "Enabled" : "Disabled"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500">Priority</dt>
                  <dd className="font-medium">{rule.priority}</dd>
                </div>
                {rule.cooldown_max && (
                  <div className="flex justify-between">
                    <dt className="text-zinc-500">Cooldown</dt>
                    <dd className="font-medium">{rule.cooldown_max}/hour</dd>
                  </div>
                )}
                {rule.blackout_start && (
                  <div className="flex justify-between">
                    <dt className="text-zinc-500">Blackout</dt>
                    <dd className="font-medium">{rule.blackout_start} - {rule.blackout_end}</dd>
                  </div>
                )}
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Conditions</CardTitle>
            </CardHeader>
            <CardContent>
              {rule.conditions.length === 0 ? (
                <p className="text-sm text-zinc-500">No conditions — matches all requests</p>
              ) : (
                <div className="space-y-2">
                  {rule.conditions.map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {i > 0 && <Badge variant="default">AND</Badge>}
                      <code className="bg-zinc-100 px-2 py-1 rounded text-xs">
                        {c.field} {c.operator} {String(c.value)}
                      </code>
                    </div>
                  ))}
                </div>
              )}
              {rule.context_template && (
                <div className="mt-4 p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs font-medium text-zinc-500">Binding Message Template</p>
                  <p className="text-sm mt-1">{rule.context_template}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
