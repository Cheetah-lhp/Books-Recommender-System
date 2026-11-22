import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { Button } from "@/components/ui/button";
import { myReviewsQuery } from "@/features/reviews/queries";
import { useAuth } from "@/lib/auth";
import { booksPageQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { RATING_THRESHOLD } from "@/lib/library";
import { useForYou, useRecommendationProfile } from "@/lib/recommend";

export const Route = createFileRoute("/discover/")({
  head: () => ({
    meta: [
      { title: "Discover Books — READORA" },
      { name: "description", content: "Browse the catalog and unlock personalized recommendations on READORA." },
      { property: "og:title", content: "Discover Books — READORA" },
      { property: "og:description", content: "Browse books and get personalized recommendations after you sign in." },
    ],
  }),
  component: DiscoverPage,
});

function DiscoverPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(48);
  const allBooksRef = useRef<HTMLElement>(null);
  const { user } = useAuth();
  const { data: profile } = useRecommendationProfile(user?.id ?? null);
  const { data: myReviews = [] } = useQuery(myReviewsQuery(user?.id ?? null));
  const ratedCount = myReviews.length;
  const coldStart = Boolean(user) && ratedCount < RATING_THRESHOLD;
  const ready = Boolean(user) && ratedCount >= RATING_THRESHOLD;
  const { data: forYou } = useForYou(ready ? user?.id ?? null : null);

  const {
    data: bookPage,
    isLoading: booksLoading,
    isFetching: booksFetching,
  } = useQuery({
    ...booksPageQuery(page, pageSize),
    placeholderData: keepPreviousData,
  });
  const all = bookPage?.books ?? [];

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    requestAnimationFrame(() => {
      allBooksRef.current?.scrollIntoView({ behavior: "smooth" });
    });
  };

  return (
    <AppShell>
      {!user ? (
        <section className="mb-8 rounded-2xl border border-border bg-card p-6 shadow-card">
          <h1 className="font-display text-2xl font-bold text-foreground">{t("discover.signInTitle")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("discover.signInSub")}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button asChild className="rounded-full bg-primary text-primary-foreground">
              <Link to="/login" search={{ next: "/recommend" }}>
                {t("action.login")}
              </Link>
            </Button>
            <Button asChild variant="outline" className="rounded-full">
              <Link to="/signup">{t("action.signup")}</Link>
            </Button>
          </div>
        </section>
      ) : null}

      {user && coldStart ? (
        <section className="mb-8 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6">
          <div className="mb-3 h-2 overflow-hidden rounded-full bg-emerald-500/20">
            <div
              className="h-full rounded-full bg-emerald-600 transition-all"
              style={{ width: `${Math.min(100, (ratedCount / RATING_THRESHOLD) * 100)}%` }}
            />
          </div>
          <h1 className="font-display text-2xl font-bold text-foreground">{t("discover.almostReady")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("discover.almostReadySub")}</p>
          <ul className="mt-4 list-disc space-y-2 ps-5 text-sm text-foreground">
            <li>
              <Link
                to="/recommend"
                search={{ step: "rate" }}
                className="font-semibold text-gold underline-offset-2 hover:underline"
              >
                {t("discover.rateMore")}
              </Link>{" "}
              ({ratedCount}/{RATING_THRESHOLD})
            </li>
            <li>
              <Link
                to="/recommend"
                search={{ step: "genres" }}
                className="font-semibold text-gold underline-offset-2 hover:underline"
              >
                {t("discover.refineGenres")}
              </Link>
              {profile?.genres?.length ? ` — ${profile.genres.join(", ")}` : ""}
            </li>
            <li>{t("discover.addShelves")}</li>
          </ul>
        </section>
      ) : null}

      {ready && forYou?.sections?.length ? (
        <div className="space-y-10">
          <div>
            <h1 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl">
              {t("discover.recsTitle")}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {t("discover.recsSub")}{" "}
              <Link to="/recommend" className="font-medium text-gold underline-offset-2 hover:underline">
                {t("discover.improve")}
              </Link>
            </p>
          </div>
          {forYou.sections.map((section) => (
            <section key={section.key}>
              <SectionHeader title={section.title} />
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                {section.books.slice(0, 5).map((book) => (
                  <BookCard key={String(book.id)} book={book as never} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}

      <section ref={allBooksRef} className="mt-10 scroll-mt-20">
        <SectionHeader
          title={t("discover.allBooks")}
          subtitle={bookPage ? `${bookPage.total.toLocaleString()} books in the catalog` : "Browse the full catalog"}
        />
        {booksLoading && !bookPage ? (
          <p className="text-sm text-muted-foreground">Loading books…</p>
        ) : all.length ? (
          <>
            <div
              className={`grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 transition-opacity duration-200 ${
                booksFetching ? "opacity-60" : "opacity-100"
              }`}
            >
              {all.map((book) => (
                <BookCard key={book.id} book={book} />
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                Per page
                <select
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    handlePageChange(1);
                  }}
                  className="h-9 rounded-lg border border-border bg-background px-2 text-foreground"
                  aria-label="Books per page"
                >
                  {[24, 48, 96].map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                type="button"
                variant="outline"
                disabled={page <= 1 || booksLoading}
                onClick={() => handlePageChange(Math.max(1, page - 1))}
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
                onClick={() => handlePageChange(Math.min(bookPage?.pages ?? page, page + 1))}
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
