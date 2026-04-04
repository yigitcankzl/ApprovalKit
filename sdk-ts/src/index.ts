/**
 * ApprovalKit TypeScript/JavaScript SDK
 * ======================================
 * Add human approval to AI agents with a single function call.
 * After approval, Auth0 Token Vault executes the action server-side —
 * the agent never holds credentials.
 *
 * Usage (TypeScript):
 *   import { ApprovalKit, ApprovalDenied } from 'approvalkit-sdk';
 *
 *   const kit = new ApprovalKit({
 *     baseUrl: 'http://localhost:8000',
 *     apiKey: process.env.APPROVALKIT_API_KEY!,
 *     hmacSecret: process.env.APPROVALKIT_HMAC_SECRET!,
 *     userId: 'my-ts-agent',
 *   });
 *
 *   // Gate — blocks until approved
 *   const result = await kit.gate('gmail', 'send_email', {
 *     to: 'cto@company.com',
 *     subject: 'Q4 Budget Report',
 *     body: '...',
 *   });
 *   // result.status === 'approved'
 *   // result.finalParams may differ if approver modified params
 *
 *   // Decorator pattern (wraps any async function)
 *   const safeSend = kit.requiresApproval('gmail', 'send_email')(sendEmail);
 *   const result = await safeSend({ to: '...', subject: '...' });
 */

import { createHmac } from 'crypto';
import { randomUUID } from 'crypto';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ApprovalKitConfig {
  /** ApprovalKit API base URL. Defaults to APPROVALKIT_BASE_URL env var or http://localhost:8000 */
  baseUrl?: string;
  /** API key for the agent. Defaults to APPROVALKIT_API_KEY env var */
  apiKey?: string;
  /** HMAC secret for request signing. Defaults to APPROVALKIT_HMAC_SECRET env var */
  hmacSecret?: string;
  /** Agent identifier shown in the dashboard */
  userId?: string;
  /** Polling interval in seconds (default: 3) */
  pollInterval?: number;
  /** Maximum wait time in seconds (default: 300) */
  timeout?: number;
  /** HTTP request timeout in milliseconds (default: 10000) */
  httpTimeout?: number;
}

export interface GateResult {
  status: 'approved' | 'pre_approved';
  finalParams: Record<string, unknown>;
  riskScore?: number;
  riskLevel?: string;
}

export interface ApprovalRequest {
  connection: string;
  action: string;
  params: Record<string, unknown>;
  userId?: string;
  idempotencyKey?: string;
}

// ── Error ─────────────────────────────────────────────────────────────────────

export class ApprovalDenied extends Error {
  readonly status: string;
  readonly jobId: string | null;
  /** Feature 4: human-provided rejection reason from approver */
  readonly reason: string | null;

  constructor(status: string, jobId?: string | null, reason?: string | null) {
    const msg = [
      `Approval ${status}`,
      jobId ? `(job=${jobId})` : null,
      reason ? `: ${reason}` : null,
    ]
      .filter(Boolean)
      .join(' ');
    super(msg);
    this.name = 'ApprovalDenied';
    this.status = status;
    this.jobId = jobId ?? null;
    this.reason = reason ?? null;
  }
}

// ── Main SDK Class ────────────────────────────────────────────────────────────

export class ApprovalKit {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly hmacSecret: string;
  private readonly userId: string;
  private readonly pollInterval: number;
  private readonly timeout: number;
  private readonly httpTimeout: number;

  constructor(config: ApprovalKitConfig = {}) {
    this.baseUrl = (
      config.baseUrl ||
      process.env.APPROVALKIT_BASE_URL ||
      'http://localhost:8000'
    ).replace(/\/$/, '');
    this.apiKey = config.apiKey || process.env.APPROVALKIT_API_KEY || '';
    this.hmacSecret = config.hmacSecret || process.env.APPROVALKIT_HMAC_SECRET || '';
    this.userId = config.userId || 'ts-agent';
    this.pollInterval = Math.max(1, Math.min(config.pollInterval ?? 3, 120));
    this.timeout = Math.max(10, Math.min(config.timeout ?? 300, 3600));
    this.httpTimeout = Math.max(1000, Math.min(config.httpTimeout ?? 10000, 60000));
  }

  // ── Internal helpers ───────────────────────────────────────────────────────

  private _sign(body: string): { ts: string; sig: string } {
    const ts = String(Math.floor(Date.now() / 1000));
    const signKey = this.apiKey ? `${this.hmacSecret}:${this.apiKey}` : this.hmacSecret;
    const sig = createHmac('sha256', signKey)
      .update(`${ts}.${body}`)
      .digest('hex');
    return { ts, sig };
  }

  private _headers(ts: string, sig: string): Record<string, string> {
    return {
      Authorization: `Bearer ${this.apiKey}`,
      'X-Signature': `hmac-sha256=${ts}.${sig}`,
      'Content-Type': 'application/json',
    };
  }

