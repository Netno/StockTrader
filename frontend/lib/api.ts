const API_BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

async function get<T>(path: string, revalidate = 0): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    next: revalidate > 0 ? { revalidate } : undefined,
    cache: revalidate > 0 ? undefined : "no-store",
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  watchlist:      () => get<any[]>("/api/watchlist"),
  positions:      () => get<Record<string, any>>("/api/positions"),
  signals:        (limit = 50, status?: string) =>
    get<any[]>(`/api/signals?limit=${limit}${status ? `&status=${status}` : ""}`),
  news:           (ticker?: string, limit = 50) =>
    get<any[]>(`/api/news?limit=${limit}${ticker ? `&ticker=${ticker}` : ""}`),
  portfolio:      () => get<any[]>("/api/portfolio"),
  indicators:     (ticker: string) => get<any>(`/api/indicators/${ticker}`),
  suggestions:    () => get<any[]>("/api/suggestions"),
  testTicker:     (ticker: string) => get<any>(`/api/test/${ticker}`, 60),
  trades:         (status?: string) =>
    get<any[]>(`/api/trades${status ? `?status=${status}` : ""}`),
  confirmSignal:  (id: string) => post<any>(`/api/signals/${id}/confirm`),
  rejectSignal:   (id: string) => post<any>(`/api/signals/${id}/reject`),
  closeTrade:     (id: string) => post<any>(`/api/trades/${id}/close`),
};
