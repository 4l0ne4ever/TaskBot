"use client";

import Link from "next/link";
import { API_BASE_URL } from "@/lib/config";
import { ArrowRight, GoogleMark } from "./icons";

export function FinalCta({ user, loading }: { user: { email: string } | null; loading: boolean }) {
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