  private async _fetch(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.httpTimeout);
    try {
      return await fetch(url, { ...options, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  private async _requestApproval(
    connection: string,
    action: string,
    params: Record<string, unknown>
  ): Promise<{ status: string; jobId?: string; risk?: Record<string, unknown> }> {
    const payload = {
      connection,
      action,
      params,
      user_id: this.userId,
      idempotency_key: randomUUID(),
    };
    const body = JSON.stringify(payload);
    const { ts, sig } = this._sign(body);

    const resp = await this._fetch(`${this.baseUrl}/api/v1/request`, {
      method: 'POST',
      headers: this._headers(ts, sig),
      body,
    });

    if (resp.status === 200) {
      const data = (await resp.json()) as Record<string, unknown>;
      return { status: (data.status as string) || 'pre_approved' };
    }
    if (resp.status === 202) {
      const data = (await resp.json()) as Record<string, unknown>;
      return {
        status: 'pending',
        jobId: data.job_id as string,
        risk: data.risk as Record<string, unknown> | undefined,
      };
    }
    if (resp.status === 403) {
      return { status: 'blocked' };
    }

    const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error((err as { detail: string }).detail || `HTTP ${resp.status}`);
  }

  private async _poll(
    jobId: string
  ): Promise<{ status: string; data: Record<string, unknown> }> {
    const deadline = Date.now() + this.timeout * 1000;
    while (Date.now() < deadline) {
      const ts = String(Math.floor(Date.now() / 1000));
      const signKey = this.apiKey ? `${this.hmacSecret}:${this.apiKey}` : this.hmacSecret;
      const sig = createHmac('sha256', signKey)
        .update(`${ts}.`)
        .digest('hex');

      const resp = await this._fetch(`${this.baseUrl}/api/v1/status/${jobId}`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'X-Signature': `hmac-sha256=${ts}.${sig}`,
        },
      });

      const data = (await resp.json()) as Record<string, unknown>;
      const status = (data.status as string) || 'pending';
      if (['approved', 'rejected', 'timeout', 'blocked'].includes(status)) {
        return { status, data };
      }

      await new Promise((r) =>
        setTimeout(r, (this.pollInterval + Math.random()) * 1000)
      );
    }
    return { status: 'timeout', data: {} };
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Gate — submit an approval request and wait for a decision.
   * Raises ApprovalDenied if rejected, timed out, or blocked.
   * Returns GateResult with status and finalParams (may be modified by approver).
   */
  async gate(
    connection: string,
    action: string,
    params: Record<string, unknown>
  ): Promise<GateResult> {
    if (!connection) throw new Error('connection must be a non-empty string');
    if (!action) throw new Error('action must be a non-empty string');

    const reqResult = await this._requestApproval(connection, action, params);

    if (reqResult.status === 'pre_approved') {
      return { status: 'pre_approved', finalParams: params };
    }
    if (reqResult.status === 'blocked') {
      throw new ApprovalDenied('blocked');
    }

    const { jobId } = reqResult;
    if (!jobId) throw new Error('No job_id in approval response');

    const { status, data } = await this._poll(jobId);

    if (status === 'approved') {
      return {
        status: 'approved',
        finalParams: (data.final_params as Record<string, unknown>) || params,
        riskScore: data.risk_score as number | undefined,
        riskLevel: data.risk_level as string | undefined,
      };
    }

    // Feature 4: pass rejection reason to the caller
    const reason = (data.rejection_reason as string | undefined) ?? null;
    throw new ApprovalDenied(status, jobId, reason);
  }

  /**
   * requiresApproval — decorator factory.
   * Wraps an async function so it goes through approval before executing.
   * The wrapped function is never called; Token Vault handles execution.
   *
   * @example
   *   const safeDeploy = kit.requiresApproval('github', 'deploy')(deploy);
   *   const result = await safeDeploy({ env: 'production', branch: 'main' });
   */
  requiresApproval(
    connection: string,
    action: string
  ): <T extends (params: Record<string, unknown>) => Promise<unknown>>(fn: T) => T {
    return <T extends (params: Record<string, unknown>) => Promise<unknown>>(fn: T): T => {
      const wrapped = async (params: Record<string, unknown>) => {
        void fn; // fn body intentionally unused — Token Vault handles execution
        return this.gate(connection, action, params);
      };
      return wrapped as unknown as T;
    };
  }

  /**
   * checkStatus — check the current status of a job without blocking.
   * Useful for async workflows where you want to poll manually.
   */
  async checkStatus(jobId: string): Promise<Record<string, unknown>> {
    const ts = String(Math.floor(Date.now() / 1000));
    const signKey = this.apiKey ? `${this.hmacSecret}:${this.apiKey}` : this.hmacSecret;
    const sig = createHmac('sha256', signKey)
      .update(`${ts}.`)
      .digest('hex');
    const resp = await this._fetch(`${this.baseUrl}/api/v1/status/${jobId}`, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'X-Signature': `hmac-sha256=${ts}.${sig}`,
      },
    });
    return resp.json() as Promise<Record<string, unknown>>;
  }

  /**
   * listConnections — list all active connections in the workspace.
   */
  async listConnections(): Promise<unknown[]> {
    const ts = String(Math.floor(Date.now() / 1000));
    const signKey = this.apiKey ? `${this.hmacSecret}:${this.apiKey}` : this.hmacSecret;
    const sig = createHmac('sha256', signKey).update(`${ts}.`).digest('hex');
    const resp = await this._fetch(`${this.baseUrl}/api/v1/connections`, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'X-Signature': `hmac-sha256=${ts}.${sig}`,
      },
    });
    return resp.json() as Promise<unknown[]>;
  }
}

export default ApprovalKit;
