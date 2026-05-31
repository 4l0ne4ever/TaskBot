"use client";

// One conflict row: header (type + scope badges + resolution chip), action
// buttons (merge for thread_update only, Use A / Use B / Dismiss otherwise),
// optional merge panel, then the two-column side-by-side diff.

import { useState } from "react";
import { ScopeBadge } from "@/components/conflicts/ScopeBadge";
import { MergePanel } from "./MergePanel";
import { SourceRefPanel } from "./SourceRefPanel";
import { TaskSide } from "./TaskSide";
import { parseResolution } from "./conflict-helpers";
import type { Conflict, MergeableField, Task } from "@/lib/types";

export function ConflictCard({
  conflict: c,
  tasksById,
  onResolve,
  onMerge,
}: {
  conflict: Conflict;
  tasksById: Record<string, Task>;
  onResolve: (id: string, resolution: "accept_a" | "accept_b" | "dismiss") => void;
  onMerge: (id: string, fields: MergeableField[]) => void;
}) {
  const [mergeOpen, setMergeOpen] = useState(false);
  const ids = c.task_ids ?? [];
  const a = ids[0] ? tasksById[ids[0]] : undefined;
  const b = ids[1] ? tasksById[ids[1]] : undefined;
  const { label: resolutionLabel, cleanDesc } = parseResolution(c.description);
  const canMerge = c.scope === "thread_update" && !!a && !!b;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <div className="px-5 py-4 flex justify-between items-start gap-4 flex-wrap border-b border-[var(--border)]">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-block rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-300 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5">
              {c.conflict_type.replace("_", " ")}
            </span>
            <ScopeBadge scope={c.scope} />
            {c.resolved && resolutionLabel && (
              <span className="inline-block rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5">
                {resolutionLabel}
              </span>
            )}
          </div>
          <p className="text-sm text-[var(--foreground)]">
            {cleanDesc ?? c.description ?? "Conflict between sources"}
          </p>
          <p className="text-[10px] text-[var(--muted)]">{new Date(c.created_at).toLocaleString()}</p>
        </div>
        {!c.resolved && (
          <div className="flex gap-2 flex-wrap shrink-0">
            {canMerge && (
              <button
                type="button"
                onClick={() => setMergeOpen((v) => !v)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  mergeOpen
                    ? "border-[var(--accent)] text-[var(--accent)]"
                    : "border-[var(--border)] hover:bg-[var(--card-hover)]"
                }`}
              >
                Merge fields
              </button>
            )}
            <button
              type="button"
              onClick={() => onResolve(c.id, "accept_a")}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--card-hover)] transition-colors"
            >
              Use A
            </button>
            <button
              type="button"
              onClick={() => onResolve(c.id, "accept_b")}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--card-hover)] transition-colors"
            >
              Use B
            </button>
            <button
              type="button"
              onClick={() => onResolve(c.id, "dismiss")}
              className="rounded-lg text-[var(--muted)] px-3 py-1.5 text-xs hover:text-[var(--foreground)] transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {canMerge && mergeOpen && a && b && (
        <MergePanel
          taskA={a}
          taskB={b}
          onApply={(fields) => onMerge(c.id, fields)}
          onCancel={() => setMergeOpen(false)}
        />
      )}

      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
        <div className="p-5">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-3">Source A</h3>
          {a ? <TaskSide t={a} /> : <SourceRefPanel sourceRef={c.source_a_ref ?? ids[0] ?? null} />}
        </div>
        <div className="p-5">
          <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-3">Source B</h3>
          {b ? <TaskSide t={b} /> : <SourceRefPanel sourceRef={c.source_b_ref ?? ids[1] ?? null} />}
        </div>
      </div>
    </div>
  );
}
