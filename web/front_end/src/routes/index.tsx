import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";

import heroOwl from "@/assets/readora-owl-hero-exact.png.asset.json";
import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { trendingBooksQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "READORA — Your Next Great Book, Powered by AI" },
      {
        name: "description",
        content:
          "Personalized book recommendations based on your interests, mood and reading history. Discover trending books, reviews and a reader community.",
      },
      { property: "og:title", content: "READORA — Your Next Great Book, Powered by AI" },
      {
        property: "og:description",
        content: "Personalized AI book recommendations, reviews and a community of readers.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { t } = useI18n();
  const { data: trending = [] } = useQuery(trendingBooksQuery);

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
                <Link to="/chat">{t("hero.cta2")}</Link>
              </Button>
            </div>
          </div>
          <div className="relative flex min-w-0 items-center justify-center md:justify-end">
            <img
              src={heroOwl.url}
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
          title={t("home.trending")}
          action={
            <Button asChild variant="outline" size="sm" className="rounded-full">
              <Link to="/discover">{t("action.viewAll")}</Link>
            </Button>
          }
        />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {trending.slice(0, 5).map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      </section>
    </AppShell>
  );
}
