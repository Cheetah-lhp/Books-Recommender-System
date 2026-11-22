import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { READORA_CATEGORY_DEFS } from "@/lib/categories";
import { topRatedQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { useRecommendationProfile } from "@/lib/recommend";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "READORA — Your Next Great Book, Powered by AI" },
      {
        name: "description",
        content:
          "Personalized book recommendations based on your interests, mood and reading history. Discover top-rated books and browse by genre.",
      },
      { property: "og:title", content: "READORA — Your Next Great Book, Powered by AI" },
      {
        property: "og:description",
        content: "Personalized AI book recommendations and a curated catalog of great reads.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { data: profile } = useRecommendationProfile(user?.id ?? null);
  const { data: topRated = [] } = useQuery(topRatedQuery);
  const hasGenres = Boolean(profile?.genres?.length);

  return (
    <AppShell>
      <section className="relative overflow-hidden rounded-3xl border border-border bg-card px-5 py-5 shadow-card sm:px-10 sm:py-6">
        <div className="pointer-events-none absolute inset-y-0 end-0 w-1/2 hero-glow" />
        <div className="relative grid items-center gap-6 md:grid-cols-[55%_45%]">
          <div className="min-w-0">
            <h1 className="font-display text-3xl font-extrabold leading-tight text-foreground sm:text-5xl">
              {t("hero.title1")}
              <br />
              {t("hero.title2")}
              <br />
              <span className="text-gold">{t("hero.title3")}</span>
            </h1>
            <p className="mt-3 max-w-md text-sm text-muted-foreground sm:text-base">{t("hero.sub")}</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button asChild className="rounded-full bg-primary px-6 text-primary-foreground hover:bg-primary/90">
                <Link to="/discover">{t("hero.cta1")}</Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="rounded-full border-border px-6 text-foreground hover:bg-accent"
              >
                {!user ? (
                  <Link to="/login" search={{ next: "/recommend" }}>
                    {t("hero.cta2")}
                  </Link>
                ) : hasGenres ? (
                  <Link to="/discover">{t("hero.cta2")}</Link>
                ) : (
                  <Link to="/recommend">{t("hero.cta2")}</Link>
                )}
              </Button>
            </div>
          </div>
          <div className="relative flex min-w-0 items-center justify-center md:justify-end">
            <img
              src="/chatbot_avatar.png"
              alt="READORA owl mascot reading a glowing book"
              width={1024}
              height={1024}
              className="h-auto w-full max-w-[380px] object-contain sm:max-w-[460px] md:w-[520px] md:max-w-none lg:w-[560px] xl:w-[600px]"
            />
          </div>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader
          title={t("home.topRated")}
          action={
            <Button asChild variant="outline" size="sm" className="rounded-full">
              <Link to="/top-rated">{t("action.viewAll")}</Link>
            </Button>
          }
        />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {topRated.slice(0, 5).map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader
          title={t("home.browseGenres")}
          subtitle={t("categories.sub")}
          action={
            <Button asChild variant="outline" size="sm" className="rounded-full">
              <Link to="/discover/categories">{t("action.viewAll")}</Link>
            </Button>
          }
        />
        <div className="flex flex-wrap gap-2">
          {READORA_CATEGORY_DEFS.map((cat) => (
            <Link
              key={cat.slug}
              to="/category/$slug"
              params={{ slug: cat.slug }}
              className="rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-gold hover:text-gold"
            >
              {cat.name}
            </Link>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
