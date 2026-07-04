"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

import { asNumber, integrityColor, integrityLabel } from "@/lib/style";

export function ClaimNode({ data }: NodeProps) {
  const props = (data.properties ?? {}) as Record<string, unknown>;
  const eis = asNumber(props.epistemic_integrity_score);
  const color = integrityColor(eis);
  const statement = String(props.statement ?? "(claim)");
  const pct = Math.round((eis ?? 0) * 100);

  return (
    <div className="w-56 rounded-xl border border-cafe-border bg-cafe-raised p-3.5 shadow-cafe">
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
      <div className="mb-1.5 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-cafe-muted">
          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
          Claim
        </span>
        <span className="text-[10px] font-medium" style={{ color }}>
          {integrityLabel(eis)}
        </span>
      </div>
      <p className="mb-2.5 line-clamp-3 text-[13px] leading-snug text-cafe-ink">
        {statement}
      </p>
      <div className="mb-1 flex items-center justify-between text-[10px] text-cafe-muted">
        <span>Epistemic Integrity</span>
        <span className="font-semibold" style={{ color }}>
          {eis === undefined ? "—" : `${pct}%`}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-cafe-border">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0 !bg-cafe-line" />
    </div>
  );
}
