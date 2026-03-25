"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Node,
  Edge,
  Position,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import type { Rule } from "@/types";

interface ApprovalFlowProps {
  rule: Rule;
  approverNames?: Record<string, string>;
}

const modelLabels: Record<string, string> = {
  any_one: "Any One Approves",
  specific: "Specific Approver",
  all_of_n: "All Must Approve",
  k_of_n: "K of N Approve",
  sequential: "Sequential Chain",
};

function buildNodes(rule: Rule, approverNames: Record<string, string>): Node[] {
  const nodes: Node[] = [];
  let y = 0;

  // Trigger node
  nodes.push({
    id: "trigger",
    position: { x: 250, y },
    data: {
      label: (
        <div className="text-center">
          <div className="font-semibold text-blue-700 dark:text-blue-400">TRIGGER</div>
          <div className="text-xs mt-1">
            {rule.connection}:{rule.action}
          </div>
          {rule.conditions.length > 0 && (
            <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              {rule.conditions.map((c, i) => (
                <div key={i}>
                  {c.field} {c.operator} {String(c.value)}
                </div>
              ))}
            </div>
          )}
        </div>
      ),
    },
    style: {
      background: "#eff6ff",
      border: "2px solid #3b82f6",
      borderRadius: "12px",
      padding: "12px",
      minWidth: 200,
    },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  });
  y += 120;

  // Blackout check node (if applicable)
  if (rule.blackout_start && rule.blackout_end) {
    nodes.push({
      id: "blackout",
      position: { x: 250, y },
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold text-orange-700">BLACKOUT CHECK</div>
            <div className="text-xs mt-1">
              {rule.blackout_start} - {rule.blackout_end}
            </div>
          </div>
        ),
      },
      style: {
        background: "#fff7ed",
        border: "2px solid #f97316",
        borderRadius: "12px",
        padding: "12px",
        minWidth: 180,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });
    y += 120;
  }

  // Approval node
  if (rule.model === "sequential") {
    rule.approver_ids.forEach((id, i) => {
      nodes.push({
        id: `approver-${i}`,
        position: { x: 250, y },
        data: {
          label: (
            <div className="text-center">
              <div className="font-semibold text-purple-700">
                Step {i + 1}: {approverNames[id] || `Approver ${i + 1}`}
              </div>
              <div className="text-xs mt-1">
                Guardian Push — {rule.timeout_seconds}s timeout
              </div>
            </div>
          ),
        },
        style: {
          background: "#faf5ff",
          border: "2px solid #a855f7",
          borderRadius: "12px",
          padding: "12px",
          minWidth: 200,
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });
      y += 120;
    });
  } else {
    nodes.push({
      id: "approval",
      position: { x: 250, y },
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold text-purple-700">
              {modelLabels[rule.model]}
            </div>
            <div className="text-xs mt-1">
              {rule.approver_ids.length} approver
              {rule.approver_ids.length > 1 ? "s" : ""} — {rule.timeout_seconds}s
              {rule.model === "k_of_n" && rule.k_value && ` (need ${rule.k_value})`}
            </div>
          </div>
        ),
      },
      style: {
        background: "#faf5ff",
        border: "2px solid #a855f7",
        borderRadius: "12px",
        padding: "12px",
        minWidth: 200,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });
    y += 120;
  }

  // Approved outcome
  nodes.push({
    id: "approved",
    position: { x: 100, y },
    data: {
      label: (
        <div className="text-center">
          <div className="font-semibold text-green-700 dark:text-green-400">APPROVED</div>
          <div className="text-xs mt-1">Token Vault executes action</div>
        </div>
      ),
    },
    style: {
      background: "#f0fdf4",
      border: "2px solid #22c55e",
      borderRadius: "12px",
      padding: "12px",
      minWidth: 180,
    },
    targetPosition: Position.Top,
  });

  // Timeout/escalation
  if (rule.on_timeout === "escalate" && rule.escalate_to) {
    nodes.push({
      id: "escalation",
      position: { x: 400, y },
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold text-yellow-700">ESCALATION</div>
            <div className="text-xs mt-1">
              {approverNames[rule.escalate_to] || "Escalation approver"} — {rule.timeout_seconds}s
            </div>
          </div>
        ),
      },
      style: {
        background: "#fefce8",
        border: "2px solid #eab308",
        borderRadius: "12px",
        padding: "12px",
        minWidth: 180,
      },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
    });

    y += 120;
    nodes.push({
      id: "blocked",
      position: { x: 400, y },
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold text-red-700 dark:text-red-400">BLOCKED</div>
            <div className="text-xs mt-1">403 Forbidden</div>
          </div>
        ),
      },
      style: {
        background: "#fef2f2",
        border: "2px solid #ef4444",
        borderRadius: "12px",
        padding: "12px",
        minWidth: 140,
      },
      targetPosition: Position.Top,
    });
  } else {
    nodes.push({
      id: "blocked",
      position: { x: 400, y },
      data: {
        label: (
          <div className="text-center">
            <div className="font-semibold text-red-700 dark:text-red-400">BLOCKED</div>
            <div className="text-xs mt-1">Timeout — 403 Forbidden</div>
          </div>
        ),
      },
      style: {
        background: "#fef2f2",
        border: "2px solid #ef4444",
        borderRadius: "12px",
        padding: "12px",
        minWidth: 140,
      },
      targetPosition: Position.Top,
    });
  }

  return nodes;
}

