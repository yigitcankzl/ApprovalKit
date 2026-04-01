"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Shield, CheckCircle, XCircle, Clock, AlertTriangle, Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TokenInfo {
  valid: boolean;
  job_id: string | null;
  approver_email: string | null;
}

interface JobStatus {
  id: string;
  connection: string;
  action: string;
  state: string;
  params: Record<string, unknown>;
  binding_message?: string;
  created_at: string;
}

export default function ApprovePage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";
  const presetDecision = searchParams.get("decision") as "approve" | "reject" | null;

  const [loading, setLoading] = useState(true);
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ decision: string; success: boolean; execution?: { success?: boolean; skipped?: boolean; reason?: string; error?: string } } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("No approval token provided");
      setLoading(false);
      return;
    }

    // Verify token
    fetch(`${API_BASE}/api/v1/approve/verify/${encodeURIComponent(token)}`)
      .then((r) => r.json())
      .then(async (info: TokenInfo) => {
        setTokenInfo(info);
        if (!info.valid || !info.job_id) {
          setError("This approval link has expired or is invalid.");
          setLoading(false);
          return;
        }

        // Fetch job status
        try {
          const statusResp = await fetch(`${API_BASE}/api/v1/test-status/${info.job_id}`);
          if (statusResp.ok) {
            const status = await statusResp.json();
            setJobStatus(status);
          }
        } catch {
          // Job status fetch is best-effort
        }
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to verify approval token");
        setLoading(false);
      });
  }, [token]);

  const handleDecision = async (decision: "approve" | "reject") => {
    if (!tokenInfo?.job_id) return;
    setSubmitting(true);

    try {
      const resp = await fetch(`${API_BASE}/api/v1/jobs/${tokenInfo.job_id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });

      if (resp.ok) {
        const data = await resp.json().catch(() => ({}));
        setResult({ decision, success: true, execution: data.execution || undefined });
      } else {
        const err = await resp.json().catch(() => ({ detail: "Request failed" }));
        setResult({ decision, success: false });
        setError(err.detail || "Failed to submit decision");
      }
    } catch {
      setResult({ decision: decision, success: false });
      setError("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  };

  // Auto-submit if preset decision in URL
  useEffect(() => {
    if (presetDecision && tokenInfo?.valid && !result && !submitting) {
      handleDecision(presetDecision);
    }
  }, [presetDecision, tokenInfo, result, submitting]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-950 dark:to-zinc-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-zinc-900 dark:text-zinc-100">
            <Shield className="h-8 w-8" />
            <span className="text-2xl font-bold">ApprovalKit</span>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Human Approval Middleware for AI Agents
          </p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-zinc-400 mx-auto mb-3" />
              <p className="text-zinc-500">Verifying approval link...</p>
            </div>
          ) : error && !result ? (
            <div className="p-12 text-center">
              <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-3" />
              <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Link Invalid
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{error}</p>
            </div>
          ) : result ? (
            <div className="p-12 text-center">
              {result.success ? (
                <>
                  {result.decision === "approve" ? (
                    <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
                  ) : (
                    <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
                  )}
                  <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                    {result.decision === "approve" ? "Approved" : "Rejected"}
                  </h2>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    {result.decision === "reject"
                      ? "The action has been rejected. The agent has been notified."
                      : result.execution?.success
                        ? "Approved and executed successfully via Token Vault."
                        : result.execution?.skipped
                          ? `Approved, but execution skipped: ${result.execution.reason || "service not connected"}.`
                          : result.execution?.error
                            ? `Approved, but execution failed: ${result.execution.error}.`
                            : "The action has been approved and will be executed via Token Vault."}
                  </p>
                  {result.decision === "approve" && result.execution && !result.execution.success && !result.execution.skipped && result.execution.error && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                      The agent will be notified. You may need to reconnect the service in the Connections page.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto mb-4" />
                  <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                    Submission Failed
                  </h2>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{error}</p>
                </>
              )}
            </div>
          ) : (
            <>
              {/* Job Details */}
              <div className="p-6 border-b border-zinc-100 dark:border-zinc-800">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    Approval Request
                  </span>
                </div>

                {jobStatus && (
                  <div className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                        Service
                      </label>
                      <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                        {jobStatus.connection}
                      </p>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                        Action
                      </label>
                      <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-0.5">
                        {jobStatus.action}
                      </p>
                    </div>
                    {jobStatus.params && Object.keys(jobStatus.params).length > 0 && (
                      <div>
                        <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                          Parameters
                        </label>
                        <div className="mt-1 rounded-lg bg-zinc-50 dark:bg-zinc-800 p-3 text-xs font-mono text-zinc-700 dark:text-zinc-300 max-h-32 overflow-auto">
                          {Object.entries(jobStatus.params).map(([key, value]) => (
                            <div key={key}>
                              <span className="text-zinc-500">{key}:</span>{" "}
                              <span>{JSON.stringify(value)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {!jobStatus && tokenInfo && (
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    Job ID: <span className="font-mono text-xs">{tokenInfo.job_id}</span>
                  </p>
                )}
              </div>

              {/* Approver Info */}
              {tokenInfo?.approver_email && (
                <div className="px-6 py-3 bg-zinc-50 dark:bg-zinc-800/50 text-xs text-zinc-500 dark:text-zinc-400">
                  Approving as <strong className="text-zinc-700 dark:text-zinc-300">{tokenInfo.approver_email}</strong>
                </div>
              )}

              {/* Action Buttons */}
              <div className="p-6 flex gap-3">
                <button
                  onClick={() => handleDecision("reject")}
                  disabled={submitting}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 font-medium text-sm hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" />
                  Reject
                </button>
                <button
                  onClick={() => handleDecision("approve")}
                  disabled={submitting}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-emerald-600 dark:bg-emerald-500 text-white font-medium text-sm hover:bg-emerald-700 dark:hover:bg-emerald-600 transition-colors disabled:opacity-50"
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle className="h-4 w-4" />
                  )}
                  Approve
                </button>
              </div>
            </>
          )}
        </div>

        {/* Security Note */}
        <div className="text-center mt-6">
          <p className="text-xs text-zinc-400 dark:text-zinc-500">
            Secured by Auth0 Token Vault. Credentials are never exposed to the agent.
          </p>
        </div>
      </div>
    </div>
  );
}
