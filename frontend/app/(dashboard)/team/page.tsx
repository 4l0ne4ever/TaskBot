"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { TeamMemberStats, TeamView } from "@/lib/types";
import { useAccountMode } from "@/lib/useAccountMode";
import { cn } from "@/lib/utils";

const card = "rounded-xl border border-[var(--border)] bg-[var(--surface)]";

// Risk cells get colour only when non-zero, so the eye lands on real load.
function RiskCell({ value, tone }: { value: number; tone: "danger" | "warning" | "accent" }) {
  if (value === 0) return <span className="text-[var(--muted)]">0</span>;
  const cls =
    tone === "danger"
      ? "text-[var(--danger)]"
      : tone === "warning"
        ? "text-[var(--warning)]"
        : "text-[var(--accent)]";
  return <span className={cn("font-semibold", cls)}>{value}</span>;
}

function Row({ m, label }: { m: TeamMemberStats; label?: string }) {
  const name = label ?? m.assignee ?? "—";
  return (
    <tr className="border-t border-[var(--border)] hover:bg-[var(--card-hover)]">
      <td className="px-4 py-2.5 font-medium text-[var(--foreground)]">{name}</td>
      <td className="px-3 py-2.5 text-center">{m.open}</td>
      <td className="px-3 py-2.5 text-center text-[var(--muted)]">{m.pending}</td>
      <td className="px-3 py-2.5 text-center text-[var(--muted)]">{m.confirmed}</td>
      <td className="px-3 py-2.5 text-center"><RiskCell value={m.overdue} tone="danger" /></td>
      <td className="px-3 py-2.5 text-center"><RiskCell value={m.due_this_week} tone="warning" /></td>
      <td className="px-3 py-2.5 text-center"><RiskCell value={m.in_conflict} tone="danger" /></td>
      <td className="px-3 py-2.5 text-center"><RiskCell value={m.needs_review} tone="accent" /></td>
    </tr>
  );
}

export default function TeamPage() {
  const [data, setData] = useState<TeamView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  // Round 11 (2026-05-30): /team is gated to team-mode accounts. A
  // single-mode user who types the URL directly (or has a stale bookmark)
  // gets soft-redirected to /tasks. We wait for ``loaded`` so a transient
  // pre-fetch "single" doesn't bounce a team-mode user to /tasks on every
  // navigation; once the real answer arrives the redirect (if any) fires.
  const router = useRouter();
  const { mode, loaded: modeLoaded } = useAccountMode();
  useEffect(() => {
    if (modeLoaded && mode === "single") {
      router.replace("/tasks");
    }
  }, [modeLoaded, mode, router]);

  useEffect(() => {
    // Don't fetch the team rollup until we know we're allowed to be here —
    // a single-mode user about to redirect shouldn't trigger a wasted API
    // call (and the backend will eventually 403 single-mode users from
    // /tasks/team in a follow-up, but UI-side guard is the first fence).
    if (!modeLoaded || mode !== "team") return;
    api.tasks
      .team()
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load team view"));
  }, [modeLoaded, mode]);

  async function sendBrief() {
    setSending(true);
    try {
      const res = await api.digest.send();
      if (res.status === "queued") {
        toast.success("Weekly brief is sending to your inbox.");
      } else {
        toast.error(res.message || "Could not send the brief.");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to send brief");
    } finally {
      setSending(false);
    }
  }

  const hasUnassigned = data && data.unassigned.open > 0;
  const totals = data
    ? data.members.reduce(
        (acc, m) => ({
          open: acc.open + m.open,
          overdue: acc.overdue + m.overdue,
          in_conflict: acc.in_conflict + m.in_conflict,
          needs_review: acc.needs_review + m.needs_review,
        }),
        { open: 0, overdue: 0, in_conflict: 0, needs_review: 0 },
      )
    : null;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className={cn(card, "p-6 space-y-1")}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--foreground)]">Team Workload</h2>
            <p className="text-xs text-[var(--muted)]">
              Open tasks and risk flags grouped by assignee. Busiest first.
            </p>
          </div>
          <button
            onClick={sendBrief}
            disabled={sending}
            className="shrink-0 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-1.5 text-xs font-medium transition-colors"
            title="Email yourself this week's brief (tasks, conflicts, workload)"
          >
            {sending ? "Sending…" : "Send weekly brief"}
          </button>
        </div>
        {totals && (
          <div className="flex flex-wrap gap-4 pt-3 text-sm">
            <span className="text-[var(--muted)]">
              {data!.members.length} members · <span className="text-[var(--foreground)] font-medium">{totals.open}</span> open
            </span>
            <span className="text-[var(--danger)]">{totals.overdue} overdue</span>
            <span className="text-[var(--danger)]">{totals.in_conflict} in conflict</span>
            <span className="text-[var(--accent)]">{totals.needs_review} need review</span>
          </div>
        )}
      </div>

      {err && <div className={cn(card, "p-6 text-sm text-[var(--danger)]")}>{err}</div>}
      {!data && !err && <div className={cn(card, "p-6 text-sm text-[var(--muted)]")}>Loading…</div>}

      {data && data.members.length === 0 && !hasUnassigned && (
        <div className={cn(card, "p-12 text-center text-sm text-[var(--muted)]")}>
          No assigned tasks yet.
        </div>
      )}

      {data && (data.members.length > 0 || hasUnassigned) && (
        <div className={cn(card, "overflow-hidden")}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-[var(--muted)]">
                <th className="px-4 py-2.5 text-left font-medium">Member</th>
                <th className="px-3 py-2.5 text-center font-medium">Open</th>
                <th className="px-3 py-2.5 text-center font-medium">Pending</th>
                <th className="px-3 py-2.5 text-center font-medium">Confirmed</th>
                <th className="px-3 py-2.5 text-center font-medium">Overdue</th>
                <th className="px-3 py-2.5 text-center font-medium">Due&nbsp;7d</th>
                <th className="px-3 py-2.5 text-center font-medium">Conflict</th>
                <th className="px-3 py-2.5 text-center font-medium">Review</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map((m) => (
                <Row key={m.assignee ?? "?"} m={m} />
              ))}
              {hasUnassigned && <Row m={data.unassigned} label="Unassigned" />}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
