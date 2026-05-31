"use client";

import Link from "next/link";
import { API_BASE_URL } from "@/lib/config";

export function Nav({ user, loading }: { user: { email: string } | null; loading: boolean }) {
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
