const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

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
  getApprover: (id: string) => fetchAPI(`/api/v1/approvers/${id}`),
  createApprover: (data: any) => fetchAPI("/api/v1/approvers", { method: "POST", body: JSON.stringify(data) }),
  updateApprover: (id: string, data: any) => fetchAPI(`/api/v1/approvers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  setDelegation: (id: string, data: any) => fetchAPI(`/api/v1/approvers/${id}/delegate`, { method: "PUT", body: JSON.stringify(data) }),

  // Audit & Dashboard
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
  revokeConnection: (id: string) => fetchAPI(`/api/v1/connections/${id}/revoke`, { method: "POST" }),
};
