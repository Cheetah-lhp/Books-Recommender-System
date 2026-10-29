import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { LogoLockup } from "@/components/readora/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — READORA" },
      { name: "description", content: "Sign in to READORA to sync your reading list, reviews and recommendations." },
      { property: "og:title", content: "Sign in — READORA" },
      { property: "og:description", content: "Sign in to sync your reading list and recommendations." },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  /** Returning readers go straight to the normal READORA experience. */
  const goNext = async () => {
    const { data: auth } = await supabase.auth.getUser();
    const uid = auth.user?.id;
    if (!uid) return void navigate({ to: "/" });
    const { data } = await supabase
      .from("recommendation_profiles")
      .select("onboarding_completed")
      .eq("user_id", uid)
      .maybeSingle();
    const done = (data as { onboarding_completed?: boolean } | null)?.onboarding_completed;
    void navigate({ to: done ? "/" : "/recommend" });
  };

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) toast.error(error.message);
    else void goNext();
  };

  const google = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (error) {
      toast.error("Google sign-in failed: " + error.message);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="surface-card w-full max-w-sm p-7">
        <div className="mb-6 flex justify-center">
          <LogoLockup context="auth" />
        </div>
        <h1 className="text-center font-display text-2xl font-extrabold text-foreground">{t("auth.welcome")}</h1>
        <form className="mt-6 space-y-4" onSubmit={signIn}>
          <div className="space-y-1.5">
            <Label htmlFor="email">{t("auth.email")}</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">{t("auth.password")}</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {t("action.login")}
          </Button>
        </form>
        <Button variant="outline" className="mt-3 w-full rounded-full" onClick={google}>
          {t("auth.google")}
        </Button>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          {t("auth.noAccount")}{" "}
          <Link to="/signup" className="font-semibold text-gold">
            {t("action.signup")}
          </Link>
        </p>
      </div>
    </main>
  );
}
