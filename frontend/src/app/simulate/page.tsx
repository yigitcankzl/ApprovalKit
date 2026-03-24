"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { FlaskConical, Play } from "lucide-react";

interface SimulationResult {
  matched: boolean;
  message?: string;
  rule_id?: string;
  rule_name?: string;
  model?: string;
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

  const handleSimulate = async () => {
    setRunning(true);
    try {
      let params;
      try {
        params = JSON.parse(paramsText);
      } catch {
        setResult({ matched: false, message: "Invalid JSON in params" });
        return;
      }

      const res = await api.simulateRule({ connection, action, params });
      setResult(res);
    } catch {
      // Mock result for demo
      setResult({
        matched: true,
        rule_id: "1",
        rule_name: "High-value Stripe charges",
        model: "sequential",
        approvers: [
          { id: "a1", name: "CFO", order: 0 },
          { id: "a2", name: "Finance Lead", order: 1 },
        ],
        timeout_seconds: 300,
        on_timeout: "escalate",
        binding_message: "Charge of $340 for john@example.com",
        escalation: "CEO",
        blackout: { start: null, end: null },
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Simulation Mode</h1>
        <p className="text-zinc-500 mt-1">
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
                <label className="text-sm font-medium text-zinc-700">Connection</label>
                <Input
                  value={connection}
                  onChange={(e) => setConnection(e.target.value)}
                  placeholder="stripe-prod"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-700">Action</label>
                <Input
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  placeholder="charge"
                  className="mt-1"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-700">Params (JSON)</label>
              <textarea
                value={paramsText}
                onChange={(e) => setParamsText(e.target.value)}
                rows={6}
                className="mt-1 flex w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-mono focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
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
            {!result ? (
              <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
                <FlaskConical className="h-12 w-12 mb-4" />
                <p>Run a simulation to see results</p>
              </div>
            ) : !result.matched ? (
              <div className="text-center py-8">
                <Badge variant="success" className="text-base px-4 py-1">
                  Auto-Approve
                </Badge>
                <p className="text-zinc-500 mt-3">
                  {result.message || "No matching rule — action would proceed immediately"}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-sm font-medium text-blue-800">
                    Matched: {result.rule_name}
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    Model: {result.model} | Timeout: {result.timeout_seconds}s
                  </p>
                </div>

                {result.approvers && result.approvers.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-zinc-700 mb-2">
                      CIBA Recipients:
                    </p>
                    <div className="space-y-2">
                      {result.approvers.map((a) => (
                        <div
                          key={a.id}
                          className="flex items-center justify-between p-2 bg-zinc-50 rounded"
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
                  <div className="p-3 bg-zinc-50 rounded-lg">
                    <p className="text-xs font-medium text-zinc-500">Binding Message (phone):</p>
                    <p className="text-sm mt-1">{result.binding_message}</p>
                  </div>
                )}

                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs font-medium text-zinc-500">On Timeout:</p>
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
