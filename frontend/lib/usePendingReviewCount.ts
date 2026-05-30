"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Tracks how many tasks need the user's review.
 *
 * "Pending review" is defined narrowly as ``status === "pending"`` for this
 * counter — the backend already indexes that filter and returns the total via
 * the ``X-Total-Count`` header on ``GET /tasks?status=pending&limit=1``, so the
 * count is one cheap round-trip with no new endpoint.
 *
 * Refresh policy:
 * - Once on mount.
 * - On ``window.focus`` (covers the common "user comes back to the tab" case).
 * - Imperatively via the returned ``refresh`` callback, intended for callers
 *   that mutate a task's status (Confirm / Dismiss / Revert) so the badge and
 *   banner update without waiting for the next focus event.
 *
 * Failures are intentionally silent — this is a non-critical UI signal and an
 * error toast for a background count fetch would be noise.
 */
export function usePendingReviewCount() {
  const [count, setCount] = useState<number>(0);
  const [loaded, setLoaded] = useState<boolean>(false);

  const refresh = useCallback(async () => {
    try {
      const { total } = await api.tasks.list({ status: "pending", limit: 1, offset: 0 });
      setCount(total ?? 0);
      setLoaded(true);
    } catch {
      // Silent — see docstring.
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  return { count, loaded, refresh };
}
