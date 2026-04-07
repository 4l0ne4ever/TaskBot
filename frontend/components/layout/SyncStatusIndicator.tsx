"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SyncStateRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SyncStatusIndicator() {
  const [rows, setRows] = useState<SyncStateRow[] | null>(null);

  useEffect(() => {
    const load = () => {
      api.sync
        .status()
        .then(setRows)
        .catch(() => setRows([]));
    };
    load();
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
  }, []);

  if (rows === null) {
    return <span className="text-xs text-[var(--muted)]">Loading&hellip;</span>;
  }

  const running = rows.some((r) => r.status === "running");
  const err = rows.some((r) => r.status === "error");

  return (
    <div
      className={cn(
        "flex items-center gap-2 text-xs font-medium rounded-full px-3 py-1.5 border transition-colors",
        running && "border-amber-500/40 text-amber-600 dark:text-amber-300 bg-amber-500/10",
        err && !running && "border-red-500/40 text-red-600 dark:text-red-300 bg-red-500/10",
        !running && !err && "border-emerald-500/30 text-emerald-600 dark:text-emerald-300 bg-emerald-500/10"
      )}
      title={rows.map((r) => `${r.source_type}: ${r.status}`).join(" · ")}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          running && "bg-amber-400 animate-pulse",
          err && !running && "bg-red-400",
          !running && !err && "bg-emerald-400"
        )}
      />
      {running ? "Syncing" : err ? "Error" : "Idle"}
    </div>
  );
}
