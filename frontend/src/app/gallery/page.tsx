"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ShoppingCart,
  GitBranch,
  Package,
  FlaskConical,
  CreditCard,
  Server,
  Mail,
  Shield,
} from "lucide-react";

const useCases = [
  {
    title: "E-commerce Agent",
    icon: ShoppingCart,
    description: "Stripe payment processing with tiered approvals",
    rules: [
      { label: "Under $50", action: "auto-approve", badge: "success" as const },
      { label: "$50–$200", action: "CS approval", badge: "info" as const },
      { label: "$200+", action: "CS + CFO sequential", badge: "warning" as const },
      { label: "Refunds", action: "partial approval enabled", badge: "default" as const },
    ],
  },
  {
    title: "DevOps Agent",
    icon: Server,
    description: "GitHub deployments with environment-based rules",
    rules: [
      { label: "Staging", action: "auto-approve", badge: "success" as const },
      { label: "Production", action: "any-one maintainer", badge: "info" as const },
      { label: "Rollback", action: "specific lead only", badge: "warning" as const },
      { label: "After 23:00", action: "blackout window", badge: "danger" as const },
    ],
  },
  {
    title: "Open Source Project",
    icon: Package,
    description: "Multi-maintainer governance with k-of-n voting",
    rules: [
      { label: "PR < 100 lines", action: "auto-merge", badge: "success" as const },
      { label: "npm patch", action: "lead maintainer", badge: "info" as const },
      { label: "npm major", action: "2/3 maintainers (k-of-n)", badge: "warning" as const },
      { label: "Treasury > $100", action: "treasurer + lead", badge: "danger" as const },
    ],
  },
  {
    title: "Research Lab",
    icon: FlaskConical,
    description: "AWS spending and publication controls",
    rules: [
      { label: "Compute < $20", action: "researcher auto", badge: "success" as const },
      { label: "Compute > $100", action: "PI approval", badge: "info" as const },
      { label: "Paper submit", action: "all co-authors (all-of-n)", badge: "warning" as const },
      { label: "Grant spending", action: "PI + finance dept", badge: "danger" as const },
    ],
  },
  {
    title: "Financial Services",
    icon: CreditCard,
    description: "Payment processing with compliance chain",
    rules: [
      { label: "Transfer < $1k", action: "manager approval", badge: "success" as const },
      { label: "Transfer > $10k", action: "manager + compliance", badge: "warning" as const },
      { label: "New vendor", action: "procurement + legal", badge: "danger" as const },
      { label: "Wire transfer", action: "sequential: ops → finance → CFO", badge: "danger" as const },
    ],
  },
  {
    title: "Communications Agent",
    icon: Mail,
    description: "Email and messaging with audience-based controls",
    rules: [
      { label: "Internal email", action: "auto-approve", badge: "success" as const },
      { label: "Client email", action: "manager review", badge: "info" as const },
      { label: "Mass email (>100)", action: "marketing lead + legal", badge: "warning" as const },
      { label: "Press release", action: "sequential: PR → legal → CEO", badge: "danger" as const },
    ],
  },
];

export default function GalleryPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Use Case Gallery</h1>
        <p className="text-zinc-500 mt-1">
          Pre-built rule sets you can import. Not just for developers.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {useCases.map((uc) => (
          <Card key={uc.title} className="hover:border-zinc-300 transition-colors">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-zinc-100 rounded-lg">
                  <uc.icon className="h-5 w-5 text-zinc-700" />
                </div>
                <div>
                  <CardTitle className="text-base">{uc.title}</CardTitle>
                  <CardDescription>{uc.description}</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {uc.rules.map((rule, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-zinc-600">{rule.label}</span>
                    <Badge variant={rule.badge}>{rule.action}</Badge>
                  </div>
                ))}
              </div>
              <Button variant="outline" size="sm" className="w-full mt-4">
                Import Rules
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
