"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { clearAuthToken, getAuthToken, setAuthToken } from "@/lib/auth";

type User = { id: string; email: string } | null;

type AuthContextValue = {
  user: User;
  loading: boolean;
  refresh: () => Promise<void>;
  signInWithToken: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// `/` (landing page) is public — unauthenticated visitors should be able to
// see it without being bounced to /login. Anything not in this list still
// requires an auth token.
const PUBLIC_PREFIXES = ["/", "/login", "/auth/callback"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.auth.me();
      setUser(me);
    } catch {
      clearAuthToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (loading) return;
    const isPublic = PUBLIC_PREFIXES.some((p) => pathname === p || pathname?.startsWith(p + "/"));
    if (!user && !isPublic) {
      router.replace("/login");
    }
  }, [loading, user, pathname, router]);

  const signInWithToken = useCallback(
    async (token: string) => {
      setAuthToken(token);
      await refresh();
      router.replace("/tasks");
    },
    [refresh, router]
  );

  const signOut = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      /* still clear local */
    }
    clearAuthToken();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, refresh, signInWithToken, signOut }),
    [user, loading, refresh, signInWithToken, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
