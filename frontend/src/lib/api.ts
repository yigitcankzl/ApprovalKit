const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Cached user sub from Auth0 session
let _userSub: string | null = null;

export function setUserSub(sub: string | null) {
  _userSub = sub;
}

async function fetchAPI(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(_userSub ? { "X-User-Sub": _userSub } : {}),
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    const msg = error.detail || `HTTP ${res.status}`;
    // Redirect to setup if workspace not found — but only if user sub is loaded (avoid race condition)
    if (res.status === 404 && msg.includes("No workspace") && _userSub && typeof window !== "undefined" && !window.location.pathname.startsWith("/setup") && !window.location.pathname.startsWith("/settings")) {
      window.location.href = "/setup";
      return new Promise(() => {}); // never resolves — page is navigating
    }
    throw new Error(msg);
  }

  if (res.status === 204) return null;

  return res.json();
}

export const api = {
  // Rules
  getRules: () => fetchAPI("/api/v1/rules"),
  getRule: (id: string) => fetchAPI(`/api/v1/rules/${id}`),
  createRule: (data: any) => fetchAPI("/api/v1/rules", { method: "POST", body: JSON.stringify(data) }),
  updateRule: (id: string, data: any) => fetchAPI(`/api/v1/rules/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRule: (id: string) => fetchAPI(`/api/v1/rules/${id}`, { method: "DELETE" }),
  simulateRule: (params: any) =>
    fetchAPI(`/api/v1/rules/simulate?connection=${params.connection}&action=${params.action}`, {
      method: "POST",
      body: JSON.stringify(params.params),
    }),

  // Approvers
  getApprovers: () => fetchAPI("/api/v1/approvers"),
  createApprover: (data: any) => fetchAPI("/api/v1/approvers", { method: "POST", body: JSON.stringify(data) }),
  updateApprover: (id: string, data: any) => fetchAPI(`/api/v1/approvers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteApprover: (id: string) => fetchAPI(`/api/v1/approvers/${id}`, { method: "DELETE" }),
  setDelegation: (id: string, data: any) => fetchAPI(`/api/v1/approvers/${id}/delegate`, { method: "PUT", body: JSON.stringify(data) }),
  removeDelegation: (id: string) => fetchAPI(`/api/v1/approvers/${id}/delegate`, { method: "DELETE" }),
  getLinkUrl: (id: string) => fetchAPI(`/api/v1/approvers/${id}/link-url`),

  // Audit & Dashboard
  getRecentActivity: (limit?: number) => {
    const q = limit ? `?limit=${limit}` : "";
    return fetchAPI(`/api/v1/recent-activity${q}`);
  },
  getAuditLog: (params?: { limit?: number; offset?: number; event_type?: string }) => {
    const search = new URLSearchParams();
    if (params?.limit) search.set("limit", String(params.limit));
    if (params?.offset) search.set("offset", String(params.offset));
    if (params?.event_type) search.set("event_type", params.event_type);
    return fetchAPI(`/api/v1/audit?${search.toString()}`);
  },
  getDashboard: () => fetchAPI("/api/v1/dashboard"),
  getCibaQuota: () => fetchAPI("/api/v1/ciba-quota"),
  getSecurityStatus: () => fetchAPI("/api/v1/security-status"),

  // Connections
  getConnections: () => fetchAPI("/api/v1/connections"),
  createConnection: (data: { name: string; service: string; slug: string; actions: string[]; webhook_url?: string; webhook_method?: string; webhook_headers?: Record<string, string>; webhook_body_template?: Record<string, string> }) =>
    fetchAPI("/api/v1/connections", { method: "POST", body: JSON.stringify(data) }),
  getConnectUrl: (id: string, userToken?: string | null, refreshToken?: string | null) =>
    fetchAPI(`/api/v1/connections/${id}/connect-url`, {
      headers: {
        ...(_userSub ? { "X-User-Sub": _userSub } : {}),
        ...(userToken ? { "X-User-Token": userToken } : {}),
        ...(refreshToken ? { "X-Refresh-Token": refreshToken } : {}),
      },
    }),
  updateConnection: (id: string, data: { name?: string; actions?: string[]; webhook_url?: string; webhook_method?: string; webhook_headers?: Record<string, string>; webhook_body_template?: Record<string, string>; metadata?: Record<string, string> }) =>
    fetchAPI(`/api/v1/connections/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  disconnectAuth: (id: string) => fetchAPI(`/api/v1/connections/${id}/auth`, { method: "DELETE" }),
  deleteConnection: (id: string) => fetchAPI(`/api/v1/connections/${id}`, { method: "DELETE" }),

  // Jobs
  getPendingJobs: () => fetchAPI("/api/v1/jobs/pending"),
  submitDecision: (jobId: string, data: { decision: "approve" | "reject"; modified_params?: any; note?: string }) =>
    fetchAPI(`/api/v1/jobs/${jobId}/decision`, { method: "POST", body: JSON.stringify(data) }),

  // Test
  sendTestRequest: (data: { connection: string; action: string; params: Record<string, any> }) =>
    fetchAPI("/api/v1/test-request", { method: "POST", body: JSON.stringify(data) }),
  getJobStatus: (jobId: string) => fetchAPI(`/api/v1/test-status/${jobId}`),
  testRequest: (data: { connection: string; action: string; params: Record<string, any> }) =>
    fetchAPI("/api/v1/test-request", { method: "POST", body: JSON.stringify(data) }),
  approveJob: (jobId: string) =>
    fetchAPI(`/api/v1/jobs/${jobId}/decision`, { method: "POST", body: JSON.stringify({ decision: "approve" }) }),
  rejectJob: (jobId: string) =>
    fetchAPI(`/api/v1/jobs/${jobId}/decision`, { method: "POST", body: JSON.stringify({ decision: "reject" }) }),

  // Consent
  getConsent: () => fetchAPI("/api/v1/consent"),

  // Compliance
  getComplianceStats: (days?: number) => fetchAPI(`/api/v1/audit/compliance-stats${days ? `?days=${days}` : ""}`),
  exportCompliance: (params?: { format?: string; days?: number; connection?: string }) => {
    const search = new URLSearchParams();
    if (params?.format) search.set("format", params.format);
    if (params?.days) search.set("days", String(params.days));
    if (params?.connection) search.set("connection", params.connection);
    return fetchAPI(`/api/v1/audit/export?${search.toString()}`);
  },

  // Workspace
  setupWorkspace: (data: Record<string, any>) =>
    fetchAPI("/api/v1/workspace/setup", { method: "POST", body: JSON.stringify(data) }),
  getWorkspace: () => fetchAPI("/api/v1/workspace"),

  // Demo
  getDemoAgents: () => fetchAPI("/api/v1/demo/agents"),
  seedDemoData: (agentId?: string, realUserId?: string) => {
    const params = new URLSearchParams();
    if (agentId) params.set("agent_id", agentId);
    if (realUserId) params.set("real_user_id", realUserId);
    const qs = params.toString();
    return fetchAPI(`/api/v1/demo/seed${qs ? `?${qs}` : ""}`, { method: "POST" });
  },
  clearDemoData: (body: { agent_id?: string; rule_ids?: string[]; approver_ids?: string[]; connection_ids?: string[] }) =>
    fetchAPI("/api/v1/demo/delete", { method: "POST", body: JSON.stringify(body) }),

  // Agent Chat
  orchestrate: (message: string) =>
    fetchAPI("/api/v1/demo/agents/orchestrate", { method: "POST", body: JSON.stringify({ message }) }),
  runSubAgent: (role: string, context: string) =>
    fetchAPI("/api/v1/demo/agents/sub-agent", { method: "POST", body: JSON.stringify({ role, context }) }),
  chatWithAgent: (agentId: string, message: string, agentTitle: string = "", sessionId: string = "", allowedTools?: string[]) =>
    fetchAPI(`/api/v1/demo/agents/${agentId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, agent_title: agentTitle, session_id: sessionId, ...(allowedTools ? { allowed_tools: allowedTools } : {}) }),
    }),
  getAgentSuggestions: (agentId: string) =>
    fetchAPI(`/api/v1/demo/agents/${agentId}/suggestions`),
  clearAgentSession: (agentId: string, sessionId: string) =>
    fetchAPI(`/api/v1/demo/agents/${agentId}/session/${sessionId}`, { method: "DELETE" }),
  checkOllamaStatus: () =>
    fetchAPI("/api/v1/demo/agents/ollama-status"),

  // AI API Key (encrypted server-side)
  saveAIKey: (apiKey: string, provider: string = "gemini") =>
    fetchAPI("/api/v1/workspace/ai-key", { method: "POST", body: JSON.stringify({ api_key: apiKey, provider }) }),
  deleteAIKey: () =>
    fetchAPI("/api/v1/workspace/ai-key", { method: "DELETE" }),
  getAIKeyStatus: () =>
    fetchAPI("/api/v1/workspace/ai-key/status"),

  // Credentials
  getCredentials: () => fetchAPI("/api/v1/workspace/credentials"),

  // Registered agents (My Agents)
  getMyAgents: () => fetchAPI("/api/v1/agents"),
  createMyAgent: (data: { name: string; description?: string; icon?: string; allowed_connections?: string[]; scenarios?: { title: string; connection: string; action: string; params: Record<string, unknown> }[] }) =>
    fetchAPI("/api/v1/agents", { method: "POST", body: JSON.stringify(data) }),
  deleteMyAgent: (id: string) => fetchAPI(`/api/v1/agents/${id}`, { method: "DELETE" }),
  addScenarioToAgent: (agentId: string, data: { title: string; connection: string; action: string; params: Record<string, unknown> }) =>
    fetchAPI(`/api/v1/agents/${agentId}/scenarios`, { method: "POST", body: JSON.stringify(data) }),
  updateScenario: (agentId: string, scenarioId: string, data: { title: string; connection: string; action: string; params: Record<string, unknown> }) =>
    fetchAPI(`/api/v1/agents/${agentId}/scenarios/${scenarioId}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteScenario: (agentId: string, scenarioId: string) =>
    fetchAPI(`/api/v1/agents/${agentId}/scenarios/${scenarioId}`, { method: "DELETE" }),
  regenerateAgentKey: (agentId: string) =>
    fetchAPI(`/api/v1/agents/${agentId}/regenerate-key`, { method: "POST" }),
  revokeAgent: (agentId: string) =>
    fetchAPI(`/api/v1/agents/${agentId}/revoke`, { method: "POST" }),
};
