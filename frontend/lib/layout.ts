// A tiny deterministic force-directed layout (Fruchterman-Reingold style) with
// a final collision-resolution pass so node cards never overlap. Kept
// dependency-free; seeded by node id hash for stable placement.

export interface LayoutNode {
  id: string;
  x: number;
  y: number;
}

export interface NodeSize {
  w: number;
  h: number;
}

interface Edge {
  source: string;
  target: string;
}

const DEFAULT_SIZE: NodeSize = { w: 200, h: 110 };

function seededPosition(id: string, radius: number): { x: number; y: number } {
  let h = 0;
  for (let i = 0; i < id.length; i++) {
    h = (h * 31 + id.charCodeAt(i)) >>> 0;
  }
  const angle = (h % 360) * (Math.PI / 180);
  const r = radius * (0.3 + ((h >> 9) % 100) / 100);
  return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
}

export function forceLayout(
  nodeIds: string[],
  edges: Edge[],
  sizes: Map<string, NodeSize> = new Map(),
  opts: { iterations?: number } = {},
): Map<string, LayoutNode> {
  const n = Math.max(nodeIds.length, 1);
  const iterations = opts.iterations ?? 400;

  // Ideal edge length scaled to the node footprint so there is room to breathe.
  const avgW =
    nodeIds.reduce((s, id) => s + (sizes.get(id)?.w ?? DEFAULT_SIZE.w), 0) / n;
  const avgH =
    nodeIds.reduce((s, id) => s + (sizes.get(id)?.h ?? DEFAULT_SIZE.h), 0) / n;
  const k = Math.max(avgW, avgH) * 1.8;
  const span = k * Math.sqrt(n);

  const positions = new Map<string, LayoutNode>();
  for (const id of nodeIds) {
    const p = seededPosition(id, span / 2);
    positions.set(id, { id, x: p.x, y: p.y });
  }

  const adjacency = edges.filter(
    (e) => positions.has(e.source) && positions.has(e.target),
  );

  let temperature = span / 8;
  const cool = temperature / (iterations + 1);

  for (let iter = 0; iter < iterations; iter++) {
    const disp = new Map<string, { dx: number; dy: number }>();
    for (const id of nodeIds) disp.set(id, { dx: 0, dy: 0 });

    // Repulsive forces (all pairs).
    for (let i = 0; i < nodeIds.length; i++) {
      const a = positions.get(nodeIds[i])!;
      for (let j = i + 1; j < nodeIds.length; j++) {
        const b = positions.get(nodeIds[j])!;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const dist = Math.hypot(dx, dy) || 0.01;
        const force = (k * k) / dist;
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        const da = disp.get(a.id)!;
        const db = disp.get(b.id)!;
        da.dx += dx;
        da.dy += dy;
        db.dx -= dx;
        db.dy -= dy;
      }
    }

    // Attractive forces (edges).
    for (const e of adjacency) {
      const a = positions.get(e.source)!;
      const b = positions.get(e.target)!;
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      const dist = Math.hypot(dx, dy) || 0.01;
      const force = (dist * dist) / k;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      const da = disp.get(a.id)!;
      const db = disp.get(b.id)!;
      da.dx -= dx;
      da.dy -= dy;
      db.dx += dx;
      db.dy += dy;
    }

    // Gentle gravity keeps disconnected parts from drifting away.
    const gravity = 0.06;
    for (const id of nodeIds) {
      const p = positions.get(id)!;
      const d = disp.get(id)!;
      d.dx -= gravity * p.x;
      d.dy -= gravity * p.y;
    }

    for (const id of nodeIds) {
      const d = disp.get(id)!;
      const p = positions.get(id)!;
      const len = Math.hypot(d.dx, d.dy) || 0.01;
      p.x += (d.dx / len) * Math.min(len, temperature);
      p.y += (d.dy / len) * Math.min(len, temperature);
    }
    temperature -= cool;
  }

  resolveCollisions(positions, sizes);
  recenter(positions);
  return positions;
}

// Push apart any two nodes whose padded bounding boxes overlap. Iterating a few
// times settles the whole layout into a non-overlapping arrangement.
function resolveCollisions(
  positions: Map<string, LayoutNode>,
  sizes: Map<string, NodeSize>,
  padding = 40,
  passes = 160,
): void {
  const ids = [...positions.keys()];
  for (let pass = 0; pass < passes; pass++) {
    let moved = false;
    for (let i = 0; i < ids.length; i++) {
      const a = positions.get(ids[i])!;
      const sa = sizes.get(ids[i]) ?? DEFAULT_SIZE;
      for (let j = i + 1; j < ids.length; j++) {
        const b = positions.get(ids[j])!;
        const sb = sizes.get(ids[j]) ?? DEFAULT_SIZE;
        const minDX = (sa.w + sb.w) / 2 + padding;
        const minDY = (sa.h + sb.h) / 2 + padding;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const overlapX = minDX - Math.abs(dx);
        const overlapY = minDY - Math.abs(dy);
        if (overlapX > 0 && overlapY > 0) {
          moved = true;
          // Resolve along the axis of least penetration.
          if (overlapX < overlapY) {
            const shift = (overlapX / 2) * (dx < 0 ? -1 : 1);
            a.x -= shift;
            b.x += shift;
          } else {
            const shift = (overlapY / 2) * (dy < 0 ? -1 : 1);
            a.y -= shift;
            b.y += shift;
          }
        }
      }
    }
    if (!moved) break;
  }
}

function recenter(positions: Map<string, LayoutNode>): void {
  const pts = [...positions.values()];
  if (pts.length === 0) return;
  const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
  const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
  for (const p of pts) {
    p.x -= cx;
    p.y -= cy;
  }
}
