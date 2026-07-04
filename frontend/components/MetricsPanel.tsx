"use client";

import { integrityColor } from "@/lib/style";
import type { MetricsResponse } from "@/lib/types";

export function MetricsPanel({ metrics }: { metrics: MetricsResponse | null }) {
  if (!metrics) {
    return (
      <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 text-sm text-cafe-muted">
        Loading metrics…
      </div>
    );
  }

  const mean = metrics.mean_epistemic_integrity;
  const totalNodes = Object.values(metrics.node_counts).reduce((a, b) => a + b, 0);
  const hubs = metrics.active_misinformation_hubs.filter((h) => h.is_active_hub);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 shadow-cafe-sm">
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-cafe-muted">
          Network Integrity
        </h3>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold tracking-tight" style={{ color: integrityColor(mean) }}>
            {mean === null ? "—" : `${Math.round(mean * 100)}%`}
          </span>
          <span className="text-xs text-cafe-muted">mean EIS</span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
          <Stat label="Nodes" value={totalNodes} />
          <Stat label="Claims" value={metrics.node_counts.Claim ?? 0} />
          <Stat
            label="Contradictions"
            value={metrics.contradiction_edges}
            danger={metrics.contradiction_edges > 0}
          />
        </div>
      </div>

      <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 shadow-cafe-sm">
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-cafe-muted">
          Active Misinformation Hubs
        </h3>
        {hubs.length === 0 ? (
          <p className="text-xs text-cafe-muted">None detected.</p>
        ) : (
          <ul className="space-y-2">
            {hubs.map((h) => (
              <li
                key={h.node_id}
                className="rounded-lg border border-cafe-danger/30 bg-cafe-danger/5 p-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-cafe-ink">
                    {h.name ?? h.node_id}
                  </span>
                  <span className="text-[10px] uppercase tracking-wide text-cafe-danger">
                    {h.label}
                  </span>
                </div>
                <div className="mt-1 flex justify-between text-[10px] text-cafe-muted">
                  <span>betweenness {h.betweenness.toFixed(3)}</span>
                  <span className="font-medium" style={{ color: integrityColor(h.epistemic_integrity_score) }}>
                    EIS {Math.round(h.epistemic_integrity_score * 100)}%
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  danger,
}: {
  label: string;
  value: number;
  danger?: boolean;
}) {
  return (
    <div className="rounded-lg bg-cafe-bg/70 py-2">
      <div
        className={`text-lg font-semibold ${danger ? "text-cafe-danger" : "text-cafe-ink"}`}
      >
        {value}
      </div>
      <div className="text-[10px] text-cafe-muted">{label}</div>
    </div>
  );
}
