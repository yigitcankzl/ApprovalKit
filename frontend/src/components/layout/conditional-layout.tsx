"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Sidebar } from "./sidebar";
import { setUserSub } from "@/lib/api";

const STORAGE_KEY = "sidebar-collapsed";

export function ConditionalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useUser();
  const isWelcome = pathname === "/" || pathname === "/docs";
  const [collapsed, setCollapsed] = useState(false);

  // Sync Auth0 user sub to API client so every request includes X-User-Sub
  useEffect(() => {
    setUserSub(user?.sub ?? null);
  }, [user?.sub]);

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

  return (
    <>
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <main className={`${collapsed ? "ml-16" : "ml-64"} min-h-screen p-8 transition-all duration-200`}>
        {children}
      </main>
    </>
  );
}
