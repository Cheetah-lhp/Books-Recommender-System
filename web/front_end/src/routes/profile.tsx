import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover } from "@/components/readora/BookCard";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { normalizeGenres } from "@/lib/categories";
import { userBooksQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { useRecommendationProfile } from "@/lib/recommend";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "My Profile — READORA" },
      { name: "description", content: "Track your reading list, progress and reviews on READORA." },
      { property: "og:title", content: "My Profile — READORA" },
      { property: "og:description", content: "Track your reading list, progress and reviews." },
    ],
  }),
  component: ProfilePage,
});

function ProfilePage() {
  const { t } = useI18n();
  const { user, profile } = useAuth();
  const { data: items = [] } = useQuery(userBooksQuery(user?.id ?? null));
  const { data: taste } = useRecommendationProfile(user?.id ?? null);

  const stats = [
    { label: t("profile.booksRead"), value: items.filter((i) => i.status === "read").length },
    { label: t("profile.currentlyReading"), value: items.filter((i) => i.status === "reading").length },
    { label: t("profile.wantToRead"), value: items.filter((i) => i.status === "want_to_read").length },
  ];

  if (!user) {
    return (
      <AppShell>
        <div className="surface-card mx-auto max-w-md p-8 text-center">
          <p className="text-sm text-muted-foreground">{t("auth.signedOut")}</p>
          <Button asChild className="mt-4 rounded-full bg-primary text-primary-foreground">
            <Link to="/login">{t("action.login")}</Link>
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="surface-card grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-5 sm:flex sm:flex-wrap sm:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <Avatar className="h-16 w-16 shrink-0">
            <AvatarImage src={profile?.avatar_url ?? undefined} alt="" />
            <AvatarFallback>{(profile?.full_name ?? "R").charAt(0)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <h1 className="truncate font-display text-xl font-extrabold text-foreground sm:text-2xl">
              {profile?.full_name ?? "Reader"}
            </h1>
            <p className="truncate text-sm text-muted-foreground">{user.email}</p>
          </div>
        </div>
        <Button asChild variant="outline" className="rounded-full">
          <Link to="/settings">{t("profile.edit")}</Link>
        </Button>
      </section>

      <div className="mt-5 grid grid-cols-3 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="surface-card px-4 py-5 text-center">
            <p className="font-display text-2xl font-extrabold text-gold">{s.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

      <section className="surface-card mt-8 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-xl font-bold text-foreground">Your Reading Profile</h2>
          <Button asChild variant="outline" size="sm" className="rounded-full">
            <Link to="/recommend">Edit preferences</Link>
          </Button>
        </div>
        {taste ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <ProfileFacts label="Favorite genres" values={normalizeGenres(taste.genres)} />
            <ProfileFacts label="Themes you love" values={taste.themes} />
            <ProfileFacts label="Current mood" values={taste.reading_mood ? [taste.reading_mood] : []} />
            <ProfileFacts
              label="Reading habits"
              values={[taste.reading_frequency, taste.preferred_book_length].filter(Boolean) as string[]}
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            You haven&apos;t set your reading taste yet —{" "}
            <Link to="/recommend" className="font-semibold text-gold">
              answer the recommendation questions
            </Link>
            .
          </p>
        )}
      </section>

      <h2 className="mb-4 mt-8 font-display text-xl font-bold text-foreground">{t("profile.readingList")}</h2>
      <div className="space-y-3">
        {items.map((item) => {
          const b = (item as any).books || { title: `Book #${item.book_id}`, author_name: "Reading List", cover_url: null };
          return (
            <Link
              key={item.id}
              to="/book/$bookId"
              params={{ bookId: item.book_id }}
              className="surface-card flex items-center gap-4 p-3 transition-colors hover:bg-accent"
            >
              <BookCover book={b} className="h-16 w-11 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-foreground">{b.title}</p>
                <p className="truncate text-xs text-muted-foreground">{b.author_name}</p>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-secondary">
                  <div className="h-full rounded-full bg-gold" style={{ width: `${item.progress}%` }} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {item.progress}% {t("profile.progress")}
                </p>
              </div>
            </Link>
          );
        })}
        {items.length === 0 ? <p className="text-sm text-muted-foreground">{t("profile.empty")}</p> : null}
      </div>
    </AppShell>
  );
}

function ProfileFacts({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {values.length ? (
          values.map((v) => (
            <span key={v} className="rounded-full border border-gold/40 bg-gold/10 px-3 py-1 text-xs text-foreground">
              {v}
            </span>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">Not set</span>
        )}
      </div>
    </div>
  );
}
