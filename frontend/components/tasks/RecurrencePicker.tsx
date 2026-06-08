"use client";

import { useMemo, useState, useEffect } from "react";
import { RecurrenceBadge, formatRecurrence } from "./RecurrenceBadge";

// Phase 6.6 (recurring events, 2026-06-03): pattern-builder UI for RFC 5545
// RRULE. Four presets (None / Daily / Weekly / Monthly) cover ~95% of cases
// — the "Custom" branch exposes INTERVAL + BYDAY + BYMONTHDAY + UNTIL so a
// power user can express weekly-Tue+Thu / every-2-weeks-Fri / last-Friday-
// of-the-month patterns without typing RRULE by hand.
//
// The composed RRULE is validated server-side by ``app.utils.recurrence``
// (whitelist: FREQ, INTERVAL, BYDAY, BYMONTHDAY, UNTIL, COUNT). The UI
// stays the minimum needed to keep the picker honest — anything stricter
// would be a UX choice, not a safety one.

type Mode = "none" | "daily" | "weekly" | "monthly" | "custom";

const WEEKDAYS: { code: string; vn: string }[] = [
  { code: "MO", vn: "T2" },
  { code: "TU", vn: "T3" },
  { code: "WE", vn: "T4" },
  { code: "TH", vn: "T5" },
  { code: "FR", vn: "T6" },
  { code: "SA", vn: "T7" },
  { code: "SU", vn: "CN" },
];

function rfcUntil(yyyyMmDd: string | null): string | null {
  if (!yyyyMmDd) return null;
  // Backend whitelist requires Z suffix (UTC). End-of-day in UTC is a
  // defensible default — covers the entire day in any timezone east of UTC,
  // which includes ICT (UTC+7).
  return yyyyMmDd.replace(/-/g, "") + "T235959Z";
}

