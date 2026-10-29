import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Bell, Globe, HelpCircle, Moon, Shield, Sun, UserRound } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { SectionHeader } from "@/components/readora/BookCard";
import { Switch } from "@/components/ui/switch";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { preferencesQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — READORA" },
      { name: "description", content: "Manage your READORA account, appearance, language and notifications." },
      { property: "og:title", content: "Settings — READORA" },
      { property: "og:description", content: "Manage account, appearance, language and notifications." },
    ],
  }),
  component: SettingsPage,
});

function Row({ icon: Icon, label, children }: { icon: typeof Bell; label: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border px-4 py-4 last:border-0">
      <span className="flex min-w-0 items-center gap-3">
        <Icon className="h-5 w-5 shrink-0 text-gold" />
        <span className="truncate text-sm font-semibold text-foreground">{label}</span>
      </span>
      {children}
    </div>
  );
}

function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: prefs } = useQuery(preferencesQuery(user?.id ?? null));

  const update = async (patch: { push_notifications?: boolean; email_updates?: boolean }) => {
    if (!user) {
      toast.error(t("auth.signedOut"));
      return;
    }
    const { error } = await supabase.from("user_preferences").update(patch).eq("user_id", user.id);
    if (error) toast.error("Could not save");
    else void qc.invalidateQueries({ queryKey: ["preferences", user.id] });
  };

  return (
    <AppShell>
      <SectionHeader title={t("settings.title")} subtitle={t("settings.sub")} />
      <div className="surface-card mx-auto max-w-2xl overflow-hidden">
        <Row icon={UserRound} label={t("settings.account")}>
          <span className="truncate text-sm text-muted-foreground">{user?.email ?? "—"}</span>
        </Row>
        <Row icon={theme === "dark" ? Moon : Sun} label={t("settings.appearance")}>
          <div className="inline-flex rounded-full bg-secondary p-1">
            {(["light", "dark"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setTheme(mode)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-semibold",
                  theme === mode ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                {t(`settings.${mode}`)}
              </button>
            ))}
          </div>
        </Row>
        <Row icon={Globe} label={t("settings.language")}>
          <div className="inline-flex rounded-full bg-secondary p-1">
            {(["en", "ar"] as const).map((code) => (
              <button
                key={code}
                onClick={() => setLang(code)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-semibold uppercase",
                  lang === code ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                )}
              >
                {code}
              </button>
            ))}
          </div>
        </Row>
        <Row icon={Bell} label={t("settings.push")}>
          <Switch
            checked={prefs?.push_notifications ?? true}
            onCheckedChange={(v) => update({ push_notifications: v })}
          />
        </Row>
        <Row icon={Bell} label={t("settings.email")}>
          <Switch
            checked={prefs?.email_updates ?? true}
            onCheckedChange={(v) => update({ email_updates: v })}
          />
        </Row>
        <Row icon={Shield} label={t("settings.privacy")} />
        <Row icon={HelpCircle} label={t("settings.help")} />
      </div>
    </AppShell>
  );
}
