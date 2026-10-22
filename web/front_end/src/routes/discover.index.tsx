import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { READORA_CATEGORY_DEFS } from "@/lib/categories";
import { allBooksQuery, booksByCategoryQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { useRecommendations } from "@/lib/recommendations";

export const Route = createFileRoute("/discover/")({
  head: () => ({
    meta: [
      { title: "Discover Books — READORA" },
      { name: "description", content: "Personalized book recommendations picked for your taste on READORA." },
      { property: "og:title", content: "Discover Books — READORA" },
      { property: "og:description", content: "Personalized book recommendations picked for your taste." },
    ],
  }),
  component: DiscoverPage,
});

function DiscoverPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { data: recommended = [] } = useRecommendations(user?.id ?? null);
  const featuredCategory = READORA_CATEGORY_DEFS[0]!;
  const { data: featured = [] } = useQuery(booksByCategoryQuery(featuredCategory.slug));
  const { data: all = [] } = useQuery(allBooksQuery);

  return (
    <AppShell>
      <SectionHeader
        title={t("discover.recommended")}
        subtitle={t("discover.recommendedSub")}
        action={
          <Button asChild variant="ghost" size="sm" className="rounded-full text-gold">
            <Link to="/discover/categories">{t("action.viewAll")}</Link>
          </Button>
        }
      />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {(recommended.length ? recommended : all).slice(0, 4).map((book) => (
          <BookCard key={book.id} book={book} />
        ))}
      </div>

      <section className="mt-10">
        <SectionHeader title={`${t("discover.because")} ${featuredCategory.name}`} />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {featured.slice(0, 4).map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader
          title={t("categories.title")}
          subtitle={t("categories.sub")}
          action={
            <Button asChild variant="outline" size="sm" className="rounded-full">
              <Link to="/discover/categories">{t("action.viewAll")}</Link>
            </Button>
          }
        />
      </section>
    </AppShell>
  );
}
