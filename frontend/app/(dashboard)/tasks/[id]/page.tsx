"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const t = await api.tasks.get(id);
      setTask(t);
      setDeadline(t.deadline ?? "");
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
      await api.tasks.update(task.id, { deadline: deadline.trim() || null });
      toast.success("Deadline updated");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function removeTask() {
    if (!task || !confirm("Delete this task?")) return;
    try {
      await api.tasks.delete(task.id);
      toast.success("Deleted");
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

        <dl className="grid grid-cols-2 gap-4">
          <Field label="Assignee">{task.assignee ?? "\u2014"}</Field>
          <Field label="Priority">{task.priority ?? "\u2014"}</Field>
          <Field label="Status">{task.status}</Field>
          <Field label="Source">{task.source_type ?? "\u2014"}</Field>
        </dl>

        <div className="space-y-2 pt-2 border-t border-[var(--border)]">
          <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Deadline (YYYY-MM-DD)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              placeholder="2026-04-15"
              className="flex-1 min-w-[10rem] bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
            <button
              type="button"
              onClick={() => void saveDeadline()}
              className="rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-2 text-sm font-medium transition-colors"
            >
              Save
            </button>
          </div>
        </div>

        {(task.missing_fields?.length ?? 0) > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2">
            <span className="text-xs font-medium text-amber-600 dark:text-amber-300">Missing fields: </span>
            <span className="text-xs text-amber-500 dark:text-amber-200">{(task.missing_fields ?? []).join(", ")}</span>
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
