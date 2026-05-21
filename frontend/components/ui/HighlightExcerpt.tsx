/**
 * Render `text` with the first occurrence of `quote` wrapped in <mark>.
 *
 * The pipeline validates that evidence_quote appears verbatim in the source
 * text (validate_tasks rejects tasks whose quote isn't found), so an exact,
 * case-insensitive substring match is the right primitive. When the quote is
 * null, empty, or falls outside the truncated/cleaned excerpt (e.g. beyond the
 * 600-char window, or altered by HTML stripping), we render the plain text —
 * graceful degradation, never a crash or a wrong highlight.
 */
export function HighlightExcerpt({ text, quote }: { text: string; quote: string | null }) {
  const q = quote?.trim();
  if (!q) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-300/40 dark:bg-yellow-500/30 text-[var(--foreground)] rounded px-0.5">
        {text.slice(idx, idx + q.length)}
      </mark>
      {text.slice(idx + q.length)}
    </>
  );
}
