import type {
  ApiGraphResponse,
  MetricsResponse,
  QueryResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function fetchGraph(limit = 500): Promise<ApiGraphResponse> {
  return getJSON<ApiGraphResponse>(`/graph?limit=${limit}`);
}

export async function fetchMetrics(topHubs = 10): Promise<MetricsResponse> {
  return getJSON<MetricsResponse>(`/metrics?top_hubs=${topHubs}`);
}

export async function runQuery(
  question: string,
  topK = 10,
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK }),
  });
  if (!res.ok) throw new Error(`query failed: ${res.status}`);
  return (await res.json()) as QueryResponse;
}

export async function ingestText(payload: {
  content: string;
  url?: string;
  source_name?: string;
  source_platform?: string;
  a_priori_credibility?: number;
}): Promise<{ document_id: string; queued_message_id: string }> {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`ingest failed: ${res.status}`);
  return await res.json();
}
