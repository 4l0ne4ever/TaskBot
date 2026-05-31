"use client";

// One side of a conflict pair — title/deadline/assignee/priority plus a
// collapsible source excerpt that lazily fetches via /tasks/{id}/source.

import { useState } from "react";
import { api } from "@/lib/api";
import { HighlightExcerpt } from "@/components/ui/HighlightExcerpt";
import type { Task, TaskSource } from "@/lib/types";

export function TaskSide({ t }: { t: Task }) {
  const [src, setSrc] = useState<TaskSource | null>(null);
  const [srcOpen, setSrcOpen] = useState(false);
  const [srcLoading, setSrcLoading] = useState(false);

  async function toggleSrc() {
    if (srcOpen) {
      setSrcOpen(false);
      return;
    }
    setSrcOpen(true);
    if (src || !t.source_doc_id) return;
    setSrcLoading(true);
    try {
      setSrc(await api.tasks.source(t.id));
    } catch {
      /* no source — show fallback */
    } finally {
      setSrcLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <dl className="text-sm space-y-1.5">
        <div><span className="text-[var(--muted)]">Title: </span>{t.title}</div>
        <div><span className="text-[var(--muted)]">Deadline: </span>{t.deadline ?? "—"}</div>
        <div><span className="text-[var(--muted)]">Assignee: </span>{t.assignee ?? "—"}</div>
        <div>
          <span className="text-[var(--muted)]">Priority: </span>
          {t.priority ?? "—"}
        </div>
        {t.source_type && (
          <div>
            <span className="inline-block rounded-full bg-[var(--surface-2)] border border-[var(--border)] text-[10px] px-2 py-0.5 text-[var(--muted)] uppercase font-semibold">
              {t.source_type}
            </span>
          </div>
        )}
      </dl>
      {t.source_doc_id && (
        <div>
          <button
            type="button"
            onClick={() => void toggleSrc()}
            className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
          >
            <svg className={`w-3 h-3 transition-transform ${srcOpen ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            {srcOpen ? "Hide source" : "View source"}
          </button>
          {srcOpen && (
            <div className="mt-2 rounded border border-[var(--border)] text-xs">
              {srcLoading ? (
                <p className="px-3 py-2 text-[var(--muted)]">Loading&hellip;</p>
              ) : src ? (
                <>
                  <div className="px-3 py-1.5 border-b border-[var(--border)] flex gap-2 items-center">
                    <span className="uppercase text-[10px] font-semibold text-[var(--muted)]">{src.source_type}</span>
                    <span className="font-mono text-[10px] text-[var(--muted)]">{src.source_ref}</span>
                  </div>
                  <pre className="px-3 py-2 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-48 overflow-y-auto">
                    <HighlightExcerpt text={src.excerpt ?? "No text content."} quote={t.evidence_quote} />
                  </pre>
                </>
              ) : (
                <p className="px-3 py-2 text-[var(--muted)]">No source content available.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
