"use client";

import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { SettingsPayload } from "@/lib/types";

export default function SettingsPage() {
  const [s, setS] = useState<SettingsPayload | null>(null);
  const [gmail, setGmail] = useState(15);
  const [drive, setDrive] = useState(30);
  const [profile, setProfile] = useState<"strict_work" | "balanced" | "broad">("balanced");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.settings.get();
      setS(data);
      setGmail(data.gmail_interval);
      setDrive(data.drive_interval);
      setProfile(data.sync_profile);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function saveIntervals() {
    try {
      const data = await api.settings.patch({ gmail_interval: gmail, drive_interval: drive, sync_profile: profile });
      setS(data);
      toast.success("Saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function disconnect() {
    if (!confirm("Disconnect Google? Sync will stop until you sign in again.")) return;
    try {
      await api.settings.disconnect();
      toast.success("Disconnected");
      void load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  if (loading && !s) {
    return <div className="flex items-center justify-center py-20 text-[var(--muted)]">Loading&hellip;</div>;
  }

  return (
    <div className="max-w-md space-y-8">
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 space-y-5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Sync intervals (minutes)</h2>
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-sm text-[var(--foreground)]">Gmail</span>
            <input
              type="number"
              min={5}
              max={1440}
              value={gmail}
              onChange={(e) => setGmail(Number(e.target.value))}
              className="mt-1 w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-[var(--foreground)]">Drive</span>
            <input
              type="number"
              min={5}
              max={1440}
              value={drive}
              onChange={(e) => setDrive(Number(e.target.value))}
              className="mt-1 w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </label>
          <button
            type="button"
            onClick={() => void saveIntervals()}
            className="rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-2 text-sm font-medium transition-colors"
          >
            Save intervals
          </button>
        </div>
        <div className="space-y-2 pt-2 border-t border-[var(--border)]">
          <span className="text-sm text-[var(--foreground)]">Sync profile</span>
          <select
            value={profile}
            onChange={(e) => setProfile(e.target.value as "strict_work" | "balanced" | "broad")}
            className="w-full bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          >
            <option value="strict_work">Strict work (high precision, fewer items)</option>
            <option value="balanced">Balanced (recommended)</option>
            <option value="broad">Broad (higher recall, more noise)</option>
          </select>
        </div>
      </section>

      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">Google account</h2>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${s?.google_connected ? "bg-emerald-400" : "bg-amber-400"}`}
            />
            <span className="text-sm">{s?.google_connected ? "Connected" : "Not connected"}</span>
          </div>
          <button
            type="button"
            onClick={() => void disconnect()}
            disabled={!s?.google_connected}
            className="text-sm text-[var(--danger)] hover:opacity-80 disabled:opacity-30 transition-colors"
          >
            Disconnect
          </button>
        </div>
      </section>
    </div>
  );
}
