"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { FlaskConical, Play } from "lucide-react";

interface SimulationResult {
  matched: boolean;
  message?: string;
  rule_id?: string;
  rule_name?: string;
  model?: string;
  effective_model?: string;
  step_up_triggered?: boolean;
  approvers?: { id: string; name: string; order: number }[];
  timeout_seconds?: number;
  on_timeout?: string;
  binding_message?: string;
  escalation?: string;
  blackout?: { start: string | null; end: string | null };
}

export default function SimulatePage() {
  const [connection, setConnection] = useState("stripe-prod");
  const [action, setAction] = useState("charge");
  const [paramsText, setParamsText] = useState('{\n  "amount": 340,\n  "customer": "john@example.com"\n}');
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const handleSimulate = async () => {
    setRunning(true);
    setSimError(null);
    setResult(null);
    try {
      let params;
      try {
        params = JSON.parse(paramsText);
      } catch {
        setSimError("Invalid JSON in params");
        return;
      }

      const res = await api.simulateRule({ connection, action, params });
      setResult(res);
    } catch (err: any) {
      setSimError(err.message || "Simulation failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Simulation Mode</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Test which rule matches without sending real CIBA notifications
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Test Request</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Connection</label>
                <Input
                  value={connection}
                  onChange={(e) => setConnection(e.target.value)}
                  placeholder="stripe-prod"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Action</label>
                <Input
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  placeholder="charge"
                  className="mt-1"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600">Params (JSON)</label>
              <textarea
                value={paramsText}
                onChange={(e) => setParamsText(e.target.value)}
                rows={6}
                className="mt-1 flex w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-mono focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
              />
            </div>
            <Button onClick={handleSimulate} disabled={running} className="w-full">
              <Play className="h-4 w-4 mr-2" />
              {running ? "Simulating..." : "Simulate"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
          </CardHeader>
          <CardContent>
            {simError ? (
              <div className="flex flex-col items-center justify-center py-12 text-red-500">
                <FlaskConical className="h-12 w-12 mb-4 text-red-300" />
                <p>{simError}</p>
              </div>
            ) : !result ? (
              <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
                <FlaskConical className="h-12 w-12 mb-4" />
                <p>Run a simulation to see results</p>
              </div>
            ) : !result.matched ? (
              <div className="text-center py-8">
                <Badge variant="success" className="text-base px-4 py-1">
                  Auto-Approve
                </Badge>
                <p className="text-zinc-500 dark:text-zinc-400 mt-3">
                  {result.message || "No matching rule — action would proceed immediately"}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                  <p className="text-sm font-medium text-blue-800">
                    Matched: {result.rule_name}
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    Model: {result.model}{result.step_up_triggered ? ` → ${result.effective_model}` : ""} | Timeout: {result.timeout_seconds}s
                  </p>
                </div>
                {result.step_up_triggered && (
                  <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-2">
                    <Badge variant="warning">Step-up Triggered</Badge>
                    <span className="text-sm text-yellow-800">
                      Approval model escalated: {result.model} → {result.effective_model}
                    </span>
                  </div>
                )}

                {result.approvers && result.approvers.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 dark:text-zinc-600 mb-2">
                      CIBA Recipients:
                    </p>
                    <div className="space-y-2">
                      {result.approvers.map((a) => (
                        <div
                          key={a.id}
                          className="flex items-center justify-between p-2 bg-zinc-50 dark:bg-zinc-800/50 rounded"
                        >
                          <span className="text-sm">{a.name}</span>
                          <Badge variant="info">
                            {result.model === "sequential" ? `Step ${a.order + 1}` : "Parallel"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {result.binding_message && (
                  <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                    <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">Binding Message (phone):</p>
                    <p className="text-sm mt-1">{result.binding_message}</p>
                  </div>
                )}

                <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                  <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">On Timeout:</p>
                  <p className="text-sm mt-1 capitalize">
                    {result.on_timeout}
                    {result.escalation && ` → ${result.escalation}`}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
