"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { API_BASE_URL } from "@/lib/config";
import { useAuth } from "@/components/providers/AuthProvider";

function LoginInner() {
  const { user, loading } = useAuth();
  const search = useSearchParams();
  const err = search.get("error");

  useEffect(() => {
    if (!loading && user) {
      window.location.replace("/tasks");
    }
  }, [loading, user]);

  if (loading || user) {
    return <div className="min-h-screen flex items-center justify-center text-[var(--muted)]">&hellip;</div>;
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-8 px-4 bg-gradient-to-b from-[var(--background)] to-[var(--surface)]">
      <div className="text-center space-y-4">
        <div className="h-14 w-14 mx-auto rounded-2xl bg-[var(--accent)] flex items-center justify-center text-white font-bold text-2xl shadow-lg shadow-[var(--accent)]/20">
          T
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">TaskBot</h1>
        <p className="text-[var(--muted)] text-sm max-w-sm leading-relaxed">
          Sign in with your Google account to extract and manage tasks from Gmail, Drive, and uploaded files.
        </p>
      </div>

      {err === "oauth" && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2 text-sm text-red-600 dark:text-red-300">
          Could not complete sign-in. Please try again.
        </div>
      )}

      <a
        href={`${API_BASE_URL}/auth/google`}
        className="inline-flex items-center gap-3 rounded-xl bg-white text-gray-800 px-6 py-3 text-sm font-medium shadow-md hover:shadow-lg transition-all hover:-translate-y-0.5 border border-gray-200"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
        </svg>
        Continue with Google
      </a>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">&hellip;</div>}>
      <LoginInner />
    </Suspense>
  );
}
