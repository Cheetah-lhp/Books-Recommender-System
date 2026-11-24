import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { booksByAuthorQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/author/$authorName")({
  head: ({ params }) => {
    const name = decodeURIComponent(params.authorName);
    return {
      meta: [
        { title: `Books by ${name} — READORA` },
        { name: "description", content: `Browse books by ${name} in the READORA catalog.` },
        { property: "og:title", content: `Books by ${name} — READORA` },
        { property: "og:description", content: `Browse books by ${name} on READORA.` },
      ],
    };
  },
  component: AuthorPage,
});

function AuthorPage() {
  const { authorName: raw } = Route.useParams();
  const authorName = decodeURIComponent(raw);
  const { t } = useI18n();
  const { data: books = [], isLoading } = useQuery(booksByAuthorQuery(authorName));

  return (
    <AppShell>
      <SectionHeader
        title={authorName}
        subtitle={
          isLoading
            ? t("author.loading")
            : t("author.sub").replace("{count}", String(books.length))
        }
      />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {books.map((b) => (
          <BookCard key={b.id} book={b} />
        ))}
      </div>
      {!isLoading && books.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("author.empty")}</p>
      ) : null}
    </AppShell>
  );
}
