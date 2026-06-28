"use client";

// Phase 6.6 (recurring events, 2026-06-03): render an RFC 5545 RRULE as a
// short human-readable badge. Backend stores the canonical RRULE string
// (FREQ + INTERVAL + BYDAY + BYMONTHDAY + UNTIL + COUNT subset — see
// backend/app/utils/recurrence.py for the whitelist).
//
// The component is intentionally side-effect-free and dependency-free —
// reusable in the task list, task detail, and pending-review surface
// without bringing the picker UI along.

const WEEKDAY: Record<string, string> = {
  MO: "Mon",
  TU: "Tue",
  WE: "Wed",
  TH: "Thu",
  FR: "Fri",
  SA: "Sat",
  SU: "Sun",
};

function parseKv(rrule: string): Record<string, string> {
  const out: Record<string, string> = {};
  const s = rrule.startsWith("RRULE:") ? rrule.slice(6) : rrule;
  for (const chunk of s.split(";")) {
    const [k, v] = chunk.split("=");
    if (k && v) out[k.toUpperCase()] = v.trim();
  }
  return out;
}

function formatByday(value: string): string {
  return value
    .split(",")
    .map((tok) => {
      const t = tok.trim().toUpperCase();
      const m = t.match(/^(-?\d+)?([A-Z]{2})$/);
      if (!m) return t;
      const label = WEEKDAY[m[2]] ?? m[2];
      // Numeric prefix (e.g. 2MO = "second Monday") rarely emitted by our
      // 4 presets — show inline for the custom-builder edge case.
      return m[1] ? `${m[1]}× ${label}` : label;
    })
    .join(", ");
}

export function formatRecurrence(rrule: string | null | undefined): string {
  if (!rrule) return "";
  const kv = parseKv(rrule);
  const freq = kv.FREQ;
  const interval = parseInt(kv.INTERVAL ?? "1", 10);
  let base = "";
  if (freq === "DAILY") {
    base = interval > 1 ? `Every ${interval} days` : "Daily";
  } else if (freq === "WEEKLY") {
    const days = kv.BYDAY ? formatByday(kv.BYDAY) : "";
    base = days
      ? interval > 1
        ? `Every ${interval} weeks — ${days}`
        : `Weekly — ${days}`
      : interval > 1
        ? `Every ${interval} weeks`
        : "Weekly";
  } else if (freq === "MONTHLY") {
    if (kv.BYMONTHDAY) {
      base = interval > 1
        ? `Every ${interval} months — day ${kv.BYMONTHDAY}`
        : `Monthly — day ${kv.BYMONTHDAY}`;
    } else if (kv.BYDAY) {
      base = interval > 1
        ? `Every ${interval} months — ${formatByday(kv.BYDAY)}`
        : `Monthly — ${formatByday(kv.BYDAY)}`;
    } else {
      base = interval > 1 ? `Every ${interval} months` : "Monthly";
    }
  } else if (freq === "YEARLY") {
    base = interval > 1 ? `Every ${interval} years` : "Yearly";
  } else {
    return rrule; // fall back to raw RRULE for unknown FREQ
  }
  // End condition suffix (only one of UNTIL/COUNT per whitelist).
  if (kv.UNTIL) {
    const m = kv.UNTIL.match(/^(\d{4})(\d{2})(\d{2})/);
    if (m) base += ` · until ${m[1]}-${m[2]}-${m[3]}`;
  } else if (kv.COUNT) {
    base += ` · ${kv.COUNT} time${kv.COUNT === "1" ? "" : "s"}`;
  }
  return base;
}

export function RecurrenceBadge({
  rule,
  variant = "active",
  className = "",
}: {
  rule: string | null | undefined;
  variant?: "active" | "suggested";
  className?: string;
}) {
  if (!rule) return null;
  const label = formatRecurrence(rule);
  const styles =
    variant === "suggested"
      ? "border-amber-300 bg-amber-50 text-amber-900"
      : "border-indigo-300 bg-indigo-50 text-indigo-900";
  const prefix = variant === "suggested" ? "💡 Suggested: " : "🔁 ";
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] ${styles} ${className}`}
      title={`RRULE: ${rule}`}
    >
      {prefix}
      {label}
    </span>
  );
}
