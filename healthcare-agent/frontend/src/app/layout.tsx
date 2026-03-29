import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "Healthcare AI Agent — MedCore General Hospital",
  description: "HIPAA-compliant healthcare management powered by ApprovalKit",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen flex">
        <Sidebar />
        <main className="flex-1 ml-64 p-8">{children}</main>
      </body>
    </html>
  );
}
