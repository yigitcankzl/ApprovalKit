"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
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
  LogIn,
  LogOut,
  Settings,
  Bot,
  Plug,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Connections", href: "/connections", icon: Link2 },
  { name: "Rules", href: "/rules", icon: GitBranch },
  { name: "Approvers", href: "/approvers", icon: Users },
  { name: "Audit Log", href: "/audit", icon: ScrollText },
  { name: "Consent", href: "/consent", icon: KeyRound },
  { name: "Connect Agent", href: "/connect", icon: Plug },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "Use Cases", href: "/gallery", icon: BookOpen },
  { name: "Docs", href: "/docs", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, isLoading } = useUser();

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
        {isLoading ? (
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="h-4 w-24 bg-zinc-200 rounded animate-pulse" />
          </div>
        ) : user ? (
          <div className="rounded-lg bg-zinc-50 p-3">
            <div className="flex items-center gap-2">
              {user.picture && (
                <img src={user.picture} alt="" className="h-7 w-7 rounded-full" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-zinc-700 truncate">{user.name}</p>
                <p className="text-xs text-zinc-400 truncate">{user.email}</p>
              </div>
            </div>
            <a
              href="/auth/logout"
              className="mt-2 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-700 transition-colors"
            >
              <LogOut className="h-3 w-3" /> Logout
            </a>
          </div>
        ) : (
          <a
            href="/auth/login"
            className="flex items-center justify-center gap-2 w-full rounded-lg bg-zinc-900 text-white text-sm font-medium py-2 hover:bg-zinc-800 transition-colors"
          >
            <LogIn className="h-4 w-4" /> Login with Auth0
          </a>
        )}
      </div>
    </aside>
  );
}
