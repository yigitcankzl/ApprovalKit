"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConditionBuilder } from "@/components/rule-builder/condition-builder";
import { LivePreview } from "@/components/rule-builder/live-preview";
import { WizardStepper, type WizardStep } from "@/components/rule-builder/wizard-stepper";
import { WizardReview } from "@/components/rule-builder/wizard-review";
import { api } from "@/lib/api";
import type { ApprovalModel, Approver, Condition, TimeoutAction } from "@/types";
import {
  Save, Zap, Gauge, Clock, Bot, Send, Sparkles, Shield,
  Users, Settings2, ClipboardCheck, ChevronLeft, ChevronRight,
  Layers, AlertTriangle,
} from "lucide-react";
import { FormError } from "@/components/ui/form-error";

const WIZARD_STEPS: WizardStep[] = [
  { id: "service", label: "Service & Action", icon: Layers, description: "What to gate" },
  { id: "conditions", label: "Conditions", icon: Zap, description: "When to trigger" },
  { id: "approval", label: "Approval Flow", icon: Users, description: "Who approves" },
  { id: "safety", label: "Safety & Risk", icon: Shield, description: "Step-up & risk" },
  { id: "advanced", label: "Advanced", icon: Settings2, description: "Timeout & limits" },
  { id: "review", label: "Review", icon: ClipboardCheck, description: "Confirm & save" },
];

const services = [
  { value: "stripe-prod", label: "Stripe (Production)", icon: "💳", color: "border-violet-200 dark:border-violet-800 bg-violet-50 dark:bg-violet-950/20" },
  { value: "github-main", label: "GitHub (Main)", icon: "🐙", color: "border-zinc-300 dark:border-zinc-600 bg-zinc-50 dark:bg-zinc-800/50" },
  { value: "npm-registry", label: "NPM Registry", icon: "📦", color: "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20" },
  { value: "gmail", label: "Gmail", icon: "📧", color: "border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/20" },
  { value: "slack", label: "Slack", icon: "💬", color: "border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/20" },
  { value: "salesforce", label: "Salesforce", icon: "☁️", color: "border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/20" },
  { value: "aws", label: "AWS", icon: "🔶", color: "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20" },
];

const actions: Record<string, { value: string; label: string; risk: string }[]> = {
  "stripe-prod": [
    { value: "charge", label: "Create Charge", risk: "high" },
    { value: "refund", label: "Issue Refund", risk: "medium" },
    { value: "payout", label: "Send Payout", risk: "high" },
    { value: "create_customer", label: "Create Customer", risk: "low" },
  ],
  "github-main": [
    { value: "merge_pr", label: "Merge Pull Request", risk: "medium" },
    { value: "deploy", label: "Deploy to Production", risk: "high" },
    { value: "publish_release", label: "Publish Release", risk: "high" },
    { value: "delete_branch", label: "Delete Branch", risk: "low" },
  ],
  "npm-registry": [
    { value: "publish", label: "Publish Package", risk: "high" },
    { value: "deprecate", label: "Deprecate Package", risk: "medium" },
    { value: "unpublish", label: "Unpublish Package", risk: "high" },
  ],
  gmail: [
    { value: "send_email", label: "Send Email", risk: "medium" },
    { value: "delete_email", label: "Delete Email", risk: "low" },
    { value: "share_drive", label: "Share Drive", risk: "medium" },
  ],
  slack: [
    { value: "send_message", label: "Send Message", risk: "low" },
    { value: "create_channel", label: "Create Channel", risk: "low" },
    { value: "invite_user", label: "Invite User", risk: "low" },
  ],
  salesforce: [
    { value: "create_deal", label: "Create Deal", risk: "medium" },
    { value: "update_contact", label: "Update Contact", risk: "low" },
    { value: "delete_lead", label: "Delete Lead", risk: "medium" },
  ],
  aws: [
    { value: "launch_instance", label: "Launch Instance", risk: "high" },
    { value: "terminate_instance", label: "Terminate Instance", risk: "high" },
    { value: "create_bucket", label: "Create Bucket", risk: "medium" },
  ],
};

const approvalModels: { value: ApprovalModel; label: string; description: string; icon: typeof Users }[] = [
  { value: "any_one", label: "Any One", description: "First response from any listed approver wins", icon: Users },
  { value: "specific", label: "Specific", description: "Only the designated person can approve", icon: Shield },
  { value: "all_of_n", label: "All of N", description: "Every approver must approve; one denial blocks", icon: Users },
  { value: "k_of_n", label: "K of N", description: "K approvers must approve within quorum window", icon: Users },
  { value: "sequential", label: "Sequential", description: "Ordered chain — each must approve before next", icon: Layers },
];

