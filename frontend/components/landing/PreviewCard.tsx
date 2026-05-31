// Inline product preview rendered under the hero — a hand-built "task card
// with conflict" mock that mirrors the real /tasks UI vocabulary (badges,
// priority score, evidence chips) so visitors see the actual deliverable.

export function PreviewCard() {
  return (
    <div className="mt-14 mx-auto max-w-3xl">
      <div className="relative rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl shadow-black/30 overflow-hidden text-left">
        <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--danger)]/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--warning)]/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-[var(--success)]/70" />
          <span className="ml-3 text-xs text-[var(--muted)]">taskbot · /tasks</span>
        </div>
        <div className="p-5 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium">Submit final wireframes for Atlas dashboard</span>
                <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-[var(--accent-muted)] text-[var(--accent)]">
                  multi-source
                </span>
                <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-amber-500/15 text-amber-400">
                  needs review
                </span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Assigned: You · Deadline conflict between Gmail thread and shared Drive doc
              </p>
            </div>
            <span className="text-xs text-[var(--muted)] tabular-nums shrink-0">
              priority 0.91
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-[var(--muted)] mb-1">Gmail · client@atlas.com</p>
              <p className="font-mono text-[var(--foreground)]">deadline: <b>Jun 6, 17:00</b></p>
            </div>
            <div className="rounded-lg border border-[var(--border)] p-3">
              <p className="text-[var(--muted)] mb-1">Drive · &quot;Atlas v2 spec.docx&quot;</p>
              <p className="font-mono text-[var(--foreground)]">deadline: <b className="text-[var(--danger)]">Jun 9, 17:00</b></p>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button className="text-xs rounded-md bg-[var(--accent)] text-white px-3 py-1.5 font-medium">
              Resolve conflict
            </button>
            <button className="text-xs rounded-md border border-[var(--border)] px-3 py-1.5 font-medium text-[var(--foreground)]">
              Open thread
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
