"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api, type ConflictSort } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import { ScopeBadge, SCOPE_OPTIONS } from "@/components/conflicts/ScopeBadge";
import { HighlightExcerpt } from "@/components/ui/HighlightExcerpt";
import type { Conflict, ConflictScope, MergeableField, Task, TaskSource } from "@/lib/types";

const PAGE_SIZE = 20;

const RESOLUTION_LABELS: Record<string, string> = {
  accept_a: "Accepted A",
  accept_b: "Accepted B",
  dismiss: "Dismissed",
  dismiss_all: "Dismissed (bulk)",
};

function parseResolution(description: string | null): { label: string | null; cleanDesc: string | null } {
  if (!description) return { label: null, cleanDesc: null };
  const match = /^\[resolved:([^\]]+)\]\s*/.exec(description);
  if (!match) return { label: null, cleanDesc: description };
  const label = RESOLUTION_LABELS[match[1]] ?? `Resolved (${match[1]})`;
  const cleanDesc = description.slice(match[0].length).trim() || null;
  return { label, cleanDesc };
}

function TaskSide({ t }: { t: Task }) {
  const [src, setSrc] = useState<TaskSource | null>(null);
  const [srcOpen, setSrcOpen] = useState(false);
  const [srcLoading, setSrcLoading] = useState(false);

  async function toggleSrc() {
    if (srcOpen) { setSrcOpen(false); return; }
    setSrcOpen(true);
    if (src || !t.source_doc_id) return;
    setSrcLoading(true);
    try { setSrc(await api.tasks.source(t.id)); }
    catch { /* no source — show fallback */ }
    finally { setSrcLoading(false); }
  }

  return (
    <div className="space-y-2">
      <dl className="text-sm space-y-1.5">
        <div><span className="text-[var(--muted)]">Title: </span>{t.title}</div>
        <div><span className="text-[var(--muted)]">Deadline: </span>{t.deadline ?? "—"}</div>
        <div><span className="text-[var(--muted)]">Assignee: </span>{t.assignee ?? "—"}</div>
        <div>
          <span className="text-[var(--muted)]">Priority: </span>
          {t.priority ?? "—"}
        </div>
        {t.source_type && (
          <div>
            <span className="inline-block rounded-full bg-[var(--surface-2)] border border-[var(--border)] text-[10px] px-2 py-0.5 text-[var(--muted)] uppercase font-semibold">
              {t.source_type}
            </span>
          </div>
        )}
      </dl>
      {t.source_doc_id && (
        <div>
          <button
            type="button"
            onClick={() => void toggleSrc()}
            className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
          >
            <svg className={`w-3 h-3 transition-transform ${srcOpen ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            {srcOpen ? "Hide source" : "View source"}
          </button>
          {srcOpen && (
            <div className="mt-2 rounded border border-[var(--border)] text-xs">
              {srcLoading ? (
                <p className="px-3 py-2 text-[var(--muted)]">Loading…</p>
              ) : src ? (
                <>
                  <div className="px-3 py-1.5 border-b border-[var(--border)] flex gap-2 items-center">
                    <span className="uppercase text-[10px] font-semibold text-[var(--muted)]">{src.source_type}</span>
                    <span className="font-mono text-[10px] text-[var(--muted)]">{src.source_ref}</span>
                  </div>
                  <pre className="px-3 py-2 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-48 overflow-y-auto">
                    <HighlightExcerpt text={src.excerpt ?? "No text content."} quote={t.evidence_quote} />
                  </pre>
                </>
              ) : (
                <p className="px-3 py-2 text-[var(--muted)]">No source content available.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

type ScopeFilter = ConflictScope | "all";

export default function ConflictsPage() {
  const [rows, setRows] = useState<Conflict[]>([]);
  const [total, setTotal] = useState(0);
  const [tasksById, setTasksById] = useState<Record<string, Task>>({});
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [showResolved, setShowResolved] = useState(false);
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("all");
  const [sort, setSort] = useState<ConflictSort>("priority");
  const [page, setPage] = useState(1);

  const load = useCallback(async (p = page) => {
    setLoading(true);
    try {
      const offset = (p - 1) * PAGE_SIZE;
      const list = await api.conflicts.list({
        resolved: showResolved ? true : false,
        scope: scopeFilter === "all" ? undefined : scopeFilter,
        sort,
        limit: PAGE_SIZE,
        offset,
      });
      setRows(list);
      setTotal(offset + list.length + (list.length === PAGE_SIZE ? PAGE_SIZE : 0));

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
  }, [page, showResolved, scopeFilter, sort]);

  useEffect(() => { setPage(1); }, [showResolved, scopeFilter, sort]);
  useEffect(() => { void load(page); }, [load, page]);

  async function resolve(id: string, resolution: "accept_a" | "accept_b" | "dismiss") {
    // Optimistic: remove immediately from unresolved view so user doesn't
    // accidentally click a shifted row before the reload completes.
    setRows((prev) => prev.filter((c) => c.id !== id));
    try {
      await api.conflicts.resolve(id, resolution);
      toast.success("Resolved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
      void load(page); // restore on error
    }
  }

  async function mergeConflict(id: string, fields: MergeableField[]) {
    setRows((prev) => prev.filter((c) => c.id !== id));
    try {
      const res = await api.conflicts.merge(id, fields);
      const msg = res.calendar_sync.message;
      if (res.calendar_sync.status === "queued") {
        toast.success(`Merged. ${msg}`);
      } else {
        // skipped/failed — merge itself succeeded; calendar is informational
        toast.success(`Merged. ${msg}`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Merge failed");
      void load(page); // restore on error
    }
  }

  async function dismissAll() {
    if (!confirm("Dismiss ALL unresolved conflicts?")) return;
    setCleaning(true);
    try {
      const res = await api.conflicts.dismissAll();
      toast.success(`Dismissed ${res.dismissed} conflict(s)`);
      setPage(1);
      void load(1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally {
      setCleaning(false);
    }
  }

  const scopeLabel = SCOPE_OPTIONS.find((o) => o.value === scopeFilter)?.label.toLowerCase();
  const emptyCopy =
    scopeFilter !== "all"
      ? showResolved
        ? `No resolved ${scopeLabel} conflicts.`
        : `No unresolved ${scopeLabel} conflicts.`
      : showResolved
        ? "No resolved conflicts. All decisions have been cleared."
        : "No conflicts detected. Your tasks are consistent across sources.";

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-2 flex-wrap">
        <ScopeChip
          active={scopeFilter === "all"}
          onClick={() => setScopeFilter("all")}
          variant="all"
        >
          All
        </ScopeChip>
        {SCOPE_OPTIONS.map((o) => (
          <ScopeChip
            key={o.value}
            active={scopeFilter === o.value}
            onClick={() => setScopeFilter(o.value)}
            variant={o.value}
          >
            {o.label}
          </ScopeChip>
        ))}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center rounded-lg border border-[var(--border)] text-xs overflow-hidden">
          <button
            type="button"
            onClick={() => setShowResolved(false)}
            className={`px-3 py-1.5 transition-colors ${
              !showResolved
                ? "bg-[var(--accent)] text-white font-medium"
                : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            Unresolved
          </button>
          <button
            type="button"
            onClick={() => setShowResolved(true)}
            className={`px-3 py-1.5 transition-colors border-l border-[var(--border)] ${
              showResolved
                ? "bg-[var(--accent)] text-white font-medium"
                : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            Resolved
          </button>
        </div>
        <div className="flex items-center gap-1 text-xs">
          <span className="text-[var(--muted)]">Sort:</span>
          <button
            type="button"
            onClick={() => setSort("priority")}
            className={`rounded-md px-2 py-1 transition-colors ${
              sort === "priority"
                ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            Priority
          </button>
          <button
            type="button"
            onClick={() => setSort("created_at")}
            className={`rounded-md px-2 py-1 transition-colors ${
              sort === "created_at"
                ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            Newest
          </button>
        </div>
        <div className="ml-auto">
          <button
            type="button"
            onClick={() => void dismissAll()}
            disabled={cleaning || rows.filter((r) => !r.resolved).length === 0}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)]/40 text-[var(--danger)] hover:bg-[var(--danger)]/10 px-3 py-2 text-xs disabled:opacity-40 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Dismiss All
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-12 text-center max-w-2xl space-y-3">
          <svg className="w-10 h-10 mx-auto text-emerald-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-[var(--muted)]">{emptyCopy}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((c) => (
            <ConflictCard
              key={c.id}
              conflict={c}
              tasksById={tasksById}
              onResolve={resolve}
              onMerge={mergeConflict}
            />
          ))}
          <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={(p) => { setPage(p); void load(p); }} />
        </div>
      )}
    </div>
  );
}

const MERGEABLE_FIELDS: readonly MergeableField[] = [
  "title",
  "description",
  "assignee",
  "deadline",
  "priority",
];

function fieldValue(t: Task, f: MergeableField): string | null {
  return (t[f] as string | null) ?? null;
}

function ConflictCard({
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

function MergePanel({
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
  // Older task = the existing one that survives (keeps identity, calendar
  // event, confirmed status). Newer task = the thread update supplying values.
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

function SourceRefPanel({ sourceRef }: { sourceRef: string | null }) {
  const [src, setSrc] = useState<TaskSource | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  if (!sourceRef) return <p className="text-sm text-[var(--muted)]">—</p>;

  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (src) return;
    setLoading(true);
    try { setSrc(await api.tasks.sourceByRef(sourceRef!)); }
    catch { /* source_ref not in DB (e.g. seeded fake ref) — show ref label only */ }
    finally { setLoading(false); }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-[var(--muted)] font-mono break-all">{sourceRef}</p>
      <button
        type="button"
        onClick={() => void toggle()}
        className="flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline"
      >
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        {open ? "Hide source" : "View source"}
      </button>
      {open && (
        <div className="rounded border border-[var(--border)] text-xs">
          {loading ? (
            <p className="px-3 py-2 text-[var(--muted)]">Loading…</p>
          ) : src ? (
            <>
              <div className="px-3 py-1.5 border-b border-[var(--border)] flex gap-2 items-center">
                <span className="uppercase text-[10px] font-semibold text-[var(--muted)]">{src.source_type}</span>
                <span className="ml-auto text-[var(--muted)]">{new Date(src.created_at).toLocaleDateString()}</span>
              </div>
              <pre className="px-3 py-2 whitespace-pre-wrap font-sans text-[var(--muted)] leading-relaxed max-h-48 overflow-y-auto">
                {src.excerpt ?? "No text content."}
              </pre>
            </>
          ) : (
            <p className="px-3 py-2 text-[var(--muted)]">Source content not available for this reference.</p>
          )}
        </div>
      )}
    </div>
  );
}

const CHIP_FILLED: Record<ConflictScope, string> = {
  multi_source: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/30",
  thread_update: "bg-orange-500/15 text-orange-600 dark:text-orange-300 border-orange-500/30",
  inter_doc: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-300 border-yellow-500/30",
  intra_batch: "bg-gray-500/15 text-gray-600 dark:text-gray-300 border-gray-500/30",
};

function ScopeChip({
  children,
  active,
  onClick,
  variant,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  variant: ConflictScope | "all";
}) {
  // "All" is outlined when active so it visually contrasts with the four
  // filled scope chips — same chip vocabulary, different role.
  const activeClasses =
    variant === "all"
      ? "border-[var(--accent)] text-[var(--accent)] bg-transparent"
      : CHIP_FILLED[variant];
  const inactiveClasses =
    "border-[var(--border)] text-[var(--muted)] bg-transparent hover:text-[var(--foreground)]";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active ? activeClasses : inactiveClasses
      }`}
    >
      {children}
    </button>
  );
}
