"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  GitBranch,
  Users,
  ScrollText,
  BookOpen,
  FlaskConical,
  Shield,
  Rocket,
  FileText,
  Link2,
  KeyRound,
} from "lucide-react";

const navigation = [
  { name: "Onboarding", href: "/onboarding", icon: Rocket },
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Connections", href: "/connections", icon: Link2 },
  { name: "Rules", href: "/rules", icon: GitBranch },
  { name: "Approvers", href: "/approvers", icon: Users },
  { name: "Audit Log", href: "/audit", icon: ScrollText },
  { name: "Consent", href: "/consent", icon: KeyRound },
  { name: "Use Cases", href: "/gallery", icon: BookOpen },
  { name: "Simulate", href: "/simulate", icon: FlaskConical },
  { name: "Docs", href: "/docs", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-zinc-200 bg-white">
      <Link href="/" className="flex h-16 items-center gap-2 border-b border-zinc-200 px-6 hover:bg-zinc-50 transition-colors">
        <Shield className="h-6 w-6 text-zinc-900" />
        <span className="text-lg font-bold text-zinc-900">ApprovalKit</span>
      </Link>
      <nav className="space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-zinc-100 text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="absolute bottom-0 w-full border-t border-zinc-200 p-4">
        <div className="rounded-lg bg-zinc-50 p-3">
          <p className="text-xs font-medium text-zinc-500">Auth0 Integration</p>
          <p className="mt-1 text-xs text-zinc-400">Token Vault + CIBA + FGA</p>
        </div>
      </div>
    </aside>
  );
}
