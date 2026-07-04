"use client";

import { ReactFlowProvider, type Node } from "@xyflow/react";
import { useCallback, useState } from "react";

import { GraphCanvas } from "@/components/GraphCanvas";
import { MetricsPanel } from "@/components/MetricsPanel";
import { NodeInspector } from "@/components/NodeInspector";
import { QueryBar } from "@/components/QueryBar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useGraphData } from "@/hooks/useGraphData";
import { useGraphSocket } from "@/hooks/useGraphSocket";
import { useTheme } from "@/hooks/useTheme";

export default function Home() {
  const { nodes, edges, metrics, loading, error, reload } = useGraphData();
  const [selected, setSelected] = useState<Node | null>(null);
  const { connected } = useGraphSocket(reload);
  const { theme } = useTheme();

  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelected(node);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-cafe-bg">
      {/* Graph canvas */}
      <div className="relative h-full flex-1">
        <header className="pointer-events-none absolute left-6 top-5 z-10">
          <h1 className="text-xl font-semibold tracking-tight text-cafe-ink">
            Epis-KG
            <span className="ml-2 text-xs font-normal text-cafe-muted">
              Epistemic Erosion Knowledge Graph
            </span>
          </h1>
          <div className="mt-1.5 flex items-center gap-2 text-[10px] text-cafe-muted">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${connected ? "bg-cafe-good" : "bg-cafe-line"}`}
            />
            {connected ? "live" : "offline"}
            {loading && <span>· loading…</span>}
          </div>
        </header>

        {error && (
          <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 rounded-xl border border-cafe-danger/40 bg-cafe-surface p-4 text-sm text-cafe-danger shadow-cafe">
            Failed to load graph: {error}
            <div className="mt-1 text-xs text-cafe-muted">
              Is the API running at {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}?
            </div>
          </div>
        )}

        <div className="pointer-events-none absolute right-5 top-5 z-10">
          <ThemeToggle />
        </div>

        <ReactFlowProvider>
          <GraphCanvas
            nodes={nodes}
            edges={edges}
            onNodeClick={onNodeClick}
            dark={theme === "dark"}
          />
        </ReactFlowProvider>
      </div>

      {/* Sidebar */}
      <aside className="w-96 space-y-4 overflow-y-auto border-l border-cafe-border bg-cafe-bg p-5">
        <MetricsPanel metrics={metrics} />
        <QueryBar />
        <NodeInspector node={selected} />
        <button
          onClick={() => void reload()}
          className="w-full rounded-lg border border-cafe-border bg-cafe-surface py-2 text-xs font-medium text-cafe-ink transition-colors hover:border-cafe-accent"
        >
          Refresh graph
        </button>
      </aside>
    </div>
  );
}
