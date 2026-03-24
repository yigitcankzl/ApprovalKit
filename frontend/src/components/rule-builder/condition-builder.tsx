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
  { value: "in", label: "in" },
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
      <label className="text-sm font-medium text-zinc-700">Conditions</label>
      {conditions.map((condition, index) => (
        <div key={index} className="flex items-center gap-2">
          {index > 0 && <span className="text-xs font-medium text-zinc-400 w-8">AND</span>}
          <Input
            placeholder="field (e.g. amount)"
            value={condition.field}
            onChange={(e) => updateCondition(index, { field: e.target.value })}
            className="flex-1"
          />
          <Select
            value={condition.operator}
            onChange={(e) => updateCondition(index, { operator: e.target.value })}
            className="w-32"
          >
            {operators.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </Select>
          <Input
            placeholder="value"
            value={String(condition.value)}
            onChange={(e) => {
              const val = e.target.value;
              const numVal = Number(val);
              updateCondition(index, { value: isNaN(numVal) ? val : numVal });
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
