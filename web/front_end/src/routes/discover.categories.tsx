import { useQuery } from "@tanstack/react-query";
import { Link, createFileRoute } from "@tanstack/react-router";
import {
  BookOpen,
  Briefcase,
  Compass,
  Crown,
  Feather,
  Heart,
  Landmark,
  MoreHorizontal,
  Rocket,
  Search,
  Sparkle,
  Star,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import { AppShell } from "@/components/readora/AppShell";
import { SectionHeader } from "@/components/readora/BookCard";
import { categoriesQuery } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

const ICONS: Record<string, LucideIcon> = {
  "book-open": BookOpen,
  star: Star,
  rocket: Rocket,
  heart: Heart,
  search: Search,
  "user-round": UserRound,
  sparkle: Sparkle,
  briefcase: Briefcase,
  landmark: Landmark,
  feather: Feather,
  compass: Compass,
  crown: Crown,
};

export const Route = createFileRoute("/discover/categories")({
  head: () => ({
    meta: [
      { title: "Browse Categories — READORA" },
      { name: "description", content: "Explore Readora categories: Fiction, Romance, Fantasy & Paranormal, Mystery Thriller & Crime, Young Adult, Children and more." },
      { property: "og:title", content: "Browse Categories — READORA" },
      { property: "og:description", content: "Explore books by genre on READORA." },
    ],
  }),
  component: CategoriesPage,
});

function CategoriesPage() {
  const { t } = useI18n();
  const { data: categories = [] } = useQuery(categoriesQuery);

  return (
    <AppShell>
      <SectionHeader title={t("categories.title")} subtitle={t("categories.sub")} />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {categories.map((c) => {
          const Icon = ICONS[c.icon] ?? BookOpen;
          return (
            <Link
              key={c.id}
              to="/category/$slug"
              params={{ slug: c.slug }}
              className="surface-card flex flex-col items-center gap-3 px-4 py-6 transition-colors hover:border-gold"
            >
              <Icon className="h-7 w-7 text-gold" />
              <span className="text-sm font-semibold text-foreground">{c.name}</span>
            </Link>
          );
        })}
        <div className="surface-card flex flex-col items-center gap-3 px-4 py-6 text-muted-foreground">
          <MoreHorizontal className="h-7 w-7" />
          <span className="text-sm font-semibold">{t("categories.more")}</span>
        </div>
      </div>
    </AppShell>
  );
}
