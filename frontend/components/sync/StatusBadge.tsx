"use client";

import { cn } from "@/lib/utils";

// Compact pill used in sync source cards and pipeline-run rows. The colour
// scheme tracks the canonical SyncState.status values (running/idle/error/…).
export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        status === "running" && "bg-amber-500/15 text-amber-600 dark:text-amber-300",
        status === "error" && "bg-red-500/15 text-red-600 dark:text-red-300",
        status === "completed" && "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
        status === "idle" && "bg-[var(--muted)]/15 text-[var(--muted)]",
        status === "failed" && "bg-red-500/15 text-red-600 dark:text-red-300",
      )}
    >
      {status === "running" && <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />}
      {status}
    </span>
  );
}
