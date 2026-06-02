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
 * - On the ``taskbot:tasks:changed`` custom event — dispatched by pages that
 *   mutate task status (Confirm / Dismiss / Revert) so the sidebar badge and
 *   banner update immediately without a tab refocus. Use ``emitTasksChanged()``
 *   from the same module to fire it.
 * - Imperatively via the returned ``refresh`` callback when a caller has the
 *   hook instance in scope.
 *
 * Failures are intentionally silent — this is a non-critical UI signal and an
 * error toast for a background count fetch would be noise.
 */
const TASKS_CHANGED_EVENT = "taskbot:tasks:changed";

/** Fire from anywhere that mutates a task's status. */
export function emitTasksChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(TASKS_CHANGED_EVENT));
  }
}

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
    const onChanged = () => void refresh();
    window.addEventListener("focus", onFocus);
    window.addEventListener(TASKS_CHANGED_EVENT, onChanged);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener(TASKS_CHANGED_EVENT, onChanged);
    };
  }, [refresh]);

  return { count, loaded, refresh };
}
