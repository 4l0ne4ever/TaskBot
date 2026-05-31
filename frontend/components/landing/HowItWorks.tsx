const STEPS = [
  {
    n: "01",
    title: "Connect Gmail & Drive",
    body: "One Google sign-in, read-only by default. Sent-folder sync is opt-in for team leads who delegate from their inbox.",
  },
  {
    n: "02",
    title: "Pipeline runs in the background",
    body: "Six-node LangGraph pipeline — parse → extract → normalize → validate → save → notify. Dedup is content-hash based, so the same task across two emails becomes one row, not two.",
  },
  {
    n: "03",
    title: "You see only what needs you",
    body: "Auto-confirmed tasks land directly on your calendar. Uncertain ones queue for review with a one-click confirm. Conflicts open with both sources cited.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="border-t border-[var(--border)]/50">
      <div className="max-w-6xl mx-auto px-6 py-20 sm:py-28">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="text-xs uppercase tracking-[0.18em] text-[var(--accent)] font-semibold mb-3">
            How it works
          </p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            Three steps. No new app to babysit.
          </h2>
        </div>
        <ol className="grid gap-5 sm:grid-cols-3">
          {STEPS.map((s) => (
            <li
              key={s.n}
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6"
            >
              <div className="text-[var(--accent)] font-mono text-sm font-semibold tracking-wider">
                {s.n}
              </div>
              <h3 className="mt-2 text-lg font-semibold tracking-tight">{s.title}</h3>
              <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
