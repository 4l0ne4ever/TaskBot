"use client";

import Link from "next/link";

/**
 * In-app banner surfacing tasks that need user review.
 *
 * Rendered by ``AppShell`` only when the pending count is > 0 and the user is
 * NOT already on the ``/tasks`` route — there is no value in nagging the user
 * on the page they would land on. The banner is non-dismissable on purpose:
 * the action the user can take ("review the tasks") will clear the signal
 * automatically once they confirm/dismiss the pending items, so the banner
 * disappears on its own. A dismiss button would just train the user to ignore
 * the signal — exactly the opposite of what HITL is for.
 */
export function PendingReviewBanner({ count }: { count: number }) {
  if (count <= 0) return null;
  const label = count === 1 ? "1 task needs your review" : `${count} tasks need your review`;
  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-5 flex items-center justify-between gap-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm"
    >
      <div className="flex items-center gap-3 text-amber-900 dark:text-amber-100">
        <svg
          aria-hidden
          className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.7}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m0 3.087h.008v.008H12v-.008zm9 1.213a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div>
          <p className="font-medium">{label}</p>
          <p className="text-xs text-amber-800/80 dark:text-amber-200/80">
            Tasks with missing fields or low extraction confidence are kept pending until you confirm them.
          </p>
        </div>
      </div>
      <Link
        href="/tasks?status=pending"
        className="shrink-0 rounded-md border border-amber-500/40 bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-900 transition-colors hover:bg-amber-500/25 dark:text-amber-100"
      >
        Review now →
      </Link>
    </div>
  );
}
