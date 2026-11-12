import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

import { useAuth } from "@/lib/auth";
import { authFetch } from "@/lib/auth-api";

const EXEMPT = ["/recommend", "/login", "/signup"];

export function OnboardingGate() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const checkedFor = useRef<string | null>(null);

  useEffect(() => {
    if (loading || !user) return;
    if (EXEMPT.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return;
    if (checkedFor.current === user.id) return;
    checkedFor.current = user.id;

    let cancelled = false;
    void (async () => {
      try {
        const res = await authFetch("/api/users/me/recommendation-profile");
        if (cancelled || !res.ok) return;
        const data = (await res.json()) as { genres?: string[] };
        const done = Array.isArray(data.genres) && data.genres.length > 0;
        if (!done) void navigate({ to: "/recommend", replace: true });
      } catch {
        /* ignore */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [user, loading, pathname, navigate]);

  return null;
}
