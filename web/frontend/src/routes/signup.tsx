import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";

import { LogoLockup } from "@/components/readora/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { register as apiRegister } from "@/lib/auth-api";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create your account — READORA" },
      { name: "description", content: "Create a free READORA account for AI book recommendations and reviews." },
      { property: "og:title", content: "Create your account — READORA" },
      { property: "og:description", content: "Create a free account for AI book recommendations." },
    ],
  }),
  component: SignupPage,
});

function SignupPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const signUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await apiRegister(email, password, name);
      void navigate({ to: "/recommend" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not create account";
      toast.error(
        /already|registered|exists/i.test(message)
          ? "An account with this email already exists. Please log in instead."
          : message,
      );
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
        <h1 className="text-center font-display text-2xl font-extrabold text-foreground">{t("auth.create")}</h1>
        <form className="mt-6 space-y-4" onSubmit={signUp}>
          <div className="space-y-1.5">
            <Label htmlFor="name">{t("auth.name")}</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
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
              minLength={6}
            />
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {t("action.signup")}
          </Button>
        </form>
        <p className="mt-5 text-center text-sm text-muted-foreground">
          {t("auth.haveAccount")}{" "}
          <Link to="/login" className="font-semibold text-gold">
            {t("action.login")}
          </Link>
        </p>
      </div>
    </main>
  );
}
