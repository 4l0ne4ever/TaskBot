"use client";

// Landing page (Round 14, 2026-05-31; split into sections 2026-05-31 Stage B).
//
// Previously this route was a one-line `redirect("/tasks")` — unauthenticated
// visitors bounced to /login with zero context. Now `/` renders a marketing
// page: hero with persona-led pitch, three feature blocks built around the
// hero scenario (multi-source conflict), how-it-works, and a CTA that flips
// based on auth state. AuthProvider has `/` in PUBLIC_PREFIXES so it's not
// intercepted before render.

import { useAuth } from "@/components/providers/AuthProvider";
import { Nav } from "@/components/landing/Nav";
import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { FinalCta } from "@/components/landing/FinalCta";
import { Footer } from "@/components/landing/Footer";

export default function LandingPage() {
  const { user, loading } = useAuth();

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <Nav user={user} loading={loading} />
      <Hero user={user} loading={loading} />
      <Features />
      <HowItWorks />
      <FinalCta user={user} loading={loading} />
      <Footer />
    </div>
  );
}
