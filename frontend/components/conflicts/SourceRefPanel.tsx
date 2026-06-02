"use client";

// Fallback panel rendered on a conflict side when no Task row matches the
// source ref — i.e. the conflict was detected from raw source documents that
// were never promoted to Tasks. Lazily fetches the source excerpt by ref.

import { useState } from "react";
import { api } from "@/lib/api";
import type { TaskSource } from "@/lib/types";

export function SourceRefPanel({ sourceRef }: { sourceRef: string | null }) {
  const [src, setSrc] = useState<TaskSource | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!sourceRef) return <p className="text-sm text-[var(--muted)]">—</p>;

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (src) return;
    setLoading(true);
    try {
      setSrc(await api.tasks.sourceByRef(sourceRef!));
    } catch {
      /* source_ref not in DB (e.g. seeded fake ref) — show ref label only */
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-[var(--muted)] font-mono break-all">{sourceRef}</p>
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
      >
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        {open ? "Hide source" : "View source"}
      </button>
      {open && (
        <div className="rounded border border-[var(--border)] text-xs">
          {loading ? (
            <p className="px-3 py-2 text-[var(--muted)]">Loading&hellip;</p>
          ) : src ? (
            <>
              <div className="px-3 py-1.5 border-b border-[var(--border)] flex gap-2 items-center">
                <span className="uppercase text-[10px] font-semibold text-[var(--muted)]">{src.source_type}</span>
                <span className="ml-auto text-[var(--muted)]">
                  {new Date(src.received_at ?? src.created_at).toLocaleString()}
                </span>
              </div>
              <pre className="px-3 py-2 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-48 overflow-y-auto">
                {src.excerpt ?? "No text content."}
              </pre>
            </>
          ) : (
            <p className="px-3 py-2 text-[var(--muted)]">Source content not available for this reference.</p>
          )}
        </div>
      )}
    </div>
  );
}
