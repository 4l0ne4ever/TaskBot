"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { HighlightExcerpt } from "@/components/ui/HighlightExcerpt";
import { RecurrenceBadge, formatRecurrence } from "@/components/tasks/RecurrenceBadge";
import { DatePickerPopover } from "@/components/ui/DatePickerPopover";
import { RecurrencePicker } from "@/components/tasks/RecurrencePicker";
import type { Task, TaskSource } from "@/lib/types";
import { emitTasksChanged } from "@/lib/usePendingReviewCount";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [deadline, setDeadline] = useState("");
  // Round 13 (2026-05-31): editable time-of-day. Backend stores `HH:MM:SS`,
  // <input type="time"> wants `HH:MM`, so slice on load and pad on save.
  const [deadlineTime, setDeadlineTime] = useState("");
  const [description, setDescription] = useState("");
  const [source, setSource] = useState<TaskSource | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const t = await api.tasks.get(id);
      setTask(t);
      setDeadline(t.deadline ?? "");
      setDeadlineTime(t.deadline_time ? t.deadline_time.slice(0, 5) : "");
      setDescription(t.description ?? "");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Not found");
      router.push("/tasks");
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => { void load(); }, [load]);

  async function saveDeadline() {
    if (!task) return;
    try {
      // Round 13: time saved separately. Backend's `<input type="time">`
      // emits "HH:MM"; widen to "HH:MM:00" so Postgres `TIME` accepts it
      // unambiguously. Empty time clears the column to null.
      const t = deadlineTime.trim();
      await api.tasks.update(task.id, {
        deadline: deadline.trim() || null,
        deadline_time: t ? `${t}:00` : null,
      });
      toast.success("Deadline updated");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function saveDescription() {
    if (!task) return;
    try {
      await api.tasks.update(task.id, { description: description.trim() || null });
      toast.success("Description updated");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function savePriority(next: string | null) {
    if (!task) return;
    setTask({ ...task, priority: next });
    try {
      await api.tasks.update(task.id, { priority: next });
      toast.success(next ? `Priority: ${next}` : "Priority cleared");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
      void load();
    }
  }

  async function toggleSource() {
    if (sourceOpen) { setSourceOpen(false); return; }
    setSourceOpen(true);
    if (source || !task?.source_doc_id) return;
    setSourceLoading(true);
    try {
      setSource(await api.tasks.source(id));
    } catch {
      // no source available — keep open but show fallback
    } finally {
      setSourceLoading(false);
    }
  }

  // Phase 6.6 (recurring events, 2026-06-03): handlers for the LLM-suggest
  // / user-confirm flow. ``saveRecurrence`` confirms with a warning when an
  // active rule is changing (Option B from the design review) — the change
  // applies to all future occurrences in Google Calendar, so a silent edit
  // would surprise the user.
  async function saveRecurrence(newRule: string | null) {
    if (!task) return;
    const hadActive = Boolean(task.recurrence_rule);
    const cleared = hadActive && newRule === null;
    if (hadActive) {
      const msg = cleared
        ? "Remove recurrence: the calendar will switch back to a single event at the next occurrence. Continue?"
        : `Updating recurrence will apply to all future occurrences. Continue?`;
      if (!confirm(msg)) return;
    }
    try {
      await api.tasks.update(task.id, { recurrence_rule: newRule ?? "" });
      toast.success(newRule ? "Recurrence saved" : "Recurrence removed");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function applySuggestedRecurrence() {
    if (!task || !task.recurrence_suggested) return;
    try {
      await api.tasks.update(task.id, { recurrence_rule: task.recurrence_suggested });
      toast.success("Recurrence applied");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Apply failed");
    }
  }

  async function dismissSuggestedRecurrence() {
    if (!task) return;
    try {
      await api.tasks.update(task.id, { dismiss_recurrence_suggestion: true });
      toast.success("Suggestion dismissed");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Dismiss failed");
    }
  }

  async function removeTask() {
    if (!task || !confirm("Delete this task?")) return;
    try {
      await api.tasks.delete(task.id);
      toast.success("Deleted");
      // Delete may have removed a pending task — refresh the sidebar badge
      // before navigating away so the count drops immediately on return.
      if (task.status === "pending") emitTasksChanged();
      router.push("/tasks");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    }
  }

  if (loading || !task) {
    return <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>;
  }

  return (
    <div className="max-w-xl space-y-6">
      <Link href="/tasks" className="inline-flex items-center gap-1 text-sm text-[var(--accent)] hover:underline">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to tasks
      </Link>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 space-y-5">
        <h1 className="text-lg font-semibold">{task.title}</h1>

        <div className="space-y-2">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
          <button
            type="button"
            onClick={() => void saveDescription()}
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--card-hover)]"
          >
            Save description
          </button>
        </div>

        <dl className="grid grid-cols-2 gap-4">
          <Field label="Assignee">{task.assignee ?? "\u2014"}</Field>
          <Field label="Priority">
            <select
              value={task.priority ?? ""}
              onChange={(e) => void savePriority(e.target.value || null)}
              className="bg-[var(--input-bg)] border border-[var(--border)] rounded-md px-2 py-1 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] [color-scheme:dark]"
            >
              <option value="">None</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </Field>
          <Field label="Status">{task.status}</Field>
          <Field label="Source">{task.source_type ?? "\u2014"}</Field>
        </dl>

        <div className="space-y-2 pt-2 border-t border-[var(--border)]">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Deadline
          </label>
          <div className="flex gap-2 flex-wrap">
            {/* Native HTML5 date + time pickers, plus an explicit popover
                calendar trigger because Safari's native ``type="date"``
                indicator is a thin chevron that users miss — the popover
                gives a visible grid that matches /calendar's UX. ``Task.deadline``
                is stored as ``YYYY-MM-DD`` and ``Task.deadline_time`` as
                ``HH:MM:SS`` — exactly what these inputs consume/emit (the
                time input wants ``HH:MM``; the save handler pads with ":00").
                Either field cleared independently. */}
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="flex-1 min-w-[10rem] bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] [color-scheme:dark]"
            />
            <DatePickerPopover value={deadline} onChange={setDeadline} />
            <input
              type="time"
              value={deadlineTime}
              onChange={(e) => setDeadlineTime(e.target.value)}
              title="Optional time of day"
              className="w-[7rem] bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] [color-scheme:dark]"
            />
            <button
              type="button"
              onClick={() => void saveDeadline()}
              className="rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-2 text-sm font-medium transition-colors"
            >
              Save deadline
            </button>
          </div>
        </div>

        {(task.missing_fields?.length ?? 0) > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2">
            <span className="text-xs font-medium text-amber-600 dark:text-amber-300">Missing fields: </span>
            <span className="text-xs text-amber-500 dark:text-amber-200">{(task.missing_fields ?? []).join(", ")}</span>
          </div>
        )}

        {/* Phase 6.6 (recurring events): show LLM-suggested rule with
            single-click apply/dismiss when present, then the active
            recurrence (badge + editor). Suggested only renders when
            the user hasn't already dismissed it. */}
        <div className="space-y-3 pt-2 border-t border-[var(--border)]">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Recurrence
          </label>

          {task.recurrence_suggested && !task.recurrence_rule && !task.recurrence_dismissed_at && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <span>
                💡 Suggested from content: <span className="font-medium">{formatRecurrence(task.recurrence_suggested)}</span>
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void applySuggestedRecurrence()}
                  className="rounded border border-amber-500 bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-200"
                >
                  Apply
                </button>
                <button
                  type="button"
                  onClick={() => void dismissSuggestedRecurrence()}
                  className="rounded border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--muted)] hover:bg-[var(--card-hover)]"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {task.recurrence_rule && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--muted)]">Current:</span>
              <RecurrenceBadge rule={task.recurrence_rule} />
            </div>
          )}

          <RecurrencePicker
            value={task.recurrence_rule}
            onChange={(rule) => void saveRecurrence(rule)}
            deadline={task.deadline}
          />
        </div>

        {task.source_doc_id && (
          <div className="border-t border-[var(--border)] pt-4 space-y-3">
            <button
              type="button"
              onClick={() => void toggleSource()}
              className="flex items-center gap-1.5 text-xs text-[var(--accent)] hover:underline"
            >
              <svg className={`w-3.5 h-3.5 transition-transform ${sourceOpen ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              {sourceOpen ? "Hide source" : "View source"}
            </button>
            {sourceOpen && (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs overflow-hidden">
                {sourceLoading ? (
                  <p className="px-4 py-3 text-[var(--muted)]">Loading source…</p>
                ) : source ? (
                  <>
                    <div className="px-4 py-2 border-b border-[var(--border)] flex items-center gap-2 flex-wrap">
                      <span className="rounded-full bg-[var(--surface-2)] border border-[var(--border)] px-2 py-0.5 text-[10px] uppercase font-semibold text-[var(--muted)]">
                        {source.source_type}
                      </span>
                      <span className="text-[var(--muted)] font-mono text-[10px]">{source.source_ref}</span>
                      {(() => {
                        // Prefer received_at (when Gmail says the email arrived)
                        // and fall back to created_at (when TaskBot synced it).
                        // Backfill is intentionally not done by migration 0012,
                        // so older Drive rows and pre-migration emails still
                        // surface a sensible date.
                        const raw = source.received_at ?? source.created_at;
                        const label = source.received_at ? "Received" : "Synced";
                        const formatted = new Date(raw).toLocaleString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        });
                        return (
                          <span
                            className="ml-auto text-[var(--muted)] tabular-nums"
                            title={`${label}: ${new Date(raw).toISOString()}`}
                          >
                            {label} {formatted}
                          </span>
                        );
                      })()}
                    </div>
                    <pre className="px-4 py-3 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-64 overflow-y-auto">
                      <HighlightExcerpt text={source.excerpt ?? "No text content available."} quote={task.evidence_quote} />
                    </pre>
                  </>
                ) : (
                  <p className="px-4 py-3 text-[var(--muted)]">Source content not available.</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => void removeTask()}
          className="text-sm text-[var(--danger)] hover:opacity-80 transition-colors"
        >
          Delete task
        </button>
      </div>
    </div>
  );
}
