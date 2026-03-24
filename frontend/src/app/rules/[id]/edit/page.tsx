"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConditionBuilder } from "@/components/rule-builder/condition-builder";
import { LivePreview } from "@/components/rule-builder/live-preview";
import { api } from "@/lib/api";
import type { ApprovalModel, Approver, Condition, TimeoutAction, Rule } from "@/types";
import { Save, ArrowLeft } from "lucide-react";

const services = [
  { value: "stripe-prod", label: "Stripe (Production)" },
  { value: "github-main", label: "GitHub (Main)" },
  { value: "npm-registry", label: "NPM Registry" },
  { value: "gmail", label: "Gmail" },
  { value: "slack", label: "Slack" },
  { value: "salesforce", label: "Salesforce" },
  { value: "aws", label: "AWS" },
];

const actionOptions: Record<string, string[]> = {
  "stripe-prod": ["charge", "refund", "payout", "create_customer"],
  "github-main": ["merge_pr", "deploy", "publish_release", "delete_branch"],
  "npm-registry": ["publish", "deprecate", "unpublish"],
  gmail: ["send_email", "delete_email", "share_drive"],
  slack: ["send_message", "create_channel", "invite_user"],
  salesforce: ["create_deal", "update_contact", "delete_lead"],
  aws: ["launch_instance", "terminate_instance", "create_bucket"],
};

