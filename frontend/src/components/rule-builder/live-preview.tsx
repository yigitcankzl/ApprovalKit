"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApprovalModel, Condition } from "@/types";

interface LivePreviewProps {
  connection: string;
  action: string;
  conditions: Condition[];
  model: ApprovalModel;
  approverCount: number;
  kValue?: number;
  timeoutSeconds: number;
  onTimeout: string;
  escalateTo?: string;
  partialApproval: boolean;
  contextTemplate?: string;
  blackoutStart?: string;
  blackoutEnd?: string;
}

const modelDescriptions: Record<ApprovalModel, (count: number, k?: number) => string> = {
  any_one: (count) => `Send to all ${count} approvers. First response wins.`,
  specific: () => `Send to designated approver only. No substitutions.`,
  all_of_n: (count) => `All ${count} approvers must approve. One denial = blocked.`,
  k_of_n: (count, k) => `${k} of ${count} approvers must approve within quorum window.`,
  sequential: (count) => `${count} approvers in sequence. Each must approve before next.`,
};

function conditionToText(c: Condition): string {
  const ops: Record<string, string> = {
    eq: "equals",
    ne: "does not equal",
    gt: "is greater than",
    gte: "is at least",
    lt: "is less than",
    lte: "is at most",
    in: "is in",
    contains: "contains",
  };
  return `${c.field} ${ops[c.operator] || c.operator} ${c.value}`;
}

export function LivePreview(props: LivePreviewProps) {
  const {
    connection,
    action,
    conditions,
    model,
    approverCount,
    kValue,
    timeoutSeconds,
    onTimeout,
    escalateTo,
    partialApproval,
    contextTemplate,
    blackoutStart,
    blackoutEnd,
  } = props;

  return (
    <Card className="sticky top-8">
      <CardHeader>
        <CardTitle className="text-base">Live Preview</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 text-sm text-zinc-600 dark:text-zinc-400">
          <p>
            <strong>When</strong>{" "}
            <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              {connection || "service"}:{action || "action"}
            </code>{" "}
            arrives
            {conditions.length > 0 && (
              <>
                {" "}
                with{" "}
                {conditions.map((c, i) => (
                  <span key={i}>
                    {i > 0 && " AND "}
                    <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
                      {conditionToText(c)}
                    </code>
                  </span>
                ))}
              </>
            )}
            :
          </p>

          <div className="pl-4 border-l-2 border-zinc-200 dark:border-zinc-700 space-y-2">
            <p>{modelDescriptions[model](approverCount, kValue)}</p>
            <p>
              Wait <strong>{timeoutSeconds}s</strong> for response.
            </p>
            {onTimeout === "escalate" && escalateTo ? (
              <p>
                If no response: <strong>escalate</strong> to backup approver.
              </p>
            ) : (
              <p>
                If no response: <strong>BLOCK</strong> the action.
              </p>
            )}
            {partialApproval && (
              <p>Approver may modify parameters (partial approval).</p>
            )}
            {blackoutStart && blackoutEnd && (
              <p>
                Blocked during <strong>{blackoutStart}–{blackoutEnd}</strong>.
              </p>
            )}
          </div>

          {contextTemplate && (
            <div className="mt-3 p-2 bg-zinc-50 dark:bg-zinc-800/50 rounded text-xs">
              <strong>Binding message:</strong> {contextTemplate}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
