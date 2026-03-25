"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConditionBuilder } from "@/components/rule-builder/condition-builder";
import { LivePreview } from "@/components/rule-builder/live-preview";
import { api } from "@/lib/api";
import type { ApprovalModel, Approver, Condition, TimeoutAction } from "@/types";
import { Save } from "lucide-react";
import { FormError } from "@/components/ui/form-error";

const services = [
  { value: "stripe-prod", label: "Stripe (Production)" },
  { value: "github-main", label: "GitHub (Main)" },
  { value: "npm-registry", label: "NPM Registry" },
  { value: "gmail", label: "Gmail" },
  { value: "slack", label: "Slack" },
  { value: "salesforce", label: "Salesforce" },
  { value: "aws", label: "AWS" },
];

const actions: Record<string, string[]> = {
  "stripe-prod": ["charge", "refund", "payout", "create_customer"],
  "github-main": ["merge_pr", "deploy", "publish_release", "delete_branch"],
  "npm-registry": ["publish", "deprecate", "unpublish"],
  gmail: ["send_email", "delete_email", "share_drive"],
  slack: ["send_message", "create_channel", "invite_user"],
  salesforce: ["create_deal", "update_contact", "delete_lead"],
  aws: ["launch_instance", "terminate_instance", "create_bucket"],
};

