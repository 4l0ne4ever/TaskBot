"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { Conflict, Task } from "@/lib/types";
import { cn } from "@/lib/utils";

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  return (
    <span
      className={cn(
        "rounded-full text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5",
        priority === "high" && "bg-red-500/15 text-red-600 dark:text-red-300",
        priority === "medium" && "bg-amber-500/15 text-amber-600 dark:text-amber-300",
        priority === "low" && "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300"
      )}
    >
      {priority}
    </span>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [sort, setSort] = useState<string>("created_desc");

  const conflictTaskIds = useMemo(() => {
    const s = new Set<string>();
    for (const c of conflicts) {
      if (c.resolved) continue;
      for (const id of c.task_ids ?? []) s.add(id);
    }
    return s;
  }, [conflicts]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, c] = await Promise.all([
        api.tasks.list({ status: status || undefined, source: source || undefined, sort, limit: 100 }),
        api.conflicts.list(false),
      ]);
      setTasks(t);
      setConflicts(c);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, [status, source, sort]);

  useEffect(() => { void load(); }, [load]);

  async function confirmTask(id: string) {
    try {
      await api.tasks.update(id, { status: "confirmed" });
      toast.success("Confirmed");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    }
  }

  async function dismissTask(id: string) {
    try {
      await api.tasks.update(id, { status: "dismissed" });
      toast.success("Dismissed");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Source</span>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="">All</option>
            <option value="gmail">Gmail</option>
            <option value="drive">Drive</option>
            <option value="upload">Upload</option>
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Sort</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="created_desc">Newest</option>
            <option value="deadline_asc">Deadline</option>
          </select>
        </label>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading tasks&hellip;</div>
      ) : tasks.length === 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-12 text-center space-y-3">
          <svg className="w-10 h-10 mx-auto text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p className="text-sm text-[var(--muted)]">No tasks yet. Sync from Gmail/Drive or upload a file.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Assignee</th>
                <th className="px-4 py-3 font-medium">Deadline</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Flags</th>
                <th className="px-4 py-3 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {tasks.map((t) => (
                <tr key={t.id} className="group hover:bg-[var(--card-hover)] transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/tasks/${t.id}`} className="text-[var(--accent)] hover:underline font-medium">
                      {t.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{t.assignee ?? "\u2014"}</td>
                  <td className="px-4 py-3 text-[var(--muted)] tabular-nums">{t.deadline ?? "\u2014"}</td>
                  <td className="px-4 py-3">
                    <span className="inline-block rounded-full bg-[var(--surface-2)] border border-[var(--border)] text-xs px-2 py-0.5 text-[var(--muted)]">
                      {t.source_type ?? "\u2014"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      <PriorityBadge priority={t.priority} />
                      {(t.missing_fields?.length ?? 0) > 0 && (
                        <span className="rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-300 text-[10px] font-medium px-2 py-0.5">
                          Missing: {(t.missing_fields ?? []).join(", ")}
                        </span>
                      )}
                      {conflictTaskIds.has(t.id) && (
                        <span className="rounded-full bg-yellow-500/10 text-yellow-600 dark:text-yellow-300 text-[10px] font-medium px-2 py-0.5">
                          Conflict
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex gap-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => void confirmTask(t.id)}
                        disabled={t.status === "confirmed"}
                        className="text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 disabled:opacity-30 transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => void dismissTask(t.id)}
                        disabled={t.status === "dismissed"}
                        className="text-xs font-medium text-[var(--muted)] hover:text-[var(--foreground)] disabled:opacity-30 transition-colors"
                      >
                        Dismiss
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
