import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { Sparkles } from "lucide-react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { RecommendationCard } from "@/components/readora/RecommendationCard";
import { searchQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import type { RecommendedBook } from "@/lib/recommend";
import { naturalSearch } from "@/lib/recommend.functions";

export const Route = createFileRoute("/search")({
  validateSearch: (search: Record<string, unknown>) => ({ q: typeof search["q"] === "string" ? (search["q"] as string) : "" }),
  head: () => ({
    meta: [
      { title: "Search — READORA" },
      { name: "description", content: "Search books by title, author, genre — or describe the book you want in your own words." },
      { property: "og:title", content: "Search — READORA" },
      { property: "og:description", content: "Search books by title, author or describe what you feel like reading." },
    ],
  }),
  component: SearchPage,
});

function SearchPage() {
  const { q } = Route.useSearch();
  const { t } = useI18n();
  const { data: books = [], isFetching } = useQuery(searchQuery(q));
  const understand = useServerFn(naturalSearch);

  const { data: nl } = useQuery({
    queryKey: ["nl-search", q],
    enabled: q.trim().length > 2,
    queryFn: async () => {
      const res = (await understand({ data: { query: q } })) as unknown as {
        interpreted: { genres: string[]; themes: string[]; length: string | null; similarTo: string | null } | null;
        books: RecommendedBook[];
      };
      return res;
    },
  });

  const smart = nl?.interpreted && nl.books.length ? nl : null;
  const interpretation = smart
    ? [
        smart.interpreted?.genres.join(", "),
        smart.interpreted?.themes.join(", "),
        smart.interpreted?.length ? `${smart.interpreted.length} books` : "",
        smart.interpreted?.similarTo ? `similar to ${smart.interpreted.similarTo}` : "",
      ]
        .filter(Boolean)
        .join(" · ")
    : "";

  return (
    <AppShell>
      {smart ? (
        <section className="mb-10">
          <SectionHeader title="Books matching what you described" subtitle={interpretation} />
          <p className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-gold" /> Understood from: “{q}”
          </p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {smart.books.map((b) => (
              <RecommendationCard key={b.id} book={b} />
            ))}
          </div>
        </section>
      ) : null}

      <SectionHeader title={t("search.results")} subtitle={q} />
      {isFetching ? <p className="text-sm text-muted-foreground">…</p> : null}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {books.map((b) => (
          <BookCard key={b.id} book={b} />
        ))}
      </div>
      {!isFetching && books.length === 0 && !smart ? (
        <p className="text-sm text-muted-foreground">{t("profile.empty")}</p>
      ) : null}
    </AppShell>
  );
}
