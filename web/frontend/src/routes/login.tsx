import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { LogoLockup } from "@/components/readora/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login as apiLogin } from "@/lib/auth-api";
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

  const signIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await apiLogin(email, password);
      void navigate({ to: "/" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setBusy(false);
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
