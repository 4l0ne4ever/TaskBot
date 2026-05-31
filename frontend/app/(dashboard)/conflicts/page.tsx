"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api, type ConflictSort } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import { SCOPE_OPTIONS } from "@/components/conflicts/ScopeBadge";
import { ConflictCard } from "@/components/conflicts/ConflictCard";
import { ScopeChip } from "@/components/conflicts/ScopeChip";
import type { Conflict, ConflictScope, MergeableField, Task } from "@/lib/types";

const PAGE_SIZE = 20;

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
      toast.success(`Merged. ${res.calendar_sync.message}`);
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
