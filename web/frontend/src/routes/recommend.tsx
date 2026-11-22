import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover } from "@/components/readora/BookCard";
import { ShelfButton } from "@/components/readora/ShelfButton";
import { StarRater } from "@/components/readora/StarRater";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { myReviewsQuery } from "@/features/reviews/queries";
import { READORA_CATEGORY_DEFS } from "@/lib/categories";
import { booksByCategoryQuery, userBooksQuery } from "@/lib/data";
import {
  RATING_THRESHOLD,
  normalizeShelfStatus,
  rateBook,
  setShelf,
  type ShelfStatus,
} from "@/lib/library";
import { useRecommendationProfile, useSaveRecommendationProfile } from "@/lib/recommend";
import { cn } from "@/lib/utils";

type Step = "genres" | "goal" | "rate";

type RecommendSearch = {
  step?: Step;
};

export const Route = createFileRoute("/recommend")({
  validateSearch: (search: Record<string, unknown>): RecommendSearch => {
    const s = search["step"];
    if (s === "genres" || s === "goal" || s === "rate") {
      return { step: s };
    }
    return {};
  },
  head: () => ({
    meta: [
      { title: "Getting Started — READORA" },
      {
        name: "description",
        content: "Pick your genres, set a reading goal, and rate books to unlock personalized recommendations.",
      },
      { property: "og:title", content: "Getting Started — READORA" },
      { property: "og:description", content: "Tell READORA your reading taste and get personalized book picks." },
    ],
  }),
  component: RecommendPage,
});

const STEPS: { id: Step; label: string }[] = [
  { id: "genres", label: "Favorite genres" },
  { id: "goal", label: "Reading goal" },
  { id: "rate", label: "Rate books" },
];

