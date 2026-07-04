// Wire types mirroring the FastAPI schemas.

export type NodeLabel =
  | "Document"
  | "Source"
  | "Claim"
  | "Evidence"
  | "Rhetoric";

export interface ApiGraphNode {
  id: string;
  label: NodeLabel;
  properties: Record<string, unknown>;
}

export interface ApiGraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface ApiGraphResponse {
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
}

export interface HubReport {
  node_id: string;
  label: string;
  name: string | null;
  betweenness: number;
  epistemic_integrity_score: number;
  is_active_hub: boolean;
}

export interface MetricsResponse {
  node_counts: Record<string, number>;
  edge_counts: Record<string, number>;
  mean_epistemic_integrity: number | null;
  contradiction_edges: number;
  active_misinformation_hubs: HubReport[];
}

export interface QueryResponse {
  question: string;
  cypher: string | null;
  answer: string;
  records: Record<string, unknown>[];
}
