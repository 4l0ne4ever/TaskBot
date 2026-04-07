"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { Conflict, Task } from "@/lib/types";

function TaskSide({ t }: { t: Task }) {
  return (
    <dl className="text-sm space-y-1.5">
      <div><span className="text-[var(--muted)]">Title: </span>{t.title}</div>
      <div><span className="text-[var(--muted)]">Deadline: </span>{t.deadline ?? "\u2014"}</div>
      <div><span className="text-[var(--muted)]">Assignee: </span>{t.assignee ?? "\u2014"}</div>
    </dl>
  );
}

export default function ConflictsPage() {
  const [rows, setRows] = useState<Conflict[]>([]);
  const [tasksById, setTasksById] = useState<Record<string, Task>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.conflicts.list(false);
      setRows(list);
      const ids = new Set<string>();
      for (const c of list) for (const id of c.task_ids ?? []) ids.add(id);
      const entries = await Promise.all(
        [...ids].map(async (id) => {
          try { return [id, await api.tasks.get(id)] as const; }
          catch { return [id, null] as const; }
        })
      );
      const map: Record<string, Task> = {};
      for (const [id, t] of entries) if (t) map[id] = t;
      setTasksById(map);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function resolve(id: string, resolution: "accept_a" | "accept_b" | "dismiss") {
    try {
      await api.conflicts.resolve(id, resolution);
      toast.success("Resolved");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>;
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-12 text-center max-w-2xl space-y-3">
        <svg className="w-10 h-10 mx-auto text-emerald-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-sm text-[var(--muted)]">No unresolved conflicts.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {rows.map((c) => {
        const ids = c.task_ids ?? [];
        const a = ids[0] ? tasksById[ids[0]] : undefined;
        const b = ids[1] ? tasksById[ids[1]] : undefined;
        return (
          <div key={c.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <div className="px-5 py-4 flex justify-between items-start gap-4 flex-wrap border-b border-[var(--border)]">
              <div className="space-y-1">
                <span className="inline-block rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-300 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5">
                  {c.conflict_type}
                </span>
                <p className="text-sm">{c.description ?? "Conflict between sources"}</p>
              </div>
              <div className="flex gap-2 flex-wrap shrink-0">
                <button
                  type="button"
                  onClick={() => void resolve(c.id, "accept_a")}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--card-hover)] transition-colors"
                >
                  Use A
                </button>
                <button
                  type="button"
                  onClick={() => void resolve(c.id, "accept_b")}
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--card-hover)] transition-colors"
                >
                  Use B
                </button>
                <button
                  type="button"
                  onClick={() => void resolve(c.id, "dismiss")}
                  className="rounded-lg text-[var(--muted)] px-3 py-1.5 text-xs hover:text-[var(--foreground)] transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]">
              <div className="p-5">
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-3">Source A</h3>
                {a ? <TaskSide t={a} /> : <p className="text-sm text-[var(--muted)]">Ref: {c.source_a_ref ?? ids[0] ?? "\u2014"}</p>}
              </div>
              <div className="p-5">
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)] mb-3">Source B</h3>
                {b ? <TaskSide t={b} /> : <p className="text-sm text-[var(--muted)]">Ref: {c.source_b_ref ?? ids[1] ?? "\u2014"}</p>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
