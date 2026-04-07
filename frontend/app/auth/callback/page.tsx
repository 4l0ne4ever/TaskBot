"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/providers/AuthProvider";

export default function AuthCallbackPage() {
  const router = useRouter();
  const { signInWithToken } = useAuth();
  const [msg, setMsg] = useState("Completing sign-in…");

  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");
    if (!token) {
      setMsg("Missing token");
      router.replace("/login?error=oauth");
      return;
    }
    void signInWithToken(token).catch(() => {
      setMsg("Failed");
      router.replace("/login?error=oauth");
    });
  }, [router, signInWithToken]);

  return (
    <div className="min-h-screen flex items-center justify-center text-[var(--muted)]">
      {msg}
    </div>
  );
}
