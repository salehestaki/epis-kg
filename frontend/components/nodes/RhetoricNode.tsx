"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { asNumber } from "@/lib/style";

export function RhetoricNode({ data }: NodeProps) {
  const props = (data.properties ?? {}) as Record<string, unknown>;
  const severity = asNumber(props.severity_weight) ?? 0;
  // Warmer, subtler tint that deepens with severity.
  const tint = `rgba(180,91,74,${0.1 + severity * 0.28})`;
  return (
    <div
      className="w-44 rounded-lg border border-cafe-danger/40 p-2.5 shadow-cafe-sm"
      style={{ background: tint }}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
      <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-cafe-danger">
        Rhetoric
      </div>
      <div className="text-xs font-semibold text-cafe-ink">
        {String(props.category ?? "device")}
      </div>
      <div className="mt-0.5 flex items-center gap-1.5">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-cafe-danger/20">
          <div
            className="h-full rounded-full bg-cafe-danger"
            style={{ width: `${Math.round(severity * 100)}%` }}
          />
        </div>
        <span className="text-[10px] text-cafe-muted">{severity.toFixed(2)}</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
    </div>
  );
}
