import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";

/** Routes where we never force the questionnaire. */
const EXEMPT = ["/recommend", "/login", "/signup"];

/**
 * After ANY authenticated session appears (first login, email-confirmation
 * landing, restored session), send the user to the ORIGINAL questionnaire
 * when they have not completed onboarding yet.
 */
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
      const { data, error } = await supabase
        .from("recommendation_profiles")
        .select("onboarding_completed")
        .eq("user_id", user.id)
        .maybeSingle();
      if (cancelled || error) return;
      const done = (data as { onboarding_completed?: boolean } | null)?.onboarding_completed === true;
      if (!done) void navigate({ to: "/recommend", replace: true });
    })();

    return () => {
      cancelled = true;
    };
  }, [user, loading, pathname, navigate]);

  return null;
}
