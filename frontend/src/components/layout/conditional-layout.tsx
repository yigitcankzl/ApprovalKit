"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Sidebar } from "./sidebar";
import { setUserSub } from "@/lib/api";

const STORAGE_KEY = "sidebar-collapsed";

export function ConditionalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isLoading } = useUser();
  const isWelcome = pathname === "/" || pathname === "/docs" || pathname?.startsWith("/docs/") || pathname === "/setup" || pathname === "/login";
  const [collapsed, setCollapsed] = useState(false);
  const [subReady, setSubReady] = useState(false);

  // Sync Auth0 user sub to API client so every request includes X-User-Sub
  useEffect(() => {
    if (!isLoading) {
      setUserSub(user?.sub ?? null);
      setSubReady(true);
    }
  }, [user?.sub, isLoading]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggle = () =>
    setCollapsed((prev) => {
      localStorage.setItem(STORAGE_KEY, String(!prev));
      return !prev;
    });

  if (isWelcome) {
    return <main className="min-h-screen">{children}</main>;
  }

  // Wait for Auth0 session to resolve before rendering pages (prevents race condition)
  if (!subReady) {
    return (
      <>
        <Sidebar collapsed={collapsed} onToggle={toggle} />
        <main className={`${collapsed ? "ml-16" : "ml-64"} min-h-screen p-8 transition-all duration-200`}>
          <div className="max-w-6xl mx-auto flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-400" />
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main className={`${collapsed ? "ml-16" : "ml-64"} min-h-screen p-8 transition-all duration-200`}>
        <div className="max-w-6xl mx-auto">
          {children}
        </div>
      </main>
    </>
  );
}