export default function EditRulePage() {
  const params = useParams();
  const router = useRouter();
  const ruleId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [approvers, setApprovers] = useState<Approver[]>([]);

  const [name, setName] = useState("");
  const [connection, setConnection] = useState("");
  const [action, setAction] = useState("");
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [model, setModel] = useState<ApprovalModel>("any_one");
  const [kValue, setKValue] = useState(2);
  const [timeoutSeconds, setTimeoutSeconds] = useState(300);
  const [onTimeout, setOnTimeout] = useState<TimeoutAction>("block");
  const [partialApproval, setPartialApproval] = useState(false);
  const [contextTemplate, setContextTemplate] = useState("");
  const [blackoutStart, setBlackoutStart] = useState("");
  const [blackoutEnd, setBlackoutEnd] = useState("");
  const [cooldownMax, setCooldownMax] = useState("");
  const [quorumWindow, setQuorumWindow] = useState("");
  const [priority, setPriority] = useState(0);
  const [escalateTo, setEscalateTo] = useState("");
  const [selectedApproverIds, setSelectedApproverIds] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([api.getRule(ruleId), api.getApprovers()])
      .then(([rule, allApprovers]: [Rule, Approver[]]) => {
        setApprovers(allApprovers);
        setName(rule.name);
        setConnection(rule.connection);
        setAction(rule.action);
        setConditions(rule.conditions);
        setModel(rule.model);
        setKValue(rule.k_value ?? 2);
        setTimeoutSeconds(rule.timeout_seconds);
        setOnTimeout(rule.on_timeout);
        setPartialApproval(rule.partial_approval);
        setContextTemplate(rule.context_template ?? "");
        setBlackoutStart(rule.blackout_start ?? "");
        setBlackoutEnd(rule.blackout_end ?? "");
        setCooldownMax(rule.cooldown_max !== null ? String(rule.cooldown_max) : "");
        setQuorumWindow(rule.quorum_window !== null ? String(rule.quorum_window) : "");
        setPriority(rule.priority);
        setEscalateTo(rule.escalate_to ?? "");
        setSelectedApproverIds(rule.approver_ids);
      })
      .catch((e) => setLoadError(e.message || "Failed to load rule"))
      .finally(() => setLoading(false));
  }, [ruleId]);

  const toggleApprover = (id: string) => {
    setSelectedApproverIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSave = async () => {
    setSaveError(null);
    if (selectedApproverIds.length === 0) {
      setSaveError("At least one approver must be selected.");
      return;
    }
    setSaving(true);
    try {
      await api.updateRule(ruleId, {
        name,
        connection,
        action,
        conditions,
        model,
        approver_ids: selectedApproverIds,
        k_value: model === "k_of_n" ? kValue : null,
        timeout_seconds: timeoutSeconds,
        on_timeout: onTimeout,
        escalate_to: onTimeout === "escalate" ? (escalateTo || null) : null,
        partial_approval: partialApproval,
        context_template: contextTemplate || null,
        blackout_start: blackoutStart || null,
        blackout_end: blackoutEnd || null,
        cooldown_max: cooldownMax ? parseInt(cooldownMax) : null,
        quorum_window: quorumWindow ? parseInt(quorumWindow) : null,
        priority,
      });
      router.push(`/rules/${ruleId}`);
    } catch (e: any) {
      setSaveError(e.message || "Failed to save rule");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500">{loadError}</p>
      </div>
    );
  }

  const availableActions = actionOptions[connection] || (action ? [action] : []);

  return (
    <div>
      <div className="mb-8 flex items-center gap-4">
        <Button variant="outline" size="sm" onClick={() => router.push(`/rules/${ruleId}`)}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Edit Rule</h1>
          <p className="text-zinc-500 mt-1">Modify approval workflow</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader><CardTitle>Basic Info</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-zinc-700">Rule Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Service</label>
                  <Select value={connection} onChange={(e) => { setConnection(e.target.value); }} className="mt-1">
                    <option value="">Select service...</option>
                    {services.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    {!services.find(s => s.value === connection) && connection && (
                      <option value={connection}>{connection}</option>
                    )}
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">Action</label>
                  <Select value={action} onChange={(e) => setAction(e.target.value)} className="mt-1">
                    <option value="">Select action...</option>
                    {availableActions.map((a) => <option key={a} value={a}>{a}</option>)}
                    {!availableActions.includes(action) && action && (
                      <option value={action}>{action}</option>
                    )}
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Priority</label>
                <Input type="number" min={0} max={100} value={priority} onChange={(e) => setPriority(parseInt(e.target.value) || 0)} className="mt-1 w-32" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Trigger Conditions</CardTitle></CardHeader>
            <CardContent>
              <ConditionBuilder conditions={conditions} onChange={setConditions} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Approval Model</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Select value={model} onChange={(e) => setModel(e.target.value as ApprovalModel)}>
                <option value="any_one">Any One</option>
                <option value="specific">Specific</option>
                <option value="all_of_n">All of N</option>
                <option value="k_of_n">K of N</option>
                <option value="sequential">Sequential</option>
              </Select>
              {model === "k_of_n" && (
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-zinc-600">k:</label>
                    <Input type="number" min={1} value={kValue} onChange={(e) => setKValue(parseInt(e.target.value) || 1)} className="w-20" />
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm text-zinc-600">Quorum window (s):</label>
                    <Input type="number" value={quorumWindow} onChange={(e) => setQuorumWindow(e.target.value)} placeholder="3600" className="w-32" />
                  </div>
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-zinc-700">Approvers</label>
                <div className="mt-2 space-y-2 max-h-48 overflow-y-auto border border-zinc-200 rounded-lg p-3">
                  {approvers.map((a) => (
                    <label key={a.id} className="flex items-center gap-3 cursor-pointer hover:bg-zinc-50 rounded px-1 py-0.5">
                      <input
                        type="checkbox"
                        checked={selectedApproverIds.includes(a.id)}
                        onChange={() => toggleApprover(a.id)}
                        className="rounded border-zinc-300"
                      />
                      <span className="text-sm font-medium text-zinc-800">{a.name}</span>
                      <span className="text-xs text-zinc-400">{a.email}</span>
                    </label>
                  ))}
                </div>
                <p className="text-xs text-zinc-500 mt-1">{selectedApproverIds.length} selected</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Advanced Options</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Timeout (s)</label>
                  <Input type="number" min={30} max={3600} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(parseInt(e.target.value) || 300)} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">On Timeout</label>
                  <Select value={onTimeout} onChange={(e) => setOnTimeout(e.target.value as TimeoutAction)} className="mt-1">
                    <option value="block">Block</option>
                    <option value="escalate">Escalate</option>
                  </Select>
                </div>
              </div>
              {onTimeout === "escalate" && (
                <div>
                  <label className="text-sm font-medium text-zinc-700">Escalation Approver</label>
                  <Select value={escalateTo} onChange={(e) => setEscalateTo(e.target.value)} className="mt-1">
                    <option value="">Select escalation approver...</option>
                    {approvers.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </Select>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Blackout Start</label>
                  <Input type="time" value={blackoutStart} onChange={(e) => setBlackoutStart(e.target.value)} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">Blackout End</label>
                  <Input type="time" value={blackoutEnd} onChange={(e) => setBlackoutEnd(e.target.value)} className="mt-1" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Cooldown (max/hour)</label>
                <Input type="number" value={cooldownMax} onChange={(e) => setCooldownMax(e.target.value)} placeholder="No limit" className="mt-1 w-32" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="partial" checked={partialApproval} onChange={(e) => setPartialApproval(e.target.checked)} className="rounded border-zinc-300" />
                <label htmlFor="partial" className="text-sm text-zinc-700">Allow partial approval</label>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Context Template</label>
                <Input value={contextTemplate} onChange={(e) => setContextTemplate(e.target.value)} placeholder='Charge of ${{amount}} for {{customer}}' className="mt-1" />
              </div>
            </CardContent>
          </Card>

          {saveError && <p className="text-sm text-red-500 text-right">{saveError}</p>}
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => router.push(`/rules/${ruleId}`)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !name || !connection || !action}>
              <Save className="h-4 w-4 mr-2" />
              {saving ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </div>

        <div>
          <LivePreview
            connection={connection}
            action={action}
            conditions={conditions}
            model={model}
            approverCount={selectedApproverIds.length}
            kValue={kValue}
            timeoutSeconds={timeoutSeconds}
            onTimeout={onTimeout}
            escalateTo={escalateTo || undefined}
            partialApproval={partialApproval}
            contextTemplate={contextTemplate}
            blackoutStart={blackoutStart}
            blackoutEnd={blackoutEnd}
          />
        </div>
      </div>
    </div>
  );
}
