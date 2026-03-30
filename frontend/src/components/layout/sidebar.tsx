"use client";

import { useEffect, useState } from "react";
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
  ShieldAlert,
  FileText,
  Link2,
  KeyRound,
  LogIn,
  LogOut,
  Settings,
  Bot,
  Plug,
  Plane,
  ChevronLeft,
  Menu,
  Moon,
  Sun,
  Stethoscope,
  ExternalLink,
  ShieldCheck,
  ClipboardCheck,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Connections", href: "/connections", icon: Link2 },
  { name: "Rules", href: "/rules", icon: GitBranch },
  { name: "Approvers", href: "/approvers", icon: Users },
  { name: "Audit Log", href: "/audit", icon: ScrollText },
  { name: "Compliance", href: "/audit/compliance", icon: ClipboardCheck },
  { name: "Consent", href: "/consent", icon: ShieldCheck },
  { name: "Agents", href: "/agents", icon: Bot },
  { name: "MCP Server", href: "/mcp", icon: Shield },
  { name: "Demos", href: "/demos", icon: Rocket },
  { name: "Docs", href: "/docs", icon: FileText },
  { name: "Settings", href: "/settings", icon: Settings },
];

const HEALTHCARE_URL = process.env.NEXT_PUBLIC_HEALTHCARE_URL || "http://localhost:3003";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();
  const { user, isLoading } = useUser();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  return (
    <aside
      role="navigation"
      aria-label="Main navigation"
      className={cn(
        "fixed left-0 top-0 z-40 h-screen border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 transition-all duration-200",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Header */}
      <div className="flex h-16 items-center border-b border-zinc-200 dark:border-zinc-800">
        {collapsed ? (
          <button
            onClick={onToggle}
            className="flex items-center justify-center w-full h-full text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:bg-zinc-800/50 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:text-zinc-100 transition-colors"
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
            <span className="sr-only">Expand sidebar</span>
          </button>
        ) : (
          <>
            <Link
              href="/"
              className="flex items-center gap-2 px-6 hover:bg-zinc-50 dark:bg-zinc-800/50 dark:hover:bg-zinc-800 transition-colors h-full flex-1"
            >
              <Shield className="h-6 w-6 shrink-0 text-zinc-900 dark:text-zinc-100" />
              <span className="text-lg font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
            </Link>
            <button
              onClick={onToggle}
              className="flex items-center justify-center h-full px-4 text-zinc-400 hover:bg-zinc-50 dark:bg-zinc-800/50 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:text-zinc-100 transition-colors"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              <span className="sr-only">Collapse sidebar</span>
            </button>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className={cn("space-y-1 py-4", collapsed ? "px-2" : "px-3")}>
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.name}
              href={item.href}
              title={collapsed ? item.name : undefined}
              className={cn(
                "flex items-center rounded-lg text-sm font-medium transition-colors",
                collapsed ? "justify-center px-0 py-2" : "gap-3 px-3 py-2",
                isActive
                  ? "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:bg-zinc-800/50 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:text-zinc-100"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && item.name}
            </Link>
          );
        })}
      </nav>

      {/* Healthcare End-to-End Demo */}
      <div className={cn("px-3 pb-2", collapsed && "px-2")}>
        <a
          href={`${HEALTHCARE_URL}/chat`}
          target="_blank"
          rel="noopener noreferrer"
          title={collapsed ? "Healthcare Demo" : undefined}
          className={cn(
            "flex items-center rounded-lg text-sm font-medium transition-all",
            collapsed ? "justify-center px-0 py-2" : "gap-3 px-3 py-2",
            "bg-gradient-to-r from-blue-50 to-emerald-50 dark:from-blue-950/20 dark:to-emerald-950/20",
            "border border-blue-200 dark:border-blue-800",
            "text-blue-700 dark:text-blue-400 hover:from-blue-100 hover:to-emerald-100 dark:hover:from-blue-950/40 dark:hover:to-emerald-950/40",
          )}
        >
          <Stethoscope className="h-4 w-4 shrink-0" />
          {!collapsed && (
            <>
              <span className="flex-1">Healthcare Demo</span>
              <ExternalLink className="h-3 w-3 opacity-50" />
            </>
          )}
        </a>
        {!collapsed && (
          <p className="text-[10px] text-zinc-400 mt-1 px-1">
            End-to-end AI agent with real ApprovalKit flows
          </p>
        )}
      </div>

      {/* Theme toggle */}
      <div className={cn("px-3 pb-2", collapsed && "px-2")}>
        <button
          onClick={toggleTheme}
          className={cn(
            "flex items-center rounded-lg text-sm font-medium text-zinc-600 dark:text-zinc-400 dark:text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-800 transition-colors w-full",
            collapsed ? "justify-center px-0 py-2" : "gap-3 px-3 py-2"
          )}
          aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {dark ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
          {!collapsed && (dark ? "Light Mode" : "Dark Mode")}
        </button>
      </div>

      {/* User section */}
      <div className={cn("absolute bottom-0 w-full border-t border-zinc-200 dark:border-zinc-800", collapsed ? "p-2" : "p-4")}>
        {isLoading ? (
          <div className="rounded-lg bg-zinc-50 dark:bg-zinc-800/50 p-3">
            <div className="h-4 w-6 bg-zinc-200 rounded animate-pulse mx-auto" />
          </div>
        ) : user ? (
          <div className={cn("rounded-lg bg-zinc-50 dark:bg-zinc-800/50", collapsed ? "p-2 flex flex-col items-center" : "p-3")}>
            <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-2")}>
              {user.picture && (
                <img src={user.picture} alt={`${user.name || "User"} avatar`} className="h-7 w-7 rounded-full shrink-0" />
              )}
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 truncate">{user.name}</p>
                  <p className="text-xs text-zinc-400 truncate">{user.email}</p>
                </div>
              )}
            </div>
            <a
              href="/auth/logout"
              title={collapsed ? "Logout" : undefined}
              className={cn(
                "flex items-center text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 transition-colors",
                collapsed ? "mt-2 justify-center" : "mt-2 gap-1.5"
              )}
            >
              <LogOut className="h-3 w-3" />
              {!collapsed && " Logout"}
            </a>
          </div>
        ) : (
          <a
            href="/login"
            title={collapsed ? "Login" : undefined}
            className={cn(
              "flex items-center justify-center rounded-lg bg-zinc-900 dark:bg-zinc-100 dark:bg-zinc-800 text-white dark:text-zinc-900 dark:text-zinc-100 text-sm font-medium py-2 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors",
              collapsed ? "w-full" : "gap-2 w-full"
            )}
          >
            <LogIn className="h-4 w-4" />
            {!collapsed && " Login with Auth0"}
          </a>
        )}
      </div>
    </aside>
  );
}
