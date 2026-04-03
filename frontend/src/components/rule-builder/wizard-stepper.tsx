"use client";

import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface WizardStep {
  id: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

interface WizardStepperProps {
  steps: WizardStep[];
  currentStep: number;
  onStepClick: (index: number) => void;
  completedSteps: Set<number>;
}

export function WizardStepper({ steps, currentStep, onStepClick, completedSteps }: WizardStepperProps) {
  return (
    <nav aria-label="Wizard progress" className="mb-8">
      <ol className="flex items-center w-full">
        {steps.map((step, idx) => {
          const isActive = idx === currentStep;
          const isCompleted = completedSteps.has(idx);
          const isClickable = isCompleted || idx <= currentStep;
          const Icon = step.icon;

          return (
            <li key={step.id} className={cn("flex items-center", idx < steps.length - 1 && "flex-1")}>
              <button
                type="button"
                onClick={() => isClickable && onStepClick(idx)}
                disabled={!isClickable}
                className={cn(
                  "flex items-center gap-2.5 group transition-all",
                  isClickable ? "cursor-pointer" : "cursor-not-allowed opacity-50"
                )}
              >
                <span
                  className={cn(
                    "flex items-center justify-center w-9 h-9 rounded-full border-2 transition-all shrink-0",
                    isActive && "border-blue-600 bg-blue-600 text-white shadow-lg shadow-blue-200 dark:shadow-blue-900/30",
                    isCompleted && !isActive && "border-emerald-500 bg-emerald-500 text-white",
                    !isActive && !isCompleted && "border-zinc-300 dark:border-zinc-600 text-zinc-400 dark:text-zinc-500 group-hover:border-zinc-400"
                  )}
                >
                  {isCompleted && !isActive ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                </span>
                <div className="hidden sm:block text-left">
                  <p className={cn(
                    "text-xs font-semibold leading-tight",
                    isActive ? "text-blue-600 dark:text-blue-400" : isCompleted ? "text-emerald-600 dark:text-emerald-400" : "text-zinc-400 dark:text-zinc-500"
                  )}>
                    {step.label}
                  </p>
                  <p className="text-[10px] text-zinc-400 dark:text-zinc-500 leading-tight mt-0.5 max-w-[120px]">
                    {step.description}
                  </p>
                </div>
              </button>

              {idx < steps.length - 1 && (
                <div className="flex-1 mx-3">
                  <div className={cn(
                    "h-0.5 rounded-full transition-colors",
                    isCompleted ? "bg-emerald-400 dark:bg-emerald-600" : "bg-zinc-200 dark:bg-zinc-700"
                  )} />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
