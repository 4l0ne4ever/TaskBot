"use client";

import type { LastResult } from "./types";

// Inline banner shown under each source card after a sync completes.
// Four states: error (red), throttling (amber), no-new-data (neutral), success (green).
export function ResultBanner({ result }: { result: LastResult }) {
  const noNewData =
    result.step === "done" &&
    (result.detail.toLowerCase().includes("no new") || result.current === 0);

  if (result.step === "error") {
    return (
      <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2.5 mt-2">
        <svg className="w-4 h-4 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-xs text-red-400 leading-relaxed">{result.detail || "Sync failed"}</p>
      </div>
    );
  }

  if (result.step === "throttling") {
    return (
      <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2.5 mt-2">
        <svg className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-xs text-amber-400 leading-relaxed">{result.detail}</p>
      </div>
    );
  }

  if (noNewData) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] px-3 py-2.5 mt-2">
        <svg className="w-4 h-4 text-[var(--muted)] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-xs text-[var(--muted)]">No new content found in this time range</p>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-2.5 mt-2">
      <svg className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p className="text-xs text-emerald-400 leading-relaxed">{result.detail}</p>
    </div>
  );
}
