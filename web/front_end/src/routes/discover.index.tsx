import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { READORA_CATEGORY_DEFS } from "@/lib/categories";
import { booksByCategoryQuery, booksPageQuery } from "@/lib/data";
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
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(48);
  const { user } = useAuth();
  const { data: recommended = [] } = useRecommendations(user?.id ?? null);
  const featuredCategory = READORA_CATEGORY_DEFS[0]!;
  const { data: featured = [] } = useQuery(booksByCategoryQuery(featuredCategory.slug));
  const { data: bookPage, isLoading: booksLoading } = useQuery(booksPageQuery(page, pageSize));
  const all = bookPage?.books ?? [];

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
          title="All books"
          subtitle={bookPage ? `${bookPage.total.toLocaleString()} books in the catalog` : "Browse the full catalog"}
        />
        {booksLoading ? (
          <p className="text-sm text-muted-foreground">Loading books…</p>
        ) : all.length ? (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {all.map((book) => <BookCard key={book.id} book={book} />)}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                Per page
                <select
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    setPage(1);
                  }}
                  className="h-9 rounded-lg border border-border bg-background px-2 text-foreground"
                  aria-label="Books per page"
                >
                  {[24, 48, 96].map((size) => <option key={size} value={size}>{size}</option>)}
                </select>
              </label>
              <Button
                type="button"
                variant="outline"
                disabled={page <= 1 || booksLoading}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {bookPage?.page ?? page} of {bookPage?.pages ?? 1}
              </span>
              <Button
                type="button"
                variant="outline"
                disabled={page >= (bookPage?.pages ?? 1) || booksLoading}
                onClick={() => setPage((current) => Math.min(bookPage?.pages ?? current, current + 1))}
              >
                Next
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No books found.</p>
        )}
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
