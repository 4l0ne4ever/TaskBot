"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ObservabilitySummary, QualityMetrics, SyncHealth } from "@/lib/types";
import { cn } from "@/lib/utils";

const card = "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6";
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="space-y-1">
      <div className="text-xs uppercase tracking-wide text-[var(--muted)]">{label}</div>
      <div className="text-2xl font-semibold text-[var(--foreground)]">{value}</div>
      {hint && <div className="text-xs text-[var(--muted)]">{hint}</div>}
    </div>
  );
}

const WINDOWS: { label: string; value: string | undefined }[] = [
  { label: "Lifetime", value: undefined },
  { label: "30 days", value: "30d" },
  { label: "7 days", value: "7d" },
];

function QualitySection() {
  const [data, setData] = useState<QualityMetrics | null>(null);
  const [window, setWindow] = useState<string | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      setData(await api.observability.quality(window));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load quality metrics");
    }
  }, [window]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className={cn(card, "space-y-5")}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Quality — Auto-confirm & lifecycle</h2>
          <p className="text-xs text-[var(--muted)]">Section D · task funnel and confirmation provenance</p>
        </div>
        <div className="flex gap-1 rounded-lg border border-[var(--border)] p-0.5">
          {WINDOWS.map((w) => (
            <button
              key={w.label}
              onClick={() => setWindow(w.value)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs transition-colors",
                window === w.value
                  ? "bg-[var(--accent)] text-white"
                  : "text-[var(--muted)] hover:bg-[var(--card-hover)]",
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {err && <div className="text-sm text-[var(--danger)]">{err}</div>}
      {!data && !err && <div className="text-sm text-[var(--muted)]">Loading…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <Stat
              label="Auto-confirm rate"
              value={pct(data.auto_confirm.auto_confirm_rate)}
              hint={`${data.auto_confirm.system_confirmed} of ${data.total_tasks} tasks`}
            />
            <Stat label="Need review" value={String(data.auto_confirm.need_review)} hint="pending, never confirmed" />
            <Stat label="User-confirmed" value={String(data.auto_confirm.user_confirmed)} />
            <Stat
              label="Superseded"
              value={String(data.auto_confirm.superseded)}
              hint="updated by newer message"
            />
          </div>

          {/* Honest dilution note: the lifetime aggregate mixes in pre-feature
              tasks that can never be system-confirmed. The headline thesis
              number (90.9%) is the controlled synthetic-batch measurement. */}
          {window === undefined && (
            <div className="rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/5 px-3 py-2 text-xs text-[var(--muted)]">
              Lifetime rate is diluted by tasks created before auto-confirm existed (they can
              never be system-confirmed). On the controlled enterprise sample, eligible tasks
              auto-confirm at <span className="font-medium text-[var(--foreground)]">90.9%</span>.
            </div>
          )}

          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(data.by_status).map(([status, count]) => (
              <span
                key={status}
                className="rounded-full border border-[var(--border)] px-2.5 py-1 text-[var(--muted)]"
              >
                {status}: <span className="font-medium text-[var(--foreground)]">{count}</span>
              </span>
            ))}
          </div>

          <div className="border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
            Calibration · ECE{" "}
            <span className="font-medium text-[var(--foreground)]">{data.calibration.ece}</span> ·{" "}
            {data.calibration.note} <span className="opacity-70">({data.calibration.source})</span>
          </div>
        </>
      )}
    </section>
  );
}

function SyncHealthSection() {
  const [data, setData] = useState<SyncHealth | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.observability
      .syncHealth()
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load sync health"));
  }, []);

  const dot = (s: SyncHealth["overall"]) =>
    s === "healthy" ? "bg-[var(--success)]" : s === "stale" ? "bg-[var(--warning)]" : "bg-[var(--danger)]";

  return (
    <section className={cn(card, "space-y-4")}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Sync Health</h2>
          <p className="text-xs text-[var(--muted)]">Section A · per-source staleness vs configured interval</p>
        </div>
        {data && (
          <span className="flex items-center gap-2 text-xs text-[var(--muted)]">
            <span className={cn("h-2 w-2 rounded-full", dot(data.overall))} />
            {data.overall}
          </span>
        )}
      </div>

      {err && <div className="text-sm text-[var(--danger)]">{err}</div>}
      {!data && !err && <div className="text-sm text-[var(--muted)]">Loading…</div>}

      {data && data.sources.length === 0 && (
        <div className="text-sm text-[var(--muted)]">No sync sources connected.</div>
      )}

      {data && data.sources.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.sources.map((s) => (
            <div key={s.source_type} className="rounded-lg border border-[var(--border)] p-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-medium capitalize text-[var(--foreground)]">{s.source_type}</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs",
                    s.has_error
                      ? "bg-[var(--danger)]/10 text-[var(--danger)]"
                      : s.is_stale
                        ? "bg-[var(--warning)]/10 text-[var(--warning)]"
                        : "bg-[var(--success)]/10 text-[var(--success)]",
                  )}
                >
                  {s.has_error ? "error" : s.is_stale ? "stale" : "healthy"}
                </span>
              </div>
              <div className="text-xs text-[var(--muted)]">
                {s.staleness_minutes == null
                  ? "never synced"
                  : `${s.staleness_minutes.toFixed(0)} min ago`}{" "}
                · interval {s.interval_minutes}m
              </div>
              {s.error_message && <div className="text-xs text-[var(--danger)]">{s.error_message}</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function PipelineSection() {
  const [data, setData] = useState<ObservabilitySummary | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.observability
      .summary()
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load pipeline metrics"));
  }, []);

  return (
    <section className={cn(card, "space-y-5")}>
      <div>
        <h2 className="text-sm font-semibold text-[var(--foreground)]">Pipeline & LLM Observability</h2>
        <p className="text-xs text-[var(--muted)]">Sections B/C · provider latency, errors, throughput</p>
      </div>

      {err && <div className="text-sm text-[var(--danger)]">{err}</div>}
      {!data && !err && <div className="text-sm text-[var(--muted)]">Loading…</div>}

      {data && (
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4">
          <Stat label="LLM error rate" value={pct(data.llm.error_rate)} hint={`${data.llm.sample_size} calls`} />
          <Stat
            label="Latency p50 / p95"
            value={`${data.llm.p50_ms} / ${data.llm.p95_ms} ms`}
            hint={`p99 ${data.llm.p99_ms} ms · target <${data.targets.p95_lt_ms}`}
          />
          <Stat label="Tokens" value={data.llm.total_tokens.toLocaleString()} />
          <Stat label="Est. cost" value={`$${data.llm.estimated_cost_total.toFixed(4)}`} />
          <Stat
            label="Pipeline error rate"
            value={pct(data.pipeline.error_rate)}
            hint={`${data.pipeline.failed_runs}/${data.pipeline.total_runs} · ${data.pipeline.window_days}d`}
          />
          <Stat
            label="Missing deadline"
            value={pct(data.quality.missing_deadline_rate)}
            hint={`${data.quality.missing_deadline_tasks}/${data.quality.total_tasks} tasks`}
          />
        </div>
      )}
    </section>
  );
}

export default function AdminPage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <QualitySection />
      <SyncHealthSection />
      <PipelineSection />
    </div>
  );
}