function buildEdges(rule: Rule): Edge[] {
  const edges: Edge[] = [];
  const edgeStyle = { strokeWidth: 2, stroke: "#94a3b8" };
  const marker = { type: MarkerType.ArrowClosed, color: "#94a3b8" };

  const lastBeforeApproval = rule.blackout_start ? "blackout" : "trigger";

  if (rule.blackout_start) {
    edges.push({
      id: "e-trigger-blackout",
      source: "trigger",
      target: "blackout",
      style: edgeStyle,
      markerEnd: marker,
    });
  }

  if (rule.model === "sequential") {
    edges.push({
      id: `e-${lastBeforeApproval}-approver-0`,
      source: lastBeforeApproval,
      target: "approver-0",
      style: edgeStyle,
      markerEnd: marker,
    });
    for (let i = 0; i < rule.approver_ids.length - 1; i++) {
      edges.push({
        id: `e-approver-${i}-${i + 1}`,
        source: `approver-${i}`,
        target: `approver-${i + 1}`,
        label: "approved",
        style: edgeStyle,
        markerEnd: marker,
      });
    }
    const lastApprover = `approver-${rule.approver_ids.length - 1}`;
    edges.push({
      id: `e-${lastApprover}-approved`,
      source: lastApprover,
      target: "approved",
      label: "approved",
      style: { ...edgeStyle, stroke: "#22c55e" },
      markerEnd: { ...marker, color: "#22c55e" },
    });
    edges.push({
      id: `e-${lastApprover}-blocked`,
      source: lastApprover,
      target: (rule.on_timeout === "escalate" && rule.escalate_to) ? "escalation" : "blocked",
      label: "timeout",
      style: { ...edgeStyle, stroke: "#ef4444" },
      markerEnd: { ...marker, color: "#ef4444" },
    });
  } else {
    edges.push({
      id: `e-${lastBeforeApproval}-approval`,
      source: lastBeforeApproval,
      target: "approval",
      style: edgeStyle,
      markerEnd: marker,
    });
    edges.push({
      id: "e-approval-approved",
      source: "approval",
      target: "approved",
      label: "approved",
      style: { ...edgeStyle, stroke: "#22c55e" },
      markerEnd: { ...marker, color: "#22c55e" },
    });
    edges.push({
      id: "e-approval-timeout",
      source: "approval",
      target: (rule.on_timeout === "escalate" && rule.escalate_to) ? "escalation" : "blocked",
      label: "timeout",
      style: { ...edgeStyle, stroke: "#ef4444" },
      markerEnd: { ...marker, color: "#ef4444" },
    });
  }

  if (rule.on_timeout === "escalate" && rule.escalate_to) {
    edges.push({
      id: "e-escalation-approved",
      source: "escalation",
      target: "approved",
      label: "approved",
      style: { ...edgeStyle, stroke: "#22c55e" },
      markerEnd: { ...marker, color: "#22c55e" },
    });
    edges.push({
      id: "e-escalation-blocked",
      source: "escalation",
      target: "blocked",
      label: "timeout",
      style: { ...edgeStyle, stroke: "#ef4444" },
      markerEnd: { ...marker, color: "#ef4444" },
    });
  }

  return edges;
}

export function ApprovalFlow({ rule, approverNames = {} }: ApprovalFlowProps) {
  const nodes = useMemo(() => buildNodes(rule, approverNames), [rule, approverNames]);
  const edges = useMemo(() => buildEdges(rule), [rule]);

  return (
    <div className="h-[600px] w-full rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
