import type { Edge, Node } from "@xyflow/react";

import { forceLayout, type NodeSize } from "./layout";
import type { ApiGraphResponse } from "./types";

// Map a node label to the custom React Flow node type that renders it.
const NODE_TYPE_BY_LABEL: Record<string, string> = {
  Claim: "claim",
  Source: "source",
  Document: "document",
  Evidence: "evidence",
  Rhetoric: "rhetoric",
};

// Approximate rendered footprint per node type (px). Used by the layout's
// collision-resolution pass so cards never overlap.
const NODE_SIZE_BY_LABEL: Record<string, NodeSize> = {
  Claim: { w: 232, h: 140 },
  Source: { w: 184, h: 104 },
  Document: { w: 216, h: 118 },
  Evidence: { w: 168, h: 92 },
  Rhetoric: { w: 184, h: 96 },
};

export function toReactFlow(graph: ApiGraphResponse): {
  nodes: Node[];
  edges: Edge[];
} {
  const ids = graph.nodes.map((n) => n.id);
  const sizes = new Map<string, NodeSize>(
    graph.nodes.map((n) => [
      n.id,
      NODE_SIZE_BY_LABEL[n.label] ?? { w: 200, h: 110 },
    ]),
  );
  const positions = forceLayout(
    ids,
    graph.edges.map((e) => ({ source: e.source, target: e.target })),
    sizes,
  );

  const nodes: Node[] = graph.nodes.map((n) => {
    const pos = positions.get(n.id) ?? { x: 0, y: 0 };
    return {
      id: n.id,
      type: NODE_TYPE_BY_LABEL[n.label] ?? "default",
      position: { x: pos.x, y: pos.y },
      data: { label: n.label, properties: n.properties },
    };
  });

  const edges: Edge[] = graph.edges.map((e) => {
    const isContradiction = e.type === "CONTRADICTS";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.type,
      type: isContradiction ? "contradicts" : "smoothstep",
      animated: isContradiction,
      // Styling (incl. theme-aware stroke) is handled in globals.css via the
      // .epis-edge / .epis-contradicts classes so it adapts to light/dark.
      className: isContradiction ? undefined : "epis-edge",
      data: { relType: e.type, properties: e.properties },
    };
  });

  return { nodes, edges };
}