function RecommendPage() {
  const navigate = useNavigate();
  const search = Route.useSearch();
  const qc = useQueryClient();
  const { user, loading } = useAuth();
  const { data: profile } = useRecommendationProfile(user?.id ?? null);
  const saveProfile = useSaveRecommendationProfile(user?.id ?? null);

  const [step, setStep] = useState<Step>(search.step ?? "genres");
  const [genres, setGenres] = useState<string[]>([]);
  const [goal, setGoal] = useState<string>("12");
  const [activeGenre, setActiveGenre] = useState<string>("");

  useEffect(() => {
    if (search.step) {
      setStep(search.step);
    }
  }, [search.step]);

  useEffect(() => {
    if (!user && !loading) {
      void navigate({ to: "/login", search: { next: "/recommend" }, replace: true });
    }
  }, [user, loading, navigate]);

  useEffect(() => {
    if (!profile) return;
    if (profile.genres?.length) {
      setGenres(profile.genres);
      setActiveGenre((prev) => prev || profile.genres[0]!);
    }
    if (profile.reading_goal_yearly) setGoal(String(profile.reading_goal_yearly));
  }, [profile]);

  const displayedGenres = useMemo(() => {
    if (genres.length) return genres;
    return READORA_CATEGORY_DEFS.slice(0, 5).map((c) => c.name);
  }, [genres]);

  const effectiveGenre = activeGenre || displayedGenres[0] || "Fiction";

  const activeSlug =
    READORA_CATEGORY_DEFS.find((c) => c.name === effectiveGenre)?.slug ??
    READORA_CATEGORY_DEFS[0]?.slug ??
    "fiction";

  const { data: genreBooks = [] } = useQuery({
    ...booksByCategoryQuery(activeSlug),
    enabled: step === "rate" && Boolean(effectiveGenre),
  });
  const { data: myReviews = [] } = useQuery(myReviewsQuery(user?.id ?? null));
  const { data: shelf = [] } = useQuery(userBooksQuery(user?.id ?? null));

  const ratingByBook = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of myReviews) map.set(r.book_id, r.rating);
    return map;
  }, [myReviews]);

  const shelfByBook = useMemo(() => {
    const map = new Map<string, ShelfStatus>();
    for (const s of shelf) {
      const st = normalizeShelfStatus(s.status);
      if (st) map.set(s.book_id, st);
    }
    return map;
  }, [shelf]);

  const ratedCount = myReviews.length;
  const remaining = Math.max(0, RATING_THRESHOLD - ratedCount);

  const toggleGenre = (name: string) => {
    setGenres((prev) => {
      const next = prev.includes(name) ? prev.filter((g) => g !== name) : [...prev, name];
      if (!activeGenre || !next.includes(activeGenre)) setActiveGenre(next[0] ?? "");
      return next;
    });
  };

  const persistGenres = async () => {
    if (!user) {
      void navigate({ to: "/login", search: { next: "/recommend" } });
      return;
    }
    if (!genres.length) {
      toast.error("Select at least one genre to continue.");
      return;
    }
    try {
      await saveProfile.mutateAsync({
        genres,
        themes: profile?.themes ?? [],
        reading_mood: profile?.reading_mood ?? null,
        reading_frequency: profile?.reading_frequency ?? null,
        preferred_book_length: profile?.preferred_book_length ?? null,
        favorite_books: profile?.favorite_books ?? [],
        reading_goal_yearly: profile?.reading_goal_yearly ?? null,
      });
    } catch {
      // Giu flow hoat dong tiep tuc
    }
    setActiveGenre(genres[0] || "Fiction");
    setStep("goal");
  };

  const persistGoal = async (skip: boolean) => {
    if (!user) {
      void navigate({ to: "/login", search: { next: "/recommend" } });
      return;
    }
    const yearly = skip ? null : Math.max(1, Math.min(500, Number(goal) || 1));
    try {
      await saveProfile.mutateAsync({
        genres,
        themes: profile?.themes ?? [],
        reading_mood: profile?.reading_mood ?? null,
        reading_frequency: profile?.reading_frequency ?? null,
        preferred_book_length: profile?.preferred_book_length ?? null,
        favorite_books: profile?.favorite_books ?? [],
        reading_goal_yearly: yearly,
      });
    } catch {
      // Giu flow hoat dong tiep tuc
    }
    setStep("rate");
  };

  const rateMutation = useMutation({
    mutationFn: async ({ bookId, rating }: { bookId: string; rating: number }) => {
      await rateBook(bookId, rating);
    },
    onSuccess: (_d, vars) => {
      toast.success(`${vars.rating} star rating saved`);
      void qc.invalidateQueries({ queryKey: ["reviews", "me"] });
      void qc.invalidateQueries({ queryKey: ["for-you"] });
      void qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onError: () => toast.error("Could not save rating"),
  });

  const shelfMutation = useMutation({
    mutationFn: async ({ bookId, status }: { bookId: string; status: ShelfStatus }) => {
      await setShelf(bookId, status);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["user-books"] });
    },
    onError: () => toast.error("Could not update shelf"),
  });

  if (loading || !user) {
    return (
      <AppShell>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Getting Started</p>
          <h1 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl">
            {step === "genres" && "Select your favorite genres"}
            {step === "goal" && "Set a reading goal"}
            {step === "rate" && "Rate books that you've read"}
          </h1>
        </div>
        <ol className="flex flex-wrap gap-1 text-xs font-medium">
          {STEPS.map((s, i) => {
            const active = s.id === step;
            const done = STEPS.findIndex((x) => x.id === step) > i;
            return (
              <li
                key={s.id}
                className={cn(
                  "rounded-full px-3 py-1.5",
                  active && "bg-primary text-primary-foreground",
                  done && !active && "bg-secondary text-foreground",
                  !active && !done && "bg-muted text-muted-foreground",
                )}
              >
                {i + 1}. {s.label}
              </li>
            );
          })}
          <li className="rounded-full bg-muted px-3 py-1.5 text-muted-foreground">4. Recommendations</li>
        </ol>
      </div>

      {step === "genres" ? (
        <section className="surface-card p-5 sm:p-7">
          <p className="mb-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-foreground">
            We use your favorite genres to make better book recommendations.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {READORA_CATEGORY_DEFS.map((cat) => {
              const selected = genres.includes(cat.name);
              return (
                <label
                  key={cat.slug}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition-colors",
                    selected
                      ? "border-primary bg-primary/10 font-semibold text-foreground"
                      : "border-border bg-background hover:border-gold",
                  )}
                >
                  <input
                    type="checkbox"
                    className="accent-[var(--primary)]"
                    checked={selected}
                    onChange={() => toggleGenre(cat.name)}
                  />
                  {cat.name}
                </label>
              );
            })}
          </div>
          <div className="mt-6 flex justify-center">
            <Button
              className="rounded-full bg-primary px-8 text-primary-foreground"
              disabled={!genres.length || saveProfile.isPending}
              onClick={() => void persistGenres()}
            >
              {genres.length ? "Continue" : "Select at least one genre to continue"}
            </Button>
          </div>
        </section>
      ) : null}

      {step === "goal" ? (
        <section className="surface-card mx-auto max-w-xl p-6 sm:p-8">
          <p className="text-sm text-muted-foreground">Join millions of readers and set your goal today.</p>
          <label className="mt-6 block text-sm font-medium text-foreground">
            How many books do you want to read this year?
            <Input
              type="number"
              min={1}
              max={500}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="mt-2 max-w-[8rem]"
            />
          </label>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button
              className="rounded-full bg-primary text-primary-foreground"
              disabled={saveProfile.isPending}
              onClick={() => void persistGoal(false)}
            >
              Save and continue
            </Button>
            <button
              type="button"
              className="text-sm font-medium text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => void persistGoal(true)}
            >
              skip this step »
            </button>
          </div>
        </section>
      ) : null}

      {step === "rate" ? (
        <section>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-sm text-muted-foreground">
                {remaining > 0
                  ? `Rate ${remaining} more book${remaining === 1 ? "" : "s"} to get personalized recommendations!`
                  : "Nice — you've rated enough books for personalized recommendations."}
              </p>
              <div className="mt-2 h-2 w-full max-w-md overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-gold transition-all"
                  style={{ width: `${Math.min(100, (ratedCount / RATING_THRESHOLD) * 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                You&apos;ve rated {ratedCount} book{ratedCount === 1 ? "" : "s"}
              </p>
            </div>
            <Button asChild variant="outline" className="rounded-full">
              <Link to="/discover">I&apos;m finished rating »</Link>
            </Button>
          </div>

          <div className="grid gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
            <aside className="surface-card h-fit p-4">
              <h2 className="mb-3 text-sm font-bold text-foreground">Favorite Genres</h2>
              <ul className="space-y-1">
                {displayedGenres.map((g) => (
                  <li key={g}>
                    <button
                      type="button"
                      onClick={() => setActiveGenre(g)}
                      className={cn(
                        "w-full rounded-lg px-3 py-2 text-start text-sm",
                        effectiveGenre === g ? "bg-secondary font-semibold" : "hover:bg-accent",
                      )}
                    >
                      {g}
                    </button>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="mt-3 text-xs font-medium text-gold"
                onClick={() => setStep("genres")}
              >
                Edit genres
              </button>
            </aside>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {genreBooks.slice(0, 16).map((book) => (
                <div key={book.id} className="surface-card flex flex-col gap-2 p-3">
                  <BookCover book={book} className="aspect-[2/3] w-full" />
                  <p className="truncate text-sm font-semibold text-foreground">{book.title}</p>
                  <p className="truncate text-xs text-muted-foreground">{book.author_name}</p>
                  <ShelfButton
                    compact
                    status={shelfByBook.get(book.id) ?? null}
                    disabled={shelfMutation.isPending}
                    onChange={(status) => shelfMutation.mutate({ bookId: book.id, status })}
                  />
                  <StarRater
                    value={ratingByBook.get(book.id) ?? null}
                    disabled={rateMutation.isPending}
                    onChange={(rating) => rateMutation.mutate({ bookId: book.id, rating })}
                  />
                </div>
              ))}
              {!genreBooks.length ? (
                <p className="col-span-full text-sm text-muted-foreground">No books found for this genre yet.</p>
              ) : null}
            </div>
          </div>

          <div className="mt-8 flex justify-center">
            <Button asChild className="rounded-full bg-primary px-8 text-primary-foreground">
              <Link to="/discover">View recommendations</Link>
            </Button>
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}
