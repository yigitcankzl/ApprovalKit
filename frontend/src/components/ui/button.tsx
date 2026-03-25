"use client";

import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "sm" | "md" | "lg";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none",
          {
            "bg-zinc-900 dark:bg-zinc-100 dark:bg-zinc-800 text-white dark:text-zinc-900 dark:text-zinc-100 hover:bg-zinc-800 dark:hover:bg-zinc-200 focus:ring-zinc-500": variant === "default",
            "border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 dark:text-zinc-100 hover:bg-zinc-50 dark:hover:bg-zinc-800 focus:ring-zinc-500": variant === "outline",
            "hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-800 dark:text-zinc-100 focus:ring-zinc-500": variant === "ghost",
            "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500": variant === "destructive",
          },
          {
            "h-8 px-3 text-sm": size === "sm",
            "h-10 px-4 text-sm": size === "md",
            "h-12 px-6 text-base": size === "lg",
          },
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";
export { Button };
