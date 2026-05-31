"use client";

// Sync dashboard — orchestrates the gmail/drive source cards and the pipeline-run
// table. Sub-components live under components/sync/ since 2026-05-31 (Stage B);
// this file is now just data wiring + layout.

import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { Pagination } from "@/components/ui/Pagination";
import { StatusBadge } from "@/components/sync/StatusBadge";
import { SyncProgress } from "@/components/sync/SyncProgress";
import type { LastResult } from "@/components/sync/types";
import type { PipelineRunRow, SyncStateRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const RUNS_PAGE_SIZE = 20;

export default function SyncPage() {
  const [status, setStatus] = useState<SyncStateRow[]>([]);
  const [history, setHistory] = useState<PipelineRunRow[]>([]);
  const [runsTotal, setRunsTotal] = useState(0);
  const [runsPage, setRunsPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("1d");
  const [expandedError, setExpandedError] = useState<string | null>(null);
  const [cleaningRuns, setCleaningRuns] = useState(false);
  // Track sources that were triggered but may not yet appear as "running" in DB
  const [pendingSync, setPendingSync] = useState<{ gmail: boolean; drive: boolean }>({ gmail: false, drive: false });
  const prevStatusRef = useRef<Record<string, string>>({});
  const pendingTimeoutRef = useRef<{ gmail?: ReturnType<typeof setTimeout>; drive?: ReturnType<typeof setTimeout> }>({});

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

  // Full reload every 30s; fast status-only poll every 2s
  useEffect(() => {
    void load(runsPage);
    const slow = setInterval(() => void load(runsPage), 30_000);
    return () => clearInterval(slow);
  }, [load, runsPage]);

  useEffect(() => {
    const fast = setInterval(async () => {
      try {
        const s = await api.sync.status();
        setStatus(s);
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(fast);
  }, []);

  // Clear pendingSync when DB status transitions from "running" → idle
  useEffect(() => {
    for (const s of status) {
      const prev = prevStatusRef.current[s.source_type];
      if (prev === "running" && s.status !== "running") {
        setPendingSync((p) => ({ ...p, [s.source_type]: false }));
        if (pendingTimeoutRef.current[s.source_type as "gmail" | "drive"]) {
          clearTimeout(pendingTimeoutRef.current[s.source_type as "gmail" | "drive"]);
        }
      }
      prevStatusRef.current[s.source_type] = s.status;
    }
  }, [status]);

  function handleResult(source: "gmail" | "drive", r: LastResult) {
    setPendingSync((p) => ({ ...p, [source]: false }));
    if (pendingTimeoutRef.current[source]) clearTimeout(pendingTimeoutRef.current[source]);
    const label = source === "gmail" ? "Gmail" : "Drive";
    if (r.step === "error") {
      toast.error(`${label}: ${r.detail || "Sync failed"}`, { duration: 6000 });
    } else if (r.step === "throttling") {
      toast(`${label}: ${r.detail}`, { icon: "⚠️", duration: 6000 });
    } else if (r.current === 0 || r.detail.toLowerCase().includes("no new")) {
      toast(`${label}: No new content found`, { icon: "ℹ️" });
    } else {
      toast.success(`${label}: ${r.detail}`);
    }
    setTimeout(() => void load(1), 1500);
  }

  async function trigger(source: "gmail" | "drive") {
    try {
      await api.sync.trigger(source, timeRange);
      // Mark as pending immediately so the progress tracker appears before DB updates
      setPendingSync((p) => ({ ...p, [source]: true }));
      // Safety timeout: clear pending after 2 min in case something silently fails
      if (pendingTimeoutRef.current[source]) clearTimeout(pendingTimeoutRef.current[source]);
      pendingTimeoutRef.current[source] = setTimeout(() => {
        setPendingSync((p) => ({ ...p, [source]: false }));
      }, 120_000);
      toast(`${source === "gmail" ? "Gmail" : "Drive"} sync queued`, { icon: "⏳" });
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

  const gmailRunning = pendingSync.gmail || status.some((s) => s.source_type === "gmail" && s.status === "running");
  const driveRunning = pendingSync.drive || status.some((s) => s.source_type === "drive" && s.status === "running");

  if (loading && status.length === 0) {
    return <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>;
  }

  return (
    <div className="space-y-8 max-w-4xl">

      {/* ── Toolbar ── */}
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
          {gmailRunning ? "Syncing…" : "Sync Gmail"}
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
          {driveRunning ? "Syncing…" : "Sync Drive"}
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

      {/* ── Sources ── */}
      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Sources</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {(["gmail", "drive"] as const).map((src) => {
            const s = status.find((r) => r.source_type === src);
            const running = src === "gmail" ? gmailRunning : driveRunning;
            return (
              <div
                key={src}
                className={cn(
                  "rounded-xl border bg-[var(--surface)] p-4 space-y-3 transition-colors",
                  running ? "border-[var(--accent)]/40" : "border-[var(--border)]",
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {src === "gmail" ? (
                      <svg className="w-4 h-4 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                    )}
                    <span className="font-medium text-sm capitalize">{src}</span>
                  </div>
                  <StatusBadge status={s?.status ?? "idle"} />
                </div>

                <p className="text-xs text-[var(--muted)]">
                  Last synced:{" "}
                  {s?.last_sync_at ? new Date(s.last_sync_at).toLocaleString() : "Never"}
                </p>

                {/* Persistent error from sync_state (e.g. daily quota message) */}
                {s?.error_message && !running && (
                  <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2">
                    <svg className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs text-red-400 leading-relaxed">{s.error_message}</p>
                  </div>
                )}

                <SyncProgress
                  source={src}
                  running={running}
                  onResult={(r) => handleResult(src, r)}
                />
              </div>
            );
          })}

          {status.length === 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 col-span-full text-center">
              <p className="text-sm text-[var(--muted)]">No sync state yet. Trigger a sync to get started.</p>
            </div>
          )}
        </div>
      </section>

      {/* ── Pipeline runs ── */}
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
                      className={cn(
                        "hover:bg-[var(--card-hover)] transition-colors",
                        r.error_message && "cursor-pointer",
                      )}
                      onClick={() => r.error_message && setExpandedError(expandedError === r.id ? null : r.id)}
                    >
                      <td className="px-4 py-3 text-xs text-[var(--muted)] whitespace-nowrap">
                        {new Date(r.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.tasks_extracted}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{r.conflicts_found}</td>
                      <td className="px-4 py-3 text-xs text-red-400 max-w-[220px]">
                        {r.error_message && (
                          <span className="flex items-center gap-1">
                            <span className="truncate">{r.error_message}</span>
                            <svg className="w-3 h-3 shrink-0 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d={expandedError === r.id ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
                            </svg>
                          </span>
                        )}
                      </td>
                    </tr>
                    {expandedError === r.id && r.error_message && (
                      <tr key={`${r.id}-err`}>
                        <td colSpan={5} className="px-4 py-3 bg-red-500/5 text-xs text-red-400 break-all whitespace-pre-wrap font-mono border-t border-red-500/10">
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
