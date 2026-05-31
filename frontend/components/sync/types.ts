// Shared shapes + step ordering for the Sync page and its sub-components.
// Extracted from app/(dashboard)/sync/page.tsx (2026-05-31 Stage B refactor).

export const STEPS = [
  { key: "connecting", label: "Connect" },
  { key: "fetching", label: "Fetch" },
  { key: "processing", label: "Process" },
  { key: "extracting", label: "Extract" },
  { key: "saving", label: "Save" },
  { key: "done", label: "Done" },
] as const;

// Widened to plain string[] so callers can pass arbitrary step strings from
// the API (e.g. "throttling" or future values) into indexOf without a TS narrow.
export const STEP_KEYS: string[] = STEPS.map((s) => s.key);

export interface Progress {
  active: boolean;
  step: string;
  detail: string;
  current: number;
  total: number;
}

export interface LastResult {
  step: "done" | "error" | "throttling";
  detail: string;
  current: number;
  total: number;
}
