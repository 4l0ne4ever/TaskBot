"use client";

// Field-level merge picker for thread_update conflicts. Older task = the
// current row that survives (keeps identity + calendar event); newer task =
// the thread update whose values can be applied. Renders a diff table with
// checkboxes; submitted fields are POSTed via the merge endpoint.

import { useState } from "react";
import type { MergeableField, Task } from "@/lib/types";
import { MERGEABLE_FIELDS, fieldValue } from "./conflict-helpers";

export function MergePanel({
  taskA,
  taskB,
  onApply,
  onCancel,
}: {
  taskA: Task;
  taskB: Task;
  onApply: (fields: MergeableField[]) => void;
  onCancel: () => void;
}) {
  const [current, update] =
    new Date(taskA.created_at) <= new Date(taskB.created_at) ? [taskA, taskB] : [taskB, taskA];

  const diffs = MERGEABLE_FIELDS.filter((f) => fieldValue(current, f) !== fieldValue(update, f));
  const [selected, setSelected] = useState<Set<MergeableField>>(() => new Set(diffs));

  function toggle(f: MergeableField) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }

  if (diffs.length === 0) {
    return (
      <div className="px-5 py-4 bg-[var(--card-hover)]/40 border-b border-[var(--border)] text-xs text-[var(--muted)]">
        No differing fields to merge — the two tasks are identical on mergeable fields.
        <button type="button" onClick={onCancel} className="ml-2 text-[var(--accent)] hover:underline">
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="px-5 py-4 bg-[var(--card-hover)]/40 border-b border-[var(--border)] space-y-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
        Apply update into current task
      </p>
      <div className="space-y-1.5">
        <div className="grid grid-cols-[1.5rem_5rem_1fr_1fr] gap-2 text-[10px] uppercase tracking-wider text-[var(--muted)] font-semibold px-1">
          <span />
          <span>Field</span>
          <span>Current</span>
          <span>Update (newer)</span>
        </div>
        {diffs.map((f) => (
          <label
            key={f}
            className="grid grid-cols-[1.5rem_5rem_1fr_1fr] gap-2 items-center text-xs px-1 py-1 rounded hover:bg-[var(--surface)] cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selected.has(f)}
              onChange={() => toggle(f)}
              className="rounded border-[var(--border)] accent-[var(--accent)]"
            />
            <span className="capitalize text-[var(--muted)]">{f}</span>
            <span className="text-[var(--muted)] line-through decoration-[var(--danger)]/40 break-words">
              {fieldValue(current, f) ?? "—"}
            </span>
            <span className="text-[var(--foreground)] font-medium break-words">
              {fieldValue(update, f) ?? "—"}
            </span>
          </label>
        ))}
      </div>
      <div className="flex gap-2 pt-1">
        <button
          type="button"
          disabled={selected.size === 0}
          onClick={() => onApply([...selected])}
          className="rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-3 py-1.5 text-xs font-medium disabled:opacity-40 transition-colors"
        >
          Apply selected
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg text-[var(--muted)] px-3 py-1.5 text-xs hover:text-[var(--foreground)] transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
