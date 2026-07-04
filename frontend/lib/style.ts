// Shared visual helpers for encoding epistemic integrity as colour.
// Warm cafe-cream palette: sage (sound) -> honey (contested) -> brick (eroded).

export function integrityColor(score: number | undefined | null): string {
  if (score === undefined || score === null) return "#8C7F6B"; // taupe (unscored)
  if (score >= 0.66) return "#7B8A5A"; // sage — sound
  if (score >= 0.33) return "#C68A3E"; // honey — contested
  return "#B45B4A"; // brick — eroded
}

export function integrityLabel(score: number | undefined | null): string {
  if (score === undefined || score === null) return "unscored";
  if (score >= 0.66) return "sound";
  if (score >= 0.33) return "contested";
  return "eroded";
}

export function asNumber(v: unknown): number | undefined {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : undefined;
}
