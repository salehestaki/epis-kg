"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchGraph, fetchMetrics } from "@/lib/api";
import type { MetricsResponse } from "@/lib/types";
import { toReactFlow } from "@/lib/transform";
import type { Edge, Node } from "@xyflow/react";

interface GraphData {
  nodes: Node[];
  edges: Edge[];
  metrics: MetricsResponse | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useGraphData(limit = 500): GraphData {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [graph, m] = await Promise.all([fetchGraph(limit), fetchMetrics()]);
      const { nodes: n, edges: e } = toReactFlow(graph);
      setNodes(n);
      setEdges(e);
      setMetrics(m);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { nodes, edges, metrics, loading, error, reload };
}
