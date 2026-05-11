"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import type { PipelineRunRow, SyncStateRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const RUNS_PAGE_SIZE = 20;

interface Progress {
  active: boolean;
  step: string;
  detail: string;
  current: number;
  total: number;
}

const STEP_ORDER = ["connecting", "fetching", "processing", "extracting", "saving", "done"];

function stepPercent(p: Progress): number {
  if (!p.active) return 0;
  const idx = STEP_ORDER.indexOf(p.step);
  if (idx < 0) return p.step === "error" ? 100 : 10;
  const base = ((idx + 1) / STEP_ORDER.length) * 100;
  if (p.total > 0 && p.current > 0) {
    const stepSize = 100 / STEP_ORDER.length;
    const intraStep = (p.current / p.total) * stepSize;
    return Math.min(100, (idx / STEP_ORDER.length) * 100 + intraStep);
  }
  return Math.min(100, base);
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        status === "running" && "bg-amber-500/15 text-amber-600 dark:text-amber-300",
        status === "error" && "bg-red-500/15 text-red-600 dark:text-red-300",
        status === "completed" && "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
        status === "idle" && "bg-[var(--muted)]/15 text-[var(--muted)]",
        status === "failed" && "bg-red-500/15 text-red-600 dark:text-red-300"
      )}
    >
      {status === "running" && <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />}
      {status}
    </span>
  );
}

function ProgressBar({ source, running }: { source: "gmail" | "drive"; running: boolean }) {
  const [progress, setProgress] = useState<Progress>({ active: false, step: "", detail: "", current: 0, total: 0 });
  const interval = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (!running) {
      setProgress({ active: false, step: "", detail: "", current: 0, total: 0 });
      if (interval.current) clearInterval(interval.current);
      return;
    }
    const poll = async () => {
      try {
        const p = await api.sync.progress(source);
        setProgress(p);
      } catch {
        /* ignore polling errors */
      }
    };
    void poll();
    interval.current = setInterval(() => void poll(), 2000);
    return () => { if (interval.current) clearInterval(interval.current); };
  }, [running, source]);

  if (!running && !progress.active) return null;

  const pct = stepPercent(progress);

  return (
    <div className="space-y-2 pt-2">
      <div className="h-1.5 w-full rounded-full bg-[var(--border)] overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            progress.step === "error" ? "bg-red-500" : "bg-[var(--accent)]"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {progress.detail && (
        <p className={cn(
          "text-xs",
          progress.step === "error" ? "text-red-400" : "text-[var(--muted)]"
        )}>
          {progress.detail}
        </p>
      )}
    </div>
  );
}

