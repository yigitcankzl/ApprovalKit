"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Plus, X } from "lucide-react";
import type { Condition } from "@/types";

interface ConditionBuilderProps {
  conditions: Condition[];
  onChange: (conditions: Condition[]) => void;
}

const operators = [
  { value: "eq", label: "equals" },
  { value: "ne", label: "not equals" },
  { value: "gt", label: ">" },
  { value: "gte", label: ">=" },
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
  { value: "between", label: "between" },
  { value: "in", label: "in list" },
  { value: "not_in", label: "not in list" },
  { value: "contains", label: "contains" },
  { value: "starts_with", label: "starts with" },
  { value: "ends_with", label: "ends with" },
  { value: "regex", label: "matches regex" },
  { value: "exists", label: "exists" },
  { value: "not_exists", label: "not exists" },
];

const NO_VALUE_OPS = ["exists", "not_exists"];
const LIST_OPS = ["in", "not_in"];

function getPlaceholder(op: string): string {
  if (LIST_OPS.includes(op)) return "admin, superadmin";
  if (op === "between") return "500, 5000";
  if (op === "regex") return ".*@company\\.com";
  if (op === "starts_with") return "admin";
  if (op === "ends_with") return "@hospital.org";
  return "500, urgent, true, etc.";
}

function parseValue(val: string, op: string): Condition["value"] {
  // Lists: in, not_in, between
  if (LIST_OPS.includes(op) || op === "between") {
    const items = val.split(",").map(s => {
      const trimmed = s.trim();
      const num = Number(trimmed);
      return trimmed === "" ? trimmed : isNaN(num) ? trimmed : num;
    }).filter(s => s !== "");
    return items.length > 0 ? items : val;
  }
  // Boolean
  if (val === "true") return true;
  if (val === "false") return false;
  // Number or string
  const numVal = Number(val);
  return val === "" ? "" : isNaN(numVal) ? val : numVal;
}

export function ConditionBuilder({ conditions, onChange }: ConditionBuilderProps) {
  const addCondition = () => {
    onChange([...conditions, { field: "", operator: "eq", value: "" }]);
  };

  const updateCondition = (index: number, update: Partial<Condition>) => {
    const updated = [...conditions];
    updated[index] = { ...updated[index], ...update };
    // Clear value when switching to exists/not_exists
    if (update.operator && NO_VALUE_OPS.includes(update.operator)) {
      updated[index].value = true;
    }
    onChange(updated);
  };

  const removeCondition = (index: number) => {
    onChange(conditions.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Conditions</label>
      {conditions.map((condition, index) => {
        const isNoValue = NO_VALUE_OPS.includes(condition.operator);
        return (
          <div key={index} className="flex items-center gap-2">
            {index > 0 && <span className="text-xs font-medium text-zinc-400 w-8">AND</span>}
            <Input
              placeholder="e.g. amount, type, email, billing.country"
              value={condition.field}
              onChange={(e) => updateCondition(index, { field: e.target.value })}
              className="flex-1"
            />
            <Select
              value={condition.operator}
              onChange={(e) => updateCondition(index, { operator: e.target.value })}
              className="w-36"
            >
              {operators.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </Select>
            {isNoValue ? (
              <div className="flex-1" />
            ) : (
              <Input
                placeholder={getPlaceholder(condition.operator)}
                value={Array.isArray(condition.value) ? condition.value.join(", ") : String(condition.value)}
                onChange={(e) => updateCondition(index, { value: parseValue(e.target.value, condition.operator) })}
                className="flex-1"
              />
            )}
            <Button variant="ghost" size="sm" onClick={() => removeCondition(index)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        );
      })}
      <Button variant="outline" size="sm" onClick={addCondition}>
        <Plus className="h-3 w-3 mr-1" />
        Add Condition
      </Button>
    </div>
  );
}
