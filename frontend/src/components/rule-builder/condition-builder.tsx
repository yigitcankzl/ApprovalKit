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
  { value: "in", label: "in list" },
  { value: "not_in", label: "not in list" },
  { value: "contains", label: "contains" },
];

export function ConditionBuilder({ conditions, onChange }: ConditionBuilderProps) {
  const addCondition = () => {
    onChange([...conditions, { field: "", operator: "eq", value: "" }]);
  };

  const updateCondition = (index: number, update: Partial<Condition>) => {
    const updated = [...conditions];
    updated[index] = { ...updated[index], ...update };
    onChange(updated);
  };

  const removeCondition = (index: number) => {
    onChange(conditions.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Conditions</label>
      {conditions.map((condition, index) => (
        <div key={index} className="flex items-center gap-2">
          {index > 0 && <span className="text-xs font-medium text-zinc-400 w-8">AND</span>}
          <Input
            placeholder="e.g. amount, type, role, billing.country"
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
          <Input
            placeholder={
              condition.operator === "in" || condition.operator === "not_in"
                ? "admin, superadmin"
                : "500, urgent, true, etc."
            }
            value={String(condition.value)}
            onChange={(e) => {
              const val = e.target.value;
              // Parse comma-separated lists for in/not_in
              if (condition.operator === "in" || condition.operator === "not_in") {
                const items = val.split(",").map(s => {
                  const trimmed = s.trim();
                  const num = Number(trimmed);
                  return trimmed === "" ? trimmed : isNaN(num) ? trimmed : num;
                }).filter(s => s !== "");
                updateCondition(index, { value: items.length > 0 ? items : val });
                return;
              }
              // Boolean
              if (val === "true") { updateCondition(index, { value: true }); return; }
              if (val === "false") { updateCondition(index, { value: false }); return; }
              // Number or string
              const numVal = Number(val);
              updateCondition(index, { value: val === "" ? "" : isNaN(numVal) ? val : numVal });
            }}
            className="flex-1"
          />
          <Button variant="ghost" size="sm" onClick={() => removeCondition(index)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={addCondition}>
        <Plus className="h-3 w-3 mr-1" />
        Add Condition
      </Button>
    </div>
  );
}
