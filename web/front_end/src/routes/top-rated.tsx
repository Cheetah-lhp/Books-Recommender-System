import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";

import { AppShell } from "@/components/readora/AppShell";
import { BookCover, SectionHeader } from "@/components/readora/BookCard";
import { Rating } from "@/components/readora/Rating";
import { topRatedQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/top-rated")({
  head: () => ({
    meta: [
      { title: "Top Rated Books — READORA" },
      { name: "description", content: "The highest rated books by the READORA reading community." },
      { property: "og:title", content: "Top Rated Books — READORA" },
      { property: "og:description", content: "The highest rated books by the READORA community." },
    ],
  }),
  component: TopRatedPage,
});

function TopRatedPage() {
  const { t } = useI18n();
  const { data: books = [] } = useQuery(topRatedQuery);

  return (
    <AppShell>
      <SectionHeader title={t("top.title")} subtitle={t("top.sub")} />
      <div className="surface-card divide-y divide-border overflow-hidden">
        {books.slice(0, 10).map((book, i) => (
          <Link
            key={book.id}
            to="/book/$bookId"
            params={{ bookId: book.id }}
            className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-accent"
          >
            <span className="w-5 shrink-0 text-sm font-bold text-muted-foreground">{i + 1}</span>
            <BookCover book={book} className="h-14 w-10 shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-bold text-foreground">{book.title}</span>
              <span className="block truncate text-xs text-muted-foreground">{book.author_name}</span>
            </span>
            <Rating value={book.rating} />
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground rtl:rotate-180" />
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
