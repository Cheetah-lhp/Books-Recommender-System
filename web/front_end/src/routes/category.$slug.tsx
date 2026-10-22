import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/readora/AppShell";
import { BookCard, SectionHeader } from "@/components/readora/BookCard";
import { categoryLabel } from "@/lib/categories";
import { booksByCategoryQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/category/$slug")({
  head: ({ params }) => ({
    meta: [
      { title: `${categoryLabel(params.slug)} books — READORA` },
      { name: "description", content: `Browse ${categoryLabel(params.slug)} books rated and reviewed by the READORA community.` },
      { property: "og:title", content: `${categoryLabel(params.slug)} books — READORA` },
      { property: "og:description", content: `Browse ${categoryLabel(params.slug)} books on READORA.` },
    ],
  }),
  component: CategoryPage,
});

function CategoryPage() {
  const { slug } = Route.useParams();
  const { t } = useI18n();
  const { data: books = [] } = useQuery(booksByCategoryQuery(slug));

  return (
    <AppShell>
      <SectionHeader title={categoryLabel(slug)} subtitle={t("categories.sub")} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {books.map((b) => (
          <BookCard key={b.id} book={b} />
        ))}
      </div>
      {books.length === 0 ? <p className="text-sm text-muted-foreground">{t("profile.empty")}</p> : null}
    </AppShell>
  );
}
