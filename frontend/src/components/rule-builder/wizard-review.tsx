"use client";

import type { ApprovalModel, Approver, Condition, TimeoutAction } from "@/types";
import {
  Shield, Zap, Clock, AlertTriangle, Sparkles, Gauge, Users,
  CheckCircle2, Link2, FileText,
} from "lucide-react";

interface WizardReviewProps {
  name: string;
  connection: string;
  action: string;
  conditions: Condition[];
  model: ApprovalModel;
  selectedApproverIds: string[];
  approvers: Approver[];
  kValue: number;
  timeoutSeconds: number;
  onTimeout: TimeoutAction;
  escalateTo: string;
  partialApproval: boolean;
  contextTemplate: string;
  blackoutStart: string;
  blackoutEnd: string;
  cooldownMax: string;
  quorumWindow: string;
  priority: number;
  stepUpEnabled: boolean;
  stepUpModel: ApprovalModel;
  stepUpConditions: Condition[];
  maxRequestsPerHour: string;
  approvalExpiry: string;
  triggerRules: string;
  riskAutoApproveThreshold: string;
}

const modelLabels: Record<ApprovalModel, string> = {
  any_one: "Any One",
  specific: "Specific",
  all_of_n: "All of N",
  k_of_n: "K of N",
  sequential: "Sequential",
};

const opLabels: Record<string, string> = {
  eq: "=", ne: "!=", gt: ">", gte: ">=", lt: "<", lte: "<=",
  in: "in", not_in: "not in", contains: "contains",
  starts_with: "starts with", ends_with: "ends with",
  regex: "regex", between: "between", exists: "exists", not_exists: "not exists",
};

function ReviewSection({ icon: Icon, title, children }: { icon: typeof Shield; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-zinc-100 dark:bg-zinc-800 shrink-0 mt-0.5">
        <Icon className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500 mb-1.5">{title}</h4>
        {children}
      </div>
    </div>
  );
}

function Tag({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "blue" | "amber" | "emerald" | "red" }) {
  const colors = {
    default: "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700",
    blue: "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800",
    amber: "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800",
    emerald: "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
    red: "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${colors[variant]}`}>
      {children}
    </span>
  );
}

export function WizardReview(props: WizardReviewProps) {
  const selectedApprovers = props.approvers.filter(a => props.selectedApproverIds.includes(a.id));

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">{props.name || "Untitled Rule"}</h3>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-0.5">
              <Tag variant="blue">{props.connection || "—"}</Tag>{" "}
              <span className="text-zinc-400 mx-1">:</span>{" "}
              <Tag variant="blue">{props.action || "—"}</Tag>
              {props.priority > 0 && <Tag variant="amber">Priority {props.priority}</Tag>}
            </p>
          </div>
        </div>
      </div>

      {props.conditions.length > 0 && (
        <ReviewSection icon={Zap} title="Trigger Conditions">
          <div className="space-y-1">
            {props.conditions.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-sm text-zinc-700 dark:text-zinc-300">
                {i > 0 && <span className="text-xs font-semibold text-zinc-400">AND</span>}
                <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">{c.field}</code>
                <span className="text-xs text-zinc-500">{opLabels[c.operator] || c.operator}</span>
                <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                  {Array.isArray(c.value) ? c.value.join(", ") : String(c.value)}
                </code>
              </div>
            ))}
          </div>
        </ReviewSection>
      )}

      <ReviewSection icon={Users} title="Approval Flow">
        <div className="space-y-1.5">
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            <Tag variant="emerald">{modelLabels[props.model]}</Tag>
            {props.model === "k_of_n" && <span className="ml-1 text-xs text-zinc-500">(k={props.kValue})</span>}
          </p>
          {selectedApprovers.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {selectedApprovers.map(a => (
                <Tag key={a.id}>{a.name}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-400">No approvers selected (will use workspace defaults)</p>
          )}
          {props.partialApproval && (
            <p className="text-xs text-amber-600 dark:text-amber-400">Partial approval enabled — approver can modify params</p>
          )}
        </div>
      </ReviewSection>

      {(props.stepUpEnabled || props.riskAutoApproveThreshold) && (
        <ReviewSection icon={Shield} title="Safety & Risk">
          <div className="space-y-1.5">
            {props.riskAutoApproveThreshold && (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Auto-approve when risk score ≤ <Tag variant="emerald">{props.riskAutoApproveThreshold}</Tag>
              </p>
            )}
            {props.stepUpEnabled && (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Step-up to <Tag variant="amber">{modelLabels[props.stepUpModel]}</Tag> when conditions match
              </p>
            )}
          </div>
        </ReviewSection>
      )}

      <ReviewSection icon={Clock} title="Timeout & Blackout">
        <div className="space-y-1.5">
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            Timeout: <strong>{props.timeoutSeconds}s</strong> →{" "}
            {props.onTimeout === "escalate" ? (
              <Tag variant="amber">Escalate</Tag>
            ) : (
              <Tag variant="red">Block</Tag>
            )}
          </p>
          {props.blackoutStart && props.blackoutEnd && (
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Blackout: <strong>{props.blackoutStart}</strong> – <strong>{props.blackoutEnd}</strong>
            </p>
          )}
          {props.cooldownMax && (
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Cooldown: max <strong>{props.cooldownMax}</strong> triggers/hour
            </p>
          )}
        </div>
      </ReviewSection>

      {(props.maxRequestsPerHour || props.approvalExpiry || props.contextTemplate) && (
        <ReviewSection icon={Gauge} title="Rate Limit & Expiry">
          <div className="space-y-1.5">
            {props.maxRequestsPerHour && (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Max <strong>{props.maxRequestsPerHour}</strong> requests/hour
              </p>
            )}
            {props.approvalExpiry && (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                Approval expires after <strong>{props.approvalExpiry}s</strong>
              </p>
            )}
            {props.contextTemplate && (
              <p className="text-sm text-zinc-700 dark:text-zinc-300">
                <FileText className="inline w-3 h-3 mr-1" />
                Binding message: <code className="text-xs bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">{props.contextTemplate}</code>
              </p>
            )}
          </div>
        </ReviewSection>
      )}

      {props.triggerRules && (
        <ReviewSection icon={Link2} title="Rule Chaining">
          <p className="text-xs text-zinc-500">Trigger actions configured on approval</p>
        </ReviewSection>
      )}
    </div>
  );
}
