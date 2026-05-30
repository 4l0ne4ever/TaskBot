"use client";

// Landing page (Round 14, 2026-05-31).
//
// Previously this route was a one-line `redirect("/tasks")`, which meant
// an unauthenticated visitor immediately bounced to /login with zero
// context about what the product does. Now `/` renders a real marketing
// page: hero with persona-led pitch, three feature blocks built around
// the hero scenario (multi-source conflict), a how-it-works section, and
// a CTA that flips based on auth state ("Continue with Google" vs
// "Open dashboard").
//
// AuthProvider was updated so `/` is in PUBLIC_PREFIXES — without that
// the page would still be intercepted before render.

import Link from "next/link";
import { API_BASE_URL } from "@/lib/config";
import { useAuth } from "@/components/providers/AuthProvider";

export default function LandingPage() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <Nav user={user} loading={loading} />
      <Hero user={user} loading={loading} />
      <Features />
      <HowItWorks />
      <FinalCta user={user} loading={loading} />
      <Footer />
    </div>
  );
}

// ── Top nav ───────────────────────────────────────────────────────────────

function Nav({ user, loading }: { user: { email: string } | null; loading: boolean }) {
  return (
    <header className="sticky top-0 z-20 backdrop-blur bg-[var(--background)]/80 border-b border-[var(--border)]/50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="h-8 w-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-white font-bold text-sm shadow-md shadow-[var(--accent)]/20">
            T
          </span>
          <span className="font-semibold tracking-tight">TaskBot</span>
        </Link>
        <nav className="hidden sm:flex items-center gap-6 text-sm text-[var(--muted)]">
          <a href="#features" className="hover:text-[var(--foreground)] transition-colors">
            Features
          </a>
          <a href="#how" className="hover:text-[var(--foreground)] transition-colors">
            How it works
          </a>
          <a
            href="https://github.com/4l0ne4ever"
            target="_blank"
            rel="noopener"
            className="hover:text-[var(--foreground)] transition-colors"
          >
            Thesis
          </a>
        </nav>
        <div className="flex items-center gap-2">
          {loading ? (
            <span className="text-[var(--muted)] text-sm">&hellip;</span>
          ) : user ? (
            <Link
              href="/tasks"
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-3.5 py-1.5 text-sm font-medium transition-colors"
            >
              Open dashboard
            </Link>
          ) : (
            <a
              href={`${API_BASE_URL}/auth/google`}
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-3.5 py-1.5 text-sm font-medium transition-colors"
            >
              Sign in
            </a>
          )}
        </div>
      </div>
    </header>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────

function Hero({ user, loading }: { user: { email: string } | null; loading: boolean }) {
  return (
    <section className="relative overflow-hidden">
      {/* Background accent — pure CSS, no image asset needed */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 opacity-30"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, var(--accent-muted) 0%, transparent 70%)",
        }}
      />
      <div className="max-w-6xl mx-auto px-6 pt-20 pb-24 sm:pt-28 sm:pb-32 text-center">
        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border border-[var(--border)] bg-[var(--surface)]/60 text-[var(--muted)] mb-6">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
          Enterprise task intelligence · HUST IT-E6 thesis
        </span>
        <h1 className="text-4xl sm:text-6xl font-semibold tracking-tight leading-[1.05]">
          One inbox.{" "}
          <span className="text-[var(--accent)]">Many sources.</span>
          <br />
          Zero missed deadlines.
        </h1>
        <p className="mt-6 max-w-2xl mx-auto text-base sm:text-lg text-[var(--muted)] leading-relaxed">
          TaskBot reads your Gmail and Drive, extracts the tasks hidden inside
          long threads and shared docs, and{" "}
          <span className="text-[var(--foreground)] font-medium">
            flags the moments a client&apos;s email contradicts an internal
            spec
          </span>{" "}
          — before you miss the deadline.
        </p>

        <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
          {loading ? (
            <div className="h-11 w-48 rounded-xl bg-[var(--surface-2)] animate-pulse" />
          ) : user ? (
            <Link
              href="/tasks"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-6 py-3 text-sm font-medium shadow-lg shadow-[var(--accent)]/20 transition-all hover:-translate-y-0.5"
            >
              Open your dashboard
              <ArrowRight />
            </Link>
          ) : (
            <a
              href={`${API_BASE_URL}/auth/google`}
              className="inline-flex items-center gap-3 rounded-xl bg-white text-gray-800 px-6 py-3 text-sm font-medium shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5 border border-gray-200"
            >
              <GoogleMark />
              Continue with Google
            </a>
          )}
          <a
            href="#features"
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)]/60 hover:bg-[var(--surface-2)] px-6 py-3 text-sm font-medium transition-colors text-[var(--foreground)]"
          >
            See how it works
          </a>
        </div>

        <p className="mt-5 text-xs text-[var(--muted)]">
          Read-only Gmail · Drive scopes by default. Send-scope is opt-in for daily/weekly briefs.
        </p>

        {/* Inline product preview — a tiny rendered "task with conflict" card */}
        <PreviewCard />
      </div>
    </section>
  );
}

