"use client";

import Link from "next/link";
import { API_BASE_URL } from "@/lib/config";
import { ArrowRight, GoogleMark } from "./icons";
import { PreviewCard } from "./PreviewCard";

export function Hero({ user, loading }: { user: { email: string } | null; loading: boolean }) {
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

        <PreviewCard />
      </div>
    </section>
  );
}
