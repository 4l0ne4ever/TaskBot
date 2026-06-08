"use client";

// Kanban for every non-dismissed task split by ``progress_state``
// (migration 0014). NULL state → "todo" column so legacy rows land in the
// first bucket. Both deadlined and no-deadline tasks appear here —
// /calendar gives the date-anchored view, /tracking gives the workflow
// view, /tasks gives the master list. Dismissed tasks are filtered out
// (already triaged).

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { ProgressState, Task } from "@/lib/types";
import { cn } from "@/lib/utils";
import { emitTasksChanged } from "@/lib/usePendingReviewCount";

const COLUMNS: { state: ProgressState; label: string; tone: string }[] = [
  { state: "todo", label: "Todo", tone: "text-[var(--muted)]" },
  { state: "in_progress", label: "In Progress", tone: "text-amber-600 dark:text-amber-300" },
  { state: "done", label: "Done", tone: "text-emerald-600 dark:text-emerald-300" },
];

const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };
function priorityRank(p: string | null): number {
  return p && p in PRIORITY_RANK ? PRIORITY_RANK[p] : 3;
}

function currentState(t: Task): ProgressState {
  return (t.progress_state ?? "todo") as ProgressState;
}

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-red-500/15 text-red-600 dark:text-red-300",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  low: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
};

export default function TrackingPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Pull a generous slice — Kanban needs every active task in one
      // view; we'd lose the "what am I working on" overview if we paged.
      // ``scope: "all"`` keeps the Done column populated alongside Todo
      // + In Progress (the default ``active`` scope hides done +
      // confirmed-past-deadline, which would empty the Done column).
      const { tasks: rows } = await api.tasks.list({ limit: 200, scope: "all" });
      // Dismissed tasks were already triaged — they don't belong on a
      // tracking board. Client-side filter keeps the request simple.
      setTasks(rows.filter((t) => t.status !== "dismissed"));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // Group + sort once per render. Within a column, sort by priority
  // (high → low → unset), then by newest. Stable across re-renders.
  const grouped = useMemo(() => {
    const groups: Record<ProgressState, Task[]> = {
      todo: [],
      in_progress: [],
      done: [],
    };
    for (const t of tasks) {
      groups[currentState(t)].push(t);
    }
    for (const key of Object.keys(groups) as ProgressState[]) {
      groups[key].sort((a, b) => {
        const pr = priorityRank(a.priority) - priorityRank(b.priority);
        if (pr !== 0) return pr;
        return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      });
    }
    return groups;
  }, [tasks]);

  async function setProgressState(taskId: string, next: ProgressState) {
    const before = tasks.find((t) => t.id === taskId);
    if (!before) return;
    // Optimistic: card snaps to the new column immediately so the user
    // sees the move. Revert on failure.
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, progress_state: next } : t))
    );
    try {
      await api.tasks.update(taskId, { progress_state: next });
      toast.success(`Moved to ${next === "in_progress" ? "In Progress" : next.charAt(0).toUpperCase() + next.slice(1)}`);
      emitTasksChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, progress_state: before.progress_state } : t))
      );
    }
  }

  const totalCount = tasks.length;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Tracking</h1>
        <p className="text-sm text-[var(--muted)]">
          Kanban view across every active task. Move cards between Todo / In Progress / Done.
          For the date-anchored view see{" "}
          <Link href="/calendar" className="text-[var(--accent)] hover:underline">/calendar</Link>.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-[var(--muted)]">
          Loading tasks&hellip;
        </div>
      ) : totalCount === 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
          <svg className="w-10 h-10 mx-auto text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <p className="text-sm text-[var(--muted)]">
            No tasks. Sync from Gmail/Drive or check{" "}
            <Link href="/tasks" className="text-[var(--accent)] hover:underline">/tasks</Link>{" "}
            to see history.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {COLUMNS.map((col) => {
            const items = grouped[col.state];
            return (
              <section
                key={col.state}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface)] flex flex-col min-h-[24rem]"
              >
                <header className="flex items-center justify-between px-3 py-2 border-b border-[var(--border)]">
                  <h2 className={cn("text-xs font-semibold uppercase tracking-wider", col.tone)}>
                    {col.label}
                  </h2>
                  <span className="text-[10px] font-semibold text-[var(--muted)] tabular-nums">
                    {items.length}
                  </span>
                </header>
                <div className="flex-1 p-2 space-y-2 overflow-y-auto max-h-[70vh]">
                  {items.length === 0 ? (
                    <p className="text-xs text-[var(--muted)] italic px-2 py-4 text-center">
                      Empty
                    </p>
                  ) : (
                    items.map((t) => (
                      <TaskCard
                        key={t.id}
                        task={t}
                        onMove={(next) => void setProgressState(t.id, next)}
                      />
                    ))
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function TaskCard({
  task,
  onMove,
}: {
  task: Task;
  onMove: (next: ProgressState) => void;
}) {
  const here = currentState(task);
  const prioClass = task.priority ? PRIORITY_BADGE[task.priority] : "";
  return (
    <article className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-2 hover:bg-[var(--card-hover)] transition-colors group">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/tasks/${task.id}`}
          className="text-sm font-medium text-[var(--accent)] hover:underline line-clamp-2"
        >
          {task.title}
        </Link>
        {task.priority && (
          <span className={cn("rounded-full text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 flex-shrink-0", prioClass)}>
            {task.priority}
          </span>
        )}
      </div>
      {task.assignee && (
        <p className="text-xs text-[var(--muted)]">{task.assignee}</p>
      )}
      {task.deadline && (
        <p className="text-xs text-[var(--muted)] tabular-nums">
          {task.deadline}
          {task.deadline_time && (
            <span className="ml-1 text-[var(--foreground)]">
              {task.deadline_time.slice(0, 5)}
            </span>
          )}
        </p>
      )}
      <div className="flex gap-1 pt-1 opacity-60 group-hover:opacity-100 transition-opacity">
        {COLUMNS.filter((c) => c.state !== here).map((c) => (
          <button
            key={c.state}
            type="button"
            onClick={() => onMove(c.state)}
            className="flex-1 rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--muted)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] transition-colors"
            title={`Move to ${c.label}`}
          >
            → {c.label}
          </button>
        ))}
      </div>
    </article>
  );
}
