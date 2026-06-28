"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import { RecurrenceBadge } from "@/components/tasks/RecurrenceBadge";
import type { Conflict, Task } from "@/lib/types";
import { cn } from "@/lib/utils";
import { emitTasksChanged } from "@/lib/usePendingReviewCount";

const PAGE_SIZE = 10;

const PRIORITY_CLASSES: Record<string, string> = {
  high: "bg-red-500/15 text-red-600 dark:text-red-300 hover:bg-red-500/25",
  medium: "bg-amber-500/15 text-amber-600 dark:text-amber-300 hover:bg-amber-500/25",
  low: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 hover:bg-emerald-500/25",
};
const PRIORITY_OPTIONS: { value: string | null; label: string }[] = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: null, label: "None" },
];

// Click-to-edit priority chip. Replaces the previous read-only badge so users
// can override auto-derived priorities (and set them on the manual-deadline
// path where the auto rule deliberately skipped). Sends an optimistic update
// to the parent so the table re-renders without waiting on the PATCH.
function PriorityPicker({
  priority,
  onChange,
}: {
  priority: string | null;
  onChange: (next: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const label = priority ?? "set priority";
  const colorClass = priority
    ? PRIORITY_CLASSES[priority] ?? "bg-[var(--surface-2)] hover:bg-[var(--card-hover)]"
    : "bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--card-hover)]";
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={cn(
          "rounded-full text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 transition-colors cursor-pointer",
          colorClass,
        )}
      >
        {label}
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-20 rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg overflow-hidden min-w-[7rem]">
          {PRIORITY_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { setOpen(false); if (opt.value !== priority) onChange(opt.value); }}
              className={cn(
                "block w-full text-left px-3 py-1.5 text-xs transition-colors",
                opt.value === priority
                  ? "bg-[var(--card-hover)] text-[var(--foreground)] font-medium"
                  : "hover:bg-[var(--card-hover)] text-[var(--muted)] hover:text-[var(--foreground)]",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
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
  // Phase 2 — banner counter: how many HIGH-priority tasks currently
  // lack a deadline. Loaded independently from the paginated list so it
  // reflects the global state even when the user has narrowed the view
  // with other filters. Excludes dismissed tasks.
  const [highNoDeadlineCount, setHighNoDeadlineCount] = useState(0);
  // Round 14 (2026-05-31): missing-fields filter is now sent to the backend
  // via ?missing=deadline|assignee|any. Pre-Round-14 it was client-side over
  // the already-paginated page — page 1 looked empty whenever no rows on
  // that page happened to carry the gap, even though the global count
  // ("1-10 of 25") suggested matches existed. Backend filter fixes both
  // the empty-page UX and the count-vs-content mismatch in one move.
  const [missing, setMissing] = useState<string>("");
  const [priority, setPriority] = useState<string>("");
  const [sort, setSort] = useState<string>("created_desc");
  const [page, setPage] = useState(1);
  // 2026-06-07 (v2): "Show completed" toggle. Binary inverse — OFF shows
  // the active list (default), ON shows ONLY done + past-due-confirmed
  // (the completed bucket, no active mixed in). Persisted across reloads.
  const [showCompleted, setShowCompleted] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const v = window.localStorage.getItem("taskbot:showCompleted");
      if (v === "true") setShowCompleted(true);
    } catch {
      // localStorage may throw on private/quota-exceeded — silently fall
      // back to defaults rather than breaking the page.
    }
  }, []);
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem("taskbot:showCompleted", String(showCompleted));
    } catch {
      // see hydration effect
    }
  }, [showCompleted]);

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
        api.tasks.list({
          status: status || undefined,
          source: source || undefined,
          missing: missing || undefined,
          priority: priority || undefined,
          sort,
          limit: PAGE_SIZE,
          offset,
          scope: showCompleted ? "completed" : "active",
        }),
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
    // ``missing`` must be in this list — without it the callback closure
    // captures the stale value (""), and if the user toggles Missing
    // while already on page 1, the setPage(1) below is a no-op so no
    // re-render → no recreated callback → next fetch ships without the
    // filter. ``status`` / ``source`` / ``sort`` are in the same boat;
    // page-reset alone is not enough.
  }, [status, source, sort, missing, priority, showCompleted, page]);

  useEffect(() => { setPage(1); }, [status, source, sort, missing, priority, showCompleted]);
  useEffect(() => { void load(page); }, [load, page]);

  // Phase 2 — load the high-priority-no-deadline counter independently of
  // the page filters. Refresh on mount + on the cross-component
  // ``taskbot:tasks:changed`` event (Confirm/Dismiss/Revert/Set-deadline
  // dispatch it). Watching ``tasks`` directly would re-fire on every page
  // change and filter switch — wasted round-trips for a value that only
  // mutates on actual task changes.
  const loadHighNoDeadlineCount = useCallback(async () => {
    try {
      const { total: t } = await api.tasks.list({
        missing: "deadline",
        priority: "high",
        limit: 1,
      });
      setHighNoDeadlineCount(t);
    } catch {
      // Silent — banner is non-critical; missing the count is fine.
    }
  }, []);
  useEffect(() => {
    void loadHighNoDeadlineCount();
    const onChanged = () => void loadHighNoDeadlineCount();
    window.addEventListener("taskbot:tasks:changed", onChanged);
    return () => window.removeEventListener("taskbot:tasks:changed", onChanged);
  }, [loadHighNoDeadlineCount]);

  // Phase 2 — click banner → apply the corresponding filters so the user
  // lands on the exact rows the banner warned about. Resets pagination.
  const focusHighNoDeadline = useCallback(() => {
    setStatus("");
    setSource("");
    setMissing("deadline");
    setPriority("high");
    setSort("created_desc");
    setPage(1);
  }, []);
  const isHighNoDeadlineFocused =
    missing === "deadline" && priority === "high";

  // Round 14: backend now applies the missing-fields filter (see
  // ?missing=… in api.tasks.list), so the fetched page is already the
  // visible page. Variable kept for minimal diff in the table render.
  const visibleTasks = tasks;

  // When the user has narrowed the list with a status filter, a mutation
  // that pushes the task out of that filter should also pop it from the
  // visible rows. Without this, confirming a Pending task left a stray
  // "CONFIRMED" badge on the Pending page until the next reload.
  const applyMutationToList = useCallback(
    (id: string, patch: Partial<Task>, nextStatus: string) => {
      setTasks((prev) => {
        if (status && status !== nextStatus) {
          // Row no longer matches the active filter — remove it instead of
          // mutating in place. Also adjust the total counter so pagination
          // stays consistent without waiting for the next fetch.
          if (prev.some((t) => t.id === id)) {
            setTotal((cur) => Math.max(0, cur - 1));
          }
          return prev.filter((t) => t.id !== id);
        }
        return prev.map((t) => (t.id === id ? { ...t, ...patch } : t));
      });
    },
    [status],
  );

  async function confirmTask(id: string) {
    applyMutationToList(id, { status: "confirmed", confirmed_by: "user" }, "confirmed");
    try {
      await api.tasks.update(id, { status: "confirmed" });
      toast.success("Confirmed");
      emitTasksChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function dismissTask(id: string) {
    // Hide dismissed rows from the default ("All") active view so the list
    // stays focused on work that still needs attention. When the user has
    // explicitly filtered to status="dismissed", keep the row visible so
    // they can see the just-dismissed item and Revert if it was a mistake.
    if (status === "dismissed") {
      applyMutationToList(id, { status: "dismissed" }, "dismissed");
    } else {
      setTasks((prev) => {
        if (prev.some((t) => t.id === id)) {
          setTotal((cur) => Math.max(0, cur - 1));
        }
        return prev.filter((t) => t.id !== id);
      });
    }
    try {
      await api.tasks.update(id, { status: "dismissed" });
      toast.success("Dismissed", {
        // 8-second window mirrors common email "Undo" patterns — enough
        // time to catch a misclick, short enough not to clutter the UI.
        duration: 8000,
        id: `dismiss-${id}`,
      });
      // Show an Undo affordance via a follow-up custom toast. react-hot-toast
      // doesn't support action buttons on success(), so we render a second
      // toast with the button — same id so dismissing one dismisses both.
      toast(
        (tt) => (
          <span className="flex items-center gap-3">
            <span>Task dismissed.</span>
            <button
              type="button"
              onClick={() => {
                // Revert in backend, then refresh the page so the row
                // reappears in the active list. Without ``load`` the
                // visual recovery only happens on the next manual reload.
                void (async () => {
                  await revertTask(id);
                  void load(page);
                })();
                toast.dismiss(tt.id);
              }}
              className="rounded border border-[var(--border)] px-2 py-0.5 text-xs font-medium hover:bg-[var(--card-hover)]"
            >
              Undo
            </button>
          </span>
        ),
        { duration: 8000, id: `dismiss-undo-${id}` },
      );
      emitTasksChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function updatePriority(id: string, next: string | null) {
    setTasks((prev) => prev.map((t) => t.id === id ? { ...t, priority: next } : t));
    try {
      await api.tasks.update(id, { priority: next });
      toast.success(next ? `Priority: ${next}` : "Priority cleared");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
      void load(page);
    }
  }

  async function revertTask(id: string) {
    applyMutationToList(id, { status: "pending", confirmed_by: null }, "pending");
    try {
      await api.tasks.update(id, { status: "pending" });
      toast.success("Reverted to pending");
      emitTasksChanged();
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
      emitTasksChanged();
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
      {highNoDeadlineCount > 0 && !isHighNoDeadlineFocused && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-red-500/40 bg-red-500/[0.06] px-4 py-3 text-sm"
        >
          <svg
            className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <div className="flex-1">
            <p className="font-medium text-red-600 dark:text-red-300">
              {highNoDeadlineCount} high-priority task{highNoDeadlineCount === 1 ? "" : "s"} without a deadline
            </p>
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              High-priority work without a deadline doesn&apos;t land on the calendar. Pick a date so the team knows when it&apos;s due.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/calendar"
              className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--muted)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] transition-colors"
              title="Open the calendar sidebar with Today/Tomorrow/Friday quick-set buttons"
            >
              Open calendar
            </Link>
            <button
              type="button"
              onClick={focusHighNoDeadline}
              className="rounded-md bg-red-500/15 px-2.5 py-1 text-xs font-medium text-red-600 dark:text-red-300 hover:bg-red-500/25 transition-colors"
            >
              Review here →
            </button>
          </div>
        </div>
      )}
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
          <span className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">Priority</span>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            title="Filter by priority level — None matches tasks without a set priority"
          >
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="none">None</option>
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

        <label
          className="flex items-center gap-2 self-end pb-2 cursor-pointer select-none"
          title="ON: show ONLY completed tasks (progress=done) or past-deadline confirmed tasks. OFF: show only the active list. Pending-overdue tasks always stay in the active list."
        >
          <input
            type="checkbox"
            checked={showCompleted}
            onChange={(e) => setShowCompleted(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-[var(--border)] text-[var(--accent)] focus:ring-[var(--accent)] cursor-pointer"
          />
          <span className="text-xs text-[var(--muted)]">Show completed only</span>
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
          <p className="text-sm text-[var(--muted)]">
            {showCompleted
              ? "No completed tasks yet — mark something done in /tracking or wait for a confirmed task's deadline to pass."
              : "No tasks yet. Sync from Gmail/Drive or upload a file."}
          </p>
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
                  // Same predicate as backend completed-filter — when Show
                  // completed is on, dim & strike-through completed rows so
                  // the user can distinguish them from active work.
                  const todayIso = new Date().toISOString().slice(0, 10);
                  const isCompleted =
                    t.progress_state === "done" ||
                    (t.status === "confirmed" && t.deadline != null && t.deadline < todayIso);
                  return (
                  <tr
                    key={t.id}
                    className={cn(
                      "group transition-colors",
                      isCompleted
                        ? "opacity-60 hover:opacity-100 hover:bg-[var(--card-hover)]"
                        : needsReview
                          ? "bg-amber-500/[0.04] hover:bg-amber-500/[0.08] [&_td:first-child]:border-l-2 [&_td:first-child]:border-l-amber-500/60"
                          : "hover:bg-[var(--card-hover)]"
                    )}
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/tasks/${t.id}`}
                        className={cn(
                          "text-[var(--accent)] hover:underline font-medium",
                          isCompleted && "line-through decoration-[var(--muted)]/60"
                        )}
                      >
                        {t.title}
                      </Link>
                      {isCompleted && (
                        <span
                          className="ml-2 inline-block rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0 text-[10px] uppercase tracking-wide text-[var(--muted)] align-middle"
                          title={
                            t.progress_state === "done"
                              ? "Marked done in /tracking"
                              : "Confirmed, deadline has passed"
                          }
                        >
                          Completed
                        </span>
                      )}
                      {/* Phase 6.6: recurrence indicator. Active rule shows
                          as primary badge; the LLM suggestion shows as the
                          "pending review" amber badge so the user knows to
                          click into the task. */}
                      {(t.recurrence_rule || (t.recurrence_suggested && !t.recurrence_dismissed_at)) && (
                        <span className="ml-2 inline-flex">
                          <RecurrenceBadge
                            rule={t.recurrence_rule ?? t.recurrence_suggested}
                            variant={t.recurrence_rule ? "active" : "suggested"}
                          />
                        </span>
                      )}
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
                        <PriorityPicker
                          priority={t.priority}
                          onChange={(next) => void updatePriority(t.id, next)}
                        />
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
                          {conflictTaskIds.has(t.id) ? (
                            // Task has an open conflict with another task that
                            // contradicts it (different deadline/assignee for
                            // the same deliverable). Confirming one side here
                            // would leave the conflict unresolved and would
                            // auto-create a calendar event for a deliverable
                            // whose deadline is still under dispute — point
                            // the user to /conflicts to pick a side first.
                            <Link
                              href="/conflicts"
                              className="text-xs font-medium text-yellow-600 dark:text-yellow-300 hover:underline transition-colors"
                              title="Resolve the deadline/assignee conflict before confirming so the calendar doesn't get a disputed event"
                            >
                              Resolve conflict →
                            </Link>
                          ) : (
                            <button
                              type="button"
                              onClick={() => void confirmTask(t.id)}
                              className="text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 dark:hover:text-emerald-300 transition-colors"
                            >
                              Confirm
                            </button>
                          )}
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
                          {/* Round 14 (2026-05-31): allow Revert for ANY
                              confirmed task — not just auto-confirmed. A
                              user who clicked Confirm by mistake had no way
                              back; now both confirmation paths are
                              reversible. The hover-to-show keeps the table
                              tidy. */}
                          <button
                            type="button"
                            onClick={() => void revertTask(t.id)}
                            className="text-[10px] text-[var(--muted)] hover:text-[var(--foreground)] opacity-0 group-hover:opacity-100 transition-opacity"
                            title={
                              t.confirmed_by === "system"
                                ? "Auto-confirmed — revert to pending for manual review"
                                : "Revert your confirmation back to pending"
                            }
                          >
                            Revert
                          </button>
                        </div>
                      ) : t.status === "dismissed" ? (
                        <div className="flex items-center gap-2 justify-end">
                          <span className="text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 bg-gray-500/15 text-gray-500 dark:text-gray-400">
                            dismissed
                          </span>
                          {/* Mirror the Confirmed-row Revert affordance —
                              a misclicked Dismiss left the user with no way
                              back from the list view. Hover-to-show keeps
                              the dismissed bucket visually quiet. */}
                          <button
                            type="button"
                            onClick={() => void revertTask(t.id)}
                            className="text-[10px] text-[var(--muted)] hover:text-[var(--foreground)] opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Revert this dismissal back to pending"
                          >
                            Revert
                          </button>
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
