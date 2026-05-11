"use client";

import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
  className?: string;
}

export function Pagination({ page, pageSize, total, onPage, className }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const pages: (number | "…")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("…");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pages.push(i);
    if (page < totalPages - 2) pages.push("…");
    pages.push(totalPages);
  }

  return (
    <div className={cn("flex items-center justify-between gap-4 pt-2", className)}>
      <p className="text-xs text-[var(--muted)]">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => onPage(page - 1)}
          className="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs disabled:opacity-30 hover:bg-[var(--card-hover)] transition-colors"
        >
          ‹ Prev
        </button>
        {pages.map((p, i) =>
          p === "…" ? (
            <span key={`ellipsis-${i}`} className="px-1 text-xs text-[var(--muted)]">…</span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onPage(p as number)}
              className={cn(
                "rounded-lg px-2.5 py-1 text-xs transition-colors",
                p === page
                  ? "bg-[var(--accent)] text-white font-medium"
                  : "border border-[var(--border)] hover:bg-[var(--card-hover)]"
              )}
            >
              {p}
            </button>
          )
        )}
        <button
          type="button"
          disabled={page === totalPages}
          onClick={() => onPage(page + 1)}
          className="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs disabled:opacity-30 hover:bg-[var(--card-hover)] transition-colors"
        >
          Next ›
        </button>
      </div>
    </div>
  );
}
