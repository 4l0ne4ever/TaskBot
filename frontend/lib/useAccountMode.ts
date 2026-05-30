"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AccountMode } from "@/lib/types";

/**
 * Read the current account mode (single vs team) from the backend.
 *
 * One round-trip via the existing ``GET /settings`` endpoint — no new API
 * surface. Refreshes on ``window.focus`` so a mode change made in one tab is
 * picked up by the other dashboard tabs without a hard reload. The
 * ``refresh`` callback is exposed so the Settings page can re-fetch
 * immediately after a PATCH (avoiding the brief stale-mode window).
 *
 * ``loaded=false`` until the first response arrives. AppShell uses that flag
 * to default to *hiding* /team while the answer is unknown — the safer
 * default since /team is only useful with team-mode data. The /team page
 * itself uses ``loaded=false`` to render its loading state rather than
 * redirecting based on a transient ``"single"`` default.
 */
export function useAccountMode() {
  const [mode, setMode] = useState<AccountMode>("single");
  const [loaded, setLoaded] = useState<boolean>(false);

  const refresh = useCallback(async () => {
    try {
      const s = await api.settings.get();
      setMode(s.mode);
      setLoaded(true);
    } catch {
      // Silent — non-critical UI signal. Leaves loaded=false so consumers
      // can still distinguish "asked and got single" from "haven't asked yet".
    }
  }, []);

  useEffect(() => {
    void refresh();
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refresh]);

  return { mode, loaded, refresh };
}
