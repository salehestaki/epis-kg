"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export function EvidenceNode({ data }: NodeProps) {
  const props = (data.properties ?? {}) as Record<string, unknown>;
  const url = props.reference_url ? String(props.reference_url) : null;
  return (
    <div className="w-40 rounded-lg border border-cafe-good/40 bg-cafe-surface p-2.5 shadow-cafe-sm">
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-cafe-good">
        Evidence
      </div>
      <div className="text-xs font-medium text-cafe-ink">{String(props.type ?? "citation")}</div>
      {url && (
        <div className="truncate text-[10px] text-cafe-accent" title={url}>
          {url}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
    </div>
  );
}