export default function NewRulePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [selectedApproverIds, setSelectedApproverIds] = useState<string[]>([]);

  useEffect(() => {
    api.getApprovers().then(setApprovers).catch(() => {});
  }, []);

  const toggleApprover = (id: string) => {
    setSelectedApproverIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

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
  const [cooldownMax, setCooldownMax] = useState<string>("");
  const [quorumWindow, setQuorumWindow] = useState<string>("");
  const [priority, setPriority] = useState(0);
  const [escalateTo, setEscalateTo] = useState("");
  const [stepUpEnabled, setStepUpEnabled] = useState(false);
  const [stepUpModel, setStepUpModel] = useState<ApprovalModel>("all_of_n");
  const [stepUpConditions, setStepUpConditions] = useState<Condition[]>([]);

  const availableActions = actions[connection] || [];

  const handleSave = async () => {
    setSaveError(null);
    if (!name.trim()) { setSaveError("Rule name is required."); return; }
    if (!connection) { setSaveError("Service connection is required."); return; }
    if (!action) { setSaveError("Action is required."); return; }
    if (selectedApproverIds.length === 0) {
      setSaveError("At least one approver must be selected.");
      return;
    }
    setSaving(true);
    try {
      const data = {
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
        step_up_model: stepUpEnabled ? stepUpModel : null,
        step_up_conditions: stepUpEnabled ? stepUpConditions : [],
      };
      await api.createRule(data);
      router.push("/rules");
    } catch (error: any) {
      setSaveError(error.message || "Failed to save rule");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Create Rule</h1>
        <p className="text-zinc-500 mt-1">Define an approval workflow for a service action</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-zinc-700">Rule Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. High-value Stripe charges" className="mt-1" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Service</label>
                  <Select value={connection} onChange={(e) => { setConnection(e.target.value); setAction(""); }} className="mt-1">
                    <option value="">Select service...</option>
                    {services.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">Action</label>
                  <Select value={action} onChange={(e) => setAction(e.target.value)} className="mt-1">
                    <option value="">Select action...</option>
                    {availableActions.map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Priority</label>
                <Input type="number" min={0} max={100} value={priority} onChange={(e) => setPriority(parseInt(e.target.value) || 0)} className="mt-1 w-32" />
              </div>
            </CardContent>
          </Card>

          {/* Conditions */}
          <Card>
            <CardHeader>
              <CardTitle>Trigger Conditions</CardTitle>
            </CardHeader>
            <CardContent>
              <ConditionBuilder conditions={conditions} onChange={setConditions} />
            </CardContent>
          </Card>

          {/* Approval Model */}
          <Card>
            <CardHeader>
              <CardTitle>Approval Model</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select value={model} onChange={(e) => setModel(e.target.value as ApprovalModel)}>
                <option value="any_one">Any One — first approval from any listed approver</option>
                <option value="specific">Specific — only designated person can approve</option>
                <option value="all_of_n">All of N — every approver must approve</option>
                <option value="k_of_n">K of N — k approvers must approve within quorum</option>
                <option value="sequential">Sequential — ordered chain, each must approve</option>
              </Select>
              {model === "k_of_n" && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-zinc-600">Required approvals (k):</label>
                  <Input type="number" min={1} value={kValue} onChange={(e) => setKValue(parseInt(e.target.value) || 1)} className="w-20" />
                </div>
              )}
              {model === "k_of_n" && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-zinc-600">Quorum window (seconds):</label>
                  <Input type="number" value={quorumWindow} onChange={(e) => setQuorumWindow(e.target.value)} placeholder="3600" className="w-32" />
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-zinc-700">Approvers</label>
                {approvers.length === 0 ? (
                  <p className="text-sm text-zinc-400 mt-2">
                    No approvers found.{" "}
                    <a href="/approvers" className="text-blue-600 underline">Add approvers first.</a>
                  </p>
                ) : (
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
                        {a.delegate_to && (
                          <span className="text-xs text-orange-500 ml-auto">delegated</span>
                        )}
                      </label>
                    ))}
                  </div>
                )}
                {selectedApproverIds.length > 0 && (
                  <p className="text-xs text-zinc-500 mt-1">{selectedApproverIds.length} approver{selectedApproverIds.length > 1 ? "s" : ""} selected</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Step-up Authentication */}
          <Card>
            <CardHeader>
              <CardTitle>Step-up Authentication</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                <input type="checkbox" id="stepUp" checked={stepUpEnabled} onChange={(e) => setStepUpEnabled(e.target.checked)} className="rounded border-zinc-300" />
                <label htmlFor="stepUp" className="text-sm text-zinc-700">Enable step-up for high-value requests</label>
              </div>
              {stepUpEnabled && (
                <>
                  <p className="text-xs text-zinc-500">
                    When request parameters match these conditions, the approval model escalates automatically.
                  </p>
                  <div>
                    <label className="text-sm font-medium text-zinc-700">Step-up Conditions</label>
                    <ConditionBuilder conditions={stepUpConditions} onChange={setStepUpConditions} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-zinc-700">Escalate to Model</label>
                    <Select value={stepUpModel} onChange={(e) => setStepUpModel(e.target.value as ApprovalModel)} className="mt-1">
                      <option value="any_one">Any One</option>
                      <option value="specific">Specific</option>
                      <option value="all_of_n">All of N</option>
                      <option value="k_of_n">K of N</option>
                      <option value="sequential">Sequential</option>
                    </Select>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Advanced Options */}
          <Card>
            <CardHeader>
              <CardTitle>Advanced Options</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700">Timeout (seconds)</label>
                  <Input type="number" min={30} max={3600} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(parseInt(e.target.value) || 300)} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700">On Timeout</label>
                  <Select value={onTimeout} onChange={(e) => setOnTimeout(e.target.value as TimeoutAction)} className="mt-1">
                    <option value="block">Block — permanently cancel</option>
                    <option value="escalate">Escalate — send to backup approver</option>
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
                <label className="text-sm font-medium text-zinc-700">Cooldown (max triggers/hour)</label>
                <Input type="number" value={cooldownMax} onChange={(e) => setCooldownMax(e.target.value)} placeholder="No limit" className="mt-1 w-32" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="partial" checked={partialApproval} onChange={(e) => setPartialApproval(e.target.checked)} className="rounded border-zinc-300" />
                <label htmlFor="partial" className="text-sm text-zinc-700">Allow partial approval (approver can modify params)</label>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Context Template (binding message)</label>
                <Input value={contextTemplate} onChange={(e) => setContextTemplate(e.target.value)} placeholder="Charge of ${{amount}} for {{customer}}" className="mt-1" />
                <p className="text-xs text-zinc-400 mt-1">Use {"{{variable}}"} for dynamic values from params</p>
              </div>
            </CardContent>
          </Card>

          <FormError message={saveError} />
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => router.push("/rules")}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !name || !connection || !action || selectedApproverIds.length === 0}>
              <Save className="h-4 w-4 mr-2" />
              {saving ? "Saving..." : "Save Rule"}
            </Button>
          </div>
        </div>

        {/* Live Preview */}
        <div>
          <LivePreview
            connection={connection}
            action={action}
            conditions={conditions}
            model={model}
            approverCount={selectedApproverIds.length || approvers.length}
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
