"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import dynamic from "next/dynamic";
const ApprovalFlow = dynamic(
  () => import("@/components/rule-graph/approval-flow").then((m) => m.ApprovalFlow),
  { ssr: false, loading: () => <div className="h-48 flex items-center justify-center text-sm text-zinc-400">Loading flow graph...</div> },
);
import { api } from "@/lib/api";
import type { Rule, Approver } from "@/types";
import { Pencil, Trash2, ArrowLeft } from "lucide-react";

const modelLabels: Record<string, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

export default function RuleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [rule, setRule] = useState<Rule | null>(null);
  const [approverNames, setApproverNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    const ruleId = params.id as string;
    Promise.all([
      api.getRule(ruleId),
      api.getApprovers(),
    ])
      .then(([ruleData, approvers]: [Rule, Approver[]]) => {
        setRule(ruleData);
        const names: Record<string, string> = {};
        for (const a of approvers) names[a.id] = a.name;
        setApproverNames(names);
      })
      .catch((err) => setError(err.message || "Failed to load rule"))
      .finally(() => setLoading(false));
  }, [params.id]);

  const handleDelete = async () => {
    if (!rule) return;
    if (!confirmDelete) { setConfirmDelete(true); return; }
    setDeleting(true);
    try {
      await api.deleteRule(rule.id);
      router.push("/rules");
    } catch (e: any) {
      setError(e.message || "Failed to delete rule");
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  const handleToggleActive = async () => {
    if (!rule) return;
    try {
      const updated = await api.updateRule(rule.id, { is_active: !rule.is_active });
      setRule(updated);
    } catch (e: any) {
      setError(e.message || "Failed to update rule");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (!rule) return <p>Rule not found</p>;

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 rounded-lg text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push("/rules")}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Rules
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{rule.name}</h1>
              <Badge variant={rule.is_active ? "success" : "default"}>
                {rule.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-zinc-500 dark:text-zinc-400 mt-1">
              {rule.connection}:{rule.action} — {modelLabels[rule.model]}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleToggleActive}>
            {rule.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/rules/${rule.id}/edit`)}
          >
            <Pencil className="h-4 w-4 mr-1" /> Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={confirmDelete ? "border-red-500 text-red-600 hover:bg-red-50 dark:bg-red-950/30" : ""}
            onClick={handleDelete}
            disabled={deleting}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            {deleting ? "Deleting…" : confirmDelete ? "Confirm Delete?" : "Delete"}
          </Button>
          {confirmDelete && (
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Approval Flow</CardTitle>
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
                  <dt className="text-zinc-500 dark:text-zinc-400">Model</dt>
                  <dd className="font-medium">{modelLabels[rule.model]}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Timeout</dt>
                  <dd className="font-medium">{rule.timeout_seconds}s</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">On Timeout</dt>
                  <dd className="font-medium capitalize">{rule.on_timeout}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Partial Approval</dt>
                  <dd className="font-medium">{rule.partial_approval ? "Enabled" : "Disabled"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-zinc-500 dark:text-zinc-400">Priority</dt>
                  <dd className="font-medium">{rule.priority}</dd>
                </div>
                {rule.cooldown_max && (
                  <div className="flex justify-between">
                    <dt className="text-zinc-500 dark:text-zinc-400">Cooldown</dt>
                    <dd className="font-medium">{rule.cooldown_max}/hour</dd>
                  </div>
                )}
                {rule.blackout_start && (
                  <div className="flex justify-between">
                    <dt className="text-zinc-500 dark:text-zinc-400">Blackout</dt>
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
                <p className="text-sm text-zinc-500 dark:text-zinc-400">No conditions — matches all requests</p>
              ) : (
                <div className="space-y-2">
                  {rule.conditions.map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {i > 0 && <Badge variant="default">AND</Badge>}
                      <code className="bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded text-xs">
                        {c.field} {c.operator} {String(c.value)}
                      </code>
                    </div>
                  ))}
                </div>
              )}
              {rule.context_template && (
                <div className="mt-4 p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                  <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Binding Message Template</p>
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
