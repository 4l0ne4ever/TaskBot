"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  WEEKDAYS,
  endOfMonth,
  fmt,
  fmtMonthYear,
  startOfMonth,
} from "@/components/calendar/calendar-helpers";
import { cn } from "@/lib/utils";

// Calendar popover anchored to a trigger button. Use alongside an
// <input type="date"> when the native picker is too discoverable (Safari
// renders a tiny chevron that users miss). Click outside or Esc to close.
//
// ``value`` and ``onChange`` use ISO date strings (YYYY-MM-DD), matching the
// rest of the app's date plumbing.

interface Props {
  value: string;
  onChange: (iso: string) => void;
  minDate?: string;
  maxDate?: string;
  className?: string;
}

export function DatePickerPopover({ value, onChange, minDate, maxDate, className }: Props) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => {
    const anchor = value ? new Date(value + "T00:00:00") : new Date();
    return startOfMonth(anchor);
  });
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  // Re-anchor the view on the value when the popover opens — without this,
  // navigating to Feb and closing without picking leaves Feb stuck the next
  // time you open the picker, even after the deadline moves to a different
  // month elsewhere.
  useEffect(() => {
    if (open) {
      const anchor = value ? new Date(value + "T00:00:00") : new Date();
      setView(startOfMonth(anchor));
    }
  }, [open, value]);

  // Click-outside + Esc close. Listening on document because the popover
  // floats; portal would be overkill for a single-button trigger.
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      const t = e.target as Node;
      if (popoverRef.current?.contains(t) || buttonRef.current?.contains(t)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const days = useMemo(() => {
    const start = startOfMonth(view);
    const end = endOfMonth(view);
    let dayOfWeek = start.getDay();
    dayOfWeek = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
    const list: { date: Date; inMonth: boolean }[] = [];
    for (let i = dayOfWeek - 1; i >= 0; i--) {
      const d = new Date(start);
      d.setDate(d.getDate() - i - 1);
      list.push({ date: d, inMonth: false });
    }
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      list.push({ date: new Date(d), inMonth: true });
    }
    const remaining = 7 - (list.length % 7);
    if (remaining < 7) {
      for (let i = 1; i <= remaining; i++) {
        const d = new Date(end);
        d.setDate(d.getDate() + i);
        list.push({ date: d, inMonth: false });
      }
    }
    return list;
  }, [view]);

  const todayIso = fmt(new Date());

  return (
    <div className={cn("relative inline-block", className)}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Pick a date from the calendar"
        className="flex h-full items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--input-bg)] px-2.5 text-[var(--muted)] hover:bg-[var(--card-hover)] hover:text-[var(--foreground)] transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </button>
      {open && (
        <div
          ref={popoverRef}
          className="absolute left-0 z-30 mt-2 w-[260px] rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 shadow-xl"
        >
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setView((v) => new Date(v.getFullYear(), v.getMonth() - 1, 1))}
              className="rounded p-1 hover:bg-[var(--card-hover)]"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <span className="text-xs font-medium">{fmtMonthYear(view)}</span>
            <button
              type="button"
              onClick={() => setView((v) => new Date(v.getFullYear(), v.getMonth() + 1, 1))}
              className="rounded p-1 hover:bg-[var(--card-hover)]"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <div className="grid grid-cols-7 text-center text-[10px] text-[var(--muted)]">
            {WEEKDAYS.map((d) => (
              <div key={d} className="py-1">{d.slice(0, 1)}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {days.map(({ date: d, inMonth }, i) => {
              const iso = fmt(d);
              const selected = iso === value;
              const isToday = iso === todayIso;
              const disabled = (minDate && iso < minDate) || (maxDate && iso > maxDate);
              return (
                <button
                  key={i}
                  type="button"
                  disabled={!!disabled}
                  onClick={() => {
                    onChange(iso);
                    setOpen(false);
                  }}
                  className={cn(
                    "h-7 w-7 rounded text-xs transition-colors",
                    !inMonth && "opacity-40",
                    disabled && "cursor-not-allowed opacity-30",
                    !disabled && !selected && "hover:bg-[var(--card-hover)]",
                    selected && "bg-[var(--accent)] text-white font-medium",
                    !selected && isToday && "ring-1 ring-[var(--accent)]",
                  )}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>
          <div className="mt-2 flex items-center justify-between border-t border-[var(--border)] pt-2 text-[11px]">
            <button
              type="button"
              onClick={() => {
                onChange(todayIso);
                setOpen(false);
              }}
              className="text-[var(--accent)] hover:underline"
            >
              Today
            </button>
            {value && (
              <button
                type="button"
                onClick={() => {
                  onChange("");
                  setOpen(false);
                }}
                className="text-[var(--muted)] hover:text-[var(--foreground)]"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
