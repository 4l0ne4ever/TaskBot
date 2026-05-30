"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import type { Conflict, Task } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 10;

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
  const [total, setTotal] = useState(0);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [source, setSource] = useState<string>("");
  // Client-side filter on Task.missing_fields. Composes with the server-side
  // status filter — e.g. "Pending" + "Missing deadline" surfaces just the
  // pending tasks that also lack a deadline. Kept client-side because the
  // backend has no missing_fields index and the typical page (50 tasks) is
  // tiny enough that client filtering is imperceptible. Drawback: only the
  // current page is filtered, so a "Missing" selection may show fewer rows
  // than the global truth — acceptable trade-off vs. a new backend index.
  const [missing, setMissing] = useState<string>("");
  const [sort, setSort] = useState<string>("created_desc");
  const [page, setPage] = useState(1);

  const conflictTaskIds = useMemo(() => {
    const s = new Set<string>();
    for (const c of conflicts) {
      if (c.resolved) continue;
      for (const id of c.task_ids ?? []) s.add(id);
    }
    return s;
  }, [conflicts]);

  const load = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const offset = (p - 1) * PAGE_SIZE;
      const [taskResult, c] = await Promise.all([
        api.tasks.list({ status: status || undefined, source: source || undefined, sort, limit: PAGE_SIZE, offset }),
        api.conflicts.list({ resolved: false }),
      ]);
      setTasks(taskResult.tasks);
      setTotal(taskResult.total);
      setConflicts(c);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load tasks");
    } finally {
      setLoading(false);
    }
  }, [status, source, sort, page]);

  useEffect(() => { setPage(1); }, [status, source, sort, missing]);
  useEffect(() => { void load(page); }, [load, page]);

  // Client-side missing-fields filter applied on top of the fetched page.
  const visibleTasks = useMemo(() => {
    if (!missing) return tasks;
    return tasks.filter((t) => {
      const fields = t.missing_fields ?? [];
      if (missing === "any") return fields.length > 0;
      return fields.includes(missing);
    });
  }, [tasks, missing]);

  async function confirmTask(id: string) {
    setTasks((prev) => prev.map((t) => t.id === id ? { ...t, status: "confirmed", confirmed_by: "user" } : t));
    try {
      await api.tasks.update(id, { status: "confirmed" });
      toast.success("Confirmed");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function dismissTask(id: string) {
    setTasks((prev) => prev.map((t) => t.id === id ? { ...t, status: "dismissed" } : t));
    try {
      await api.tasks.update(id, { status: "dismissed" });
      toast.success("Dismissed");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function revertTask(id: string) {
    setTasks((prev) => prev.map((t) => t.id === id ? { ...t, status: "pending", confirmed_by: null } : t));
    try {
      await api.tasks.update(id, { status: "pending" });
      toast.success("Reverted to pending");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function cleanAll() {
    if (!confirm("Delete ALL tasks? This cannot be undone.")) return;
    setCleaning(true);
    try {
      const res = await api.tasks.deleteAll();
      toast.success(`Deleted ${res.deleted} task(s)`);
      setPage(1);
      void load(1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Clean failed");
    } finally {
      setCleaning(false);
    }
  }

  async function cleanDismissed() {
    setCleaning(true);
    try {
      const res = await api.tasks.deleteAll("dismissed");
      toast.success(`Deleted ${res.deleted} dismissed task(s)`);
      void load(page);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Clean failed");
    } finally {
      setCleaning(false);
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
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Missing</span>
          <select
            value={missing}
            onChange={(e) => setMissing(e.target.value)}
            className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            title="Filter to tasks that are missing one or more fields"
          >
            <option value="">All</option>
            <option value="deadline">Missing deadline</option>
            <option value="assignee">Missing assignee</option>
            <option value="any">Any missing field</option>
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

        <div className="ml-auto flex gap-2">
          <button
            type="button"
            onClick={() => void cleanDismissed()}
            disabled={cleaning}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-[var(--muted)] hover:bg-[var(--card-hover)] disabled:opacity-40 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clean Dismissed
          </button>
          <button
            type="button"
            onClick={() => void cleanAll()}
            disabled={cleaning}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)]/40 text-[var(--danger)] hover:bg-[var(--danger)]/10 px-3 py-2 text-xs disabled:opacity-40 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Clean All
          </button>
        </div>
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
        <div className="space-y-3">
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
                {visibleTasks.map((t) => {
                  // A task needs the user's attention when it's still pending
                  // OR when it was kept by graceful degradation but is missing
                  // a deadline/assignee. Both cases benefit from a row-level
                  // visual signal so the user spots them in a long list without
                  // having to scan every chip.
                  const needsReview = t.status === "pending" || (t.missing_fields?.length ?? 0) > 0;
                  return (
                  <tr
                    key={t.id}
                    className={cn(
                      "group transition-colors",
                      needsReview
                        ? "bg-amber-500/[0.04] hover:bg-amber-500/[0.08] [&_td:first-child]:border-l-2 [&_td:first-child]:border-l-amber-500/60"
                        : "hover:bg-[var(--card-hover)]"
                    )}
                  >
                    <td className="px-4 py-3">
                      <Link href={`/tasks/${t.id}`} className="text-[var(--accent)] hover:underline font-medium">
                        {t.title}
                      </Link>
                      {t.description && (
                        <p className="mt-1 text-xs text-[var(--muted)] line-clamp-2 max-w-[36rem]">{t.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">{t.assignee ?? "—"}</td>
                    <td className="px-4 py-3 text-[var(--muted)] tabular-nums whitespace-nowrap">
                      {t.deadline ? (
                        <>
                          {t.deadline}
                          {t.deadline_time && (
                            <span className="ml-1 text-[var(--foreground)]">
                              {t.deadline_time.slice(0, 5)}
                            </span>
                          )}
                        </>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block rounded-full bg-[var(--surface-2)] border border-[var(--border)] text-xs px-2 py-0.5 text-[var(--muted)]">
                        {t.source_type ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        <PriorityBadge priority={t.priority} />
                        {t.status === "confirmed" && t.confirmed_by === "system" && (
                          <span className="rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-300 text-[10px] font-medium px-2 py-0.5" title="Auto-confirmed by AI — click Revert to review manually">
                            Auto
                          </span>
                        )}
                        {t.status === "pending" && t.confirmed_by !== null && (
                          <span className="rounded-full bg-orange-500/10 text-orange-600 dark:text-orange-300 text-[10px] font-medium px-2 py-0.5" title="Updated by a new message — please re-confirm">
                            Updated
                          </span>
                        )}
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
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      {t.status === "pending" ? (
                        <div className="flex gap-2 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            type="button"
                            onClick={() => void confirmTask(t.id)}
                            className="text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 transition-colors"
                          >
                            Confirm
                          </button>
                          <button
                            type="button"
                            onClick={() => void dismissTask(t.id)}
                            className="text-xs font-medium text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                          >
                            Dismiss
                          </button>
                        </div>
                      ) : t.status === "confirmed" ? (
                        <div className="flex items-center gap-2 justify-end">
                          <span className="text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300">
                            confirmed
                          </span>
                          {t.confirmed_by === "system" && (
                            <button
                              type="button"
                              onClick={() => void revertTask(t.id)}
                              className="text-[10px] text-[var(--muted)] hover:text-[var(--foreground)] opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Revert to pending for manual review"
                            >
                              Revert
                            </button>
                          )}
                        </div>
                      ) : (
                        <span className="text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 bg-gray-500/15 text-gray-500 dark:text-gray-400">
                          {t.status}
                        </span>
                      )}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPage={(p) => setPage(p)}
          />
        </div>
      )}
    </div>
  );
}
