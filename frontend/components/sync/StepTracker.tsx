"use client";

import { cn } from "@/lib/utils";
import { STEPS, STEP_KEYS } from "./types";

// Horizontal step indicator for the sync pipeline (connect → fetch → … → done).
// Error and throttling tone the *current* step red/amber respectively; everything
// past the current step stays neutral.
export function StepTracker({ step }: { step: string }) {
  const currentIdx = STEP_KEYS.indexOf(step);
  const isError = step === "error";
  const isThrottling = step === "throttling";

  return (
    <div className="flex items-center gap-0 w-full mt-1">
      {STEPS.map((s, i) => {
        const isDone = !isError && !isThrottling && (currentIdx > i || step === "done");
        const isCurrent = !isError && !isThrottling && currentIdx === i && step !== "done";
        const isFuture = !isDone && !isCurrent;
        const isLast = i === STEPS.length - 1;

        return (
          <div key={s.key} className="flex items-center" style={{ flex: isLast ? "0 0 auto" : 1 }}>
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300",
                  isDone && "bg-emerald-500",
                  isCurrent && "bg-[var(--accent)] ring-4 ring-[var(--accent)]/20",
                  isFuture && "bg-[var(--border)]",
                  isError && i === currentIdx && "bg-red-500",
                )}
              >
                {isDone ? (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : isCurrent ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                ) : null}
              </div>
              <span
                className={cn(
                  "text-[9px] font-medium whitespace-nowrap",
                  isDone ? "text-emerald-500" : isCurrent ? "text-[var(--accent)]" : "text-[var(--muted)]",
                )}
              >
                {s.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "h-px flex-1 mb-4 transition-colors duration-300",
                  isDone ? "bg-emerald-500/60" : "bg-[var(--border)]",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