export default function SyncPage() {
  const [status, setStatus] = useState<SyncStateRow[]>([]);
  const [history, setHistory] = useState<PipelineRunRow[]>([]);
  const [runsTotal, setRunsTotal] = useState(0);
  const [runsPage, setRunsPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("1d");
  const [expandedError, setExpandedError] = useState<string | null>(null);
  const [cleaningRuns, setCleaningRuns] = useState(false);

  const load = useCallback(async (p = runsPage) => {
    setLoading(true);
    try {
      const offset = (p - 1) * RUNS_PAGE_SIZE;
      const [s, h] = await Promise.all([
        api.sync.status(),
        api.sync.history(RUNS_PAGE_SIZE, offset),
      ]);
      setStatus(s);
      setHistory(h);
      setRunsTotal(offset + h.length + (h.length === RUNS_PAGE_SIZE ? RUNS_PAGE_SIZE : 0));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, [runsPage]);

  useEffect(() => {
    void load(runsPage);
    const t = setInterval(() => void load(runsPage), 10_000);
    return () => clearInterval(t);
  }, [load, runsPage]);

  async function trigger(source: "gmail" | "drive") {
    try {
      await api.sync.trigger(source, timeRange);
      toast.success(`${source} sync queued (last ${timeRange})`);
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Queue failed");
    }
  }

  async function cleanFailedRuns() {
    setCleaningRuns(true);
    try {
      const res = await api.sync.deleteHistory("failed");
      toast.success(`Deleted ${res.deleted} failed run(s)`);
      setRunsPage(1);
      void load(1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Clean failed");
    } finally {
      setCleaningRuns(false);
    }
  }

  async function cleanAllRuns() {
    if (!confirm("Delete ALL pipeline run history?")) return;
    setCleaningRuns(true);
    try {
      const res = await api.sync.deleteHistory();
      toast.success(`Deleted ${res.deleted} run(s)`);
      setRunsPage(1);
      void load(1);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Clean failed");
    } finally {
      setCleaningRuns(false);
    }
  }

  async function clearAll() {
    try {
      await api.sync.clear();
      toast.success("Sync state cleared");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Clear failed");
    }
  }

  const gmailRunning = status.some((s) => s.source_type === "gmail" && s.status === "running");
  const driveRunning = status.some((s) => s.source_type === "drive" && s.status === "running");

  if (loading && status.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>
    );
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
        >
          <option value="12h">Last 12 hours</option>
          <option value="1d">Last 1 day</option>
          <option value="3d">Last 3 days</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
        </select>
        <button
          type="button"
          onClick={() => void trigger("gmail")}
          disabled={gmailRunning}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 text-sm font-medium transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          {gmailRunning ? "Syncing..." : "Sync Gmail"}
        </button>
        <button
          type="button"
          onClick={() => void trigger("drive")}
          disabled={driveRunning}
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 text-sm font-medium transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          {driveRunning ? "Syncing..." : "Sync Drive"}
        </button>
        <button
          type="button"
          onClick={() => void load()}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] hover:bg-[var(--card-hover)] px-4 py-2 text-sm transition-colors"
        >
          Refresh
        </button>
        <button
          type="button"
          onClick={() => void clearAll()}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--danger)]/40 text-[var(--danger)] hover:bg-[var(--danger)]/10 px-4 py-2 text-sm transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          Clear
        </button>
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Sources</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {status.map((s) => (
            <div key={s.id} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-sm capitalize">{s.source_type}</span>
                <StatusBadge status={s.status} />
              </div>
              <p className="text-xs text-[var(--muted)]">
                Last synced: {s.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}
              </p>
              {s.error_message && (
                <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-1.5">{s.error_message}</p>
              )}
              <ProgressBar
                source={s.source_type as "gmail" | "drive"}
                running={s.status === "running"}
              />
            </div>
          ))}
          {status.length === 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 col-span-full text-center">
              <p className="text-sm text-[var(--muted)]">No sync state yet. Trigger a sync to get started.</p>
            </div>
          )}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Pipeline runs</h2>
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={() => void cleanFailedRuns()}
              disabled={cleaningRuns || history.filter((r) => r.status === "failed").length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--card-hover)] disabled:opacity-40 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Clean Failed
            </button>
            <button
              type="button"
              onClick={() => void cleanAllRuns()}
              disabled={cleaningRuns || history.length === 0}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)]/40 text-[var(--danger)] hover:bg-[var(--danger)]/10 px-3 py-1.5 text-xs disabled:opacity-40 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Clean All
            </button>
          </div>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
          {history.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                  <th className="px-4 py-3 font-medium">Started</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium text-right">Tasks</th>
                  <th className="px-4 py-3 font-medium text-right">Conflicts</th>
                  <th className="px-4 py-3 font-medium">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {history.map((r) => (
                  <>
                    <tr
                      key={r.id}
                      className="hover:bg-[var(--card-hover)] transition-colors cursor-default"
                      onClick={() => r.error_message && setExpandedError(expandedError === r.id ? null : r.id)}
                    >
                      <td className="px-4 py-3 text-xs text-[var(--muted)] whitespace-nowrap">
                        {new Date(r.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.tasks_extracted}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.conflicts_found}</td>
                      <td className="px-4 py-3 text-xs text-red-400 max-w-[220px]">
                        {r.error_message ? (
                          <span className="truncate block">{r.error_message}</span>
                        ) : null}
                      </td>
                    </tr>
                    {expandedError === r.id && r.error_message && (
                      <tr key={`${r.id}-err`} className="bg-red-500/5">
                        <td colSpan={5} className="px-4 py-3 text-xs text-red-400 break-all whitespace-pre-wrap font-mono">
                          {r.error_message}
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center">
              <p className="text-sm text-[var(--muted)]">No runs recorded yet.</p>
            </div>
          )}
        </div>
        <Pagination
          page={runsPage}
          pageSize={RUNS_PAGE_SIZE}
          total={runsTotal}
          onPage={(p) => { setRunsPage(p); void load(p); }}
        />
      </section>
    </div>
  );
}