function PreviewCard() {
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

// ── Features ──────────────────────────────────────────────────────────────

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

function Features() {
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

// ── How it works ──────────────────────────────────────────────────────────

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

function HowItWorks() {
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

// ── Final CTA ─────────────────────────────────────────────────────────────

function FinalCta({ user, loading }: { user: { email: string } | null; loading: boolean }) {
  return (
    <section className="border-t border-[var(--border)]/50 bg-gradient-to-b from-[var(--background)] to-[var(--surface)]/50">
      <div className="max-w-3xl mx-auto px-6 py-20 sm:py-28 text-center">
        <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
          Stop reading every thread.{" "}
          <span className="text-[var(--accent)]">Start finishing every task.</span>
        </h2>
        <p className="mt-4 text-[var(--muted)] leading-relaxed">
          Free for now — built as a thesis prototype, used like a real tool.
        </p>
        <div className="mt-8 flex items-center justify-center">
          {loading ? (
            <div className="h-11 w-56 rounded-xl bg-[var(--surface-2)] animate-pulse" />
          ) : user ? (
            <Link
              href="/tasks"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-6 py-3 text-sm font-medium shadow-lg shadow-[var(--accent)]/20 transition-all hover:-translate-y-0.5"
            >
              Open your dashboard
              <ArrowRight />
            </Link>
          ) : (
            <a
              href={`${API_BASE_URL}/auth/google`}
              className="inline-flex items-center gap-3 rounded-xl bg-white text-gray-800 px-6 py-3 text-sm font-medium shadow-lg hover:shadow-xl transition-all hover:-translate-y-0.5 border border-gray-200"
            >
              <GoogleMark />
              Continue with Google
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="border-t border-[var(--border)]/50">
      <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[var(--muted)]">
        <p>
          © {new Date().getFullYear()} TaskBot · HUST IT-E6 K67 thesis prototype
        </p>
        <p className="flex items-center gap-4">
          <a href="/login" className="hover:text-[var(--foreground)] transition-colors">
            Sign in
          </a>
          <span>·</span>
          <a
            href="https://github.com/4l0ne4ever"
            target="_blank"
            rel="noopener"
            className="hover:text-[var(--foreground)] transition-colors"
          >
            Source
          </a>
        </p>
      </div>
    </footer>
  );
}

// ── Tiny inline SVG icons (no external dep) ───────────────────────────────

function ArrowRight() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  );
}

function GoogleMark() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  );
}

function ConflictIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="m7.5 4.27 9 5.15" />
      <path d="M21 8 12 3 3 8l9 5 9-5z" />
      <path d="m3 16 9 5 9-5" />
      <path d="m3 12 9 5 9-5" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}
