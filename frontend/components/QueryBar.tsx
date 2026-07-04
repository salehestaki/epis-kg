"use client";

import { useState } from "react";

import { runQuery } from "@/lib/api";
import type { QueryResponse } from "@/lib/types";

export function QueryBar() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await runQuery(question));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-cafe-border bg-cafe-surface p-4 shadow-cafe-sm">
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-cafe-muted">
        Ask the Graph
      </h3>
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Which claims have the lowest integrity?"
          className="flex-1 rounded-lg border border-cafe-border bg-cafe-raised px-3 py-2 text-sm text-cafe-ink placeholder:text-cafe-muted/70 outline-none focus:border-cafe-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-cafe-accent px-4 py-2 text-sm font-medium text-cafe-surface transition-colors hover:bg-cafe-accentDark disabled:opacity-50"
        >
          {loading ? "…" : "Ask"}
        </button>
      </form>

      {error && <p className="mt-2 text-xs text-cafe-danger">{error}</p>}

      {result && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-cafe-ink/80">{result.answer}</p>
          {result.cypher && (
            <pre className="overflow-x-auto rounded-lg border border-cafe-border bg-cafe-bg/60 p-2 text-[10px] leading-relaxed text-cafe-accentDark">
              {result.cypher}
            </pre>
          )}
          {result.records.length > 0 && (
            <pre className="max-h-40 overflow-auto rounded-lg border border-cafe-border bg-cafe-bg/60 p-2 text-[10px] text-cafe-ink/80">
              {JSON.stringify(result.records, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
