"use client";

// Filter chip for scope tabs at the top of the conflicts page. "All" uses the
// accent outline style; the four scope variants use distinct tinted fills so
// the filter row mirrors the scope-badge vocabulary used on each card.

import type { ConflictScope } from "@/lib/types";

const CHIP_FILLED: Record<ConflictScope, string> = {
  multi_source: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/30",
  thread_update: "bg-orange-500/15 text-orange-600 dark:text-orange-300 border-orange-500/30",
  inter_doc: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-300 border-yellow-500/30",
  intra_batch: "bg-gray-500/15 text-gray-600 dark:text-gray-300 border-gray-500/30",
};

export function ScopeChip({
  children,
  active,
  onClick,
  variant,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  variant: ConflictScope | "all";
}) {
  const activeClasses =
    variant === "all"
      ? "border-[var(--accent)] text-[var(--accent)] bg-transparent"
      : CHIP_FILLED[variant];
  const inactiveClasses =
    "border-[var(--border)] text-[var(--muted)] bg-transparent hover:text-[var(--foreground)]";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active ? activeClasses : inactiveClasses
      }`}
    >
      {children}
    </button>
  );
}
