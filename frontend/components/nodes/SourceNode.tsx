"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { asNumber } from "@/lib/style";

export function SourceNode({ data }: NodeProps) {
  const props = (data.properties ?? {}) as Record<string, unknown>;
  const credibility = asNumber(props.a_priori_credibility);
  return (
    <div className="w-44 rounded-full border border-cafe-line bg-cafe-surface px-4 py-3 text-center shadow-cafe-sm">
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-cafe-accent">
        Source
      </div>
      <div className="truncate text-sm font-semibold text-cafe-ink">
        {String(props.name ?? "unknown")}
      </div>
      <div className="text-[10px] text-cafe-muted">
        {String(props.platform ?? "—")} · cred{" "}
        {credibility === undefined ? "—" : credibility.toFixed(2)}
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
    </div>
  );
}
