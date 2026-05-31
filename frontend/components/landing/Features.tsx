import { ConflictIcon, MailIcon, ShieldIcon } from "./icons";

const FEATURES: { title: string; body: string; tag: string; icon: React.ReactNode }[] = [
  {
    tag: "Hero",
    title: "Multi-source conflict detection",
    body: "Cross-checks every task against Gmail threads, Drive docs, and uploaded PDFs. When the deadline a client sent contradicts the spec your team wrote, TaskBot surfaces both sources side-by-side — so you decide, not the inbox.",
    icon: <ConflictIcon />,
  },
  {
    tag: "Quality",
    title: "Confidence-banded auto-confirm",
    body: "Three decision bands (abstain / uncertain / accept) keep the noisy 30% off your dashboard and the high-confidence 70% out of your way. Backed by a 250-sample policy sweep — every threshold has CSV evidence, no magic numbers.",
    icon: <ShieldIcon />,
  },
  {
    tag: "Signal",
    title: "Daily Digest & Weekly Brief",
    body: "End-of-day summary of what was auto-confirmed, what still needs you, and what slipped overdue — sent from your own Gmail to yourself. Manager Weekly Brief adds team workload and open conflicts in one inbox-friendly card.",
    icon: <MailIcon />,
  },
];

export function Features() {
  return (
    <section id="features" className="border-t border-[var(--border)]/50 bg-[var(--surface)]/40">
      <div className="max-w-6xl mx-auto px-6 py-20 sm:py-28">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <p className="text-xs uppercase tracking-[0.18em] text-[var(--accent)] font-semibold mb-3">
            What it actually does
          </p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            Built around one persona, not a feature list
          </h2>
          <p className="mt-4 text-[var(--muted)] leading-relaxed">
            Designed for Anna, a frontend tech lead handling 30–50 emails and 5–10 Drive docs a day.
            Every feature traces back to a missed deadline she once had to apologise for.
          </p>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <article
              key={f.title}
              className="group rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 hover:border-[var(--accent)]/40 hover:-translate-y-0.5 transition-all"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="h-10 w-10 rounded-xl bg-[var(--accent-muted)] text-[var(--accent)] flex items-center justify-center">
                  {f.icon}
                </span>
                <span className="text-[10px] uppercase tracking-[0.16em] font-semibold text-[var(--muted)]">
                  {f.tag}
                </span>
              </div>
              <h3 className="text-lg font-semibold tracking-tight">{f.title}</h3>
              <p className="mt-2 text-sm text-[var(--muted)] leading-relaxed">{f.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
