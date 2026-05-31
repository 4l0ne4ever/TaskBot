"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ResultBanner } from "./ResultBanner";
import { StepTracker } from "./StepTracker";
import type { LastResult, Progress } from "./types";

// Live progress tracker for one source (gmail or drive). Polls /sync/progress
// every 2s while ``running`` is true; on transition to idle, captures the
// terminal state once and surfaces it via both ResultBanner and the parent's
// onResult callback (which uses it to toast + refresh the run list).
export function SyncProgress({
  source,
  running,
  onResult,
}: {
  source: "gmail" | "drive";
  running: boolean;
  onResult: (r: LastResult) => void;
}) {
  const [progress, setProgress] = useState<Progress>({
    active: false,
    step: "",
    detail: "",
    current: 0,
    total: 0,
  });
  const [lastResult, setLastResult] = useState<LastResult | null>(null);
  const wasActive = useRef(false);
  const wasEverRunning = useRef(false);
  const interval = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // Track whether this component ever received running=true
  useEffect(() => {
    if (running) wasEverRunning.current = true;
  }, [running]);

  useEffect(() => {
    if (!running) {
      if (interval.current) clearInterval(interval.current);
      const hadActive = wasActive.current;
      const hadRun = wasEverRunning.current;
      wasActive.current = false;
      wasEverRunning.current = false;

      if (hadActive) {
        // Sync was running — do one final poll to capture terminal state
        const lastProgress = progress;
        api.sync
          .progress(source)
          .then((p) => {
            const terminal = p.active ? p : lastProgress;
            if (terminal.step === "done" || terminal.step === "error" || terminal.step === "throttling") {
              const r: LastResult = {
                step: terminal.step as LastResult["step"],
                detail: terminal.detail,
                current: terminal.current,
                total: terminal.total,
              };
              setLastResult(r);
              onResult(r);
            } else {
              // Progress key already cleared — infer from last known state
              const r: LastResult = {
                step:
                  lastProgress.step === "error" || lastProgress.step === "throttling"
                    ? (lastProgress.step as LastResult["step"])
                    : "done",
                detail: lastProgress.detail || "Sync completed",
                current: lastProgress.current,
                total: lastProgress.total,
              };
              setLastResult(r);
              onResult(r);
            }
          })
          .catch(() => {
            const r: LastResult = { step: "done", detail: "Sync completed", current: 0, total: 0 };
            setLastResult(r);
            onResult(r);
          });
      } else if (hadRun) {
        // Was triggered but sync completed before we saw any Redis progress (very fast)
        const r: LastResult = { step: "done", detail: "Sync completed", current: 0, total: 0 };
        setLastResult(r);
        onResult(r);
      }

      setProgress({ active: false, step: "", detail: "", current: 0, total: 0 });
      return;
    }

    const poll = async () => {
      try {
        const p = await api.sync.progress(source);
        setProgress(p);
        if (p.active) {
          wasActive.current = true;
          // Capture terminal state immediately if step is final
          if (p.step === "done" || p.step === "error" || p.step === "throttling") {
            const r: LastResult = {
              step: p.step as LastResult["step"],
              detail: p.detail,
              current: p.current,
              total: p.total,
            };
            setLastResult(r);
            onResult(r);
          }
        }
      } catch {
        /* ignore */
      }
    };

    void poll();
    interval.current = setInterval(() => void poll(), 2000);
    return () => {
      if (interval.current) clearInterval(interval.current);
    };
  }, [running, source]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear result when a new sync starts
  useEffect(() => {
    if (running) setLastResult(null);
  }, [running]);

  if (!running && !lastResult) return null;

  return (
    <div className="pt-2 space-y-1">
      {running && (
        <>
          <StepTracker step={progress.step || "connecting"} />
          {progress.detail && (
            <p
              className={cn(
                "text-xs mt-1",
                progress.step === "error"
                  ? "text-red-400"
                  : progress.step === "throttling"
                    ? "text-amber-400"
                    : "text-[var(--muted)]",
              )}
            >
              {progress.step === "throttling" && "⚠ "}
              {progress.detail}
              {progress.total > 0 && progress.current > 0 && progress.step !== "done" && (
                <span className="ml-1 tabular-nums">
                  ({progress.current}/{progress.total})
                </span>
              )}
            </p>
          )}
        </>
      )}
      {!running && lastResult && <ResultBanner result={lastResult} />}
    </div>
  );
}
