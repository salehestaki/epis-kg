"use client";

import type { Node } from "@xyflow/react";

export function NodeInspector({ node }: { node: Node | null }) {
  if (!node) {
    return (
      <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 text-xs text-cafe-muted shadow-cafe-sm">
        Select a node to inspect its rhetorical metadata and scores.
      </div>
    );
  }
  const label = String(node.data?.label ?? node.type ?? "Node");
  const props = (node.data?.properties ?? {}) as Record<string, unknown>;

  return (
    <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 shadow-cafe-sm">
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-cafe-accent">
        {label}
      </h3>
      <dl className="space-y-1.5 text-xs">
        {Object.entries(props).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3">
            <dt className="text-cafe-muted">{k}</dt>
            <dd className="max-w-[60%] truncate text-right text-cafe-ink" title={String(v)}>
              {String(v)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
