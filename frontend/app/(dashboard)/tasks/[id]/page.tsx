"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { Task, TaskSource } from "@/lib/types";

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
      await api.tasks.update(task.id, { deadline: deadline.trim() || null });
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
                      <span className="ml-auto text-[var(--muted)]">{new Date(source.created_at).toLocaleDateString()}</span>
                    </div>
                    <pre className="px-4 py-3 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-64 overflow-y-auto">
                      {source.excerpt ?? "No text content available."}
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
