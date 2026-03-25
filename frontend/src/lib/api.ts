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
    throw new Error(error.detail || `HTTP ${res.status}`);
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
  createConnection: (data: { name: string; service: string; slug: string; actions: string[] }) =>
    fetchAPI("/api/v1/connections", { method: "POST", body: JSON.stringify(data) }),
  getConnectUrl: (id: string, userToken?: string | null, refreshToken?: string | null) =>
    fetchAPI(`/api/v1/connections/${id}/connect-url`, {
      headers: {
        ...(userToken ? { "X-User-Token": userToken } : {}),
        ...(refreshToken ? { "X-Refresh-Token": refreshToken } : {}),
      },
    }),
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

  // Consent
  getConsent: () => fetchAPI("/api/v1/consent"),

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
  clearDemoData: () => fetchAPI("/api/v1/demo/seed", { method: "DELETE" }),

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
