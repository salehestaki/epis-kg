"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import { useMemo } from "react";

import { ContradictsEdge } from "./edges/ContradictsEdge";
import { ClaimNode } from "./nodes/ClaimNode";
import { DocumentNode } from "./nodes/DocumentNode";
import { EvidenceNode } from "./nodes/EvidenceNode";
import { RhetoricNode } from "./nodes/RhetoricNode";
import { SourceNode } from "./nodes/SourceNode";

const MINIMAP_COLORS: Record<string, string> = {
  claim: "#A9744F",
  source: "#8E5E3D",
  document: "#C9B58E",
  evidence: "#7B8A5A",
  rhetoric: "#B45B4A",
};

export function GraphCanvas({
  nodes,
  edges,
  onNodeClick,
  dark = false,
}: {
  nodes: Node[];
  edges: Edge[];
  onNodeClick?: NodeMouseHandler;
  dark?: boolean;
}) {
  const nodeTypes = useMemo(
    () => ({
      claim: ClaimNode,
      source: SourceNode,
      document: DocumentNode,
      evidence: EvidenceNode,
      rhetoric: RhetoricNode,
    }),
    [],
  );
  const edgeTypes = useMemo(() => ({ contradicts: ContradictsEdge }), []);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={onNodeClick}
      fitView
      fitViewOptions={{ padding: 0.25 }}
      minZoom={0.1}
      maxZoom={2.5}
      proOptions={{ hideAttribution: false }}
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={26}
        size={1.4}
        color={dark ? "#4A3F32" : "#DDCEB1"}
      />
      <Controls showInteractive={false} />
      <MiniMap
        pannable
        zoomable
        maskColor={dark ? "rgba(27,23,18,0.72)" : "rgba(243,236,221,0.7)"}
        style={{
          background: dark ? "#241E18" : "#FBF6EC",
          border: `1px solid ${dark ? "#3A3128" : "#E4D8C2"}`,
          borderRadius: 10,
        }}
        nodeColor={(n) => MINIMAP_COLORS[n.type ?? "default"] ?? "#C9B58E"}
      />
    </ReactFlow>
  );
}
