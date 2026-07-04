"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export function DocumentNode({ data }: NodeProps) {
  const props = (data.properties ?? {}) as Record<string, unknown>;
  const content = String(props.content ?? "");
  return (
    <div className="w-52 rounded-lg border border-cafe-border bg-cafe-surface p-3 shadow-cafe-sm">
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-cafe-muted">
        Document
      </div>
      <p className="mt-1 line-clamp-3 text-xs leading-snug text-cafe-ink/80">
        {content || "(document)"}
      </p>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
    </div>
  );
}
