// Pure date + visual helpers shared by the calendar page and EventModal.
// Extracted from app/(dashboard)/calendar/page.tsx 2026-05-31 (Stage B).

import { formatLocalDateKey } from "@/lib/utils";

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

export function fmt(d: Date): string {
  return formatLocalDateKey(d);
}

export function fmtMonthYear(d: Date): string {
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function priorityColor(p: string | null): string {
  if (p === "high") return "bg-red-500/20 text-red-600 dark:text-red-300 border-red-500/30";
  if (p === "medium") return "bg-amber-500/20 text-amber-600 dark:text-amber-300 border-amber-500/30";
  return "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/30";
}

export function statusIcon(s: string): string {
  if (s === "confirmed") return "✓";
  if (s === "dismissed") return "✕";
  return "○";
}
