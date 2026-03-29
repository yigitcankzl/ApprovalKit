const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3002";

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export function apiPost(path: string, body: any) {
  return apiFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function apiPut(path: string, body: any) {
  return apiFetch(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export const API_BASE = API_URL;
