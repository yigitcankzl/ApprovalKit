"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { Rule } from "@/types";
import { Plus, GitBranch, ArrowRight } from "lucide-react";

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

const modelColors: Record<string, "default" | "success" | "warning" | "danger" | "info"> = {
  any_one: "info",
  specific: "warning",
  all_of_n: "danger",
  k_of_n: "success",
  sequential: "default",
};

interface Approver { id: string; name: string; email: string; }

export default function RulesPage() {
  const [rules, setRules]       = useState<Rule[]>([]);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getRules(),
      api.getApprovers().catch(() => []),
    ])
      .then(([r, a]) => { setRules(r); setApprovers(a); })
      .catch((err) => setError(err.message || "Failed to load rules"))
      .finally(() => setLoading(false));
  }, []);

  const approverMap = Object.fromEntries(approvers.map((a) => [a.id, a]));

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Rules</h1>
          <p className="text-zinc-500 mt-1">
            Define approval workflows for each service action
          </p>
        </div>
        <Link href="/rules/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Rule
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <p className="text-red-500">{error}</p>
          </CardContent>
        </Card>
      ) : rules.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <GitBranch className="h-12 w-12 text-zinc-300 mb-4" />
            <h3 className="text-lg font-medium text-zinc-900">No rules yet</h3>
            <p className="text-zinc-500 mt-1">Create your first approval rule to get started</p>
            <Link href="/rules/new" className="mt-4">
              <Button>Create Rule</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => (
            <Link key={rule.id} href={`/rules/${rule.id}`}>
              <Card className="hover:border-zinc-300 transition-colors cursor-pointer mb-4">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-zinc-900">{rule.name}</h3>
                          {!rule.is_active && <Badge variant="default">Inactive</Badge>}
                        </div>
                        <p className="text-sm text-zinc-500 mt-1">
                          {rule.connection}:{rule.action}
                          {rule.conditions.length > 0 && (
                            <span className="ml-2">
                              ({rule.conditions.length} condition{rule.conditions.length > 1 ? "s" : ""})
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant={modelColors[rule.model]}>
                        {modelLabels[rule.model]}
                        {rule.model === "k_of_n" && rule.k_value && ` (${rule.k_value}/${rule.approver_ids.length})`}
                      </Badge>
                      {rule.on_timeout === "escalate" && <Badge variant="warning">Escalation</Badge>}
                      {rule.blackout_start && <Badge variant="danger">Blackout</Badge>}
                      <ArrowRight className="h-4 w-4 text-zinc-400" />
                    </div>
                  </div>

                  {/* Trust Chain */}
                  {rule.approver_ids.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-zinc-100">
                      <p className="text-xs text-zinc-400 mb-2 uppercase tracking-wide">
                        {rule.model === "sequential" ? "Approval chain" : "Approvers"} · FGA controlled
                      </p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="text-xs bg-zinc-100 text-zinc-600 px-2 py-0.5 rounded font-mono">
                          {rule.connection}:{rule.action}
                        </code>
                        {rule.approver_ids.map((id, idx) => {
                          const a = approverMap[id];
                          return (
                            <div key={id} className="flex items-center gap-1">
                              <span className="text-zinc-300 text-xs">→</span>
                              <span className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded">
                                {a ? a.name : `Approver ${idx + 1}`}
                              </span>
                            </div>
                          );
                        })}
                        <span className="text-zinc-300 text-xs">→</span>
                        <span className="text-xs bg-green-50 border border-green-200 text-green-700 px-2 py-0.5 rounded">
                          Auth0 Token Vault
                        </span>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
