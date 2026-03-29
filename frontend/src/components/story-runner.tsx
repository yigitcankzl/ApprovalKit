"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Play, CheckCircle2, Clock, Loader2, XCircle, Smartphone, Shield,
  ArrowRight, AlertTriangle, Bot,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

export interface StoryStep {
  label: string;
  description: string;
  connection: string;
  action: string;
  params: Record<string, unknown>;
  expectApproval: boolean; // true = will need human approval, false = auto-approve
}

export interface Story {
  id: string;
  title: string;
  prompt: string; // what the "user" said to the agent
  steps: StoryStep[];
}

interface StepState {
  status: "waiting" | "running" | "pending" | "approved" | "rejected" | "auto_approved" | "timeout" | "error";
  jobId?: string;
  message?: string;
}

// ── Story Runner Component ───────────────────────────────────────────────────

export function StoryRunner({ story, onDone }: { story: Story; onDone?: () => void }) {
  const [stepStates, setStepStates] = useState<StepState[]>(
    story.steps.map(() => ({ status: "waiting" }))
  );
  const [currentStep, setCurrentStep] = useState(-1);
  const [started, setStarted] = useState(false);
  const [finished, setFinished] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timelineRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    timelineRef.current?.scrollTo({ top: timelineRef.current.scrollHeight, behavior: "smooth" });
  }, [stepStates, currentStep]);

  // Cleanup
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const updateStep = (index: number, update: Partial<StepState>) => {
    setStepStates(prev => prev.map((s, i) => i === index ? { ...s, ...update } : s));
  };

  const runStep = async (index: number) => {
    const step = story.steps[index];
    setCurrentStep(index);
    updateStep(index, { status: "running" });

    // Small delay for visual effect
    await sleep(600);

    try {
      const res = await api.sendTestRequest({
        connection: step.connection,
        action: step.action,
        params: step.params,
      });

      if (res.status === "auto_approved" || res.status === "pre_approved") {
        updateStep(index, { status: "auto_approved" });
        await sleep(800);
        proceedToNext(index);
      } else if (res.job_id) {
        updateStep(index, { status: "pending", jobId: res.job_id });
        // Start polling
        pollRef.current = setInterval(async () => {
          try {
            const s = await api.getJobStatus(res.job_id);
            const terminal = ["approved", "rejected", "timeout", "blocked"];
            if (terminal.includes(s.status)) {
              if (pollRef.current) clearInterval(pollRef.current);
              updateStep(index, { status: s.status as StepState["status"] });
              if (s.status === "approved") {
                await sleep(600);
                proceedToNext(index);
              } else {
                // Rejected/timeout - story stops
                setFinished(true);
                onDone?.();
              }
            }
          } catch {}
        }, 2000);
      } else {
        updateStep(index, { status: "auto_approved" });
        await sleep(800);
        proceedToNext(index);
      }
    } catch (e: any) {
      updateStep(index, { status: "error", message: e.message });
      setFinished(true);
      onDone?.();
    }
  };

  const proceedToNext = (index: number) => {
    if (index + 1 < story.steps.length) {
      runStep(index + 1);
    } else {
      setFinished(true);
      onDone?.();
    }
  };

  const handleStart = () => {
    setStarted(true);
    setFinished(false);
    setStepStates(story.steps.map(() => ({ status: "waiting" })));
    runStep(0);
  };

  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setStarted(false);
    setFinished(false);
    setCurrentStep(-1);
    setStepStates(story.steps.map(() => ({ status: "waiting" })));
  };

  const approvedCount = stepStates.filter(s => s.status === "approved").length;
  const autoCount = stepStates.filter(s => s.status === "auto_approved").length;
  const pendingStep = stepStates.findIndex(s => s.status === "pending");

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 overflow-hidden bg-white dark:bg-zinc-900">
      {/* Header */}
      <div className="p-5 border-b border-zinc-100 dark:border-zinc-800">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg shrink-0">
            <Bot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">{story.title}</h3>
            <div className="mt-2 p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-100 dark:border-zinc-700">
              <p className="text-xs text-zinc-400 mb-1">User prompt:</p>
              <p className="text-sm text-zinc-700 dark:text-zinc-300 italic">&ldquo;{story.prompt}&rdquo;</p>
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div ref={timelineRef} className="p-5 space-y-1 max-h-[500px] overflow-y-auto">
        {!started ? (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-400 mb-1">Agent will execute {story.steps.length} actions</p>
            <p className="text-xs text-zinc-400">
              {story.steps.filter(s => s.expectApproval).length} need approval,{" "}
              {story.steps.filter(s => !s.expectApproval).length} auto-approve
            </p>
          </div>
        ) : (
          story.steps.map((step, i) => {
            const state = stepStates[i];
            return (
              <div key={i} className="relative">
                {/* Connector line */}
                {i > 0 && (
                  <div className={`absolute left-[17px] -top-1 w-0.5 h-2 ${
                    state.status !== "waiting" ? "bg-zinc-300 dark:bg-zinc-600" : "bg-zinc-100 dark:bg-zinc-800"
                  }`} />
                )}

                <div className={`flex items-start gap-3 p-3 rounded-lg transition-all duration-300 ${
                  state.status === "waiting" ? "opacity-40" :
                  state.status === "running" ? "bg-blue-50/50 dark:bg-blue-950/10" :
                  state.status === "pending" ? "bg-amber-50/50 dark:bg-amber-950/10" :
                  state.status === "approved" || state.status === "auto_approved" ? "bg-green-50/30 dark:bg-green-950/10" :
                  state.status === "rejected" || state.status === "timeout" ? "bg-red-50/30 dark:bg-red-950/10" : ""
                }`}>
                  {/* Status icon */}
                  <div className="mt-0.5 shrink-0">
                    {state.status === "waiting" && <div className="w-[18px] h-[18px] rounded-full border-2 border-zinc-200 dark:border-zinc-700" />}
                    {state.status === "running" && <Loader2 className="h-[18px] w-[18px] text-blue-500 animate-spin" />}
                    {state.status === "pending" && <Clock className="h-[18px] w-[18px] text-amber-500 animate-pulse" />}
                    {state.status === "approved" && <CheckCircle2 className="h-[18px] w-[18px] text-green-500" />}
                    {state.status === "auto_approved" && <CheckCircle2 className="h-[18px] w-[18px] text-green-400" />}
                    {state.status === "rejected" && <XCircle className="h-[18px] w-[18px] text-red-500" />}
                    {state.status === "timeout" && <Clock className="h-[18px] w-[18px] text-zinc-400" />}
                    {state.status === "error" && <AlertTriangle className="h-[18px] w-[18px] text-red-500" />}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{step.label}</span>
                      <Badge variant="default" className="text-[9px] font-mono">
                        {step.connection}/{step.action}
                      </Badge>
                    </div>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{step.description}</p>

                    {/* Status messages */}
                    {state.status === "running" && (
                      <p className="text-xs text-blue-600 dark:text-blue-400 mt-1.5">Submitting to ApprovalKit...</p>
                    )}
                    {state.status === "auto_approved" && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-1.5">
                        Auto-approved — no rule match. Token Vault executed.
                      </p>
                    )}
                    {state.status === "pending" && (
                      <div className="mt-2 space-y-1.5">
                        <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                          <Smartphone className="h-3 w-3 shrink-0" />
                          Waiting for approval — Guardian push sent to approver(s)
                        </div>
                        <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
                          <Shield className="h-3 w-3 shrink-0" />
                          Approve from your phone or from the Dashboard
                        </div>
                      </div>
                    )}
                    {state.status === "approved" && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-1.5">
                        Approved — Token Vault executed. Agent never saw the credentials.
                      </p>
                    )}
                    {state.status === "rejected" && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1.5">
                        Rejected by approver. Action was NOT executed.
                      </p>
                    )}
                    {state.status === "error" && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1.5">{state.message}</p>
                    )}
                  </div>

                  {/* Step number */}
                  <span className="text-[10px] text-zinc-300 dark:text-zinc-600 font-mono shrink-0">
                    {i + 1}/{story.steps.length}
                  </span>
                </div>
              </div>
            );
          })
        )}

        {/* Summary */}
        {finished && (
          <div className="mt-4 p-4 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-4 w-4 text-emerald-500" />
              <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Story Complete</span>
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-zinc-500 dark:text-zinc-400">
              <span>{story.steps.length} actions total</span>
              {approvedCount > 0 && <span className="text-green-600 dark:text-green-400">{approvedCount} human-approved</span>}
              {autoCount > 0 && <span className="text-emerald-600 dark:text-emerald-400">{autoCount} auto-approved</span>}
              {stepStates.some(s => s.status === "rejected") && (
                <span className="text-red-600 dark:text-red-400">
                  {stepStates.filter(s => s.status === "rejected").length} rejected
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-2">
              The agent never held any credentials. All actions were executed via Auth0 Token Vault after human approval.
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-zinc-100 dark:border-zinc-800 flex items-center gap-3">
        {!started ? (
          <Button onClick={handleStart} className="bg-gradient-to-r from-blue-600 to-emerald-500 hover:from-blue-700 hover:to-emerald-600 text-white shadow-lg shadow-blue-500/20">
            <Play className="h-4 w-4 mr-2" /> Run Story
          </Button>
        ) : finished ? (
          <Button variant="outline" onClick={handleReset}>
            <Play className="h-4 w-4 mr-2" /> Run Again
          </Button>
        ) : (
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {pendingStep >= 0 ? "Waiting for approval..." : "Processing..."}
          </div>
        )}
        <div className="flex-1" />
        {started && (
          <div className="flex items-center gap-1.5">
            {story.steps.map((_, i) => (
              <div key={i} className={`w-2 h-2 rounded-full transition-colors ${
                stepStates[i].status === "approved" || stepStates[i].status === "auto_approved" ? "bg-green-500" :
                stepStates[i].status === "pending" ? "bg-amber-500 animate-pulse" :
                stepStates[i].status === "running" ? "bg-blue-500 animate-pulse" :
                stepStates[i].status === "rejected" || stepStates[i].status === "error" ? "bg-red-500" :
                "bg-zinc-200 dark:bg-zinc-700"
              }`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)); }

// ── Story definitions for each demo agent ────────────────────────────────────

export const AGENT_STORIES: Record<string, Story[]> = {
  expense: [{
    id: "conference",
    title: "Organize Team Conference Trip",
    prompt: "Plan a trip to AWS re:Invent 2026 for 3 engineers. Book everything needed.",
    steps: [
      { label: "Book flights", description: "$2,800 x 3 engineers = $8,400 total", connection: "stripe-prod", action: "charge", params: { type: "expense", amount_usd: 8400, category: "travel", description: "AWS re:Invent 2026 — flights for 3 engineers", customer: "travel@company.com" }, expectApproval: true },
      { label: "Reserve hotel", description: "$285/night x 4 nights x 3 rooms = $3,420", connection: "stripe-prod", action: "charge", params: { type: "expense", amount_usd: 3420, category: "accommodation", description: "Hotel near Las Vegas Convention Center — 3 rooms, 4 nights", customer: "travel@company.com" }, expectApproval: true },
      { label: "Buy conference tickets", description: "$350 registration x 3", connection: "stripe-prod", action: "charge", params: { type: "expense", amount_usd: 1050, category: "registration", description: "AWS re:Invent 2026 registration x 3", customer: "travel@company.com" }, expectApproval: true },
      { label: "Send itinerary email", description: "Email trip details to all attendees", connection: "gmail-prod", action: "send_email", params: { type: "invite", recipient: "team@company.com", subject: "AWS re:Invent 2026 — Trip Itinerary", body_preview: "Your flights, hotel, and registration are confirmed." }, expectApproval: false },
      { label: "Post in #team Slack", description: "Announce the trip to the team", connection: "slack-prod", action: "send_message", params: { channel: "#engineering", message: "AWS re:Invent 2026 trip confirmed for 3 engineers. Total: $12,870." }, expectApproval: false },
    ],
  }],

  release_manager: [{
    id: "prod_deploy",
    title: "Ship v2.5.0 to Production",
    prompt: "Deploy version 2.5.0 to production with all safety checks.",
    steps: [
      { label: "Deploy to staging", description: "Run full test suite on staging environment", connection: "github-main", action: "deploy", params: { ref: "v2.5.0", environment: "staging", service: "api" }, expectApproval: false },
      { label: "Deploy to production", description: "Push v2.5.0 to production servers", connection: "github-main", action: "deploy", params: { ref: "v2.5.0", environment: "production", service: "api" }, expectApproval: true },
      { label: "Notify team on Slack", description: "Post deployment status to #releases", connection: "slack-prod", action: "send_message", params: { channel: "#releases", message: "v2.5.0 deployed to production successfully." }, expectApproval: false },
    ],
  }],

  security_incident: [{
    id: "breach_response",
    title: "Respond to Data Breach",
    prompt: "We detected unauthorized access from IP 203.0.113.42. Lock everything down.",
    steps: [
      { label: "Alert security team", description: "Post critical alert to #security channel", connection: "slack-prod", action: "send_message", params: { channel: "#security", message: "[CRITICAL] Unauthorized access detected from 203.0.113.42 — 47 failed attempts in 5 minutes. Initiating lockdown." }, expectApproval: false },
      { label: "Lock compromised repo", description: "Prevent any code changes to affected repository", connection: "github-prod", action: "lock_repo", params: { repo: "acme/api", reason: "Suspicious commits detected from compromised account" }, expectApproval: true },
      { label: "Revoke production tokens", description: "Nuclear option — revoke all production access tokens", connection: "github-prod", action: "revoke_tokens", params: { scope: "production", reason: "Confirmed data breach — all production credentials potentially compromised" }, expectApproval: true },
      { label: "Send incident report", description: "Email incident summary to leadership", connection: "gmail-prod", action: "send_email", params: { type: "incident_report", recipient: "leadership@company.com", subject: "INCIDENT: Production credentials compromised — lockdown complete", body_preview: "All production tokens revoked. Affected repo locked. Full investigation underway." }, expectApproval: false },
    ],
  }],

  account_takeover: [{
    id: "fraud_response",
    title: "Handle Account Takeover Attempt",
    prompt: "User reports unauthorized transactions on their account. Investigate and remediate.",
    steps: [
      { label: "Freeze account", description: "Immediately suspend the compromised account", connection: "salesforce-prod", action: "update_case", params: { type: "account_freeze", email: "victim@example.com", reason: "Multiple unauthorized transactions detected" }, expectApproval: true },
      { label: "Issue compensation", description: "Refund $450 for unauthorized charges", connection: "stripe-prod", action: "credit", params: { amount_usd: 450, customer: "victim@example.com", reason: "Compensation for unauthorized transactions during account takeover" }, expectApproval: true },
      { label: "Notify customer", description: "Email customer about account freeze and next steps", connection: "gmail-prod", action: "send_email", params: { type: "security_notice", recipient: "victim@example.com", subject: "Your account has been secured", body_preview: "We detected unauthorized activity and froze your account. $450 has been refunded." }, expectApproval: false },
    ],
  }],

  recruitment: [{
    id: "hire_engineer",
    title: "Hire Senior Engineer",
    prompt: "Extend offer to Sarah Chen for the Senior Engineer role. $175k package.",
    steps: [
      { label: "Send offer letter", description: "Email formal offer to candidate", connection: "gmail-prod", action: "send_email", params: { type: "offer_letter", recipient: "sarah.chen@email.com", subject: "Offer Letter — Senior Engineer at Acme Corp", salary_usd: 175000, body_preview: "We are excited to offer you the Senior Engineer position." }, expectApproval: true },
      { label: "Provision GitHub access", description: "Add to organization as member", connection: "github-prod", action: "add_member", params: { username: "sarahchen", org: "acme", role: "member", system: "github" }, expectApproval: true },
      { label: "Send welcome email", description: "Welcome package with onboarding info", connection: "gmail-prod", action: "send_email", params: { type: "invite", recipient: "sarah.chen@email.com", subject: "Welcome to Acme — Onboarding Info", body_preview: "Your first day is March 15. Here's everything you need." }, expectApproval: false },
      { label: "Announce in Slack", description: "Post new hire announcement", connection: "slack-prod", action: "send_message", params: { channel: "#general", message: "Welcome Sarah Chen! She joins us as Senior Engineer starting March 15." }, expectApproval: false },
    ],
  }],

  access_provisioning: [{
    id: "onboard_admin",
    title: "Provision Admin Access for New CTO",
    prompt: "New CTO starts Monday. Set up full admin access across all systems.",
    steps: [
      { label: "Grant GitHub admin", description: "Add to org with admin privileges", connection: "github-prod", action: "add_member", params: { username: "newcto", org: "acme", role: "admin" }, expectApproval: true },
      { label: "Grant financial systems", description: "Access to financial dashboards and billing", connection: "github-prod", action: "add_member", params: { username: "newcto", system: "financial", role: "admin" }, expectApproval: true },
      { label: "Send access credentials", description: "Email with all access details", connection: "gmail-prod", action: "send_email", params: { type: "invite", recipient: "newcto@company.com", subject: "Your system access is ready", body_preview: "GitHub admin, financial systems — all provisioned." }, expectApproval: false },
    ],
  }],

  patient_data: [{
    id: "external_referral",
    title: "Share Patient Records for Specialist Referral",
    prompt: "Patient MRN-4821 needs cardiology consultation. Share records with City Heart Clinic.",
    steps: [
      { label: "Share with external clinic", description: "Send patient records to City Heart Clinic", connection: "google-drive-prod", action: "share", params: { patient_id: "MRN-4821", recipient_name: "City Heart Clinic", recipient_type: "external_clinic", recipient_email: "records@cityheartclinic.com" }, expectApproval: true },
      { label: "Notify patient", description: "Email patient about the referral", connection: "gmail-prod", action: "send_email", params: { type: "referral_notice", recipient: "patient4821@email.com", subject: "Referral to City Heart Clinic", body_preview: "Your records have been shared with City Heart Clinic for cardiology consultation." }, expectApproval: false },
      { label: "Log in Slack", description: "Notify care team about referral", connection: "slack-prod", action: "send_message", params: { channel: "#patient-care", message: "Patient MRN-4821 referred to City Heart Clinic for cardiology. Records shared." }, expectApproval: false },
    ],
  }],

  prescription_refill: [{
    id: "controlled_substance",
    title: "Process Controlled Substance Prescription",
    prompt: "Patient MRN-1122 needs Adderall refill and dosage adjustment from 20mg to 30mg.",
    steps: [
      { label: "Refill prescription", description: "Adderall 20mg — controlled substance refill", connection: "gmail-prod", action: "send_email", params: { type: "controlled_refill", medication: "Adderall", dosage: "20mg", patient_id: "MRN-1122", recipient: "pharmacy@hospital.com", subject: "Rx Refill: Adderall 20mg for MRN-1122" }, expectApproval: true },
      { label: "Adjust dosage", description: "Increase from 20mg to 30mg — requires doctor + pharmacist", connection: "gmail-prod", action: "send_email", params: { type: "dosage_change", medication: "Adderall", dosage: "30mg", patient_id: "MRN-1122", recipient: "pharmacy@hospital.com", subject: "Dosage Change: Adderall 20mg → 30mg for MRN-1122" }, expectApproval: true },
      { label: "Notify patient", description: "Confirm prescription changes to patient", connection: "gmail-prod", action: "send_email", params: { type: "invite", recipient: "patient1122@email.com", subject: "Your prescription has been updated", body_preview: "Adderall dosage adjusted to 30mg. Refill ready at pharmacy." }, expectApproval: false },
    ],
  }],

  gdpr_request: [{
    id: "data_deletion",
    title: "Process GDPR Deletion Request",
    prompt: "User john@example.com requested complete data deletion under GDPR Article 17.",
    steps: [
      { label: "Delete user data", description: "Remove all personal data for john@example.com", connection: "github-prod", action: "deploy", params: { type: "gdpr_deletion", subject_email: "john@example.com", scope: "full", is_bulk: false }, expectApproval: true },
      { label: "Confirmation email", description: "Notify user that deletion is complete", connection: "gmail-prod", action: "send_email", params: { type: "gdpr_confirmation", recipient: "john@example.com", subject: "Your data has been deleted — GDPR Request Complete", body_preview: "All personal data associated with your account has been permanently deleted." }, expectApproval: false },
      { label: "Log compliance event", description: "Post to #legal for compliance tracking", connection: "slack-prod", action: "send_message", params: { channel: "#legal", message: "GDPR Art.17 deletion complete for john@example.com. All data removed." }, expectApproval: false },
    ],
  }],

  api_key_rotation: [{
    id: "emergency_rotation",
    title: "Emergency Key Rotation After Leak",
    prompt: "A production API key was accidentally committed to a public repo. Rotate everything.",
    steps: [
      { label: "Rotate leaked key", description: "Emergency rotation of exposed production key", connection: "github-prod", action: "deploy", params: { type: "key_rotation", service: "stripe-production", urgency: "emergency", reason: "Key leaked in public commit" }, expectApproval: true },
      { label: "Rotate all related keys", description: "Full rotation of all production credentials", connection: "github-prod", action: "deploy", params: { type: "key_rotation", migration_name: "rotate_all_keys", scope: "production", reason: "Precautionary rotation after key leak", is_third_party: false }, expectApproval: true },
      { label: "Alert on Slack", description: "Notify team about completed rotation", connection: "slack-prod", action: "send_message", params: { channel: "#security", message: "EMERGENCY: All production keys rotated after public leak. Services restored." }, expectApproval: false },
      { label: "Send postmortem", description: "Email incident postmortem to stakeholders", connection: "gmail-prod", action: "send_email", params: { type: "incident_report", recipient: "engineering@company.com", subject: "Postmortem: Production Key Leaked in Public Commit", body_preview: "Root cause: .env file committed. All keys rotated. Pre-commit hook added." }, expectApproval: false },
    ],
  }],
};