export default function NewRulePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [approvers, setApprovers] = useState<Approver[]>([]);
  const [selectedApproverIds, setSelectedApproverIds] = useState<string[]>([]);

  // Form state
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
  const [riskAutoApproveThreshold, setRiskAutoApproveThreshold] = useState<string>("");

  useEffect(() => {
    api.getApprovers().then(setApprovers).catch(() => {});
  }, []);

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
      .catch(() => {});
  }, [searchParams]);

  const toggleApprover = (id: string) => {
    setSelectedApproverIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const availableActions = actions[connection] || [];

  const validateStep = useCallback((step: number): string | null => {
    switch (step) {
      case 0:
        if (!name.trim()) return "Rule name is required";
        if (!connection) return "Select a service";
        if (!action) return "Select an action";
        return null;
      case 1: return null;
      case 2: return null;
      case 3: return null;
      case 4: return null;
      case 5: return null;
      default: return null;
    }
  }, [name, connection, action]);

  const goToStep = useCallback((step: number) => {
    if (step > currentStep) {
      const error = validateStep(currentStep);
      if (error) {
        setSaveError(error);
        return;
      }
      setCompletedSteps(prev => { const next = new Set(Array.from(prev)); next.add(currentStep); return next; });
    }
    setSaveError(null);
    setCurrentStep(step);
  }, [currentStep, validateStep]);

  const handleSave = async () => {
    setSaveError(null);
    const error = validateStep(0);
    if (error) { setSaveError(error); return; }
    setSaving(true);
    try {
      const data = {
        name, connection, action, conditions, model,
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
        risk_auto_approve_threshold: riskAutoApproveThreshold ? parseInt(riskAutoApproveThreshold) : null,
      };
      await api.createRule(data);
      router.push("/rules");
    } catch (error: any) {
      setSaveError(error.message || "Failed to save rule");
    } finally {
      setSaving(false);
    }
  };

  const applyAIRule = (rule: any) => {
    if (rule.name) setName(rule.name);
    if (rule.connection) setConnection(rule.connection);
    if (rule.action) setAction(rule.action);
    if (rule.model) setModel(rule.model as ApprovalModel);
    if (rule.conditions) {
      setConditions(rule.conditions.map((c: any) => ({
        field: c.field || "",
        operator: c.operator || "eq",
        value: typeof c.value === "string" && !isNaN(Number(c.value)) ? Number(c.value) : c.value,
      })));
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
    if (selectedApproverIds.length === 0 && approvers.length > 0) {
      setSelectedApproverIds([approvers[0].id]);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Create Rule</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">Build an approval workflow step by step</p>
      </div>

      <WizardStepper
        steps={WIZARD_STEPS}
        currentStep={currentStep}
        onStepClick={goToStep}
        completedSteps={completedSteps}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main wizard content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Step 0: Service & Action */}
          {currentStep === 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="h-5 w-5 text-blue-600" />
                  Service & Action
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Rule Name</label>
                  <Input
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="e.g. High-value Stripe charges"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">Service Connection</label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {services.map(s => (
                      <button
                        key={s.value}
                        type="button"
                        onClick={() => { setConnection(s.value); setAction(""); }}
                        className={`flex items-center gap-2.5 p-3 rounded-xl border-2 transition-all text-left ${
                          connection === s.value
                            ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30 ring-2 ring-blue-200 dark:ring-blue-800"
                            : `${s.color} hover:border-zinc-400 dark:hover:border-zinc-500`
                        }`}
                      >
                        <span className="text-xl">{s.icon}</span>
                        <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{s.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {connection && (
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">Action</label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {availableActions.map(a => (
                        <button
                          key={a.value}
                          type="button"
                          onClick={() => setAction(a.value)}
                          className={`flex items-center justify-between p-3 rounded-xl border-2 transition-all text-left ${
                            action === a.value
                              ? "border-blue-500 bg-blue-50 dark:bg-blue-950/30 ring-2 ring-blue-200 dark:ring-blue-800"
                              : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500 bg-white dark:bg-zinc-900"
                          }`}
                        >
                          <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{a.label}</span>
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
                            a.risk === "high" ? "bg-red-100 dark:bg-red-950/40 text-red-600 dark:text-red-400"
                              : a.risk === "medium" ? "bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400"
                              : "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400"
                          }`}>
                            {a.risk}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Priority</label>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={priority}
                    onChange={e => setPriority(parseInt(e.target.value) || 0)}
                    className="mt-1 w-32"
                  />
                  <p className="text-xs text-zinc-400 mt-1">Higher priority rules are evaluated first (0 = default)</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 1: Conditions */}
          {currentStep === 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-amber-500" />
                  Trigger Conditions
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Define when this rule should trigger. Leave empty to match all requests for this service/action.
                </p>
                <ConditionBuilder conditions={conditions} onChange={setConditions} />
                {conditions.length === 0 && (
                  <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center">
                    <Zap className="h-8 w-8 text-zinc-300 dark:text-zinc-600 mx-auto mb-2" />
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">No conditions added</p>
                    <p className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
                      This rule will trigger for ALL <code className="bg-zinc-100 dark:bg-zinc-800 px-1 rounded">{connection}:{action}</code> requests
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Step 2: Approval Flow */}
          {currentStep === 2 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-emerald-500" />
                  Approval Flow
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">Approval Model</label>
                  <div className="grid grid-cols-1 gap-2">
                    {approvalModels.map(m => {
                      const Icon = m.icon;
                      return (
                        <button
                          key={m.value}
                          type="button"
                          onClick={() => setModel(m.value)}
                          className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left ${
                            model === m.value
                              ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/20 ring-2 ring-emerald-200 dark:ring-emerald-800"
                              : "border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500 bg-white dark:bg-zinc-900"
                          }`}
                        >
                          <Icon className={`h-5 w-5 shrink-0 ${model === m.value ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400"}`} />
                          <div>
                            <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{m.label}</p>
                            <p className="text-xs text-zinc-500 dark:text-zinc-400">{m.description}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {model === "k_of_n" && (
                  <div className="flex items-center gap-4">
                    <div>
                      <label className="text-sm text-zinc-600 dark:text-zinc-400">Required approvals (k)</label>
                      <Input type="number" min={1} value={kValue} onChange={e => setKValue(parseInt(e.target.value) || 1)} className="w-20 mt-1" />
                    </div>
                    <div>
                      <label className="text-sm text-zinc-600 dark:text-zinc-400">Quorum window (seconds)</label>
                      <Input type="number" value={quorumWindow} onChange={e => setQuorumWindow(e.target.value)} placeholder="3600" className="w-32 mt-1" />
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2 block">Approvers</label>
                  {approvers.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-4 text-center">
                      <p className="text-sm text-zinc-400">
                        No approvers found.{" "}
                        <a href="/approvers" className="text-blue-600 underline">Add approvers first.</a>
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1.5 max-h-56 overflow-y-auto border border-zinc-200 dark:border-zinc-700 rounded-xl p-3">
                      {approvers.map(a => (
                        <label
                          key={a.id}
                          className={`flex items-center gap-3 cursor-pointer rounded-lg px-3 py-2 transition-colors ${
                            selectedApproverIds.includes(a.id)
                              ? "bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800"
                              : "hover:bg-zinc-50 dark:hover:bg-zinc-800 border border-transparent"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedApproverIds.includes(a.id)}
                            onChange={() => toggleApprover(a.id)}
                            className="rounded border-zinc-300 dark:border-zinc-600 text-emerald-600 focus:ring-emerald-500"
                          />
                          <div className="flex-1 min-w-0">
                            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{a.name}</span>
                            <span className="text-xs text-zinc-400 ml-2">{a.email}</span>
                          </div>
                          {a.delegate_to && (
                            <span className="text-xs text-orange-500 shrink-0">delegated</span>
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                  {selectedApproverIds.length > 0 && (
                    <p className="text-xs text-zinc-500 mt-1.5">
                      {selectedApproverIds.length} approver{selectedApproverIds.length > 1 ? "s" : ""} selected
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="checkbox"
                    id="partial"
                    checked={partialApproval}
                    onChange={e => setPartialApproval(e.target.checked)}
                    className="rounded border-zinc-300 dark:border-zinc-600 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="partial" className="text-sm text-zinc-700 dark:text-zinc-300">
                    Allow partial approval (approver can modify params)
                  </label>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 3: Safety & Risk */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-purple-500" />
                    Risk-based Auto-approve
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Automatically approve low-risk requests without human review.
                  </p>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Auto-approve threshold (0–100)</label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={riskAutoApproveThreshold}
                      onChange={e => setRiskAutoApproveThreshold(e.target.value)}
                      placeholder="Disabled"
                      className="mt-1 w-40"
                    />
                    <p className="text-xs text-zinc-400 mt-1">
                      Requests with risk score ≤ this value are auto-approved.
                      Empty = disabled (all requests require human approval).
                    </p>
                  </div>
                  {riskAutoApproveThreshold && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
                      <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-xs text-amber-700 dark:text-amber-300">
                        Requests with risk score ≤ {riskAutoApproveThreshold} will be auto-approved without human review.
                        {parseInt(riskAutoApproveThreshold) >= 50 && " This is a relatively high threshold — consider lowering it."}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-red-500" />
                    Step-up Authentication
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="stepUp"
                      checked={stepUpEnabled}
                      onChange={e => setStepUpEnabled(e.target.checked)}
                      className="rounded border-zinc-300 dark:border-zinc-600 text-red-600 focus:ring-red-500"
                    />
                    <label htmlFor="stepUp" className="text-sm text-zinc-700 dark:text-zinc-300">
                      Enable step-up for high-value requests
                    </label>
                  </div>
                  {stepUpEnabled && (
                    <>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        When request parameters match these conditions, the approval model escalates automatically.
                      </p>
                      <div>
                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Step-up Conditions</label>
                        <ConditionBuilder conditions={stepUpConditions} onChange={setStepUpConditions} />
                      </div>
                      <div>
                        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Escalate to Model</label>
                        <Select value={stepUpModel} onChange={e => setStepUpModel(e.target.value as ApprovalModel)} className="mt-1">
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
            </div>
          )}

          {/* Step 4: Advanced */}
          {currentStep === 4 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings2 className="h-5 w-5 text-zinc-500" />
                  Advanced Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Timeout */}
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" /> Timeout & Escalation
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Timeout (seconds)</label>
                      <Input type="number" min={30} max={3600} value={timeoutSeconds} onChange={e => setTimeoutSeconds(parseInt(e.target.value) || 300)} className="mt-1" />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">On Timeout</label>
                      <Select value={onTimeout} onChange={e => setOnTimeout(e.target.value as TimeoutAction)} className="mt-1">
                        <option value="block">Block — permanently cancel</option>
                        <option value="escalate">Escalate — send to backup</option>
                      </Select>
                    </div>
                  </div>
                  {onTimeout === "escalate" && (
                    <div className="mt-3">
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Escalation Approver</label>
                      <Select value={escalateTo} onChange={e => setEscalateTo(e.target.value)} className="mt-1">
                        <option value="">Select escalation approver...</option>
                        {approvers.map(a => (
                          <option key={a.id} value={a.id}>{a.name}</option>
                        ))}
                      </Select>
                    </div>
                  )}
                </div>

                {/* Blackout */}
                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3">Blackout Window</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Blackout Start</label>
                      <Input type="time" value={blackoutStart} onChange={e => setBlackoutStart(e.target.value)} className="mt-1" />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Blackout End</label>
                      <Input type="time" value={blackoutEnd} onChange={e => setBlackoutEnd(e.target.value)} className="mt-1" />
                    </div>
                  </div>
                </div>

                {/* Rate Limiting */}
                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                    <Gauge className="h-3.5 w-3.5" /> Rate Limiting
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Cooldown (max triggers/hour)</label>
                      <Input type="number" value={cooldownMax} onChange={e => setCooldownMax(e.target.value)} placeholder="No limit" className="mt-1" />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Max requests per hour</label>
                      <Input type="number" min={1} max={10000} value={maxRequestsPerHour} onChange={e => setMaxRequestsPerHour(e.target.value)} placeholder="Unlimited" className="mt-1" />
                    </div>
                  </div>
                </div>

                {/* Context & Expiry */}
                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3">Context & Expiry</p>
                  <div className="space-y-3">
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Context Template (binding message)</label>
                      <Input value={contextTemplate} onChange={e => setContextTemplate(e.target.value)} placeholder="Charge of ${{amount}} for {{customer}}" className="mt-1" />
                      <p className="text-xs text-zinc-400 mt-1">Use {"{{variable}}"} for dynamic values from params</p>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Approval Expiry (seconds)</label>
                      <Input type="number" min={60} max={86400} value={approvalExpiry} onChange={e => setApprovalExpiry(e.target.value)} placeholder="No expiry" className="mt-1 w-40" />
                    </div>
                  </div>
                </div>

                {/* Rule Chaining */}
                <div className="border-t border-zinc-200 dark:border-zinc-700 pt-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-3 flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5" /> Rule Chaining
                  </p>
                  <div>
                    <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Trigger actions on approval (JSON)</label>
                    <textarea
                      value={triggerRules}
                      onChange={e => setTriggerRules(e.target.value)}
                      placeholder='[{"connection": "slack", "action": "send_message", "params": {"text": "Approved!"}}]'
                      className="mt-1 w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-mono text-zinc-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px]"
                      rows={3}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 5: Review */}
          {currentStep === 5 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-blue-500" />
                  Review & Save
                </CardTitle>
              </CardHeader>
              <CardContent>
                <WizardReview
                  name={name}
                  connection={connection}
                  action={action}
                  conditions={conditions}
                  model={model}
                  selectedApproverIds={selectedApproverIds}
                  approvers={approvers}
                  kValue={kValue}
                  timeoutSeconds={timeoutSeconds}
                  onTimeout={onTimeout}
                  escalateTo={escalateTo}
                  partialApproval={partialApproval}
                  contextTemplate={contextTemplate}
                  blackoutStart={blackoutStart}
                  blackoutEnd={blackoutEnd}
                  cooldownMax={cooldownMax}
                  quorumWindow={quorumWindow}
                  priority={priority}
                  stepUpEnabled={stepUpEnabled}
                  stepUpModel={stepUpModel}
                  stepUpConditions={stepUpConditions}
                  maxRequestsPerHour={maxRequestsPerHour}
                  approvalExpiry={approvalExpiry}
                  triggerRules={triggerRules}
                  riskAutoApproveThreshold={riskAutoApproveThreshold}
                />
              </CardContent>
            </Card>
          )}

          {/* Error + Navigation */}
          <FormError message={saveError} />
          <div className="flex items-center justify-between">
            <div>
              {currentStep > 0 ? (
                <Button variant="outline" onClick={() => goToStep(currentStep - 1)}>
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Back
                </Button>
              ) : (
                <Button variant="outline" onClick={() => router.push("/rules")}>
                  Cancel
                </Button>
              )}
            </div>
            <div className="flex gap-3">
              {currentStep < WIZARD_STEPS.length - 1 ? (
                <Button onClick={() => goToStep(currentStep + 1)}>
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              ) : (
                <Button onClick={handleSave} disabled={saving || !name || !connection || !action}>
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? "Saving..." : "Create Rule"}
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar: Live Preview + AI Assistant */}
        <div className="space-y-6 sticky top-8 self-start">
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
          <RuleAssistant
            approverIds={selectedApproverIds.length > 0 ? selectedApproverIds : approvers.slice(0, 1).map(a => a.id)}
            onApplyRule={applyAIRule}
          />
        </div>
      </div>
    </div>
  );
}

function RuleAssistant({ onApplyRule, approverIds }: { onApplyRule: (rule: any) => void; approverIds: string[] }) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [, setLastRule] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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
        approver_ids: approverIds,
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
      setSaved(true);
      setMessages(prev => [...prev, { role: "assistant", content: `Rule "${rule.name}" saved successfully!` }]);
      setTimeout(() => router.push("/rules"), 2000);
    } catch (e: any) {
      const errMsg = typeof e.message === "string" ? e.message : JSON.stringify(e.message || e);
      setMessages(prev => [...prev, { role: "assistant", content: `Failed to save: ${errMsg}` }]);
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
      }
    } catch (e: any) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${e.message}` }]);
    }
    setLoading(false);
  };

  return (
    <div className="rounded-2xl border border-purple-200 dark:border-purple-800 bg-white dark:bg-zinc-900 shadow-sm flex flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 rounded-t-2xl">
        <Bot className="h-5 w-5 text-purple-600 dark:text-purple-400" />
        <span className="text-sm font-semibold text-purple-800 dark:text-purple-200 flex-1">AI Rule Assistant</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3" style={{ minHeight: "200px", maxHeight: "400px" }}>
        {messages.length === 0 && (
          <div className="text-center py-6 space-y-2">
            <Sparkles className="h-8 w-8 text-purple-300 mx-auto" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Describe the rule you need</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {[
                "Block charges over $10K",
                "Require CFO for deployments",
                "Auto-approve Slack messages",
                "Step-up auth for refunds > $500",
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
                  <button onClick={() => saveRuleDirect(rule)} disabled={saving || saved} className={`text-[10px] px-2.5 py-1 rounded-md font-medium disabled:opacity-50 ${saved ? "bg-green-600 text-white" : "bg-purple-600 text-white hover:bg-purple-700"}`}>
                    {saved ? "Saved!" : saving ? "Saving..." : "Save Rule Directly"}
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

      <form onSubmit={e => { e.preventDefault(); send(); }} className="px-3 py-2 border-t border-zinc-200 dark:border-zinc-800 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
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
