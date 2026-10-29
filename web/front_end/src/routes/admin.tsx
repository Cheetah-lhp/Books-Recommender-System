import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { BookOpen, MessageSquare, Star, Users } from "lucide-react";

import { AppShell } from "@/components/readora/AppShell";
import { SectionHeader } from "@/components/readora/BookCard";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { adminStatsQuery, topRatedQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Admin Dashboard — READORA" },
      { name: "description", content: "READORA admin dashboard for users, books and reviews." },
      { property: "og:title", content: "Admin Dashboard — READORA" },
      { property: "og:description", content: "Manage users, books and reviews." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminPage,
});

function AdminPage() {
  const { t } = useI18n();
  const { isAdmin, loading } = useAuth();
  const { data: stats } = useQuery({ ...adminStatsQuery, enabled: isAdmin });
  const { data: top = [] } = useQuery({ ...topRatedQuery, enabled: isAdmin });

  if (!loading && !isAdmin) {
    return (
      <AppShell>
        <div className="surface-card mx-auto max-w-md p-8 text-center">
          <p className="text-sm text-muted-foreground">You do not have access to this page.</p>
          <Button asChild className="mt-4 rounded-full bg-primary text-primary-foreground">
            <Link to="/">Go home</Link>
          </Button>
        </div>
      </AppShell>
    );
  }

  const cards = [
    { icon: Users, label: t("admin.totalUsers"), value: stats?.users ?? 0 },
    { icon: BookOpen, label: t("admin.totalBooks"), value: stats?.books ?? 0 },
    { icon: MessageSquare, label: t("admin.totalReviews"), value: stats?.reviews ?? 0 },
    { icon: Star, label: t("admin.activeUsers"), value: stats?.users ?? 0 },
  ];

  return (
    <AppShell>
      <SectionHeader title={t("admin.title")} subtitle={t("admin.dashboard")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="surface-card p-4">
            <c.icon className="h-5 w-5 text-gold" />
            <p className="mt-3 font-display text-2xl font-extrabold text-foreground">{c.value.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">{c.label}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="surface-card p-5">
          <h2 className="mb-3 font-display text-lg font-bold text-foreground">{t("admin.topRated")}</h2>
          <div className="space-y-2">
            {top.slice(0, 5).map((b) => (
              <div key={b.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-foreground">{b.title}</span>
                <span className="shrink-0 font-semibold text-gold">{b.rating.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="surface-card p-5">
          <h2 className="mb-3 font-display text-lg font-bold text-foreground">{t("admin.recentUsers")}</h2>
          <div className="space-y-3">
            {(stats?.recent ?? []).map((u) => (
              <div key={u.id} className="flex items-center gap-3">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={u.avatar_url ?? undefined} alt="" />
                  <AvatarFallback>{(u.full_name ?? "R").charAt(0)}</AvatarFallback>
                </Avatar>
                <span className="min-w-0 flex-1 truncate text-sm text-foreground">{u.full_name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {new Date(u.created_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
