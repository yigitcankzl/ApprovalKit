"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";

const STORAGE_KEY = "sidebar-collapsed";

export function ConditionalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isWelcome = pathname === "/" || pathname === "/docs";
  const [collapsed, setCollapsed] = useState(false);

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
