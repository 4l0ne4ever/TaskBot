export function Footer() {
  return (
    <footer className="border-t border-[var(--border)]/50">
      <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[var(--muted)]">
        <p>
          © {new Date().getFullYear()} TaskBot · HUST IT-E6 K67 thesis prototype
        </p>
        <p className="flex items-center gap-4">
          <a href="/login" className="hover:text-[var(--foreground)] transition-colors">
            Sign in
          </a>
          <span>·</span>
          <a
            href="https://github.com/4l0ne4ever"
            target="_blank"
            rel="noopener"
            className="hover:text-[var(--foreground)] transition-colors"
          >
            Source
          </a>
        </p>
      </div>
    </footer>
  );
}
