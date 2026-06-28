// Minimal RFC 5545 RRULE expander. Mirrors the backend whitelist in
// ``backend/app/utils/recurrence.py``:
//   FREQ ∈ {DAILY, WEEKLY, MONTHLY, YEARLY}
//   INTERVAL    (default 1)
//   BYDAY       (MO TU WE TH FR SA SU; numeric prefix tolerated, e.g. 2MO)
//   BYMONTHDAY  (1-31; comma list)
//   UNTIL       (YYYYMMDDTHHMMSSZ; we read date only)
//   COUNT       (positive integer)
//
// Used by /calendar to render one chip per occurrence in the visible month —
// without this, a weekly recurring task would render only on its anchor
// deadline, defeating the point of the recurrence rule.
//
// Returns ISO date strings (YYYY-MM-DD) sorted ascending. Caller passes the
// inclusive [start, end] window so we can stop expanding as soon as we leave
// the window — important because COUNT-less rules without UNTIL would expand
// forever.

const WEEKDAY_INDEX: Record<string, number> = {
  MO: 1, TU: 2, WE: 3, TH: 4, FR: 5, SA: 6, SU: 0,
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

function parseUntilDate(until: string | undefined): Date | null {
  if (!until) return null;
  const m = until.match(/^(\d{4})(\d{2})(\d{2})/);
  if (!m) return null;
  return new Date(`${m[1]}-${m[2]}-${m[3]}T23:59:59`);
}

function isoDate(d: Date): string {
  // Local-time YYYY-MM-DD — matches the rest of /calendar (which serialises
  // task.deadline as a naive local date). Using UTC here would skew the
  // grid by a day for users east of UTC late at night.
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function bydayCodes(value: string | undefined): number[] {
  if (!value) return [];
  return value
    .split(",")
    .map((tok) => {
      // Strip numeric prefix (2MO → MO). Numeric prefix only meaningful for
      // MONTHLY/YEARLY positional patterns; for the grid expansion we treat
      // it as "this weekday", same as raw MO.
      const t = tok.trim().toUpperCase();
      const m = t.match(/^(-?\d+)?([A-Z]{2})$/);
      return m ? WEEKDAY_INDEX[m[2]] : NaN;
    })
    .filter((n) => !Number.isNaN(n));
}

function addDays(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
}

function addMonths(d: Date, n: number): Date {
  const out = new Date(d);
  out.setMonth(out.getMonth() + n);
  return out;
}

function addYears(d: Date, n: number): Date {
  const out = new Date(d);
  out.setFullYear(out.getFullYear() + n);
  return out;
}

const MAX_OCCURRENCES = 366; // hard cap so a malformed rule can't hang the UI

export function expandRecurrence(
  rrule: string | null | undefined,
  anchorIso: string,
  rangeStartIso: string,
  rangeEndIso: string,
): string[] {
  if (!rrule || !anchorIso) return anchorIso ? [anchorIso] : [];
  const kv = parseKv(rrule);
  const freq = (kv.FREQ ?? "").toUpperCase();
  const interval = Math.max(1, parseInt(kv.INTERVAL ?? "1", 10) || 1);
  const until = parseUntilDate(kv.UNTIL);
  const count = kv.COUNT ? parseInt(kv.COUNT, 10) : 0;
  const byday = bydayCodes(kv.BYDAY);
  const bymonthday = kv.BYMONTHDAY
    ? kv.BYMONTHDAY.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => n >= 1 && n <= 31)
    : [];

  const anchor = new Date(`${anchorIso}T00:00:00`);
  const rangeStart = new Date(`${rangeStartIso}T00:00:00`);
  const rangeEnd = new Date(`${rangeEndIso}T23:59:59`);
  const out: string[] = [];
  let emitted = 0;

  const tryEmit = (d: Date): boolean => {
    // Returns false when we've passed the rule's hard stop (UNTIL/COUNT) and
    // expansion should halt entirely.
    if (until && d > until) return false;
    if (count && emitted >= count) return false;
    if (d >= rangeStart && d <= rangeEnd) {
      out.push(isoDate(d));
    }
    emitted++;
    return true;
  };

  if (freq === "DAILY") {
    let cur = new Date(anchor);
    for (let i = 0; i < MAX_OCCURRENCES; i++) {
      if (!tryEmit(cur)) break;
      if (cur > rangeEnd) break;
      cur = addDays(cur, interval);
    }
  } else if (freq === "WEEKLY") {
    // When BYDAY is set, every interval-th week emits one occurrence per
    // listed weekday. Without BYDAY, the anchor's weekday is the implicit
    // single day-of-week.
    const days = byday.length > 0 ? byday.slice().sort((a, b) => a - b) : [anchor.getDay()];
    let weekStart = new Date(anchor);
    // Snap to Sunday of the anchor's week — RFC 5545 default WKST=MO, but we
    // only use this to walk weeks, not to compute week-numbers, so the
    // anchor offset is what matters.
    weekStart.setDate(weekStart.getDate() - weekStart.getDay());
    for (let i = 0; i < MAX_OCCURRENCES; i++) {
      let halt = false;
      for (const dow of days) {
        const occ = addDays(weekStart, dow);
        // Skip occurrences that fall before the anchor (only possible in the
        // first iteration when anchor's weekday > smallest BYDAY weekday).
        if (occ < anchor) continue;
        if (!tryEmit(occ)) { halt = true; break; }
      }
      if (halt) break;
      if (weekStart > rangeEnd) break;
      weekStart = addDays(weekStart, 7 * interval);
    }
  } else if (freq === "MONTHLY") {
    // BYMONTHDAY > BYDAY > anchor's day-of-month, in priority order. Our
    // 4 presets only emit BYMONTHDAY for MONTHLY, but BYDAY support is cheap
    // and covers the custom-builder case ("first Monday of the month" via
    // numeric-prefix BYDAY — we already strip the prefix, so it degrades
    // to "every Monday of every month", which is a reasonable graceful
    // fallback for an out-of-whitelist input).
    let cur = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    for (let i = 0; i < MAX_OCCURRENCES; i++) {
      let halt = false;
      const year = cur.getFullYear();
      const month = cur.getMonth();
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const days = bymonthday.length > 0
        ? bymonthday.filter((d) => d <= daysInMonth)
        : byday.length > 0
          ? Array.from({ length: daysInMonth }, (_, k) => k + 1)
              .filter((d) => byday.includes(new Date(year, month, d).getDay()))
          : [anchor.getDate()];
      for (const d of days.sort((a, b) => a - b)) {
        const occ = new Date(year, month, d);
        if (occ < anchor) continue;
        if (!tryEmit(occ)) { halt = true; break; }
      }
      if (halt) break;
      if (cur > rangeEnd) break;
      cur = addMonths(cur, interval);
    }
  } else if (freq === "YEARLY") {
    let cur = new Date(anchor);
    for (let i = 0; i < MAX_OCCURRENCES; i++) {
      if (!tryEmit(cur)) break;
      if (cur > rangeEnd) break;
      cur = addYears(cur, interval);
    }
  } else {
    // Unknown FREQ — degrade gracefully to the anchor alone so the chip
    // still appears, instead of erasing the event from the grid.
    if (anchor >= rangeStart && anchor <= rangeEnd) out.push(anchorIso);
  }

  return out;
}