function parseUntilDate(until: string | undefined): string {
  if (!until) return "";
  const m = until.match(/^(\d{4})(\d{2})(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}

function parseRule(rule: string | null | undefined) {
  if (!rule) return { mode: "none" as Mode, freq: "", interval: 1, byday: [] as string[], bymonthday: "", until: "" };
  const s = rule.startsWith("RRULE:") ? rule.slice(6) : rule;
  const kv: Record<string, string> = {};
  for (const chunk of s.split(";")) {
    const [k, v] = chunk.split("=");
    if (k && v) kv[k.toUpperCase()] = v.trim();
  }
  const freq = (kv.FREQ ?? "").toUpperCase();
  const interval = parseInt(kv.INTERVAL ?? "1", 10);
  const byday = kv.BYDAY ? kv.BYDAY.split(",").map((t) => t.trim().toUpperCase()) : [];
  const bymonthday = kv.BYMONTHDAY ?? "";
  const until = parseUntilDate(kv.UNTIL);
  // Pick the preset mode that round-trips exactly; otherwise fall to custom.
  if (freq === "DAILY" && interval === 1 && byday.length === 0 && !bymonthday && !kv.COUNT && !until) {
    return { mode: "daily" as Mode, freq, interval, byday, bymonthday, until };
  }
  if (freq === "WEEKLY" && interval === 1 && !bymonthday && !kv.COUNT && !until) {
    return { mode: "weekly" as Mode, freq, interval, byday, bymonthday, until };
  }
  if (freq === "MONTHLY" && interval === 1 && bymonthday && byday.length === 0 && !kv.COUNT && !until) {
    return { mode: "monthly" as Mode, freq, interval, byday, bymonthday, until };
  }
  return { mode: "custom" as Mode, freq: freq || "WEEKLY", interval, byday, bymonthday, until };
}

function composeRule(opts: {
  mode: Mode;
  weekdayDefault: string;
  monthdayDefault: number;
  weekly: string[];
  monthly: string;
  customFreq: string;
  customInterval: number;
  customByday: string[];
  customBymonthday: string;
  until: string;
}): string | null {
  if (opts.mode === "none") return null;
  const parts: string[] = [];
  const pushUntil = () => {
    const u = rfcUntil(opts.until || null);
    if (u) parts.push(`UNTIL=${u}`);
  };
  if (opts.mode === "daily") {
    parts.push("FREQ=DAILY");
    pushUntil();
    return parts.join(";");
  }
  if (opts.mode === "weekly") {
    parts.push("FREQ=WEEKLY");
    const days = opts.weekly.length > 0 ? opts.weekly : [opts.weekdayDefault];
    parts.push(`BYDAY=${days.join(",")}`);
    pushUntil();
    return parts.join(";");
  }
  if (opts.mode === "monthly") {
    parts.push("FREQ=MONTHLY");
    const md = opts.monthly || String(opts.monthdayDefault);
    parts.push(`BYMONTHDAY=${md}`);
    pushUntil();
    return parts.join(";");
  }
  // custom
  parts.push(`FREQ=${opts.customFreq}`);
  if (opts.customInterval && opts.customInterval > 1) parts.push(`INTERVAL=${opts.customInterval}`);
  if (opts.customByday.length > 0) parts.push(`BYDAY=${opts.customByday.join(",")}`);
  if (opts.customBymonthday) parts.push(`BYMONTHDAY=${opts.customBymonthday}`);
  pushUntil();
  return parts.join(";");
}

export function RecurrencePicker({
  value,
  onChange,
  deadline,
}: {
  value: string | null;
  onChange: (newRule: string | null) => void;
  // Used to derive the default weekday (weekly preset) and monthday
  // (monthly preset). When the task already has a deadline, we anchor
  // recurrence to that day so "weekly" defaults to the deadline's
  // weekday — the least-surprise behaviour.
  deadline?: string | null;
}) {
  const parsed = useMemo(() => parseRule(value), [value]);
  const deadlineWeekday = useMemo(() => {
    if (!deadline) return "MO";
    try {
      const d = new Date(deadline + "T00:00:00");
      return WEEKDAYS[(d.getUTCDay() + 6) % 7].code;
    } catch {
      return "MO";
    }
  }, [deadline]);
  const deadlineMonthday = useMemo(() => {
    if (!deadline) return 1;
    try {
      return new Date(deadline + "T00:00:00").getUTCDate();
    } catch {
      return 1;
    }
  }, [deadline]);

  const [mode, setMode] = useState<Mode>(parsed.mode);
  const [weekly, setWeekly] = useState<string[]>(parsed.byday.length > 0 ? parsed.byday : [deadlineWeekday]);
  const [monthly, setMonthly] = useState<string>(parsed.bymonthday || String(deadlineMonthday));
  const [customFreq, setCustomFreq] = useState<string>(parsed.freq || "WEEKLY");
  const [customInterval, setCustomInterval] = useState<number>(parsed.interval || 1);
  const [customByday, setCustomByday] = useState<string[]>(parsed.byday);
  const [customBymonthday, setCustomBymonthday] = useState<string>(parsed.bymonthday);
  const [until, setUntil] = useState<string>(parsed.until);

  // Re-sync when ``value`` prop changes from outside (e.g. Apply suggested).
  useEffect(() => {
    const p = parseRule(value);
    setMode(p.mode);
    if (p.byday.length > 0) setWeekly(p.byday);
    if (p.bymonthday) setMonthly(p.bymonthday);
    setCustomFreq(p.freq || "WEEKLY");
    setCustomInterval(p.interval || 1);
    setCustomByday(p.byday);
    setCustomBymonthday(p.bymonthday);
    setUntil(p.until);
  }, [value]);

  const composed = useMemo(
    () =>
      composeRule({
        mode,
        weekdayDefault: deadlineWeekday,
        monthdayDefault: deadlineMonthday,
        weekly,
        monthly,
        customFreq,
        customInterval,
        customByday,
        customBymonthday,
        until,
      }),
    [mode, weekly, monthly, customFreq, customInterval, customByday, customBymonthday, until, deadlineWeekday, deadlineMonthday],
  );

  function toggleWeekly(code: string) {
    setWeekly((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }
  function toggleCustomByday(code: string) {
    setCustomByday((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  return (
    <div className="space-y-3 rounded border border-[var(--border)] bg-[var(--surface)] p-3 text-sm">
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {([
          ["none", "Không lặp"],
          ["daily", "Hằng ngày"],
          ["weekly", "Hằng tuần"],
          ["monthly", "Hằng tháng"],
          ["custom", "Tùy chỉnh"],
        ] as [Mode, string][]).map(([m, label]) => (
          <label key={m} className="inline-flex items-center gap-1.5">
            <input
              type="radio"
              name="recurrence-mode"
              checked={mode === m}
              onChange={() => setMode(m)}
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      {mode === "weekly" && (
        <div className="flex flex-wrap gap-1.5">
          {WEEKDAYS.map((d) => (
            <button
              key={d.code}
              type="button"
              onClick={() => toggleWeekly(d.code)}
              className={`rounded border px-2 py-0.5 text-[11px] ${
                weekly.includes(d.code)
                  ? "border-indigo-500 bg-indigo-100 text-indigo-900"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {d.vn}
            </button>
          ))}
        </div>
      )}

      {mode === "monthly" && (
        <div className="flex items-center gap-2">
          <span className="text-[var(--muted)]">Ngày trong tháng:</span>
          <input
            type="number"
            min={1}
            max={31}
            value={monthly}
            onChange={(e) => setMonthly(e.target.value)}
            className="w-16 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
        </div>
      )}

      {mode === "custom" && (
        <div className="space-y-2 rounded bg-[var(--bg)] p-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[var(--muted)]">Tần suất:</span>
            <select
              value={customFreq}
              onChange={(e) => setCustomFreq(e.target.value)}
              className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            >
              <option value="DAILY">Ngày</option>
              <option value="WEEKLY">Tuần</option>
              <option value="MONTHLY">Tháng</option>
              <option value="YEARLY">Năm</option>
            </select>
            <span className="text-[var(--muted)]">mỗi</span>
            <input
              type="number"
              min={1}
              max={365}
              value={customInterval}
              onChange={(e) => setCustomInterval(parseInt(e.target.value || "1", 10))}
              className="w-16 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
            />
          </div>
          {(customFreq === "WEEKLY" || customFreq === "MONTHLY") && (
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((d) => (
                <button
                  key={d.code}
                  type="button"
                  onClick={() => toggleCustomByday(d.code)}
                  className={`rounded border px-2 py-0.5 text-[11px] ${
                    customByday.includes(d.code)
                      ? "border-indigo-500 bg-indigo-100 text-indigo-900"
                      : "border-[var(--border)] text-[var(--muted)]"
                  }`}
                >
                  {d.vn}
                </button>
              ))}
            </div>
          )}
          {customFreq === "MONTHLY" && (
            <div className="flex items-center gap-2">
              <span className="text-[var(--muted)]">Hoặc ngày trong tháng:</span>
              <input
                type="number"
                min={1}
                max={31}
                value={customBymonthday}
                onChange={(e) => setCustomBymonthday(e.target.value)}
                className="w-16 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
                placeholder="—"
              />
            </div>
          )}
        </div>
      )}

      {mode !== "none" && (
        <div className="flex items-center gap-2">
          <span className="text-[var(--muted)]">Kết thúc vào:</span>
          <input
            type="date"
            value={until}
            onChange={(e) => setUntil(e.target.value)}
            className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
          {until && (
            <button
              type="button"
              onClick={() => setUntil("")}
              className="text-[11px] text-[var(--muted)] underline"
            >
              xóa
            </button>
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 border-t border-[var(--border)] pt-2">
        <div className="text-[11px] text-[var(--muted)]">
          {composed ? (
            <>
              Xem trước: <RecurrenceBadge rule={composed} />
            </>
          ) : (
            "Không có lặp lại"
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onChange(composed)}
            className="rounded border border-indigo-500 bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700"
          >
            Lưu
          </button>
        </div>
      </div>
    </div>
  );
}
