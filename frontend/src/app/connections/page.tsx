"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { CheckCircle2, Link2, Unlink, X, AlertCircle } from "lucide-react";
import { useRouter } from "next/navigation";

interface Connection {
  id: string;
  name: string;
  service: string;
  slug: string;
  actions: string[];
  has_credentials: boolean;
  connected_via: "auth0" | null;
  connected_user_name: string | null;
  is_active: boolean;
}

const SERVICE_LABEL: Record<string, string> = {
  github:     "GitHub",
  stripe:     "Stripe Connect",
  slack:      "Slack",
  salesforce: "Salesforce",
  gmail:      "Google",
};

const SERVICE_SUPPORTED: Record<string, boolean> = {
  github:     true,
  stripe:     true,
  slack:      true,
  salesforce: true,
  gmail:      true,
};

export default function ConnectionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [successSlug, setSuccessSlug] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api.getConnections()
      .then(setConnections)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const connected = searchParams.get("connected");
    const err = searchParams.get("error");
    if (connected) setSuccessSlug(connected);
    if (err) setError(`OAuth connect failed: ${err.replace(/_/g, " ")}`);
  }, []);

  const handleConnect = async (conn: Connection) => {
    setConnecting(conn.id);
    setError(null);
    try {
      const { url } = await api.getConnectUrl(conn.id);
      window.location.href = url;
    } catch (e: any) {
      setError(e.message || "Failed to get connect URL");
      setConnecting(null);
    }
  };

  const handleDisconnect = async (conn: Connection) => {
    if (!confirm(`Disconnect ${conn.name} from Auth0 Token Vault?`)) return;
    try {
      await api.disconnectAuth(conn.id);
      load();
    } catch (e: any) {
      setError(e.message || "Failed to disconnect");
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Connections</h1>
        <p className="text-zinc-500 mt-1">
          Connect services via Auth0 Token Vault — no API keys stored, ever.
        </p>
      </div>

      {successSlug && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex justify-between items-center">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <strong>{successSlug}</strong> connected successfully via Auth0 Token Vault.
          </span>
          <button onClick={() => setSuccessSlug(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between items-center">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span>
          <button onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900" />
        </div>
      ) : connections.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Link2 className="h-12 w-12 text-zinc-300 mx-auto mb-4" />
            <p className="text-zinc-500 mb-4">No connections yet.</p>
            <Button onClick={() => router.push("/onboarding")}>Set Up Connections</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {connections.map((conn) => {
            const label = SERVICE_LABEL[conn.service.toLowerCase()] || conn.service;
            const supported = SERVICE_SUPPORTED[conn.service.toLowerCase()] ?? false;
            const isConnecting = connecting === conn.id;

            return (
              <Card key={conn.id} className="hover:border-zinc-300 transition-colors">
                <CardContent className="py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center text-sm font-bold text-zinc-700 uppercase">
                        {conn.service.slice(0, 2)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-zinc-900">{conn.name}</span>
                          <code className="text-xs text-zinc-400 bg-zinc-50 px-1.5 py-0.5 rounded">{conn.slug}</code>
                        </div>
                        <div className="text-sm text-zinc-500 mt-0.5">
                          {conn.actions.join(", ")}
                        </div>
                        {conn.connected_user_name && (
                          <div className="text-xs text-zinc-400 mt-0.5">
                            Connected as: <span className="font-medium text-zinc-600">{conn.connected_user_name}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {conn.connected_via === "auth0" ? (
                        <>
                          <Badge variant="success">
                            <CheckCircle2 className="h-3 w-3 mr-1" /> Auth0 Token Vault
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDisconnect(conn)}
                          >
                            <Unlink className="h-4 w-4 mr-1" /> Disconnect
                          </Button>
                        </>
                      ) : supported ? (
                        <>
                          <Badge variant="warning">Not connected</Badge>
                          <Button
                            size="sm"
                            disabled={isConnecting}
                            onClick={() => handleConnect(conn)}
                          >
                            <Link2 className="h-4 w-4 mr-2" />
                            {isConnecting ? "Redirecting…" : `Connect with ${label}`}
                          </Button>
                        </>
                      ) : (
                        <Badge variant="secondary">OAuth not supported</Badge>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <div className="mt-8 p-4 bg-zinc-50 rounded-lg border border-zinc-200">
        <p className="text-xs text-zinc-500">
          <strong className="text-zinc-700">How it works:</strong> Clicking "Connect" redirects you to Auth0,
          which handles the OAuth flow with the service provider. The access token is stored securely
          in Auth0 Token Vault — ApprovalKit never sees or stores your credentials.
          When an agent action is approved, ApprovalKit retrieves the token from Auth0 and executes the action server-side.
        </p>
      </div>
    </div>
  );
}
