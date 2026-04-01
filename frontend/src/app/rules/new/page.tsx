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
import { Save, Zap, Gauge, Clock, Bot, Send, X, Sparkles, ChevronUp, ChevronDown } from "lucide-react";
import { FormError } from "@/components/ui/form-error";
import { useSearchParams } from "next/navigation";

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
  const searchParams = useSearchParams();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [selectedApproverIds, setSelectedApproverIds] = useState<string[]>([]);

  useEffect(() => {
    api.getApprovers().then(setApprovers).catch(() => { });
  }, []);

  // Load template from URL param
  useEffect(() => {
    const tplId = searchParams.get("template");
    if (!tplId) return;
    fetch(`/api/v1/rules/templates/${tplId}`)
      .then(r => r.ok ? r.json() : null)
      .then(tpl => {
        if (!tpl) return;
        setName(tpl.name);
        setConnection(tpl.connection || "");
        setAction(tpl.action || "");
        setConditions(tpl.conditions || []);
        setModel(tpl.model || "any_one");
        setTimeoutSeconds(tpl.timeout_seconds || 300);
        setOnTimeout(tpl.on_timeout || "block");
        setContextTemplate(tpl.context_template || "");
        setMaxRequestsPerHour(tpl.max_requests_per_hour?.toString() || "");
        setApprovalExpiry(tpl.approval_expiry_seconds?.toString() || "");
        if (tpl.blackout_start) setBlackoutStart(tpl.blackout_start);
        if (tpl.blackout_end) setBlackoutEnd(tpl.blackout_end);
        if (tpl.step_up_model) { setStepUpEnabled(true); setStepUpModel(tpl.step_up_model); }
        if (tpl.step_up_conditions) setStepUpConditions(tpl.step_up_conditions);
        if (tpl.trigger_rules) setTriggerRules(JSON.stringify(tpl.trigger_rules, null, 2));
      })
      .catch(() => { });
  }, [searchParams]);

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
  const [maxRequestsPerHour, setMaxRequestsPerHour] = useState<string>("");
  const [approvalExpiry, setApprovalExpiry] = useState<string>("");
  const [triggerRules, setTriggerRules] = useState<string>("");

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
        max_requests_per_hour: maxRequestsPerHour ? parseInt(maxRequestsPerHour) : null,
        approval_expiry_seconds: approvalExpiry ? parseInt(approvalExpiry) : null,
        trigger_rules: triggerRules ? JSON.parse(triggerRules) : null,
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
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Create Rule</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">Define an approval workflow for a service action</p>
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
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Rule Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. High-value Stripe charges" className="mt-1" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Service</label>
                  <Select value={connection} onChange={(e) => { setConnection(e.target.value); setAction(""); }} className="mt-1">
                    <option value="">Select service...</option>
                    {services.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </Select>
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Action</label>
                  <Select value={action} onChange={(e) => setAction(e.target.value)} className="mt-1">
                    <option value="">Select action...</option>
                    {availableActions.map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Priority</label>
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
                  <label className="text-sm text-zinc-600 dark:text-zinc-400">Required approvals (k):</label>
                  <Input type="number" min={1} value={kValue} onChange={(e) => setKValue(parseInt(e.target.value) || 1)} className="w-20" />
                </div>
              )}
              {model === "k_of_n" && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-zinc-600 dark:text-zinc-400">Quorum window (seconds):</label>
                  <Input type="number" value={quorumWindow} onChange={(e) => setQuorumWindow(e.target.value)} placeholder="3600" className="w-32" />
                </div>
              )}
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Approvers</label>
                {approvers.length === 0 ? (
                  <p className="text-sm text-zinc-400 mt-2">
                    No approvers found.{" "}
                    <a href="/approvers" className="text-blue-600 underline">Add approvers first.</a>
                  </p>
                ) : (
                  <div className="mt-2 space-y-2 max-h-48 overflow-y-auto border border-zinc-200 dark:border-zinc-700 rounded-lg p-3">
                    {approvers.map((a) => (
                      <label key={a.id} className="flex items-center gap-3 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800 dark:bg-zinc-800/50 rounded px-1 py-0.5">
                        <input
                          type="checkbox"
                          checked={selectedApproverIds.includes(a.id)}
                          onChange={() => toggleApprover(a.id)}
                          className="rounded border-zinc-300 dark:border-zinc-600"
                        />
                        <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{a.name}</span>
                        <span className="text-xs text-zinc-400">{a.email}</span>
                        {a.delegate_to && (
                          <span className="text-xs text-orange-500 ml-auto">delegated</span>
                        )}
                      </label>
                    ))}
                  </div>
                )}
                {selectedApproverIds.length > 0 && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{selectedApproverIds.length} approver{selectedApproverIds.length > 1 ? "s" : ""} selected</p>
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
                <input type="checkbox" id="stepUp" checked={stepUpEnabled} onChange={(e) => setStepUpEnabled(e.target.checked)} className="rounded border-zinc-300 dark:border-zinc-600" />
                <label htmlFor="stepUp" className="text-sm text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Enable step-up for high-value requests</label>
              </div>
              {stepUpEnabled && (
                <>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    When request parameters match these conditions, the approval model escalates automatically.
                  </p>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Step-up Conditions</label>
                    <ConditionBuilder conditions={stepUpConditions} onChange={setStepUpConditions} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Escalate to Model</label>
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
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Timeout (seconds)</label>
                  <Input type="number" min={30} max={3600} value={timeoutSeconds} onChange={(e) => setTimeoutSeconds(parseInt(e.target.value) || 300)} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">On Timeout</label>
                  <Select value={onTimeout} onChange={(e) => setOnTimeout(e.target.value as TimeoutAction)} className="mt-1">
                    <option value="block">Block — permanently cancel</option>
                    <option value="escalate">Escalate — send to backup approver</option>
                  </Select>
                </div>
              </div>
              {onTimeout === "escalate" && (
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Escalation Approver</label>
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
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Blackout Start</label>
                  <Input type="time" value={blackoutStart} onChange={(e) => setBlackoutStart(e.target.value)} className="mt-1" />
                </div>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Blackout End</label>
                  <Input type="time" value={blackoutEnd} onChange={(e) => setBlackoutEnd(e.target.value)} className="mt-1" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Cooldown (max triggers/hour)</label>
                <Input type="number" value={cooldownMax} onChange={(e) => setCooldownMax(e.target.value)} placeholder="No limit" className="mt-1 w-32" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="partial" checked={partialApproval} onChange={(e) => setPartialApproval(e.target.checked)} className="rounded border-zinc-300 dark:border-zinc-600" />
                <label htmlFor="partial" className="text-sm text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Allow partial approval (approver can modify params)</label>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Context Template (binding message)</label>
                <Input value={contextTemplate} onChange={(e) => setContextTemplate(e.target.value)} placeholder="Charge of ${{amount}} for {{customer}}" className="mt-1" />
                <p className="text-xs text-zinc-400 mt-1">Use {"{{variable}}"} for dynamic values from params</p>
              </div>

              {/* ─── New: Rate Limiting ─── */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4 mt-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                  <Gauge className="h-3.5 w-3.5" /> Agent Rate Limiting
                </p>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Max requests per hour</label>
                  <Input type="number" min={1} max={10000} value={maxRequestsPerHour} onChange={(e) => setMaxRequestsPerHour(e.target.value)} placeholder="Unlimited" className="mt-1 w-40" />
                  <p className="text-xs text-zinc-400 mt-1">Per-agent hourly limit for this connection. Leave empty for unlimited.</p>
                </div>
              </div>

              {/* ─── New: Approval Expiry ─── */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Approval Expiry
                </p>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Expiry time (seconds)</label>
                  <Input type="number" min={60} max={86400} value={approvalExpiry} onChange={(e) => setApprovalExpiry(e.target.value)} placeholder="No expiry" className="mt-1 w-40" />
                  <p className="text-xs text-zinc-400 mt-1">Approved decisions expire if not executed within this window.</p>
                </div>
              </div>

              {/* ─── New: Rule Chaining ─── */}
              <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                  <Zap className="h-3.5 w-3.5" /> Rule Chaining
                </p>
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Trigger actions on approval (JSON)</label>
                  <textarea
                    value={triggerRules}
                    onChange={(e) => setTriggerRules(e.target.value)}
                    placeholder='[{"connection": "slack", "action": "send_message", "params": {"text": "Approved!"}}]'
                    className="mt-1 w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-mono text-zinc-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px]"
                    rows={3}
                  />
                  <p className="text-xs text-zinc-400 mt-1">After this rule is approved, automatically trigger these actions via Token Vault.</p>
                </div>
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

      {/* AI Rule Assistant */}
      <RuleAssistant onApplyRule={(rule) => {
        if (rule.name) setName(rule.name);
        if (rule.connection) setConnection(rule.connection);
        if (rule.action) setAction(rule.action);
        if (rule.model) setModel(rule.model as ApprovalModel);
        if (rule.conditions) {
          // Normalize conditions: ensure value is correct type
          const normalized = rule.conditions.map((c: any) => ({
            field: c.field || "",
            operator: c.operator || "eq",
            value: typeof c.value === "string" && !isNaN(Number(c.value)) ? Number(c.value) : c.value,
          }));
          setConditions(normalized);
        }
        if (rule.context_template) setContextTemplate(rule.context_template);
        if (rule.timeout_seconds) setTimeoutSeconds(Number(rule.timeout_seconds));
        if (rule.on_timeout) setOnTimeout(rule.on_timeout as TimeoutAction);
        if (rule.step_up_model) { setStepUpEnabled(true); setStepUpModel(rule.step_up_model as ApprovalModel); }
        if (rule.step_up_conditions) setStepUpConditions(rule.step_up_conditions);
        if (rule.max_requests_per_hour) setMaxRequestsPerHour(String(rule.max_requests_per_hour));
        if (rule.approval_expiry_seconds) setApprovalExpiry(String(rule.approval_expiry_seconds));
        if (rule.blackout_start) setBlackoutStart(rule.blackout_start);
        if (rule.blackout_end) setBlackoutEnd(rule.blackout_end);
      }} />
    </div>
  );
}

function RuleAssistant({ onApplyRule }: { onApplyRule: (rule: any) => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRule, setLastRule] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  const extractRule = (text: string): any | null => {
    const jsonMatch = text.match(/```json\n?([\s\S]*?)```/);
    if (jsonMatch) {
      try { return JSON.parse(jsonMatch[1]); } catch {}
    }
    return null;
  };

  const saveRuleDirect = async (rule: any) => {
    setSaving(true);
    try {
      await api.createRule({
        name: rule.name || "AI-Generated Rule",
        connection: rule.connection,
        action: rule.action,
        model: rule.model || "any_one",
        conditions: rule.conditions || [],
        approver_ids: [],
        timeout_seconds: rule.timeout_seconds || 300,
        on_timeout: rule.on_timeout || "block",
        context_template: rule.context_template || "",
        step_up_model: rule.step_up_model || null,
        step_up_conditions: rule.step_up_conditions || [],
        max_requests_per_hour: rule.max_requests_per_hour || null,
        approval_expiry_seconds: rule.approval_expiry_seconds || null,
        blackout_start: rule.blackout_start || null,
        blackout_end: rule.blackout_end || null,
      });
      setMessages(prev => [...prev, { role: "assistant", content: `✅ Rule "${rule.name}" saved successfully! Redirecting to rules list...` }]);
      setTimeout(() => router.push("/rules"), 1500);
    } catch (e: any) {
      setMessages(prev => [...prev, { role: "assistant", content: `❌ Failed to save: ${e.message}` }]);
    }
    setSaving(false);
  };

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const res = await api.ruleAssistant(userMsg, messages);
      const reply = res.response || "Sorry, I could not process that.";
      setMessages(prev => [...prev, { role: "assistant", content: reply }]);

      const rule = extractRule(reply);
      if (rule && (rule.name || rule.connection)) {
        setLastRule(rule);
        // Don't auto-apply — user clicks "Apply to Form" or "Save Rule" button
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${e.message}` }]);
    }
    setLoading(false);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-2xl bg-gradient-to-r from-purple-600 to-blue-500 text-white shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all text-sm font-semibold"
      >
        <Sparkles className="h-4 w-4" />
        AI Rule Assistant
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 rounded-2xl border border-purple-200 dark:border-purple-800 bg-white dark:bg-zinc-900 shadow-2xl flex flex-col" style={{ maxHeight: "500px" }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 rounded-t-2xl">
        <Bot className="h-5 w-5 text-purple-600 dark:text-purple-400" />
        <span className="text-sm font-semibold text-purple-800 dark:text-purple-200 flex-1">AI Rule Assistant</span>
        <button onClick={() => setOpen(false)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3" style={{ maxHeight: "350px" }}>
        {messages.length === 0 && (
          <div className="text-center py-6 space-y-2">
            <Sparkles className="h-8 w-8 text-purple-300 mx-auto" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Describe the rule you need</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {[
                "Block charges over $10K",
                "Require CFO for deployments",
                "Auto-approve Slack messages",
                "Step-up auth for refunds over $500",
              ].map(s => (
                <button key={s} onClick={() => setInput(s)} className="text-[10px] px-2 py-1 rounded-full border border-purple-200 dark:border-purple-800 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/20">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => {
          const rule = msg.role === "assistant" ? extractRule(msg.content) : null;
          return (
          <div key={i}>
            <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-purple-600 text-white"
                  : "bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200"
              }`}>
                <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed">{msg.content}</pre>
              </div>
            </div>
            {rule && (
              <div className="flex gap-2 mt-1.5 ml-1">
                <button onClick={() => onApplyRule(rule)} className="text-[10px] px-2.5 py-1 rounded-md border border-purple-300 dark:border-purple-700 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/20 font-medium">
                  Apply to Form
                </button>
                <button onClick={() => saveRuleDirect(rule)} disabled={saving} className="text-[10px] px-2.5 py-1 rounded-md bg-purple-600 text-white hover:bg-purple-700 font-medium disabled:opacity-50">
                  {saving ? "Saving..." : "Save Rule Directly"}
                </button>
              </div>
            )}
          </div>
          );
        })}
        {loading && (
          <div className="flex items-center gap-2 text-purple-500 text-xs">
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-purple-500" />
            Thinking...
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={(e) => { e.preventDefault(); send(); }} className="px-3 py-2 border-t border-zinc-200 dark:border-zinc-800 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Block payments over $5000..."
          className="flex-1 text-sm px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-purple-500"
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !input.trim()} size="sm" className="rounded-lg bg-purple-600 hover:bg-purple-700">
          <Send className="h-3.5 w-3.5" />
        </Button>
      </form>
    </div>
  );
}
