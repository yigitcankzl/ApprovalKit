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

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getRules()
      .then(setRules)
      .catch((err) => setError(err.message || "Failed to load rules"))
      .finally(() => setLoading(false));
  }, []);

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
                      <span className="text-sm text-zinc-400">
                        {rule.approver_ids.length} approver{rule.approver_ids.length > 1 ? "s" : ""}
                      </span>
                      {rule.on_timeout === "escalate" && (
                        <Badge variant="warning">Escalation</Badge>
                      )}
                      {rule.blackout_start && (
                        <Badge variant="danger">Blackout</Badge>
                      )}
                      <ArrowRight className="h-4 w-4 text-zinc-400" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
