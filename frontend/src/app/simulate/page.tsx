"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { FlaskConical, Play, CheckCircle2, AlertTriangle, ArrowRight, Loader2 } from "lucide-react";

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
    <div className="max-w-5xl mx-auto">
      <div className="mb-12">
        <h1 className="text-3xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-500">
          Simulate
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-2 text-sm">
          Test which rule matches without sending real CIBA notifications
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input */}
        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400">Test Request</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 block mb-1.5">Connection</label>
                <Input
                  value={connection}
                  onChange={(e) => setConnection(e.target.value)}
                  placeholder="stripe-prod"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 block mb-1.5">Action</label>
                <Input
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  placeholder="charge"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 block mb-1.5">Params (JSON)</label>
              <textarea
                value={paramsText}
                onChange={(e) => setParamsText(e.target.value)}
                rows={6}
                className="flex w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <Button onClick={handleSimulate} disabled={running} className="w-full bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white shadow-lg shadow-blue-500/20">
              {running ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Simulating...</>
              ) : (
                <><Play className="h-4 w-4 mr-2" /> Simulate</>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Result */}
        <Card>
          <CardContent className="p-6">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-4">Result</p>

            {simError ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="p-3 bg-red-50 dark:bg-red-950/20 rounded-xl mb-3">
                  <AlertTriangle className="h-8 w-8 text-red-400" />
                </div>
                <p className="text-sm text-red-600 dark:text-red-400">{simError}</p>
              </div>
            ) : !result ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="p-3 bg-zinc-100 dark:bg-zinc-800 rounded-xl mb-3">
                  <FlaskConical className="h-8 w-8 text-zinc-300 dark:text-zinc-600" />
                </div>
                <p className="text-sm text-zinc-400">Run a simulation to see results</p>
              </div>
            ) : !result.matched ? (
              <div className="flex flex-col items-center justify-center py-10">
                <div className="p-3 bg-green-50 dark:bg-green-950/20 rounded-xl mb-3">
                  <CheckCircle2 className="h-8 w-8 text-green-500" />
                </div>
                <Badge variant="success" className="text-sm px-4 py-1.5 mb-2">Auto-Approve</Badge>
                <p className="text-xs text-zinc-400 text-center max-w-xs">
                  {result.message || "No matching rule — action would proceed immediately"}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Matched rule */}
                <div className="p-4 rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
                  <p className="text-xs font-semibold text-blue-800 dark:text-blue-300">Matched Rule</p>
                  <p className="text-sm font-bold text-blue-900 dark:text-blue-200 mt-0.5">{result.rule_name}</p>
                  <div className="flex items-center gap-3 mt-2 text-xs text-blue-600 dark:text-blue-400">
                    <span>Model: <strong>{result.model}</strong></span>
                    <span>Timeout: <strong>{result.timeout_seconds}s</strong></span>
                  </div>
                </div>

                {/* Step-up */}
                {result.step_up_triggered && (
                  <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 flex items-center gap-3">
                    <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">Step-up Triggered</p>
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5 flex items-center gap-1.5">
                        {result.model} <ArrowRight className="h-3 w-3" /> {result.effective_model}
                      </p>
                    </div>
                  </div>
                )}

                {/* Approvers */}
                {result.approvers && result.approvers.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-2">CIBA Recipients</p>
                    <div className="space-y-1.5">
                      {result.approvers.map((a) => (
                        <div key={a.id} className="flex items-center justify-between p-2.5 rounded-lg border border-zinc-200 dark:border-zinc-700">
                          <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{a.name}</span>
                          <Badge variant="info" className="text-[10px]">
                            {result.model === "sequential" ? `Step ${a.order + 1}` : "Parallel"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Binding message */}
                {result.binding_message && (
                  <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1">Binding Message</p>
                    <p className="text-sm text-zinc-700 dark:text-zinc-300">{result.binding_message}</p>
                  </div>
                )}

                {/* On timeout */}
                <div className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-400 mb-1">On Timeout</p>
                  <p className="text-sm text-zinc-700 dark:text-zinc-300 capitalize">
                    {result.on_timeout}{result.escalation && ` → ${result.escalation}`}
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
