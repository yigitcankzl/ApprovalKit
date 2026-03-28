"use client";

import { useEffect, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Shield, Loader2 } from "lucide-react";

export default function LoginPage() {
  const { user, isLoading } = useUser();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isLoading && user) {
      window.location.href = "/dashboard";
    }
  }, [isLoading, user]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center gap-2 mb-6">
          <Shield className="h-8 w-8 text-zinc-900 dark:text-zinc-100" />
          <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">ApprovalKit</span>
        </div>
        <p className="text-sm text-zinc-500 mb-6">Human approval middleware for AI agents</p>
        <Card className="border-zinc-200 dark:border-zinc-800">
          <CardContent className="pt-6">
            <Button
              className="w-full"
              onClick={() => { setLoading(true); window.location.href = "/auth/login?returnTo=/dashboard"; }}
              disabled={loading}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
